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

from .models import *


class SimpleRateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(deque)  # IP -> deque of timestamps
        
    def is_allowed(self, client_ip: str) -> bool:
        """Check if request from client IP is allowed.
        
        Args:
            client_ip: Client IP address
            
        Returns:
            bool: True if request is allowed, False if rate limited
        """
        now = time.time()
        minute_ago = now - 60
        
        # Clean old requests
        client_requests = self.requests[client_ip]
        while client_requests and client_requests[0] < minute_ago:
            client_requests.popleft()
            
        # Check limit
        if len(client_requests) >= self.requests_per_minute:
            return False
            
        # Add current request
        client_requests.append(now)
        return True


class AuthMiddleware(BaseHTTPMiddleware):
    """API key authentication middleware."""
    
    def __init__(self, app, api_key: str, rate_limiter: SimpleRateLimiter):
        super().__init__(app)
        self.api_key = api_key
        self.rate_limiter = rate_limiter
    
    async def dispatch(self, request: Request, call_next):
        # Skip auth for non-API paths and WebSocket upgrades
        if not request.url.path.startswith('/api') or request.headers.get('upgrade') == 'websocket':
            return await call_next(request)
            
        # Get client IP
        client_ip = request.client.host
        
        # Check rate limit
        if not self.rate_limiter.is_allowed(client_ip):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        # Check API key
        api_key = request.headers.get('X-API-Key')
        if api_key != self.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
            
        return await call_next(request)


class WebSocketManager:
    """Manage WebSocket connections and event broadcasting."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.subscriptions: Dict[WebSocket, List[str]] = {}
    
    async def connect(self, websocket: WebSocket):
        """Accept WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = []
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.subscriptions:
            del self.subscriptions[websocket]
    
    def subscribe(self, websocket: WebSocket, events: List[str]):
        """Subscribe WebSocket to events."""
        self.subscriptions[websocket] = events
    
    def broadcast_sync(self, event: Dict[str, Any]):
        """Synchronously broadcast event to subscribed clients."""
        import asyncio
        
        # Get current event loop or create new one
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run broadcast in event loop
        if loop.is_running():
            # If loop is running, schedule coroutine
            asyncio.create_task(self._broadcast_async(event))
        else:
            # If loop is not running, run coroutine
            loop.run_until_complete(self._broadcast_async(event))
    
    async def _broadcast_async(self, event: Dict[str, Any]):
        """Asynchronously broadcast event to subscribed clients."""
        event_type = event.get('event')
        if not event_type:
            return
            
        # Send to subscribed connections
        disconnected = []
        for websocket in self.active_connections:
            if event_type in self.subscriptions.get(websocket, []):
                try:
                    await websocket.send_json(event)
                except:
                    disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket)


class EventBridge:
    """Bridge between pyjs8call callbacks and WebSocket events."""
    
    def __init__(self, websocket_manager: WebSocketManager):
        self.ws_manager = websocket_manager
        
    def register_with_client(self, client):
        """Register all callbacks with the pyjs8call client."""
        # Register for directed messages (RX_DIRECTED is default)
        client.callback.register_incoming(self.on_incoming_message)
        
        # Register for spots
        client.callback.register_spots(self.on_new_spots)
        
        # Set outgoing callback (single function, not list)
        client.callback.outgoing = self.on_outgoing_status
        
        # Set inbox callback (single function, not list)  
        client.callback.inbox = self.on_inbox_message
    
    def on_incoming_message(self, msg):
        """Callback for incoming directed messages."""
        event = {
            "event": "incoming_message",
            "timestamp": time.time(),
            "data": MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
        }
        self.ws_manager.broadcast_sync(event)
    
    def on_new_spots(self, spots):
        """Callback for new spots."""
        event = {
            "event": "new_spots",
            "timestamp": time.time(),
            "data": [MessageModel.from_pyjs8call_message(spot).dict(exclude_none=True) for spot in spots]
        }
        self.ws_manager.broadcast_sync(event)
    
    def on_outgoing_status(self, msg):
        """Callback for outgoing message status changes."""
        event = {
            "event": "outgoing_status",
            "timestamp": time.time(),
            "data": MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
        }
        self.ws_manager.broadcast_sync(event)
    
    def on_inbox_message(self, msgs):
        """Callback for new inbox messages."""
        event = {
            "event": "inbox_message",
            "timestamp": time.time(),
            "data": msgs  # Already list of dicts
        }
        self.ws_manager.broadcast_sync(event)


def create_app(client, config: Dict[str, Any]) -> FastAPI:
    """Create FastAPI application.
    
    Args:
        client: pyjs8call.client.Client instance
        config: API configuration dictionary
        
    Returns:
        FastAPI: Configured FastAPI application
    """
    # Create rate limiter
    rate_limit = int(config.get('rate_limit_per_minute', 1000))
    rate_limiter = SimpleRateLimiter(rate_limit)
    
    # Create middleware
    auth_middleware = AuthMiddleware(
        app=None,  # Will be set by FastAPI
        api_key=config['api_key'],
        rate_limiter=rate_limiter
    )
    
    # Create FastAPI app with middleware
    app = FastAPI(
        title="PyJS8Call API",
        description="REST API and WebSocket interface for pyjs8call",
        version="0.2.4",
        middleware=[Middleware(AuthMiddleware, api_key=config['api_key'], rate_limiter=rate_limiter)]
    )
    
    # Create WebSocket manager and event bridge
    ws_manager = WebSocketManager()
    event_bridge = EventBridge(ws_manager)
    event_bridge.register_with_client(client)
    
    # Store references for route handlers
    app.state.client = client
    app.state.ws_manager = ws_manager
    
    # Add routes
    add_routes(app)
    
    return app


def add_routes(app: FastAPI):
    """Add all API routes to the FastAPI app."""
    
    @app.get("/")
    async def root():
        return {"message": "PyJS8Call API", "version": "0.2.4"}
    
    # WebSocket endpoint for real-time events
    @app.websocket("/api/events")
    async def websocket_endpoint(websocket: WebSocket):
        client = app.state.client
        ws_manager = app.state.ws_manager
        
        # Check API key for WebSocket connection
        api_key = websocket.headers.get('X-API-Key')
        try:
            expected_key = client.config.get_option('api', 'api_key')
        except:
            expected_key = None
        if api_key != expected_key:
            await websocket.close(code=1008, reason="Invalid API key")
            return
        
        await ws_manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                
                if data.get('action') == 'subscribe':
                    events = data.get('events', [])
                    ws_manager.subscribe(websocket, events)
                    await websocket.send_json({
                        "event": "subscribed",
                        "timestamp": time.time(),
                        "data": {"events": events}
                    })
                    
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)
    
    # Connection status
    @app.get("/api/status/connection")
    async def get_connection_status():
        client = app.state.client
        return StatusResponse(
            success=True,
            data={
                "connected": client.connected(),
                "online": client.online
            }
        )
    
    # Send directed message
    @app.post("/api/messages/send/directed")
    async def send_directed_message(request: SendMessageRequest):
        client = app.state.client
        try:
            msg = client.send_directed_message(request.destination, request.message)
            return StatusResponse(
                success=True,
                message="Message queued for transmission",
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Send heartbeat
    @app.post("/api/messages/send/heartbeat")
    async def send_heartbeat(request: SendHeartbeatRequest):
        client = app.state.client
        try:
            msg = client.send_heartbeat(request.grid)
            return StatusResponse(
                success=True,
                message="Heartbeat queued for transmission",
                data=MessageModel.from_pyjs8call_message(msg).dict(exclude_none=True)
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Get frequency
    @app.get("/api/settings/frequency")
    async def get_frequency():
        client = app.state.client
        try:
            freq = client.settings.get_freq()
            return StatusResponse(
                success=True,
                data={"frequency": freq}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Set frequency
    @app.put("/api/settings/frequency")
    async def set_frequency(request: SetFrequencyRequest):
        client = app.state.client
        try:
            freq = client.settings.set_freq(request.frequency)
            return StatusResponse(
                success=True,
                message="Frequency updated",
                data={"frequency": freq}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Get callsign
    @app.get("/api/settings/callsign")
    async def get_callsign():
        client = app.state.client
        try:
            callsign = client.settings.get_station_callsign()
            return StatusResponse(
                success=True,
                data={"callsign": callsign}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Get grid
    @app.get("/api/settings/grid") 
    async def get_grid():
        client = app.state.client
        try:
            grid = client.settings.get_station_grid()
            return StatusResponse(
                success=True,
                data={"grid": grid}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Get spots
    @app.get("/api/activity/spots/all")
    async def get_all_spots():
        client = app.state.client
        try:
            spots = client.spots.all()
            return StatusResponse(
                success=True,
                data={
                    "spots": [MessageModel.from_pyjs8call_message(spot).dict(exclude_none=True) for spot in spots],
                    "count": len(spots)
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    # Get inbox messages
    @app.get("/api/reception/inbox/messages")
    async def get_inbox_messages():
        client = app.state.client
        try:
            messages = client.get_inbox_messages()
            return StatusResponse(
                success=True,
                data={
                    "messages": messages,
                    "count": len(messages)
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))