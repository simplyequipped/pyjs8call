#!/usr/bin/env python3

"""
Simple test client for pyjs8call API.

This script demonstrates how to interact with the pyjs8call REST API
and WebSocket events.
"""

import json
import time
import requests
import asyncio
import websockets
from concurrent.futures import ThreadPoolExecutor

# Import Message class for deserialization example
try:
    from pyjs8call import Message
    MESSAGE_AVAILABLE = True
except ImportError:
    MESSAGE_AVAILABLE = False


class PyJS8CallAPIClient:
    """Simple client for pyjs8call REST API."""
    
    def __init__(self, base_url="http://localhost:8080", api_key="test-api-key"):
        self.base_url = base_url
        self.headers = {
            'Content-Type': 'application/json',
            'X-API-Key': api_key
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def get_connection_status(self):
        """Get JS8Call connection status."""
        response = self.session.get(f"{self.base_url}/api/js8call/connected")
        response.raise_for_status()
        return response.json()
    
    def get_frequency(self):
        """Get current frequency."""
        response = self.session.get(f"{self.base_url}/api/settings/frequency")
        response.raise_for_status()
        return response.json()
    
    def set_frequency(self, freq):
        """Set frequency."""
        response = self.session.put(
            f"{self.base_url}/api/settings/frequency",
            json={"frequency": freq}
        )
        response.raise_for_status()
        return response.json()
    
    def get_callsign(self):
        """Get station callsign."""
        response = self.session.get(f"{self.base_url}/api/settings/callsign")
        response.raise_for_status()
        return response.json()
    
    def get_grid(self):
        """Get station grid."""
        response = self.session.get(f"{self.base_url}/api/settings/grid")
        response.raise_for_status()
        return response.json()
    
    def send_directed_message(self, destination, message):
        """Send directed message."""
        response = self.session.post(
            f"{self.base_url}/api/message/directed",
            json={
                "destination": destination,
                "message": message
            }
        )
        response.raise_for_status()
        return response.json()
    
    def send_heartbeat(self, grid=None):
        """Send heartbeat."""
        params = {}
        if grid:
            params["grid"] = grid
            
        response = self.session.post(
            f"{self.base_url}/api/message/heartbeat",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def get_spots(self):
        """Get all spots."""
        response = self.session.get(f"{self.base_url}/api/activity/spots/all")
        response.raise_for_status()
        return response.json()
    
    def get_inbox_messages(self):
        """Get inbox messages."""
        response = self.session.get(f"{self.base_url}/api/inbox/messages")
        response.raise_for_status()
        return response.json()


async def websocket_client(base_url="ws://localhost:8080", api_key="test-api-key"):
    """WebSocket client for real-time events."""
    uri = f"{base_url}/api/events"
    
    try:
        # Connect with API key in headers
        async with websockets.connect(
            uri, 
            extra_headers={"X-API-Key": api_key}
        ) as websocket:
            
            print("Connected to WebSocket!")
            
            # Subscribe to events
            subscription = {
                "action": "subscribe",
                "events": ["incoming_message", "new_spots", "outgoing_status", "inbox_message", "window_transition"]
            }
            await websocket.send(json.dumps(subscription))
            
            # Listen for events
            async for message in websocket:
                event = json.loads(message)
                print(f"WebSocket Event: {event['event']}")
                print(f"Timestamp: {event['timestamp']}")
                print(f"Data: {json.dumps(event['data'], indent=2)}")
                print("-" * 50)
                
    except websockets.exceptions.ConnectionClosedError:
        print("WebSocket connection closed")
    except Exception as e:
        print(f"WebSocket error: {e}")


def test_rest_api():
    """Test REST API endpoints."""
    print("Testing PyJS8Call REST API...")
    
    client = PyJS8CallAPIClient()
    
    try:
        # Test connection status
        print("\n1. Testing connection status...")
        status = client.get_connection_status()
        print(f"Connection Status: {json.dumps(status, indent=2)}")
        
        # Test settings
        print("\n2. Testing settings...")
        freq = client.get_frequency()
        print(f"Current Frequency: {json.dumps(freq, indent=2)}")
        
        callsign = client.get_callsign()
        print(f"Station Callsign: {json.dumps(callsign, indent=2)}")
        
        grid = client.get_grid()
        print(f"Station Grid: {json.dumps(grid, indent=2)}")
        
        # Test spots
        print("\n3. Testing spots...")
        spots = client.get_spots()
        print(f"Spots (showing count): {spots['data']['count']} spots")
        
        # Test inbox
        print("\n4. Testing inbox...")
        inbox = client.get_inbox_messages()
        print(f"Inbox (showing count): {inbox['data']['count']} messages")
        
        # Test message sending (commented out to avoid actual transmission)
        print("\n5. Testing message sending (skipped - would transmit)")
        # result = client.send_directed_message("TEST", "API test message")
        # print(f"Send Message Result: {json.dumps(result, indent=2)}")
        
        # result = client.send_heartbeat()
        # print(f"Send Heartbeat Result: {json.dumps(result, indent=2)}")
        
        # Test Message deserialization if available
        if MESSAGE_AVAILABLE:
            print("\n6. Testing Message deserialization...")
            try:
                spots = client.get_spots()
                if spots['data']['spots']:
                    # Take first spot and convert to Message object
                    spot_data = spots['data']['spots'][0]
                    msg = Message.load_from_api(spot_data)
                    
                    print(f"   Converted spot to Message object:")
                    print(f"   - Origin: {msg.origin}")
                    print(f"   - Age: {msg.age():.1f} seconds")
                    print(f"   - Is directed: {msg.is_directed()}")
                    if hasattr(msg, 'grid') and msg.grid:
                        print(f"   - Grid: {msg.grid}")
                else:
                    print("   No spots available for deserialization test")
            except Exception as e:
                print(f"   Message deserialization test failed: {e}")
        
        print("\nREST API tests completed successfully!")
        
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to API server. Is pyjs8call running with API enabled?")
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        if e.response.status_code == 401:
            print("   Check your API key configuration")
    except Exception as e:
        print(f"Error: {e}")


def test_websocket():
    """Test WebSocket events."""
    print("\nTesting PyJS8Call WebSocket Events...")
    print("Connecting to WebSocket... (Press Ctrl+C to stop)")
    
    try:
        asyncio.run(websocket_client())
    except KeyboardInterrupt:
        print("\nWebSocket test stopped by user")
    except Exception as e:
        print(f"WebSocket Error: {e}")


if __name__ == "__main__":
    print("PyJS8Call API Test Client")
    print("=" * 40)
    
    # Test REST API
    test_rest_api()
    
    # Ask user if they want to test WebSocket
    print("\nWebSocket test will run continuously until stopped.")
    response = input("Test WebSocket events? (y/n): ").lower().strip()
    
    if response in ('y', 'yes'):
        test_websocket()
    
    print("\nDone!")