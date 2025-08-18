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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from fastapi.responses import JSONResponse
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
                content={
                    'success': False,
                    'error': "Rate limit exceeded, try again later"
                }
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
            # if loop is running, schedule coroutine with error handling
            task = asyncio.create_task(self._broadcast_async(event))
            # add done callback to handle any exceptions
            task.add_done_callback(self._handle_task_exception)
        else:
            # if loop is not running, run coroutine
            loop.run_until_complete(self._broadcast_async(event))
    
    def _handle_task_exception(self, task):
        '''Handle exceptions from async tasks.'''
        try:
            task.result()  # This will raise the exception if one occurred
        except Exception as e:
            import traceback
            print(f"Error in WebSocket broadcast: {e}")
            traceback.print_exc()
    
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
        
        # register for directed messages (type RX_DIRECTED is default)
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
        event = MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
        event['event'] = 'incoming_message'
        self.ws_manager.broadcast_sync(event)
    
    def on_new_spots(self, spots):
        '''Callback for new spots.'''
        event = {
            'event': 'new_spots',
            'spots': [MessageModel.from_pyjs8call_message(spot).dict(exclude_none=True) for spot in spots]
        }
        self.ws_manager.broadcast_sync(event)
    
    def on_outgoing_status(self, msg):
        '''Callback for outgoing message status changes.'''
        event = MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
        event['event'] = 'outgoing_status'
        self.ws_manager.broadcast_sync(event)
    
    def on_inbox_message(self, msgs):
        '''Callback for new inbox messages.'''
        event = {
            'event': 'inbox_message',
            'messages': msgs  # already list of dicts
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
        
        event = data
        event['event'] = 'window_transition'
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
    
    # Add CORS middleware to allow cross-origin requests
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
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
        return {
            'service': 'pyjs8call API',
            'pyjs8call_version': pyjs8call.__version__,
            'api_version': pyjs8call.__api_version__
        }
    
    @app.websocket('/api/events')
    async def websocket_endpoint(websocket: WebSocket):
        client = app.state.client
        ws_manager = app.state.ws_manager
        
        await ws_manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                
                if data.get('action') == 'subscribe':
                    events = data.get('events', [])
                    ws_manager.subscribe(websocket, events)
                    await websocket.send_json({
                        'event': 'subscribed',
                        'events': events
                    })
                    
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)
    
    @app.post('/api/message/freetext')
    async def send_freetext_message(request: SendRawMessageRequest):
        client = app.state.client
        try:
            msg = client.send_message(request.message)
            response = {
                'success': True
            }
            response.update(MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True))
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/heartbeat')
    async def send_heartbeat(grid: Optional[str] = None):
        client = app.state.client
        try:
            msg = client.send_heartbeat(grid)
            response = {
                'success': True
            }
            response.update(MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True))
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/directed')
    async def send_directed_message(request: SendMessageRequest):
        client = app.state.client
        try:
            msg = client.send_directed_message(request.destination, request.message)
            response = {
                'success': True
            }
            response.update(MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True))
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/directed/command')
    async def send_directed_command_message(request: SendDirectedCommandRequest):
        client = app.state.client
        try:
            msg = client.send_directed_command_message(request.destination, request.command, request.message)
            response = {
                'success': True
            }
            response.update(MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True))
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/directed/bytes')
    async def send_directed_bytes_message(request: SendDirectedBytesRequest):
        client = app.state.client
        try:
            import base64
            bytes_data = base64.b64decode(request.data)
            msg = client.send_directed_bytes_message(request.destination, bytes_data)
            response = {
                'success': True
            }
            response.update(MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True))
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/command/msg')
    async def send_inbox_message(request: SendInboxMessageRequest):
        client = app.state.client
        try:
            msg = client.send_inbox_message(request.destination, request.message)
            response = {
                'success': True
            }
            response.update(MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True))
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/command/msg-to')
    async def send_inbox_message_command(request: SendInboxMessageRequest):
        client = app.state.client
        try:
            client.send_inbox_message(request.destination, request.message)
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/inbox/local')
    async def store_local_inbox_message(request: StoreInboxMessageRequest):
        client = app.state.client
        try:
            success = client.store_local_inbox_message(request.origin, request.destination, request.message, request.path)
            return {
                'success': success
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/inbox/remote')
    async def store_remote_inbox_message(request: StoreInboxMessageRequest):
        client = app.state.client
        try:
            success = client.store_remote_inbox_message(request.origin, request.destination, request.message, request.path)
            return {
                'success': success
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/query/call')
    async def query_call(request: QueryCallRequest):
        client = app.state.client
        try:
            msg = client.query_call(request.callsign, request.destination)
            response = {
                'success': True
            }
            response.update(MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True))
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/query/messages')
    async def query_messages(request: QueryMessagesRequest):
        client = app.state.client
        try:
            msg = client.query_messages(request.destination)
            response = {
                'success': True
            }
            response.update(MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True))
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/query/message-id')
    async def query_message_id(request: QueryMessageIdRequest):
        client = app.state.client
        try:
            msg = client.query_message_id(request.destination, request.message_id)
            response = {
                'success': True
            }
            response.update(MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True))
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/query/hearing')
    async def query_hearing(request: StationRequest):
        client = app.state.client
        try:
            msg = client.query_hearing(request.callsign)
            response = {
                'success': True
            }
            response.update(MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True))
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/query/snr')
    async def query_snr(request: StationRequest):
        client = app.state.client
        try:
            msg = client.query_snr(request.callsign)
            response = {
                'success': True
            }
            response.update(MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True))
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/query/grid')
    async def query_grid(request: StationRequest):
        client = app.state.client
        try:
            msg = client.query_grid(request.callsign)
            response = {
                'success': True
            }
            response.update(MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True))
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/query/info')
    async def query_info(request: StationRequest):
        client = app.state.client
        try:
            msg = client.query_info(request.callsign)
            response = {
                'success': True
            }
            response.update(MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True))
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/query/status')
    async def query_status(request: StationRequest):
        client = app.state.client
        try:
            msg = client.query_status(request.callsign)
            response = {
                'success': True
            }
            response.update(MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True))
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/aprs/grid')
    async def send_aprs_grid(request: SendAPRSGridRequest):
        client = app.state.client
        try:
            msg = client.send_aprs_grid(request.grid)
            response = {
                'success': True
            }
            response.update(MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True))
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/aprs/sms')
    async def send_aprs_sms(request: SendAPRSSMSRequest):
        client = app.state.client
        try:
            msg = client.send_aprs_sms(request.phone, request.message)
            response = {
                'success': True
            }
            response.update(MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True))
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/aprs/email')
    async def send_aprs_email(request: SendAPRSEmailRequest):
        client = app.state.client
        try:
            msg = client.send_aprs_email(request.email, request.message)
            response = {
                'success': True
            }
            response.update(MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True))
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/message/aprs/pota')
    async def send_aprs_pota_spot(request: SendAPRSPOTARequest):
        client = app.state.client
        try:
            msg = client.send_aprs_pota_spot(request.park, request.freq, request.mode, request.message, request.callsign)
            response = {
                'success': True
            }
            response.update(MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True))
            return response
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )

    @app.get('/api/config/get/{section}/{option}')
    async def get_config_option(section: str, option: str, value_type: str = 'str'):
        client = app.state.client
        TYPE_MAP = {
            'str': str,
            'int': int,
            'float': float,
            'bool': bool
        }

        try:
            if value_type in TYPE_MAP:
                value_type = TYPE_MAP[value_type]
            else:
                value_type = str

            value = client.config.get(section, option, value_type)
            return {
                'success': True,
                'value': value
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )

    @app.put('/api/config/{section}/{option}')
    async def clear_config_call_activity(section: str, option: str, request: ConfigRequest):
        client = app.state.client
        try:
            previous_value = client.config.get(section, option)
            client.config.set(section, option, request.value)
            current_value = client.config.get(section, option)
            requires_restart = current_value != previous_value
            return {
                'success': True,
                'value': current_value,
                'restart': requires_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )

    @app.post('/api/config/clear-call-activity')
    async def clear_config_call_activity():
        client = app.state.client
        try:
            client.config.clear_call_activity()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/frequency')
    async def get_frequency():
        client = app.state.client
        try:
            freq = client.settings.get_freq()
            return {
                'success': True,
                'frequency': freq,
                'restart': False
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/frequency')
    async def set_frequency(request: SetFrequencyRequest):
        client = app.state.client
        try:
            freq = client.settings.set_freq(request.frequency)
            return {
                'success': True,
                'frequency': freq,
                'restart': False
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/callsign')
    async def get_callsign():
        client = app.state.client
        try:
            callsign = client.settings.get_station_callsign()
            return {
                'success': True,
                'callsign': callsign,
                'restart': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/grid') 
    async def get_grid():
        client = app.state.client
        try:
            grid = client.settings.get_station_grid()
            return {
                'success': True,
                'grid': grid,
                'restart': False
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/callsign')
    async def set_callsign(request: SetCallsignRequest):
        client = app.state.client
        try:
            previous_callsign = client.settings.get_station_callsign()
            client.settings.set_station_callsign(request.callsign)
            current_callsign = client.settings.get_station_callsign()
            needs_restart = previous_callsign != current_callsign
            return {
                'success': True,
                'callsign': current_callsign,
                'restart': needs_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/grid')
    async def set_grid(request: SetGridRequest):
        client = app.state.client
        try:
            client.settings.set_station_grid(request.grid)
            return {
                'success': True,
                'grid': request.grid,
                'restart': False
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/offset')
    async def get_offset():
        client = app.state.client
        try:
            offset = client.settings.get_offset()
            return {
                'success': True,
                'offset': offset,
                'restart': False
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/offset')
    async def set_offset(request: SetOffsetRequest):
        client = app.state.client
        try:
            offset = client.settings.set_offset(request.offset)
            return {
                'success': True,
                'offset': offset,
                'restart': False
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/speed')
    async def get_speed():
        client = app.state.client
        try:
            speed = client.settings.get_speed()
            return {
                'success': True,
                'speed': speed,
                'restart': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/speed')
    async def set_speed(request: SetSpeedRequest):
        client = app.state.client
        try:
            previous_speed = client.settings.get_speed()
            client.settings.set_speed(request.speed)
            current_speed = client.settings.get_speed()
            needs_restart = previous_speed != current_speed
            return {
                'success': True,
                'speed': current_speed,
                'restart': needs_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/info')
    async def get_station_info():
        client = app.state.client
        try:
            info = client.settings.get_station_info()
            return {
                'success': True,
                'info': info,
                'restart': False
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/info')
    async def set_station_info(request: SetStationInfoRequest):
        client = app.state.client
        try:
            client.settings.set_station_info(request.info)
            return {
                'success': True,
                'info': request.info,
                'restart': False
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/heartbeat/interval')
    async def get_heartbeat_interval():
        client = app.state.client
        try:
            interval = client.settings.get_heartbeat_interval()
            return {
                'success': True,
                'interval': interval,
                'restart': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/heartbeat/interval')
    async def set_heartbeat_interval(request: SetHeartbeatIntervalRequest):
        client = app.state.client
        try:
            previous_interval = client.settings.get_heartbeat_interval()
            client.settings.set_heartbeat_interval(request.interval)
            current_interval = client.settings.get_heartbeat_interval()
            needs_restart = previous_interval != current_interval
            return {
                'success': True,
                'interval': current_interval,
                'restart': needs_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/idle-timeout')
    async def get_idle_timeout():
        client = app.state.client
        try:
            timeout = client.settings.get_idle_timeout()
            return {
                'success': True,
                'timeout': timeout,
                'restart': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/idle-timeout')
    async def set_idle_timeout(request: SetIdleTimeoutRequest):
        client = app.state.client
        try:
            previous_timeout = client.settings.get_idle_timeout()
            client.settings.set_idle_timeout(request.timeout)
            current_timeout = client.settings.get_idle_timeout()
            needs_restart = previous_timeout != current_timeout
            return {
                'success': True,
                'timeout': current_timeout,
                'restart': needs_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/distance-units')
    async def get_distance_units():
        client = app.state.client
        try:
            units_miles = client.settings.get_distance_units_miles()
            return {
                'success': True,
                'units_miles': units_miles,
                'restart': False
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/distance-units')
    async def set_distance_units(request: SetDistanceUnitsRequest):
        client = app.state.client
        try:
            client.settings.set_distance_units_miles(request.units_miles)
            return {
                'success': True,
                'restart': False
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/highlights')
    async def get_primary_highlights():
        client = app.state.client
        try:
            words = client.settings.get_primary_highlight_words()
            return {
                'success': True,
                'words': words,
                'restart': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/secondary-highlights')
    async def get_secondary_highlights():
        client = app.state.client
        try:
            words = client.settings.get_secondary_highlight_words()
            return {
                'success': True,
                'words': words,
                'restart': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/highlights')
    async def set_primary_highlights(request: SetHighlightWordsRequest):
        client = app.state.client
        try:
            previous_words = client.settings.get_primary_highlight_words()
            client.settings.set_primary_highlight_words(request.words)
            current_words = client.settings.get_primary_highlight_words()
            needs_restart = previous_words != current_words
            return {
                'success': True,
                'words': current_words,
                'restart': needs_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/secondary-highlights')
    async def set_secondary_highlights(request: SetHighlightWordsRequest):
        client = app.state.client
        try:
            previous_words = client.settings.get_secondary_highlight_words()
            client.settings.set_secondary_highlight_words(request.words)
            current_words = client.settings.get_secondary_highlight_words()
            needs_restart = previous_words != current_words
            return {
                'success': True,
                'words': current_words,
                'restart': needs_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/heartbeat/networking')
    async def get_heartbeat_networking():
        client = app.state.client
        try:
            enabled = client.settings.get_heartbeat_networking()
            return {
                'success': True,
                'enabled': enabled,
                'restart': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/heartbeat/networking')
    async def set_heartbeat_networking(request: EnableFeatureRequest):
        client = app.state.client
        try:
            previous_enabled = client.settings.get_heartbeat_networking()
            if request.enabled:
                client.settings.enable_heartbeat_networking()
            else:
                client.settings.disable_heartbeat_networking()
            current_enabled = client.settings.get_heartbeat_networking()
            needs_restart = previous_enabled != current_enabled
            return {
                'success': True,
                'enabled': current_enabled,
                'restart': needs_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/heartbeat/acknowledgements')
    async def get_heartbeat_acknowledgements():
        client = app.state.client
        try:
            enabled = client.settings.get_heartbeat_acknowledgements()
            return {
                'success': True,
                'enabled': enabled,
                'restart': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/heartbeat/acknowledgements')
    async def set_heartbeat_acknowledgements(request: EnableFeatureRequest):
        client = app.state.client
        try:
            previous_enabled = client.settings.get_heartbeat_acknowledgements()
            if request.enabled:
                client.settings.enable_heartbeat_acknowledgements()
            else:
                client.settings.disable_heartbeat_acknowledgements()
            current_enabled = client.settings.get_heartbeat_acknowledgements()
            needs_restart = previous_enabled != current_enabled
            return {
                'success': True,
                'enabled': current_enabled,
                'restart': needs_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/heartbeat/qso-pause')
    async def get_heartbeat_qso_pause():
        client = app.state.client
        try:
            paused = client.settings.heartbeat_during_qso_paused()
            return {
                'success': True,
                'paused': paused,
                'restart': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/heartbeat/qso-pause')
    async def set_heartbeat_qso_pause(request: EnableFeatureRequest):
        client = app.state.client
        try:
            previous_paused = client.settings.heartbeat_during_qso_paused()
            if request.enabled:
                client.settings.pause_heartbeat_during_qso()
            else:
                client.settings.allow_heartbeat_during_qso()
            current_paused = client.settings.heartbeat_during_qso_paused()
            needs_restart = previous_paused != current_paused
            return {
                'success': True,
                'paused': current_paused,
                'restart': needs_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/multi-decode')
    async def get_multi_decode():
        client = app.state.client
        try:
            enabled = client.settings.get_multi_decode()
            return {
                'success': True,
                'enabled': enabled,
                'restart': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/multi-decode')
    async def set_multi_decode(request: EnableFeatureRequest):
        client = app.state.client
        try:
            previous_enabled = client.settings.get_multi_decode()
            if request.enabled:
                client.settings.enable_multi_decode()
            else:
                client.settings.disable_multi_decode()
            current_enabled = client.settings.get_multi_decode()
            needs_restart = previous_enabled != current_enabled
            return {
                'success': True,
                'enabled': current_enabled,
                'restart': needs_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/autoreply-startup')
    async def get_autoreply_startup():
        client = app.state.client
        try:
            enabled = client.settings.get_autoreply_startup()
            return {
                'success': True,
                'enabled': enabled,
                'restart': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/autoreply-startup')
    async def set_autoreply_startup(request: EnableFeatureRequest):
        client = app.state.client
        try:
            previous_enabled = client.settings.get_autoreply_startup()
            if request.enabled:
                client.settings.enable_autoreply_startup()
            else:
                client.settings.disable_autoreply_startup()
            current_enabled = client.settings.get_autoreply_startup()
            needs_restart = previous_enabled != current_enabled
            return {
                'success': True,
                'enabled': current_enabled,
                'restart': needs_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/autoreply-confirmation')
    async def get_autoreply_confirmation():
        client = app.state.client
        try:
            enabled = client.settings.get_autoreply_confirmation()
            return {
                'success': True,
                'enabled': enabled,
                'restart': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/autoreply-confirmation')
    async def set_autoreply_confirmation(request: EnableFeatureRequest):
        client = app.state.client
        try:
            previous_enabled = client.settings.get_autoreply_confirmation()
            if request.enabled:
                client.settings.enable_autoreply_confirmation()
            else:
                client.settings.disable_autoreply_confirmation()
            current_enabled = client.settings.get_autoreply_confirmation()
            needs_restart = previous_enabled != current_enabled
            return {
                'success': True,
                'enabled': current_enabled,
                'restart': needs_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/allcall')
    async def get_allcall():
        client = app.state.client
        try:
            enabled = client.settings.get_allcall()
            return {
                'success': True,
                'enabled': enabled,
                'restart': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/allcall')
    async def set_allcall(request: EnableFeatureRequest):
        client = app.state.client
        try:
            previous_enabled = client.settings.get_allcall()
            if request.enabled:
                client.settings.enable_allcall()
            else:
                client.settings.disable_allcall()
            current_enabled = client.settings.get_allcall()
            needs_restart = previous_enabled != current_enabled
            return {
                'success': True,
                'enabled': current_enabled,
                'restart': needs_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/reporting')
    async def get_reporting():
        client = app.state.client
        try:
            enabled = client.settings.get_reporting()
            return {
                'success': True,
                'enabled': enabled,
                'restart': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/reporting')
    async def set_reporting(request: EnableFeatureRequest):
        client = app.state.client
        try:
            previous_enabled = client.settings.get_reporting()
            if request.enabled:
                client.settings.enable_reporting()
            else:
                client.settings.disable_reporting()
            current_enabled = client.settings.get_reporting()
            needs_restart = previous_enabled != current_enabled
            return {
                'success': True,
                'enabled': current_enabled,
                'restart': needs_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/transmit')
    async def get_transmit():
        client = app.state.client
        try:
            enabled = client.settings.get_transmit()
            return {
                'success': True,
                'enabled': enabled,
                'restart': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/transmit')
    async def set_transmit(request: EnableFeatureRequest):
        client = app.state.client
        try:
            previous_enabled = client.settings.get_transmit()
            if request.enabled:
                client.settings.enable_transmit()
            else:
                client.settings.disable_transmit()
            current_enabled = client.settings.get_transmit()
            needs_restart = previous_enabled != current_enabled
            return {
                'success': True,
                'enabled': current_enabled,
                'restart': needs_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/daily-restart')
    async def get_daily_restart():
        client = app.state.client
        try:
            enabled, restart_time = client.settings.get_daily_restart()
            return {
                'success': True,
                'enabled': enabled,
                'restart_time': restart_time,
                'restart': False
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/daily-restart')
    async def set_daily_restart(request: SetDailyRestartRequest):
        client = app.state.client
        try:
            if request.enabled:
                client.settings.enable_daily_restart(request.restart_time)
            else:
                client.settings.disable_daily_restart()
            current_enabled = client.settings.get_daily_restart_enabled()
            current_restart_time = client.settings.get_daily_restart_time() if current_enabled else None
            return {
                'success': True,
                'enabled': current_enabled,
                'restart_time': current_restart_time,
                'restart': False
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/profile')
    async def get_profile():
        client = app.state.client
        try:
            profile = client.settings.get_profile()
            return {
                'success': True,
                'profile': profile,
                'restart': False
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/profiles')
    async def get_profile_list():
        client = app.state.client
        try:
            profiles = client.settings.get_profile_list()
            return {
                'success': True,
                'profiles': profiles,
                'restart': False
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/profile')
    async def set_profile(request: SetProfileRequest):
        client = app.state.client
        try:
            previous_profile = client.settings.get_profile()
            client.settings.set_profile(request.profile, request.restore_on_exit, request.create)
            current_profile = client.settings.get_profile()
            needs_restart = previous_profile != current_profile
            return {
                'success': True,
                'profile': current_profile,
                'restart': needs_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/settings/create-profile')
    async def create_profile(request: CreateProfileRequest):
        client = app.state.client
        try:
            client.settings.create_new_profile(request.new_profile, request.copy_profile)
            return {
                'success': True,
                'new_profile': request.new_profile,
                'copy_profile': request.copy_profile,
                'restart': False # restart to set profile, but not create profile
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/settings/groups')
    async def get_groups():
        client = app.state.client
        try:
            groups = client.settings.get_groups_list()
            return {
                'success': True,
                'groups': groups,
                'restart': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/groups')
    async def set_groups(request: SetGroupsRequest):
        client = app.state.client
        try:
            previous_groups = client.settings.get_groups_list()
            client.settings.set_groups(request.groups)
            current_groups = client.settings.get_groups_list()
            needs_restart = previous_groups != current_groups
            return {
                'success': True,
                'groups': current_groups,
                'restart': needs_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/settings/groups/{group}')
    async def add_group(group: str):
        client = app.state.client
        try:
            current_groups = client.settings.get_groups_list()
            client.settings.add_group(group)
            new_groups = client.settings.get_groups_list()
            needs_restart = current_groups != new_groups
            return {
                'success': True,
                'groups': new_groups,
                'restart': needs_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.delete('/api/settings/groups/{group}')
    async def remove_group(group: str):
        client = app.state.client
        try:
            current_groups = client.settings.get_groups_list()
            client.settings.remove_group(group)
            new_groups = client.settings.get_groups_list()
            needs_restart = current_groups != new_groups
            return {
                'success': True,
                'groups': new_groups,
                'restart': needs_restart
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/heartbeat/enable')
    async def enable_heartbeat_module():
        client = app.state.client
        try:
            client.heartbeat.enable()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/heartbeat/disable')
    async def disable_heartbeat_module():
        client = app.state.client
        try:
            client.heartbeat.disable()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/heartbeat/config')
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
            current_enabled = client.heartbeat.enabled
            current_interval = client.heartbeat.interval if current_enabled else None
            return {
                'success': True,
                'enabled': current_enabled,
                'interval': current_interval
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/inbox/enable')
    async def enable_inbox_module():
        client = app.state.client
        try:
            client.inbox.enable()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/inbox/disable')
    async def disable_inbox_module():
        client = app.state.client
        try:
            client.inbox.disable()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/inbox/config')
    async def configure_inbox(request: InboxConfigRequest):
        client = app.state.client
        try:
            if request.enabled:
                client.inbox.enable(query=request.query, destination=request.destination, interval=request.interval)
            else:
                client.inbox.disable()
            current_enabled = client.inbox.enabled
            current_query = client.inbox.query if current_enabled else False
            current_destination = client.inbox.destination if current_enabled else None
            current_interval = client.inbox.interval if current_enabled else None
            return {
                'success': True,
                'enabled': current_enabled,
                'query': current_query,
                'destination': current_destination,
                'interval': current_interval
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/offset/enable')
    async def enable_offset_module():
        client = app.state.client
        try:
            client.offset.enable()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/inbox/messages')
    async def get_inbox_messages():
        client = app.state.client
        try:
            msgs = client.inbox.messages()
            return {
                'success': True,
                'messages': msgs,
                'count': len(msgs)
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/inbox/messages/unread')
    async def get_unread_inbox_messages():
        client = app.state.client
        try:
            msgs = client.inbox.unread()
            return {
                'success': True,
                'messages': msgs,
                'count': len(msgs)
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/inbox/messages/stored')
    async def get_stored_inbox_messages():
        client = app.state.client
        try:
            msgs = client.inbox.stored()
            return {
                'success': True,
                'messages': msgs,
                'count': len(msgs)
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/inbox/messages/mark-read')
    async def mark_inbox_messages_read():
        client = app.state.client
        try:
            client.inbox.mark_all_read()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/inbox/messages/clear-read')
    async def clear_inbox_messages():
        client = app.state.client
        try:
            client.inbox.clear()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/inbox/message/{id}')
    async def get_inbox_message_by_id(id: int):
        client = app.state.client
        try:
            msg = client.inbox.message(id)
            return {
                'success': True,
                'message': msg
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/inbox/message/{id}/mark-read')
    async def mark_inbox_message_read_by_id(id: int):
        client = app.state.client
        try:
            client.inbox.mark_read(id)
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/inbox/message/{id}/mark-unread')
    async def mark_inbox_message_unread_by_id(id: int):
        client = app.state.client
        try:
            client.inbox.mark_unread(id)
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/offset/disable')
    async def disable_offset_module():
        client = app.state.client
        try:
            client.offset.disable()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/offset/config')
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
            current_enabled = client.offset.enabled
            current_min_offset = client.offset.min_offset if current_enabled else None
            current_max_offset = client.offset.max_offset if current_enabled else None
            current_activity_cycles = client.offset.activity_cycles if current_enabled else None
            current_bandwidth_safety_factor = client.offset.bandwidth_safety_factor if current_enabled else None
            return {
                'success': True,
                'enabled': current_enabled,
                'min_offset': current_min_offset,
                'max_offset': current_max_offset,
                'activity_cycles': current_activity_cycles,
                'bandwidth_safety_factor': current_bandwidth_safety_factor
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/outgoing/enable')
    async def enable_outgoing_module():
        client = app.state.client
        try:
            client.outgoing.enable()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/outgoing/disable')
    async def disable_outgoing_module():
        client = app.state.client
        try:
            client.outgoing.disable()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/spots/enable')
    async def enable_spots_module():
        client = app.state.client
        try:
            client.spots.enable()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/spots/disable')
    async def disable_spots_module():
        client = app.state.client
        try:
            client.spots.disable()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/spots/config')
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
            current_enabled = client.spots.enabled
            current_watched_stations = client.spots.watched_stations if current_enabled else None
            current_watched_groups = client.spots.watched_groups if current_enabled else None
            return {
                'success': True,
                'enabled': current_enabled,
                'watched_stations': current_watched_stations,
                'watched_groups': current_watched_groups
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/window/enable')
    async def enable_window_module():
        client = app.state.client
        try:
            client.window.enable()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/window/disable')
    async def disable_window_module():
        client = app.state.client
        try:
            client.window.disable()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/schedule/enable')
    async def enable_schedule_module():
        client = app.state.client
        try:
            client.schedule.enable()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/schedule/disable')
    async def disable_schedule_module():
        client = app.state.client
        try:
            client.schedule.disable()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/notifications/enable')
    async def enable_notifications_module():
        client = app.state.client
        try:
            client.notifications.enable()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/notifications/disable')
    async def disable_notifications_module():
        client = app.state.client
        try:
            client.notifications.disable()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/notifications/config')
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

            current_enabled = client.notifications.enabled
            current_incoming_enabled = client.notifications.incoming_enabled if current_enabled else None
            current_spots_enabled = client.notifications.spots_enabled if current_enabled else None
            current_station_spots_enabled = client.notifications.station_spots_enabled if current_enabled else None
            current_group_spots_enabled = client.notifications.group_spots_enabled if current_enabled else None

            return {
                'success': True,
                'enabled': current_enabled,
                'incoming_enabled': current_incoming_enabled,
                'spots_enabled': current_spots_enabled,
                'station_spots_enabled': current_station_spots_enabled,
                'group_spots_enabled': current_group_spots_enabled
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/time/enable')
    async def enable_time_module():
        client = app.state.client
        try:
            client.time.enable()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/time/disable')
    async def disable_time_module():
        client = app.state.client
        try:
            client.time.disable()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/time/config')
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

            current_enabled = client.time.enabled
            current_drift_monitor_enabled = client.time.drift.enabled if current_enabled else None
            current_timemaster_enabled = client.time.timemaster.enabled if current_enabled else None

            return {
                'success': True,
                'enabled': current_enabled,
                'drift_monitor_enabled': current_drift_monitor_enabled,
                'timemaster_enabled': current_timemaster_enabled
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/schedule')
    async def get_schedule():
        client = app.state.client
        try:
            schedule = client.schedule.get_schedule()
            return {
                'success': True,
                'schedule': schedule
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
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
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.delete('/api/schedule/{start_time}')
    async def remove_schedule_entry(start_time: str, profile: Optional[str] = None):
        client = app.state.client
        try:
            client.schedule.remove(start_time=start_time, profile=profile)
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/spots/all')
    async def get_all_spots():
        client = app.state.client
        try:
            spots = client.spots.all()
            return {
                'success': True,
                'spots': [MessageModel.from_pyjs8call_message(spot).dict(exclude_none=True) for spot in spots],
                'count': len(spots)
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/activity/stations')
    async def get_call_activity(age: Optional[int] = None, hearing_age: Optional[int] = None):
        client = app.state.client
        try:
            activity = client.get_call_activity_from_spots(age=age, hearing_age=hearing_age)
            return {
                'success': True,
                'activity': activity,
                'count': len(activity)
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/activity/band')
    async def get_band_activity(age: Optional[int] = None):
        client = app.state.client
        try:
            activity = client.get_band_activity(age=age)
            return {
                'success': True,
                'activity': activity,
                'count': len(activity)
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/activity/hearing')
    async def get_hearing(age: Optional[int] = None):
        client = app.state.client
        try:
            hearing = client.hearing(age=age)
            return {
                'success': True,
                'hearing': hearing,
                'count': len(hearing)
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/activity/heard-by')
    async def get_heard_by(age: Optional[int] = None):
        client = app.state.client
        try:
            heard_by = client.heard_by(age=age)
            return {
                'success': True,
                'heard_by': heard_by,
                'count': len(heard_by)
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/activity/{callsign}/hearing')
    async def get_station_hearing(callsign: str):
        client = app.state.client
        try:
            hearing = client.station_hearing(callsign)
            return {
                'success': True,
                'callsign': callsign,
                'hearing': hearing,
                'count': len(hearing)
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/activity/{callsign}/heard-by')
    async def get_station_heard_by(callsign: str):
        client = app.state.client
        try:
            heard_by = client.station_heard_by(callsign)
            return {
                'success': True,
                'callsign': callsign,
                'heard_by': heard_by,
                'count': len(heard_by)
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/activity')
    async def get_activity(age: int = 0):
        client = app.state.client
        try:
            has_activity = client.activity(age=age)
            return {
                'success': True,
                'activity': has_activity,
                'age': age
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/text/rx')
    async def get_rx_text():
        client = app.state.client
        try:
            rx_text = client.get_rx_text()
            return {
                'success': True,
                'text': rx_text
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )

    @app.get('/api/text/rx/messages')
    async def get_rx_messages():
        client = app.state.client
        try:
            messages = client.get_rx_messages()
            return {
                'success': True,
                'messages': messages,
                'count': len(messages)
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/text/tx')
    async def get_tx_text():
        client = app.state.client
        try:
            tx_text = client.get_tx_text()
            return {
                'success': True,
                'text': tx_text
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/text/tx')
    async def set_tx_text(request: TextFieldRequest):
        client = app.state.client
        try:
            client.set_tx_text(request.text)
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/js8call')
    async def get_system_status():
        client = app.state.client
        try:
            status = {
                'pyjs8call_online': client.online,
                'socket_connected': client.connected(),
                'process_restarting': client.restarting,
                'process_running': client.js8call.app.is_running(),
                'process_start_time': client.js8call.app.start_time(),
                'process_run_time': client.js8call.app.run_time(),
                'profile': client.settings.get_profile(),
                'freq': client.settings.get_freq(),
                'offset': client.settings.get_offset(),
                'speed': client.settings.get_speed(),
                'callsign': client.settings.get_station_callsign(),
                'grid': client.settings.get_station_grid(),
                'groups': client.settings.get_groups_list(),
                'selected_call': client.get_selected_call(),
            }
            return {
                'success': True,
                **status
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/js8call/connected')
    async def get_connection_status():
        client = app.state.client
        return {
            'success': True,
            'connected': client.connected(),
            'online': client.online
        }
    
    @app.post('/api/js8call/start')
    async def start_client_with_args(request: StartClientRequest):
        client = app.state.client
        try:
            client.start(
                headless=request.headless,
                args=request.args,
                debugging=request.debugging,
                logging=request.logging
            )
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/js8call/stop')
    async def stop_client(request: StopClientRequest):
        client = app.state.client
        try:
            client.stop(terminate_js8call=request.terminate_js8call)
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/js8call/restart')
    async def pyjs8call_restart():
        client = app.state.client
        try:
            client.restart()
            return {
                'success': True
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/js8call/restart-when-inactive')
    async def pyjs8call_restart_when_inactive(timeout: int = 300):
        client = app.state.client
        try:
            client.restart_when_inactive(timeout)
            return {
                'success': True,
                'timeout': timeout
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.post('/api/js8call/raise-window')
    async def js8call_raise_window():
        client = app.state.client
        try:
            client.raise_window()
            return {
                'success': True,
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/js8call/selected-call')
    async def get_js8call_selected():
        client = app.state.client
        try:
            selected = client.get_selected_call()
            return {
                'success': True,
                'selected': selected
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/js8call/queued-msg-count')
    async def get_js8call_queued_msg_count():
        client = app.state.client
        try:
            return {
                'success': True,
                'count': client.js8call.queued_msg_count()
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/utils/grid-distance/{grid}')
    async def calculate_grid_distance_from_local(grid: str):
        client = app.state.client
        try:
            distance, units, bearing = client.grid_distance(grid)
            local_grid = client.settings.get_station_grid()
            return {
                'success': True,
                'station_grid': local_grid,
                'grid': grid,
                'distance': distance,
                'units': units,
                'bearing': bearing
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/utils/grid-distance/{grid_a}/{grid_b}')
    async def calculate_grid_distance(grid_a: str, grid_b: str):
        client = app.state.client
        try:
            distance, units, bearing = client.grid_distance(grid_a, grid_b)
            return {
                'success': True,
                'grid_a': grid_a,
                'grid_b': grid_b,
                'distance': distance,
                'units': units,
                'bearing': bearing
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/utils/grid-to-lat-lon/{grid}')
    async def grid_to_latlon(grid: str):
        client = app.state.client
        try:
            lat, lon = client.grid_to_lat_lon(grid)
            return {
                'success': True,
                'grid': grid,
                'lat': lat,
                'lon': lon
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/utils/freq-to-band/{frequency}')
    async def freq_to_band(frequency: int):
        client = app.state.client
        try:
            band = client.freq_to_band(frequency)
            return {
                'success': True,
                'freq': frequency,
                'band': band
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/utils/band-to-freq/{band}')
    async def get_band_freq_range(band: str):
        client = app.state.client
        try:
            freq_range = client.band_freq_range(band)
            return {
                'success': True,
                'band': band,
                'freq': freq_range,
                'min': freq_range[0],
                'max': freq_range[1]
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/utils/heard-freq-bands')
    async def get_heard_freq_bands():
        client = app.state.client
        try:
            bands = client.heard_freq_bands()
            return {
                'success': True,
                'bands': bands
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/propagation/grids')
    async def get_grids_dataset(age: Optional[int] = None):
        client = app.state.client
        try:
            dataset = client.propagation.grids_dataset(age=age)
            return {
                'success': True,
                'grids': dataset,
                'count': len(dataset),
                'age': age
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/propagation/grids/median')
    async def get_grids_median_dataset(age: Optional[int] = None):
        client = app.state.client
        try:
            dataset = client.propagation.grids_median_dataset(age=age)
            return {
                'success': True,
                'grids': dataset,
                'count': len(dataset),
                'age': age
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/propagation/origins')
    async def get_origins_dataset(age: Optional[int] = None):
        client = app.state.client
        try:
            dataset = client.propagation.origins_dataset(age=age)
            return {
                'success': True,
                'origins': dataset,
                'count': len(dataset),
                'age': age
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/propagation/origins/median')
    async def get_origins_median_dataset(age: Optional[int] = None):
        client = app.state.client
        try:
            dataset = client.propagation.origins_median_dataset(age=age)
            return {
                'success': True,
                'origins': dataset,
                'count': len(dataset),
                'age': age
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/propagation/origin-median-snr/{origin}')
    async def get_origin_median_snr(origin: str, age: Optional[int] = None):
        client = app.state.client
        try:
            median_snr = client.propagation.origin_median_snr(origin, age=age)
            return {
                'success': True,
                'origin': origin,
                'snr': median_snr,
                'age': age
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/propagation/best-band/grid/{grid}')
    async def get_best_band_for_grid(grid: str):
        client = app.state.client
        try:
            best_band = client.propagation.best_band_for_grid(grid)
            return {
                'success': True,
                'grid': grid,
                'band': best_band
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/propagation/best-band/origin/{origin}')
    async def get_best_band_for_origin(origin: str):
        client = app.state.client
        try:
            best_band = client.propagation.best_band_for_origin(origin)
            return {
                'success': True,
                'origin': origin,
                'band': best_band
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/spots/filter')
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
            return {
                'success': True,
                'spots': [MessageModel.from_pyjs8call_message(spot).dict(exclude_none=True) for spot in spots],
                'count': len(spots),
                'filters': filter_kwargs
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/spots/watched/stations')
    async def get_watched_stations():
        client = app.state.client
        try:
            return {
                'success': True,
                'stations': client.spots.get_watched_stations()
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.get('/api/spots/watched/groups')
    async def get_watched_groups():
        client = app.state.client
        try:
            return {
                'success': True,
                'groups': client.spots.get_watched_groups()
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/spots/watch/station/{callsign}')
    async def add_station_watch(callsign: str):
        client = app.state.client
        try:
            client.spots.add_station_watch(callsign)
            return {
                'success': True,
                'stations': client.spots.get_watched_stations()
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.delete('/api/spots/watch/station/{callsign}')
    async def remove_station_watch(callsign: str):
        client = app.state.client
        try:
            client.spots.remove_station_watch(callsign)
            return {
                'success': True,
                'stations': client.spots.get_watched_stations()
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.put('/api/spots/watch/group/{group}')
    async def add_group_watch(group: str):
        client = app.state.client
        try:
            client.spots.add_group_watch(group)
            return {
                'success': True,
                'groups': client.spots.get_watched_groups()
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
    
    @app.delete('/api/spots/watch/group/{group}')
    async def remove_group_watch(group: str):
        client = app.state.client
        try:
            client.spots.remove_group_watch(group)
            return {
                'success': True,
                'groups': client.spots.get_watched_groups()
            }
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    'success': False,
                    'error': str(e)
                }
            )
