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

'''Monitor recent station spots.'''

__docformat__ = 'google'


import threading
import time


class SpotMonitor:
    '''Monitor recent station spots.'''

    def __init__(self, client):
        '''Initialize spot monitor.

        Args:
            client (pyjs8call.client): Parent client object

        Returns:
            pyjs8call.spotmonitor: Constructed spot monitor object
        '''
        self._client = client
        self._last_spot_update_timestamp = 0
        self._station_watch_list = []

        monitor_thread = threading.Thread(target=self._monitor)
        monitor_thread.setDaemon(True)
        monitor_thread.start()

    def _spots_callback(self, spots):
        '''New spots callback function handling.

        Calls the *pyjs8call.client.callback.spots* and *pyjs8call.client.callback.station_spot* callback functions.

        Args:
            spots (list): List of new spots
        '''
        if self._client.callback.spots != None:
            self._client.callback.spots(spots)

        if self._client.callback.station_spot != None:
            for spot in spots:
                if spot.origin in self._station_watch_list:
                    self._client.callback.station_spot(spot)

    def add_station_watch(self, station):
        '''Add watched station.

        Args:
            station (str): Callsign of station to watch for
        '''
        if station not in self._station_watch_list:
            self._station_watch_list.append(station)

    def remove_station_watch(self, station):
        '''Remove watched station.

        Args:
            station (str): Callsign of station to stop watching for
        '''
        if station in self._station_watch_list:
            self._station_watch_list.remove(station)

    def get_watched_stations(self):
        '''Get watched stations.

        Returns:
            list: List of watched station callsigns
        '''
        return self._station_watch_list

    def _monitor(self):
        '''Spot monitor thread.

        Uses pyjs8call.client.Client.get_station_spots internally.
        '''
        while self._client.online:
            next_tx_window = self._client.window_monitor.next_window_start()

            if next_tx_window == 0:
                # use tx window duration if tx window timestamp is not available yet
                time.sleep(self._client.get_tx_window_duration() / 3)
            else:
                # sleep until next tx window
                time.sleep(next_tx_window - time.time())

            # update timestamps
            now = time.time()
            time_since_last_update = now - self._last_spot_update_timestamp
            # get new spots since last update
            new_spots = self._client.get_station_spots(max_age = time_since_last_update)
            self._last_spot_update_timestamp = now

            if len(new_spots) > 0:
                self._spots_callback(new_spots)

