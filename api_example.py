#!/usr/bin/env python3

"""
Example of running pyjs8call with API enabled.

This demonstrates how to enable the REST API server alongside 
the normal pyjs8call functionality.
"""

import sys
import time
import pyjs8call


def main():
    print("PyJS8Call API Example")
    print("=" * 40)
    
    # Create client
    js8call = pyjs8call.Client()
    
    # Set up some callbacks for demonstration
    def on_incoming_message(msg):
        print(f"📥 Incoming message from {msg.origin}: {msg.text}")
    
    def on_new_spots(spots):
        for spot in spots:
            print(f"📡 New spot: {spot.origin} on {spot.freq} Hz (SNR: {spot.snr})")
    
    # Register callbacks
    js8call.callback.register_incoming(on_incoming_message)
    js8call.callback.register_spots(on_new_spots)
    
    # Check if we should run headless
    headless = '--headless' in sys.argv
    
    print(f"Starting pyjs8call (headless={headless})...")
    print("API server will start automatically if enabled in config.")
    print("")
    print("To enable API, add this to your pyjs8call.ini:")
    print("[api]")
    print("enabled=true")
    print("api_key=your-secret-key-here")
    print("port=8080")
    print("")
    
    try:
        # Start JS8Call and API server
        js8call.start(headless=headless)
        
        # Get current status
        freq = js8call.settings.get_freq() / 1000000
        callsign = js8call.settings.get_station_callsign()
        grid = js8call.settings.get_station_grid()
        connected = js8call.connected()
        
        print(f"Station: {callsign} ({grid})")
        print(f"Frequency: {freq:.3f} MHz")
        print(f"Connected: {'Yes' if connected else 'No'}")
        print("")
        
        if connected:
            print("✅ PyJS8Call is running!")
            print("If API is enabled, you can now:")
            print("- Visit http://localhost:8080/docs for API documentation")
            print("- Test with: python test_api_client.py")
            print("- Connect WebSocket to: ws://localhost:8080/api/events")
        else:
            print("⚠️  Not connected to JS8Call application")
        
        print("")
        print("Press Ctrl+C to stop...")
        
        # Keep running
        while js8call.online:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping...")
        js8call.stop()
    except Exception as e:
        print(f"Error: {e}")
        js8call.stop()


if __name__ == "__main__":
    main()