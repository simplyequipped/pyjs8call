# MIT License
# 
# Copyright (c) 2022-2023 Simply Equipped
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
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

__docformat__ = 'google'


import threading
import time


class SpotMonitor:
    def __init__(self, client):
        self._client = client
        self._new_spots = []
        self._last_spot_update_timestamp = 0
        self._new_spot_callback = None
        self.spot_update_delay = 3 # seconds

        self._station_watch_list = []
        self._watch_callback = None

        monitor_thread = threading.Thread(target=self._monitor)
        monitor_thread.setDaemon(True)
        monitor_thread.start()

    def set_new_spot_callback(self, callback):
        self._new_spot_callback = callback

    def set_watch_callback(self, callback):
        self._watch_callback = callback

    def add_station_watch(self, station):
        if station not in self._station_watch_list:
            self._station_watch_list.append(station)

    def remove_station_watch(self, station):
        if station in self._station_watch_list:
            self._station_watch_list.remove(station)

    def _monitor(self):
        while self._client.online:
            now = time.time()
            time_since_last_update = now - self._last_spot_update_timestamp
            self._new_spots = self._client.get_station_spots(max_age = time_since_last_update)
            self._last_spot_update_timestamp = now
            if len(self._new_spots) > 0:
                if self._new_spot_callback != None:
                    self._new_spot_callback(self._new_spots)

                if self._watch_callback != None:
                    for spot in self._new_spots:
                        if spot.origin in self._station_watch_list:
                            self._watch_callback(spot)

            time.sleep(self.spot_update_delay)
                    

