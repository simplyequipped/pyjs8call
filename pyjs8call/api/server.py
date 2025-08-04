# MIT License
# 
# Copyright (c) 2022-2025 Simply Equipped
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

'''FastAPI server implementation for pyjs8call API.'''

__docformat__ = 'google'

import time
from typing import Dict, List, Any, Optional
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware import Middleware
from fastapi.security import HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

import pyjs8call
from .models import *


class SimpleRateLimiter:
    '''Simple in-memory rate limiter.'''
    
    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(deque)  # ip -> deque of timestamps
        
    def is_allowed(self, client_ip: str) -> bool:
        '''Check if request from client IP is allowed.
        
        Args:
            client_ip: Client IP address
            
        Returns:
            bool: True if request is allowed, False if rate limited
        '''
        now = time.time()
        minute_ago = now - 60
        
        # clean old requests
        client_requests = self.requests[client_ip]
        while client_requests and client_requests[0] < minute_ago:
            client_requests.popleft()
            
        # check limit
        if len(client_requests) >= self.requests_per_minute:
            return False
            
        # add current request
        client_requests.append(now)
        return True

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, rate_limiter: SimpleRateLimiter):
        super().__init__(app)
        self.rate_limiter = rate_limiter
        
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host
        
        if not self.rate_limiter.is_allowed(client_ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded, try again later"}
            )
            
        response = await call_next(request)
        return response

class WebSocketManager:
    '''Manage WebSocket connections and event broadcasting.'''
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[WebSocket, List[str]] = {}
    
    async def connect(self, websocket: WebSocket):
        '''Accept WebSocket connection.'''
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = []
    
    def disconnect(self, websocket: WebSocket):
        '''Remove WebSocket connection.'''
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]
    
    def subscribe(self, websocket: WebSocket, events: List[str]):
        '''Subscribe WebSocket to events.'''
        self.subscriptions[websocket] = events
    
    def broadcast_sync(self, event: Dict[str, Any]):
        '''Synchronously broadcast event to subscribed clients.'''
        import asyncio
        
        # get current event loop or create new one
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # run broadcast in event loop
        if loop.is_running():
            # if loop is running, schedule coroutine
            asyncio.create_task(self._broadcast_async(event))
        else:
            # if loop is not running, run coroutine
            loop.run_until_complete(self._broadcast_async(event))
    
    async def _broadcast_async(self, event: Dict[str, Any]):
        '''Asynchronously broadcast event to subscribed clients.'''
        event_type = event.get('event')
        if not event_type:
            return
            
        # send to subscribed connections
        disconnected = []
        for websocket in self.active_connections:
            if event_type in self.subscriptions.get(websocket, []):
                try:
                    await websocket.send_json(event)
                except:
                    disconnected.append(websocket)
        
        # clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket)


class EventBridge:
    '''Bridge between pyjs8call callbacks and WebSocket events.'''
    
    def __init__(self, websocket_manager: WebSocketManager):
        self.ws_manager = websocket_manager
        self.client = None
        
    def register_with_client(self, client):
        '''Register all callbacks with the pyjs8call client.'''
        # store client reference for callbacks that need it
        self.client = client
        
        # register for directed messages (rx_directed is default)
        client.callback.register_incoming(self.on_incoming_message)
        
        # register for spots
        client.callback.register_spots(self.on_new_spots)
        
        # register outgoing callback
        client.callback.register_outgoing(self.on_outgoing_status)
        
        # register inbox callback
        client.callback.register_inbox(self.on_inbox_message)
        
        # register window transition callback
        client.callback.register_window(self.on_window_transition)
    
    def on_incoming_message(self, msg):
        '''Callback for incoming directed messages.'''
        event = {
            'event': 'incoming_message',
            'timestamp': time.time(),
            'data': MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
        }
        self.ws_manager.broadcast_sync(event)
    
    def on_new_spots(self, spots):
        '''Callback for new spots.'''
        event = {
            'event': 'new_spots',
            'timestamp': time.time(),
            'data': [MessageModel.from_pyjs8call_message(spot).dict(exclude_none=True) for spot in spots]
        }
        self.ws_manager.broadcast_sync(event)
    
    def on_outgoing_status(self, msg):
        '''Callback for outgoing message status changes.'''
        event = {
            'event': 'outgoing_status',
            'timestamp': time.time(),
            'data': MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
        }
        self.ws_manager.broadcast_sync(event)
    
    def on_inbox_message(self, msgs):
        '''Callback for new inbox messages.'''
        event = {
            'event': 'inbox_message',
            'timestamp': time.time(),
            'data': msgs  # already list of dicts
        }
        self.ws_manager.broadcast_sync(event)
    
    def on_window_transition(self):
        '''Callback for RX/TX window transitions.'''
        transition_time = time.time()
        data = {
            'transition_time': transition_time
        }
        
        # add window timing info if available
        if self.client and hasattr(self.client, 'window'):
            try:
                data['next_transition'] = self.client.window.next_transition()
                data['seconds_to_transition'] = self.client.window.next_transition_seconds()
            except:
                pass  # window info not available
        
        event = {
            'event': 'window_transition',
            'timestamp': transition_time,
            'data': data
        }
        self.ws_manager.broadcast_sync(event)

def create_app(client, rate_limit=1000):
    '''Create FastAPI application.
    
    Args:
        client: pyjs8call.client.Client instance
        rate_limit (int): requests per minute per IP address before limiting, defaults to 1000
        
    Returns:
        FastAPI: FastAPI application
    '''
    rate_limiter = SimpleRateLimiter(rate_limit)
    app = FastAPI(
        title='pyjs8call API',
        description='REST API and WebSocket interface for pyjs8call',
        version=pyjs8call.__api_version__
    )
    app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)
    
    ws_manager = WebSocketManager()
    event_bridge = EventBridge(ws_manager)
    event_bridge.register_with_client(client)
    
    # store references for route handlers
    app.state.client = client
    app.state.ws_manager = ws_manager
    # configure api routes
    add_routes(app)
    
    return app

def add_routes(app: FastAPI):
    '''Add all API routes to the FastAPI app.'''
    
    @app.get('/')
    async def root():
        return {'message': 'PyJS8Call API', 'version': pyjs8call.__version__}
    
    # websocket endpoint for real-time events
    @app.websocket('/api/events')
    async def websocket_endpoint(websocket: WebSocket):
        client = app.state.client
        ws_manager = app.state.ws_manager
        
        # check api key for WebSocket connection
        api_key = websocket.headers.get('X-API-Key')
        try:
            expected_key = client.config.get_option('api', 'api_key')
        except:
            expected_key = None
        if api_key != expected_key:
            await websocket.close(code=1008, reason='Invalid API key')
            return
        
        await ws_manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                
                if data.get('action') == 'subscribe':
                    events = data.get('events', [])
                    ws_manager.subscribe(websocket, events)
                    await websocket.send_json({
                        'event': 'subscribed',
                        'timestamp': time.time(),
                        'data': {'events': events}
                    })
                    
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)
    
    # connection status
    @app.get('/api/js8call/connected')
    async def get_connection_status():
        client = app.state.client
        return StatusResponse(
            success=True,
            data={
                'connected': client.connected(),
                'online': client.online
            }
        )
    
    # send directed message
    @app.post('/api/message/directed')
    async def send_directed_message(request: SendMessageRequest):
        client = app.state.client
        try:
            msg = client.send_directed_message(request.destination, request.message)
            return StatusResponse(
                success=True,
                message='Message queued for transmission',
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # send heartbeat
    @app.post('/api/message/heartbeat')
    async def send_heartbeat(grid: Optional[str] = None):
        client = app.state.client
        try:
            msg = client.send_heartbeat(grid)
            return StatusResponse(
                success=True,
                message='Heartbeat queued for transmission',
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # send directed command message
    @app.post('/api/message/directed/command')
    async def send_directed_command_message(request: SendDirectedCommandRequest):
        client = app.state.client
        try:
            msg = client.send_directed_command_message(request.destination, request.command, request.message)
            return StatusResponse(
                success=True,
                message='Command message queued for transmission',
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # send freetext message
    @app.post('/api/message/freetext')
    async def send_freetext_message(request: SendRawMessageRequest):
        client = app.state.client
        try:
            msg = client.send_message(request.message)
            return StatusResponse(
                success=True,
                message='Raw message queued for transmission',
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # send directed bytes message
    @app.post('/api/message/directed/bytes')
    async def send_directed_bytes_message(request: SendDirectedBytesRequest):
        client = app.state.client
        try:
            import base64
            bytes_data = base64.b64decode(request.data)
            msg = client.send_directed_bytes_message(request.destination, bytes_data)
            return StatusResponse(
                success=True,
                message='Bytes message queued for transmission',
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # send inbox message
    @app.post('/api/message/command/msg')
    async def send_inbox_message(request: SendInboxMessageRequest):
        client = app.state.client
        try:
            msg = client.send_inbox_message(request.destination, request.message)
            return StatusResponse(
                success=True,
                message='Inbox message queued for transmission',
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # send inbox message (MSG command to destination)
    @app.post('/api/message/command/msg-to')
    async def send_inbox_message_command(request: SendInboxMessageRequest):
        client = app.state.client
        try:
            client.send_inbox_message(request.destination, request.message)
            return StatusResponse(
                success=True,
                message='Inbox message sent successfully'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # store local inbox message
    @app.post('/api/message/inbox/local')
    async def store_local_inbox_message(request: StoreInboxMessageRequest):
        client = app.state.client
        try:
            success = client.store_local_inbox_message(request.origin, request.destination, request.message, request.path)
            return StatusResponse(
                success=success,
                message='Local inbox message stored successfully' if success else 'Failed to store local inbox message'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # store remote inbox message  
    @app.post('/api/message/inbox/remote')
    async def store_remote_inbox_message(request: StoreInboxMessageRequest):
        client = app.state.client
        try:
            success = client.store_remote_inbox_message(request.origin, request.destination, request.message, request.path)
            return StatusResponse(
                success=success,
                message='Remote inbox message stored successfully' if success else 'Failed to store remote inbox message'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # query callsign
    @app.post('/api/message/query/call')
    async def query_call(request: QueryCallRequest):
        client = app.state.client
        try:
            msg = client.query_call(request.callsign, request.destination)
            return StatusResponse(
                success=True,
                message='Callsign query queued for transmission',
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # query messages
    @app.post('/api/message/query/messages')
    async def query_messages(request: QueryMessagesRequest):
        client = app.state.client
        try:
            msg = client.query_messages(request.destination)
            return StatusResponse(
                success=True,
                message='Messages query queued for transmission',
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # query message id
    @app.post('/api/message/query/message-id')
    async def query_message_id(request: QueryMessageIdRequest):
        client = app.state.client
        try:
            msg = client.query_message_id(request.destination, request.message_id)
            return StatusResponse(
                success=True,
                message='Message ID query queued for transmission',
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # query hearing
    @app.post('/api/message/query/hearing')
    async def query_hearing(request: StationRequest):
        client = app.state.client
        try:
            msg = client.query_hearing(request.callsign)
            return StatusResponse(
                success=True,
                message='Hearing query queued for transmission',
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # query snr
    @app.post('/api/message/query/snr')
    async def query_snr(request: StationRequest):
        client = app.state.client
        try:
            msg = client.query_snr(request.callsign)
            return StatusResponse(
                success=True,
                message='SNR query queued for transmission',
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # query grid
    @app.post('/api/message/query/grid')
    async def query_grid(request: StationRequest):
        client = app.state.client
        try:
            msg = client.query_grid(request.callsign)
            return StatusResponse(
                success=True,
                message='Grid query queued for transmission',
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # query info
    @app.post('/api/message/query/info')
    async def query_info(request: StationRequest):
        client = app.state.client
        try:
            msg = client.query_info(request.callsign)
            return StatusResponse(
                success=True,
                message='Info query queued for transmission',
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # query status
    @app.post('/api/message/query/status')
    async def query_status(request: StationRequest):
        client = app.state.client
        try:
            msg = client.query_status(request.callsign)
            return StatusResponse(
                success=True,
                message='Status query queued for transmission',
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # send aprs grid
    @app.post('/api/message/aprs/grid')
    async def send_aprs_grid(request: SendAPRSGridRequest):
        client = app.state.client
        try:
            msg = client.send_aprs_grid(request.grid)
            return StatusResponse(
                success=True,
                message='APRS grid message queued for transmission',
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # send aprs sms
    @app.post('/api/message/aprs/sms')
    async def send_aprs_sms(request: SendAPRSSMSRequest):
        client = app.state.client
        try:
            msg = client.send_aprs_sms(request.phone, request.message)
            return StatusResponse(
                success=True,
                message='APRS SMS message queued for transmission',
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # send aprs email
    @app.post('/api/message/aprs/email')
    async def send_aprs_email(request: SendAPRSEmailRequest):
        client = app.state.client
        try:
            msg = client.send_aprs_email(request.email, request.message)
            return StatusResponse(
                success=True,
                message='APRS email message queued for transmission',
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # send aprs pota spot
    @app.post('/api/message/aprs/pota')
    async def send_aprs_pota_spot(request: SendAPRSPOTARequest):
        client = app.state.client
        try:
            msg = client.send_aprs_pota_spot(request.park, request.freq, request.mode, request.message, request.callsign)
            return StatusResponse(
                success=True,
                message='APRS POTA spot queued for transmission',
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get frequency
    @app.get('/api/settings/frequency')
    async def get_frequency():
        client = app.state.client
        try:
            freq = client.settings.get_freq()
            return StatusResponse(
                success=True,
                data={'frequency': freq, 'restart': False}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # set frequency
    @app.put('/api/settings/frequency')
    async def set_frequency(request: SetFrequencyRequest):
        client = app.state.client
        try:
            freq = client.settings.set_freq(request.frequency)
            return StatusResponse(
                success=True,
                message='Frequency updated',
                data={'frequency': freq, 'restart': False}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get callsign
    @app.get('/api/settings/callsign')
    async def get_callsign():
        client = app.state.client
        try:
            callsign = client.settings.get_station_callsign()
            return StatusResponse(
                success=True,
                data={'callsign': callsign, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get grid
    @app.get('/api/settings/grid') 
    async def get_grid():
        client = app.state.client
        try:
            grid = client.settings.get_station_grid()
            return StatusResponse(
                success=True,
                data={'grid': grid, 'restart': False}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # set callsign
    @app.put('/api/settings/callsign')
    async def set_callsign(request: SetCallsignRequest):
        client = app.state.client
        try:
            client.settings.set_station_callsign(request.callsign)
            return StatusResponse(
                success=True,
                message='Station callsign updated',
                data={'callsign': request.callsign, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # set grid
    @app.put('/api/settings/grid')
    async def set_grid(request: SetGridRequest):
        client = app.state.client
        try:
            client.settings.set_station_grid(request.grid)
            return StatusResponse(
                success=True,
                message='Station grid updated',
                data={'grid': request.grid, 'restart': False}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get offset
    @app.get('/api/settings/offset')
    async def get_offset():
        client = app.state.client
        try:
            offset = client.settings.get_offset()
            return StatusResponse(
                success=True,
                data={'offset': offset, 'restart': False}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # set offset
    @app.put('/api/settings/offset')
    async def set_offset(request: SetOffsetRequest):
        client = app.state.client
        try:
            offset = client.settings.set_offset(request.offset)
            return StatusResponse(
                success=True,
                message='Frequency offset updated',
                data={'offset': offset, 'restart': False}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get speed
    @app.get('/api/settings/speed')
    async def get_speed():
        client = app.state.client
        try:
            speed = client.settings.get_speed()
            return StatusResponse(
                success=True,
                data={'speed': speed, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # set speed
    @app.put('/api/settings/speed')
    async def set_speed(request: SetSpeedRequest):
        client = app.state.client
        try:
            client.settings.set_speed(request.speed)
            return StatusResponse(
                success=True,
                message='Modem speed updated',
                data={'speed': request.speed, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get station info
    @app.get('/api/settings/info')
    async def get_station_info():
        client = app.state.client
        try:
            info = client.settings.get_station_info()
            return StatusResponse(
                success=True,
                data={'info': info, 'restart': False}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # set station info
    @app.put('/api/settings/info')
    async def set_station_info(request: SetStationInfoRequest):
        client = app.state.client
        try:
            client.settings.set_station_info(request.info)
            return StatusResponse(
                success=True,
                message='Station info updated',
                data={'info': request.info, 'restart': False}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get heartbeat interval
    @app.get('/api/settings/heartbeat/interval')
    async def get_heartbeat_interval():
        client = app.state.client
        try:
            interval = client.settings.get_heartbeat_interval()
            return StatusResponse(
                success=True,
                data={'interval': interval, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # set heartbeat interval
    @app.put('/api/settings/heartbeat/interval')
    async def set_heartbeat_interval(request: SetHeartbeatIntervalRequest):
        client = app.state.client
        try:
            client.settings.set_heartbeat_interval(request.interval)
            return StatusResponse(
                success=True,
                message='Heartbeat interval updated',
                data={'interval': request.interval, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get idle timeout  
    @app.get('/api/settings/idle-timeout')
    async def get_idle_timeout():
        client = app.state.client
        try:
            timeout = client.settings.get_idle_timeout()
            return StatusResponse(
                success=True,
                data={'timeout': timeout, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # set idle timeout
    @app.put('/api/settings/idle-timeout')
    async def set_idle_timeout(request: SetIdleTimeoutRequest):
        client = app.state.client
        try:
            client.settings.set_idle_timeout(request.timeout)
            return StatusResponse(
                success=True,
                message='Idle timeout updated',
                data={'timeout': request.timeout, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get distance units
    @app.get('/api/settings/distance-units')
    async def get_distance_units():
        client = app.state.client
        try:
            units_miles = client.settings.get_distance_units_miles()
            return StatusResponse(
                success=True,
                data={'units_miles': units_miles, 'restart': False}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # set distance units
    @app.put('/api/settings/distance-units')
    async def set_distance_units(request: SetDistanceUnitsRequest):
        client = app.state.client
        try:
            client.settings.set_distance_units_miles(request.units_miles)
            return StatusResponse(
                success=True,
                message='Distance units updated',
                data={'units_miles': request.units_miles, 'restart': False}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get primary highlight words
    @app.get('/api/settings/highlights')
    async def get_primary_highlights():
        client = app.state.client
        try:
            words = client.settings.get_primary_highlight_words()
            return StatusResponse(
                success=True,
                data={'words': words, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get secondary highlight words
    @app.get('/api/settings/secondary-highlights')
    async def get_secondary_highlights():
        client = app.state.client
        try:
            words = client.settings.get_secondary_highlight_words()
            return StatusResponse(
                success=True,
                data={'words': words, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # set primary highlight words
    @app.put('/api/settings/highlights')
    async def set_primary_highlights(request: SetHighlightWordsRequest):
        client = app.state.client
        try:
            client.settings.set_primary_highlight_words(request.words)
            return StatusResponse(
                success=True,
                message='Primary highlight words updated',
                data={'words': request.words, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # set secondary highlight words
    @app.put('/api/settings/secondary-highlights')
    async def set_secondary_highlights(request: SetHighlightWordsRequest):
        client = app.state.client
        try:
            client.settings.set_secondary_highlight_words(request.words)
            return StatusResponse(
                success=True,
                message='Secondary highlight words updated',
                data={'words': request.words, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get heartbeat networking
    @app.get('/api/settings/heartbeat/networking')
    async def get_heartbeat_networking():
        client = app.state.client
        try:
            enabled = client.settings.get_heartbeat_networking()
            return StatusResponse(
                success=True,
                data={'enabled': enabled, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # heartbeat networking
    @app.put('/api/settings/heartbeat/networking')
    async def set_heartbeat_networking(request: EnableFeatureRequest):
        client = app.state.client
        try:
            if request.enabled:
                client.settings.enable_heartbeat_networking()
            else:
                client.settings.disable_heartbeat_networking()
            return StatusResponse(
                success=True,
                message=f'Heartbeat networking {"enabled" if request.enabled else "disabled"}',
                data={'enabled': request.enabled, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get heartbeat acknowledgements
    @app.get('/api/settings/heartbeat/acknowledgements')
    async def get_heartbeat_acknowledgements():
        client = app.state.client
        try:
            enabled = client.settings.get_heartbeat_acknowledgements()
            return StatusResponse(
                success=True,
                data={'enabled': enabled, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # heartbeat acknowledgements
    @app.put('/api/settings/heartbeat/acknowledgements')
    async def set_heartbeat_acknowledgements(request: EnableFeatureRequest):
        client = app.state.client
        try:
            if request.enabled:
                client.settings.enable_heartbeat_acknowledgements()
            else:
                client.settings.disable_heartbeat_acknowledgements()
            return StatusResponse(
                success=True,
                message=f'Heartbeat acknowledgements {"enabled" if request.enabled else "disabled"}',
                data={'enabled': request.enabled, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get heartbeat during QSO
    @app.get('/api/settings/heartbeat/qso-pause')
    async def get_heartbeat_qso_pause():
        client = app.state.client
        try:
            paused = client.settings.heartbeat_during_qso_paused()
            return StatusResponse(
                success=True,
                data={'paused': paused, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # heartbeat during QSO
    @app.put('/api/settings/heartbeat/qso-pause')
    async def set_heartbeat_qso_pause(request: EnableFeatureRequest):
        client = app.state.client
        try:
            if request.enabled:
                client.settings.pause_heartbeat_during_qso()
                message = 'Heartbeat during QSO paused'
            else:
                client.settings.allow_heartbeat_during_qso()
                message = 'Heartbeat during QSO allowed'
            return StatusResponse(
                success=True,
                message=message,
                data={'paused': request.enabled, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get multi decode
    @app.get('/api/settings/multi-decode')
    async def get_multi_decode():
        client = app.state.client
        try:
            enabled = client.settings.get_multi_decode()
            return StatusResponse(
                success=True,
                data={'enabled': enabled, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # multi decode
    @app.put('/api/settings/multi-decode')
    async def set_multi_decode(request: EnableFeatureRequest):
        client = app.state.client
        try:
            if request.enabled:
                client.settings.enable_multi_decode()
            else:
                client.settings.disable_multi_decode()
            return StatusResponse(
                success=True,
                message=f'Multi decode {"enabled" if request.enabled else "disabled"}',
                data={'enabled': request.enabled, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get autoreply startup
    @app.get('/api/settings/autoreply-startup')
    async def get_autoreply_startup():
        client = app.state.client
        try:
            enabled = client.settings.get_autoreply_startup()
            return StatusResponse(
                success=True,
                data={'enabled': enabled, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # autoreply startup
    @app.put('/api/settings/autoreply-startup')
    async def set_autoreply_startup(request: EnableFeatureRequest):
        client = app.state.client
        try:
            if request.enabled:
                client.settings.enable_autoreply_startup()
            else:
                client.settings.disable_autoreply_startup()
            return StatusResponse(
                success=True,
                message=f'Autoreply startup {"enabled" if request.enabled else "disabled"}',
                data={'enabled': request.enabled, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get autoreply confirmation
    @app.get('/api/settings/autoreply-confirmation')
    async def get_autoreply_confirmation():
        client = app.state.client
        try:
            enabled = client.settings.get_autoreply_confirmation()
            return StatusResponse(
                success=True,
                data={'enabled': enabled, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # autoreply confirmation
    @app.put('/api/settings/autoreply-confirmation')
    async def set_autoreply_confirmation(request: EnableFeatureRequest):
        client = app.state.client
        try:
            if request.enabled:
                client.settings.enable_autoreply_confirmation()
            else:
                client.settings.disable_autoreply_confirmation()
            return StatusResponse(
                success=True,
                message=f'Autoreply confirmation {"enabled" if request.enabled else "disabled"}',
                data={'enabled': request.enabled, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get allcall
    @app.get('/api/settings/allcall')
    async def get_allcall():
        client = app.state.client
        try:
            enabled = client.settings.get_allcall()
            return StatusResponse(
                success=True,
                data={'enabled': enabled, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # allcall
    @app.put('/api/settings/allcall')
    async def set_allcall(request: EnableFeatureRequest):
        client = app.state.client
        try:
            if request.enabled:
                client.settings.enable_allcall()
            else:
                client.settings.disable_allcall()
            return StatusResponse(
                success=True,
                message=f'Allcall {"enabled" if request.enabled else "disabled"}',
                data={'enabled': request.enabled, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get reporting
    @app.get('/api/settings/reporting')
    async def get_reporting():
        client = app.state.client
        try:
            enabled = client.settings.get_reporting()
            return StatusResponse(
                success=True,
                data={'enabled': enabled, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # reporting
    @app.put('/api/settings/reporting')
    async def set_reporting(request: EnableFeatureRequest):
        client = app.state.client
        try:
            if request.enabled:
                client.settings.enable_reporting()
            else:
                client.settings.disable_reporting()
            return StatusResponse(
                success=True,
                message=f'Reporting {"enabled" if request.enabled else "disabled"}',
                data={'enabled': request.enabled, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get transmit
    @app.get('/api/settings/transmit')
    async def get_transmit():
        client = app.state.client
        try:
            enabled = client.settings.get_transmit()
            return StatusResponse(
                success=True,
                data={'enabled': enabled, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # transmit
    @app.put('/api/settings/transmit')
    async def set_transmit(request: EnableFeatureRequest):
        client = app.state.client
        try:
            if request.enabled:
                client.settings.enable_transmit()
            else:
                client.settings.disable_transmit()
            return StatusResponse(
                success=True,
                message=f'Transmit {"enabled" if request.enabled else "disabled"}',
                data={'enabled': request.enabled, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get daily restart
    @app.get('/api/settings/daily-restart')
    async def get_daily_restart():
        client = app.state.client
        try:
            enabled, restart_time = client.settings.get_daily_restart()
            return StatusResponse(
                success=True,
                data={'enabled': enabled, 'restart_time': restart_time, 'restart': False}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # set daily restart
    @app.put('/api/settings/daily-restart')
    async def set_daily_restart(request: SetDailyRestartRequest):
        client = app.state.client
        try:
            if request.enabled:
                client.settings.enable_daily_restart(request.restart_time)
            else:
                client.settings.disable_daily_restart()
            return StatusResponse(
                success=True,
                message=f'Daily restart {"enabled" if request.enabled else "disabled"}',
                data={'enabled': request.enabled, 'restart_time': request.restart_time if request.enabled else None, 'restart': False}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get active profile
    @app.get('/api/settings/profile')
    async def get_profile():
        client = app.state.client
        try:
            profile = client.settings.get_profile()
            return StatusResponse(
                success=True,
                data={'profile': profile, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get profile list
    @app.get('/api/settings/profiles')
    async def get_profile_list():
        client = app.state.client
        try:
            profiles = client.settings.get_profile_list()
            return StatusResponse(
                success=True,
                data={'profiles': profiles, 'restart': False}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # set active profile
    @app.put('/api/settings/profile')
    async def set_profile(request: SetProfileRequest):
        client = app.state.client
        try:
            client.settings.set_profile(request.profile, request.restore_on_exit, request.create)
            return StatusResponse(
                success=True,
                message='Active profile updated',
                data={'profile': request.profile, 'restore_on_exit': request.restore_on_exit, 'create': request.create, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # create new profile
    @app.post('/api/settings/profiles')
    async def create_profile(request: CreateProfileRequest):
        client = app.state.client
        try:
            client.settings.create_new_profile(request.new_profile, request.copy_profile)
            return StatusResponse(
                success=True,
                message='New profile created',
                data={'new_profile': request.new_profile, 'copy_profile': request.copy_profile, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get groups
    @app.get('/api/settings/groups')
    async def get_groups():
        client = app.state.client
        try:
            groups = client.settings.get_groups_list()
            return StatusResponse(
                success=True,
                data={'groups': groups, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # set groups
    @app.put('/api/settings/groups')
    async def set_groups(request: SetGroupsRequest):
        client = app.state.client
        try:
            client.settings.set_groups(request.groups)
            return StatusResponse(
                success=True,
                message='Groups list updated',
                data={'groups': request.groups, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # add group
    @app.post('/api/settings/groups/add')
    async def add_group(request: AddGroupRequest):
        client = app.state.client
        try:
            client.settings.add_group(request.group)
            return StatusResponse(
                success=True,
                message='Group added',
                data={'group': request.group, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # remove group
    @app.post('/api/settings/groups/remove')
    async def remove_group(request: RemoveGroupRequest):
        client = app.state.client
        try:
            client.settings.remove_group(request.group)
            return StatusResponse(
                success=True,
                message='Group removed',
                data={'group': request.group, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # heartbeat module control
    @app.put('/api/pyjs8call/heartbeat/enable')
    async def enable_heartbeat_module():
        client = app.state.client
        try:
            client.heartbeat.enable()
            return StatusResponse(
                success=True,
                message='Heartbeat module enabled'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put('/api/pyjs8call/heartbeat/disable')
    async def disable_heartbeat_module():
        client = app.state.client
        try:
            client.heartbeat.disable()
            return StatusResponse(
                success=True,
                message='Heartbeat module disabled'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # inbox module control
    @app.put('/api/pyjs8call/inbox/enable')
    async def enable_inbox_module():
        client = app.state.client
        try:
            client.inbox.enable()
            return StatusResponse(
                success=True,
                message='Inbox module enabled'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put('/api/pyjs8call/inbox/disable')
    async def disable_inbox_module():
        client = app.state.client
        try:
            client.inbox.disable()
            return StatusResponse(
                success=True,
                message='Inbox module disabled'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # offset module control
    @app.put('/api/pyjs8call/offset/enable')
    async def enable_offset_module():
        client = app.state.client
        try:
            client.offset.enable()
            return StatusResponse(
                success=True,
                message='Offset module enabled'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put('/api/pyjs8call/offset/disable')
    async def disable_offset_module():
        client = app.state.client
        try:
            client.offset.disable()
            return StatusResponse(
                success=True,
                message='Offset module disabled'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # outgoing module control
    @app.put('/api/pyjs8call/outgoing/enable')
    async def enable_outgoing_module():
        client = app.state.client
        try:
            client.outgoing.enable()
            return StatusResponse(
                success=True,
                message='Outgoing module enabled'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put('/api/pyjs8call/outgoing/disable')
    async def disable_outgoing_module():
        client = app.state.client
        try:
            client.outgoing.disable()
            return StatusResponse(
                success=True,
                message='Outgoing module disabled'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # spots module control
    @app.put('/api/pyjs8call/spots/enable')
    async def enable_spots_module():
        client = app.state.client
        try:
            client.spots.enable()
            return StatusResponse(
                success=True,
                message='Spots module enabled'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put('/api/pyjs8call/spots/disable')
    async def disable_spots_module():
        client = app.state.client
        try:
            client.spots.disable()
            return StatusResponse(
                success=True,
                message='Spots module disabled'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # window module control
    @app.put('/api/pyjs8call/window/enable')
    async def enable_window_module():
        client = app.state.client
        try:
            client.window.enable()
            return StatusResponse(
                success=True,
                message='Window module enabled'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put('/api/pyjs8call/window/disable')
    async def disable_window_module():
        client = app.state.client
        try:
            client.window.disable()
            return StatusResponse(
                success=True,
                message='Window module disabled'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # schedule module control
    @app.put('/api/pyjs8call/schedule/enable')
    async def enable_schedule_module():
        client = app.state.client
        try:
            client.schedule.enable()
            return StatusResponse(
                success=True,
                message='Schedule module enabled'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put('/api/pyjs8call/schedule/disable')
    async def disable_schedule_module():
        client = app.state.client
        try:
            client.schedule.disable()
            return StatusResponse(
                success=True,
                message='Schedule module disabled'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # notifications module control
    @app.put('/api/pyjs8call/notifications/enable')
    async def enable_notifications_module():
        client = app.state.client
        try:
            client.notifications.enable()
            return StatusResponse(
                success=True,
                message='Notifications module enabled'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put('/api/pyjs8call/notifications/disable')
    async def disable_notifications_module():
        client = app.state.client
        try:
            client.notifications.disable()
            return StatusResponse(
                success=True,
                message='Notifications module disabled'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # time module control
    @app.put('/api/pyjs8call/time/enable')
    async def enable_time_module():
        client = app.state.client
        try:
            client.time.enable()
            return StatusResponse(
                success=True,
                message='Time module enabled'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.put('/api/pyjs8call/time/disable')
    async def disable_time_module():
        client = app.state.client
        try:
            client.time.disable()
            return StatusResponse(
                success=True,
                message='Time module disabled'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # configure inbox
    @app.put('/api/pyjs8call/inbox/config')
    async def configure_inbox(request: InboxConfigRequest):
        client = app.state.client
        try:
            if request.enabled:
                client.inbox.enable(query=request.query, destination=request.destination, interval=request.interval)
            else:
                client.inbox.disable()
            return StatusResponse(
                success=True,
                message=f'Inbox module {"enabled" if request.enabled else "disabled"}',
                data={
                    'enabled': request.enabled,
                    'query': request.query if request.enabled else False,
                    'destination': request.destination if request.enabled else None,
                    'interval': request.interval if request.enabled else None
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # configure heartbeat
    @app.put('/api/pyjs8call/heartbeat/config')
    async def configure_heartbeat(request: HeartbeatConfigRequest):
        client = app.state.client
        try:
            if request.enabled:
                if request.interval:
                    client.heartbeat.enable(interval=request.interval)
                else:
                    client.heartbeat.enable()
            else:
                client.heartbeat.disable()
            return StatusResponse(
                success=True,
                message=f'Heartbeat module {"enabled" if request.enabled else "disabled"}',
                data={
                    'enabled': request.enabled,
                    'interval': request.interval if request.enabled else None
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # configure offset
    @app.put('/api/pyjs8call/offset/config')
    async def configure_offset(request: OffsetConfigRequest):
        client = app.state.client
        try:
            if request.enabled:
                client.offset.enable()
                if request.min_offset is not None:
                    client.offset.min_offset = request.min_offset
                if request.max_offset is not None:
                    client.offset.max_offset = request.max_offset
                if request.activity_cycles is not None:
                    client.offset.activity_cycles = request.activity_cycles
                if request.bandwidth_safety_factor is not None:
                    client.offset.bandwidth_safety_factor = request.bandwidth_safety_factor
            else:
                client.offset.disable()
            return StatusResponse(
                success=True,
                message=f'Offset module {"enabled" if request.enabled else "disabled"}',
                data={
                    'enabled': request.enabled,
                    'min_offset': request.min_offset if request.enabled else None,
                    'max_offset': request.max_offset if request.enabled else None,
                    'activity_cycles': request.activity_cycles if request.enabled else None,
                    'bandwidth_safety_factor': request.bandwidth_safety_factor if request.enabled else None
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # configure spots
    @app.put('/api/pyjs8call/spots/config')
    async def configure_spots(request: SpotsConfigRequest):
        client = app.state.client
        try:
            if request.enabled:
                client.spots.enable()
                if request.watched_stations is not None:
                    client.spots.set_watched_stations(request.watched_stations)
                if request.watched_groups is not None:
                    client.spots.set_watched_groups(request.watched_groups)
            else:
                client.spots.disable()
            return StatusResponse(
                success=True,
                message=f'Spots module {"enabled" if request.enabled else "disabled"}',
                data={
                    'enabled': request.enabled,
                    'watched_stations': request.watched_stations if request.enabled else None,
                    'watched_groups': request.watched_groups if request.enabled else None
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # configure notifications
    @app.put('/api/pyjs8call/notifications/config')
    async def configure_notifications(request: NotificationsConfigRequest):
        client = app.state.client
        try:
            if request.enabled:
                client.notifications.enable()
                if request.incoming_enabled is not None:
                    if request.incoming_enabled:
                        client.notifications.enable_incoming()
                    else:
                        client.notifications.disable_incoming()
                if request.spots_enabled is not None:
                    if request.spots_enabled:
                        client.notifications.enable_spots()
                    else:
                        client.notifications.disable_spots()
                if request.station_spots_enabled is not None:
                    if request.station_spots_enabled:
                        client.notifications.enable_station_spots()
                    else:
                        client.notifications.disable_station_spots()
                if request.group_spots_enabled is not None:
                    if request.group_spots_enabled:
                        client.notifications.enable_group_spots()
                    else:
                        client.notifications.disable_group_spots()
                if request.smtp_email and request.smtp_password:
                    client.notifications.set_smtp_credentials(request.smtp_email, request.smtp_password)
                if request.smtp_server and request.smtp_port:
                    client.notifications.set_smtp_server(request.smtp_server, request.smtp_port)
                if request.email_destination:
                    client.notifications.set_email_destination(request.email_destination)
                if request.email_subject:
                    client.notifications.set_email_subject(request.email_subject)
            else:
                client.notifications.disable()
            return StatusResponse(
                success=True,
                message=f'Notifications module {"enabled" if request.enabled else "disabled"}',
                data={
                    'enabled': request.enabled,
                    'incoming_enabled': request.incoming_enabled if request.enabled else None,
                    'spots_enabled': request.spots_enabled if request.enabled else None,
                    'station_spots_enabled': request.station_spots_enabled if request.enabled else None,
                    'group_spots_enabled': request.group_spots_enabled if request.enabled else None
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # configure time
    @app.put('/api/pyjs8call/time/config')
    async def configure_time(request: TimeConfigRequest):
        client = app.state.client
        try:
            if request.enabled:
                client.time.enable()
                if request.drift_monitor_enabled:
                    client.time.drift.enable(
                        station=request.drift_station,
                        group=request.drift_group, 
                        interval=request.drift_interval,
                        threshold=request.drift_threshold,
                        age=request.drift_age
                    )
                if request.timemaster_enabled:
                    client.time.timemaster.enable(
                        destination=request.timemaster_destination,
                        message=request.timemaster_message,
                        interval=request.timemaster_interval
                    )
            else:
                client.time.disable()
            return StatusResponse(
                success=True,
                message=f'Time module {"enabled" if request.enabled else "disabled"}',
                data={
                    'enabled': request.enabled,
                    'drift_monitor_enabled': request.drift_monitor_enabled if request.enabled else None,
                    'timemaster_enabled': request.timemaster_enabled if request.enabled else None
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # start pyjs8call client
    @app.post('/api/pyjs8call/start')
    async def start_client(request: StartClientRequest):
        client = app.state.client
        try:
            client.start(
                headless=request.headless,
                args=request.args,
                debugging=request.debugging,
                logging=request.logging
            )
            return StatusResponse(
                success=True,
                message='PyJS8Call client started successfully',
                data={
                    'headless': request.headless,
                    'debugging': request.debugging,
                    'logging': request.logging,
                    'args': request.args
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # stop pyjs8call client
    @app.post('/api/pyjs8call/stop')
    async def stop_client(request: StopClientRequest):
        client = app.state.client
        try:
            client.stop(terminate_js8call=request.terminate_js8call)
            return StatusResponse(
                success=True,
                message='PyJS8Call client stopped successfully',
                data={'terminate_js8call': request.terminate_js8call}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get pyjs8call client status
    @app.get('/api/pyjs8call/status')
    async def get_client_status():
        client = app.state.client
        try:
            online = client.online
            connected = client.connected()
            js8call_running = client.js8call.is_running() if hasattr(client.js8call, 'is_running') else None
            
            status_data = {
                'online': online,
                'connected': connected,
                'js8call_running': js8call_running
            }
            
            # Add additional status info if available
            if hasattr(client.js8call, 'start_time'):
                try:
                    start_time = client.js8call.start_time()
                    run_time = client.js8call.run_time()
                    status_data.update({
                        'start_time': start_time,
                        'run_time': run_time
                    })
                except:
                    pass
            
            return StatusResponse(
                success=True,
                data=status_data
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get schedule
    @app.get('/api/schedule')
    async def get_schedule():
        client = app.state.client
        try:
            schedule = client.schedule.get_schedule()
            return StatusResponse(
                success=True,
                data={'schedule': schedule, 'count': len(schedule)}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # add schedule entry
    @app.post('/api/schedule')
    async def add_schedule_entry(request: ScheduleEntryRequest):
        client = app.state.client
        try:
            client.schedule.add(
                start_time=request.start_time,
                freq=request.freq,
                speed=request.speed,
                profile=request.profile,
                restart=request.restart
            )
            return StatusResponse(
                success=True,
                message='Schedule entry added',
                data={
                    'start_time': request.start_time,
                    'freq': request.freq,
                    'speed': request.speed,
                    'profile': request.profile,
                    'restart': request.restart
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # remove schedule entry
    @app.delete('/api/schedule/{start_time}')
    async def remove_schedule_entry(start_time: str, profile: Optional[str] = None):
        client = app.state.client
        try:
            client.schedule.remove(start_time=start_time, profile=profile)
            return StatusResponse(
                success=True,
                message='Schedule entry removed',
                data={'start_time': start_time, 'profile': profile}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get spots
    @app.get('/api/activity/spots/all')
    async def get_all_spots():
        client = app.state.client
        try:
            spots = client.spots.all()
            return StatusResponse(
                success=True,
                data={
                    'spots': [MessageModel.from_pyjs8call_message(spot).dict(exclude_none=True) for spot in spots],
                    'count': len(spots)
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get call activity
    @app.get('/api/activity/calls')
    async def get_call_activity(age: Optional[int] = None, hearing_age: Optional[int] = None):
        client = app.state.client
        try:
            activity = client.get_call_activity_from_spots(age=age, hearing_age=hearing_age)
            return StatusResponse(
                success=True,
                data={
                    'call_activity': activity,
                    'count': len(activity)
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get band activity
    @app.get('/api/activity/bands')
    async def get_band_activity(age: Optional[int] = None):
        client = app.state.client
        try:
            activity = client.get_band_activity(age=age)
            return StatusResponse(
                success=True,
                data={
                    'band_activity': activity,
                    'count': len(activity)
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get hearing analysis
    @app.get('/api/activity/hearing')
    async def get_hearing(age: Optional[int] = None):
        client = app.state.client
        try:
            hearing = client.hearing(age=age)
            return StatusResponse(
                success=True,
                data={
                    'hearing': hearing,
                    'count': len(hearing)
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get heard by analysis
    @app.get('/api/activity/heard-by')
    async def get_heard_by(age: Optional[int] = None):
        client = app.state.client
        try:
            heard_by = client.heard_by(age=age)
            return StatusResponse(
                success=True,
                data={
                    'heard_by': heard_by,
                    'count': len(heard_by)
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get station hearing
    @app.get('/api/activity/station/{callsign}/hearing')
    async def get_station_hearing(callsign: str):
        client = app.state.client
        try:
            hearing = client.station_hearing(callsign)
            return StatusResponse(
                success=True,
                data={
                    'callsign': callsign,
                    'hearing': hearing,
                    'count': len(hearing)
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get station heard by
    @app.get('/api/activity/station/{callsign}/heard-by')
    async def get_station_heard_by(callsign: str):
        client = app.state.client
        try:
            heard_by = client.station_heard_by(callsign)
            return StatusResponse(
                success=True,
                data={
                    'callsign': callsign,
                    'heard_by': heard_by,
                    'count': len(heard_by)
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # check if JS8Call has activity
    @app.get('/api/activity')
    async def get_activity(age: int = 0):
        client = app.state.client
        try:
            has_activity = client.activity(age=age)
            return StatusResponse(
                success=True,
                data={'has_activity': has_activity, 'age': age}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get inbox messages
    @app.get('/api/inbox/messages')
    async def get_inbox_messages():
        client = app.state.client
        try:
            messages = client.get_inbox_messages()
            return StatusResponse(
                success=True,
                data={
                    'messages': messages,
                    'count': len(messages)
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get rx text
    @app.get('/api/text/rx')
    async def get_rx_text():
        client = app.state.client
        try:
            rx_text = client.get_rx_text()
            return StatusResponse(
                success=True,
                data={'rx_text': rx_text}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get tx text
    @app.get('/api/text/tx')
    async def get_tx_text():
        client = app.state.client
        try:
            tx_text = client.get_tx_text()
            return StatusResponse(
                success=True,
                data={'tx_text': tx_text}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # set tx text
    @app.put('/api/text/tx')
    async def set_tx_text(request: TextFieldRequest):
        client = app.state.client
        try:
            client.set_tx_text(request.text)
            return StatusResponse(
                success=True,
                message='TX text updated',
                data={'tx_text': request.text}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get rx messages
    @app.get('/api/text/rx-messages')
    async def get_rx_messages():
        client = app.state.client
        try:
            messages = client.get_rx_messages()
            return StatusResponse(
                success=True,
                data={
                    'messages': [MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True) for msg in messages],
                    'count': len(messages)
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # enhanced system status
    @app.get('/api/status/system')
    async def get_system_status():
        client = app.state.client
        try:
            status = {
                'connected': client.connected(),
                'online': client.online,
                'active_profile': client.settings.get_profile(),
                'frequency': client.settings.get_freq(),
                'offset': client.settings.get_offset(),
                'speed': client.settings.get_speed(),
                'callsign': client.settings.get_station_callsign(),
                'grid': client.settings.get_station_grid(),
                'groups': client.settings.get_groups_list(),
                'selected_call': client.get_selected_call()
            }
            return StatusResponse(
                success=True,
                data=status
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # JS8Call application control
    @app.post('/api/pyjs8call/restart')
    async def pyjs8call_restart():
        client = app.state.client
        try:
            client.restart()
            return StatusResponse(
                success=True,
                message='PyJS8Call restart initiated'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post('/api/pyjs8call/restart-when-inactive')
    async def pyjs8call_restart_when_inactive(timeout: int = 300):
        client = app.state.client
        try:
            client.restart_when_inactive(timeout)
            return StatusResponse(
                success=True,
                message=f'PyJS8Call will restart when inactive for {timeout} seconds',
                data={'timeout': timeout, 'restart': True}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post('/api/js8call/raise-window')
    async def js8call_raise_window():
        client = app.state.client
        try:
            client.raise_window()
            return StatusResponse(
                success=True,
                message='JS8Call window raised'
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get('/api/js8call/selected')
    async def get_js8call_selected():
        client = app.state.client
        try:
            selected = client.get_selected_call()
            return StatusResponse(
                success=True,
                data={'selected_call': selected}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # grid distance calculation
    @app.get('/api/utils/grid-distance/{grid1}/{grid2}')
    async def calculate_grid_distance(grid1: str, grid2: str):
        client = app.state.client
        try:
            distance, units, bearing = client.grid_distance(grid1, grid2)
            return StatusResponse(
                success=True,
                data={
                    'grid1': grid1,
                    'grid2': grid2,
                    'distance': distance,
                    'units': units,
                    'bearing': bearing
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # frequency to band conversion
    @app.get('/api/utils/freq-to-band/{frequency}')
    async def freq_to_band(frequency: int):
        client = app.state.client
        try:
            band = client.freq_to_band(frequency)
            return StatusResponse(
                success=True,
                data={
                    'frequency': frequency,
                    'band': band
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # filter spots with advanced criteria
    @app.get('/api/activity/spots/filter')
    async def filter_spots(
        origin: Optional[str] = None,
        destination: Optional[str] = None, 
        grid: Optional[str] = None,
        distance: Optional[int] = None,
        age: Optional[int] = None,
        count: Optional[int] = None,
        profile: Optional[str] = None,
        dial_freq: Optional[int] = None,
        band: Optional[str] = None
    ):
        client = app.state.client
        try:
            # build filter kwargs, excluding None values  
            filter_kwargs = {}
            if origin is not None:
                filter_kwargs['origin'] = origin
            if destination is not None:
                filter_kwargs['destination'] = destination
            if grid is not None:
                filter_kwargs['grid'] = grid
            if distance is not None:
                filter_kwargs['distance'] = distance
            if age is not None:
                filter_kwargs['age'] = age
            if count is not None:
                filter_kwargs['count'] = count
            if profile is not None:
                filter_kwargs['profile'] = profile
            if dial_freq is not None:
                filter_kwargs['dial_freq'] = dial_freq
            if band is not None:
                filter_kwargs['band'] = band
                
            spots = client.spots.filter(**filter_kwargs)
            return StatusResponse(
                success=True,
                data={
                    'spots': [MessageModel.from_pyjs8call_message(spot).dict(exclude_none=True) for spot in spots],
                    'count': len(spots),
                    'filters': filter_kwargs
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # grid to lat/lon conversion
    @app.get('/api/utils/grid-to-latlon/{grid}')
    async def grid_to_latlon(grid: str):
        client = app.state.client
        try:
            lat, lon = client.grid_to_lat_lon(grid)
            return StatusResponse(
                success=True,
                data={
                    'grid': grid,
                    'latitude': lat,
                    'longitude': lon
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # band frequency range
    @app.get('/api/utils/band-freq-range/{band}')
    async def get_band_freq_range(band: str):
        client = app.state.client
        try:
            freq_range = client.band_freq_range(band)
            return StatusResponse(
                success=True,
                data={
                    'band': band,
                    'frequency_range': freq_range
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # heard frequency bands
    @app.get('/api/utils/heard-freq-bands')
    async def get_heard_freq_bands():
        client = app.state.client
        try:
            bands = client.heard_freq_bands()
            return StatusResponse(
                success=True,
                data={'heard_bands': bands}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # propagation analysis - grids dataset
    @app.get('/api/analysis/propagation/grids')
    async def get_grids_dataset(age: Optional[int] = None):
        client = app.state.client
        try:
            dataset = client.propagation.grids_dataset(age=age)
            return StatusResponse(
                success=True,
                data={
                    'grids_dataset': dataset,
                    'count': len(dataset),
                    'age_filter': age
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # propagation analysis - grids median dataset
    @app.get('/api/analysis/propagation/grids-median')
    async def get_grids_median_dataset(age: Optional[int] = None):
        client = app.state.client
        try:
            dataset = client.propagation.grids_median_dataset(age=age)
            return StatusResponse(
                success=True,
                data={
                    'grids_median_dataset': dataset,
                    'count': len(dataset),
                    'age_filter': age
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # propagation analysis - origins dataset
    @app.get('/api/analysis/propagation/origins')
    async def get_origins_dataset(age: Optional[int] = None):
        client = app.state.client
        try:
            dataset = client.propagation.origins_dataset(age=age)
            return StatusResponse(
                success=True,
                data={
                    'origins_dataset': dataset,
                    'count': len(dataset),
                    'age_filter': age
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # propagation analysis - origins median dataset
    @app.get('/api/analysis/propagation/origins-median')
    async def get_origins_median_dataset(age: Optional[int] = None):
        client = app.state.client
        try:
            dataset = client.propagation.origins_median_dataset(age=age)
            return StatusResponse(
                success=True,
                data={
                    'origins_median_dataset': dataset,
                    'count': len(dataset),
                    'age_filter': age
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # propagation analysis - origin median SNR
    @app.get('/api/analysis/propagation/origin/{origin}/median-snr')
    async def get_origin_median_snr(origin: str, age: Optional[int] = None):
        client = app.state.client
        try:
            median_snr = client.propagation.origin_median_snr(origin, age=age)
            return StatusResponse(
                success=True,
                data={
                    'origin': origin,
                    'median_snr': median_snr,
                    'age_filter': age
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # propagation analysis - best band for grid
    @app.get('/api/analysis/propagation/best-band/grid/{grid}')
    async def get_best_band_for_grid(grid: str):
        client = app.state.client
        try:
            best_band = client.propagation.best_band_for_grid(grid)
            return StatusResponse(
                success=True,
                data={
                    'grid': grid,
                    'best_band': best_band
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # propagation analysis - best band for origin
    @app.get('/api/analysis/propagation/best-band/origin/{origin}')
    async def get_best_band_for_origin(origin: str):
        client = app.state.client
        try:
            best_band = client.propagation.best_band_for_origin(origin)
            return StatusResponse(
                success=True,
                data={
                    'origin': origin,
                    'best_band': best_band
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get watched stations
    @app.get('/api/activity/spots/watched/stations')
    async def get_watched_stations():
        client = app.state.client
        try:
            watched = client.spots.watched_stations
            return StatusResponse(
                success=True,
                data={
                    'watched_stations': list(watched),
                    'count': len(watched)
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # get watched groups
    @app.get('/api/activity/spots/watched/groups')
    async def get_watched_groups():
        client = app.state.client
        try:
            watched = client.spots.watched_groups
            return StatusResponse(
                success=True,
                data={
                    'watched_groups': list(watched),
                    'count': len(watched)
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # add station watch
    @app.put('/api/activity/spots/watch/station/{callsign}')
    async def add_station_watch(callsign: str):
        client = app.state.client
        try:
            client.spots.add_station_watch(callsign)
            return StatusResponse(
                success=True,
                message=f'Now watching station {callsign}',
                data={'callsign': callsign}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # remove station watch
    @app.delete('/api/activity/spots/watch/station/{callsign}')
    async def remove_station_watch(callsign: str):
        client = app.state.client
        try:
            client.spots.remove_station_watch(callsign)
            return StatusResponse(
                success=True,
                message=f'Stopped watching station {callsign}',
                data={'callsign': callsign}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # add group watch
    @app.put('/api/activity/spots/watch/group/{group}')
    async def add_group_watch(group: str):
        client = app.state.client
        try:
            client.spots.add_group_watch(group)
            return StatusResponse(
                success=True,
                message=f'Now watching group {group}',
                data={'group': group}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # remove group watch
    @app.delete('/api/activity/spots/watch/group/{group}')
    async def remove_group_watch(group: str):
        client = app.state.client
        try:
            client.spots.remove_group_watch(group)
            return StatusResponse(
                success=True,
                message=f'Stopped watching group {group}',
                data={'group': group}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # grid distance from local station
    @app.get('/api/utils/grid-distance-local/{grid}')
    async def calculate_grid_distance_from_local(grid: str):
        client = app.state.client
        try:
            distance, units, bearing = client.grid_distance(grid)
            local_grid = client.settings.get_station_grid()
            return StatusResponse(
                success=True,
                data={
                    'local_grid': local_grid,
                    'target_grid': grid,
                    'distance': distance,
                    'units': units,
                    'bearing': bearing
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
