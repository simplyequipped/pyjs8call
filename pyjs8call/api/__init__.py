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

Provides HTTP REST API and WebSocket interfaces for remote access to pyjs8call functionality.
API server starts automatically if enabled in configuration.
'''

__docformat__ = 'google'

import threading
import time


def start_api_server(client):
    '''Start API server if dependencies available and API enabled in config.
    
    Args:
        client (pyjs8call.client.Client): pyjs8call client instance
        
    Raises:
        ImportError: If FastAPI/uvicorn dependencies not available
        ValueError: If API key not configured
    '''
    # get API configuration first
    api_config = {}
    try:
        api_section = client.config.get_section('api')
        if api_section:
            api_config = dict(api_section)
    except:
        return  # no API config section
    
    # check if API is enabled
    enabled = api_config.get('enabled', 'false').lower()
    if enabled not in ('true', '1', 'yes', 'on'):
        return
        
    # validate API key
    api_key = api_config.get('api_key', '').strip()
    if not api_key:
        raise ValueError('API key must be set in [api] section of config file')
    
    # only import dependencies when actually starting API
    try:
        import fastapi
        import uvicorn
    except ImportError as e:
        raise ImportError(f'API dependencies not available: {e}. Install with: pip install fastapi uvicorn')
    
    from .server import create_app
    
    # create FastAPI app
    app = create_app(client, api_config)
    
    # get server configuration
    bind_address = api_config.get('bind_address', '0.0.0.0')
    port = int(api_config.get('port', 8080))
    
    print(f'Starting pyjs8call API server on {bind_address}:{port}')
    
    # start server (this blocks)
    uvicorn.run(
        app, 
        host=bind_address, 
        port=port,
        log_level='info'
    )


def start_api_server_background(client):
    '''Start API server in background thread.
    
    Args:
        client (pyjs8call.client.Client): pyjs8call client instance
    '''
    try:
        api_thread = threading.Thread(
            target=start_api_server,
            args=(client,),
            daemon=True,
            name='pyjs8call-api'
        )
        api_thread.start()
        
        # give server time to start
        time.sleep(0.5)
        
    except ImportError:
        print('Warning: API enabled but FastAPI/Uvicorn not installed')
    except Exception as e:
        print(f'Warning: Failed to start API server: {e}')

