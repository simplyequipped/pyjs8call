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

'''FastAPI REST API layer for pyjs8call.

Provides HTTP REST API and WebSocket interfaces for remote access to pyjs8call functionality. API server starts automatically if enabled in configuration.
'''

__docformat__ = 'google'

import configparser
import threading
import time


def _start_api_server(client, port=8080, bind_address='0.0.0.0', rate_limit=1000):
    '''Start API server.
    
    Args:
        client (pyjs8call.client.Client): pyjs8call client instance
        port (int): server port number, defaults to 8080
        bind_address (str): server bind address, defaults to '0.0.0.0'
        rate_limit (int): requests per minute per IP address before limiting, defaults to 1000
        
    Raises:
        ImportError: FastAPI and/or uvicorn packages not installed
    '''
    try:
        # attempt to load api settings from settings.ini file
        if client.settings.loaded_settings:
            api_settings = client.settings.loaded_settings.get('api')
            if api_settings:
                for key, value in api_settings.items():
                    if 'port' in key.lower(): port = client.settings.parse_loaded_value(value)
                    elif 'address' in key.lower(): bind_address = client.settings.parse_loaded_value(value)
                    elif 'limit' in key.lower(): rate_limit = client.settings.parse_loaded_value(value)
    except (configparser.NoSectionError, AttributeError, TypeError):
        pass
    
    # lazy load api dependencies
    try:
        import fastapi
        import uvicorn
    except ImportError as e:
        raise ImportError(f'API dependencies not available: {e}. Install with: pip install fastapi uvicorn')
    
    from .server import create_app
    app = create_app(client, rate_limit)
    
    # start server (blocking)
    uvicorn.run(
        app, 
        host=bind_address, 
        port=port
    )

def start_api_server(client, port=8080, bind_address='0.0.0.0', rate_limit=1000):
    '''Start API server via thread.
    
    Args:
        client (pyjs8call.client.Client): pyjs8call client instance
        port (int): server port number, defaults to 8080
        bind_address (str): server bind address, defaults to '0.0.0.0'
        rate_limit (int): requests per minute per IP address before limiting, defaults to 1000
        
    Raises:
        ImportError: FastAPI and/or uvicorn packages not installed
    '''
    api_thread = threading.Thread(
        target=_start_api_server,
        args=(client, port, bind_address, rate_limit),
        daemon=True,
        name='pyjs8call-api'
    )
    api_thread.start()

