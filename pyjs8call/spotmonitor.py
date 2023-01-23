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

'''Monitor recent station spots.

Set `client.callback.spots` to receive all new activity.

Set `client.callback.station_spot` to receive new activity for a specific station.

Set `client.callback.group_spot` to receive new activity for a specific group.

See pyjs8call.client.Callbacks for callback function details.

'''

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
        self._enabled = False
        self._station_watch_list = []
        self._group_watch_list = []

        self.enable()

    def enable(self):
        '''Enable spot monitoring.'''
        if self._enabled:
            return

        self._enabled = True

        thread = threading.Thread(target=self._monitor)
        thread.daemon = True
        thread.start()

    def disable(self):
        '''Disable spot monitoring.'''
        self._enabled = False

    def _callback(self, spots):
        '''New spots callback function handling.

        Calls the *pyjs8call.client.callback.spots*, *pyjs8call.client.callback.station_spot*, and *pyjs8call.client.callback.group_spot* callback functions using *threading.Thread*.

        Args:
            spots (list): Spotted message objects
        '''
        if self._client.callback.spots is not None:
            thread = threading.Thread(target=self._client.callback.spots, args=(spots,))
            thread.daemon = True
            thread.start()

            for spot in spots:
                if (
                    self._client.callback.station_spot is not None and
                    spot.origin in self._station_watch_list
                ):
                    thread = threading.Thread(target=self._client.callback.station_spot, args=(spot,))
                    thread.daemon = True
                    thread.start()

                if (
                    self._client.callback.group_spot is not None and
                    spot.destination in self._group_watch_list
                ):
                    thread = threading.Thread(target=self._client.callback.group_spot, args=(spot,))
                    thread.daemon = True
                    thread.start()

    def add_station_watch(self, station):
        '''Add watched station.

        Args:
            station (str): Station callsign to watch for
        '''
        if station not in self._station_watch_list:
            self._station_watch_list.append(station)

    def add_group_watch(self, group):
        '''Add watched group.

        Args:
            group (str): Group designator to watch for
        '''
        if group[0] != '@':
            raise ValueError('Group designator must begin with \'@\'')

        if group not in self._group_watch_list:
            self._group_watch_list.append(group)

    def remove_station_watch(self, station):
        '''Remove watched station.

        Args:
            station (str): Station callsign to stop watching for
        '''
        if station in self._station_watch_list:
            self._station_watch_list.remove(station)

    def remove_group_watch(self, group):
        '''Remove watched group.

        Args:
            group (str): Group designator to stop watching for
        '''
        if group[0] != '@':
            raise ValueError('Group designator must begin with \'@\'')

        if group in self._group_watch_list:
            self._group_watch_list.remove(group)

    def get_watched_stations(self):
        '''Get watched stations.

        Returns:
            list: Watched station callsigns
        '''
        return self._station_watch_list

    def get_watched_groups(self):
        '''Get watched groups.

        Returns:
            list: Watched group designators
        '''
        return self._group_watch_list

    def _monitor(self):
        '''Spot monitor thread.

        Uses *pyjs8call.client.get_station_spots* internally.
        '''
        last_spot_update_timestamp = 0

        while self._enabled:
            default_delay = self._client.get_tx_window_duration() / 3
            delay = self._client.window_monitor.next_transition_seconds(count = 1, fallback = default_delay)
            time.sleep(delay)

            # get new spots since last update
            time_since_last_update = time.time() - last_spot_update_timestamp
            new_spots = self._client.get_station_spots(age = time_since_last_update)
            last_spot_update_timestamp = time.time()

            if len(new_spots) > 0:
                self._callback(new_spots)

