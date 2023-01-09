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


import statistics

#TODO document adding @TIME to groups before starting pyjs8call

class TimeMonitor:

    def __init__(self, client):
        self._client = client
        self._time_station = False
        self._time_station_interval = 3600 # 1 hour

    def get_drift(self):
        return self._client.config.get('MainWindow', 'TimeDrift', value_type=int())

    def set_drift(self, drift):
        #TODO js8call must be restarted to utilize new drift settings
        self._client.config.get('MainWindow', 'TimeDrift', drift)
        self._client.config.write()
        return self.get_drift()

    def enable_auto_sync(self, station=None):
        pass

    def disable_auto_sync(self):
        pass

    def enable_time_station(self):
        self._time_station = True

    def disable_time_station(self):
        self._time_station = False

    def set_time_station_interval(self, interval):
        self._time_station_interval = interval

    def search(self):
        '''Repeatedly adjust time drift until signals are found.'''
        pass

    def activity_sync(self):
        '''Use time deltas from recent activity to set time drift.'''
        max_age = self._client.get_tx_window_duration() * 30
        spots = self._client.get_station_spots(age = max_age)

        if len(spots) == 0:
            return False

        # message time delta in seconds
        delta = statistics.median([spot.tdelta for spot in spots])
        # js8call time delta in milliseconds
        delta = int(delta * 1000)

    def sync(self, station=None, min_delta=1.0):
        '''Sync time drift to a specified source.

        Note that since the JS8Call time delta cannot be set via API the application will be restarted in order to apply the time delta setting from the config file.

        Note that only JS8Call transmit/receive window timing relative to other heard stations is syncronized. Clock time is not effected.

        There are 3 sources of time drift information:
        - a specific station callsign
        - a specific group designator (ex. @TIME)
        - all recently heard stations

        Calling *sync* with no arguments will set the JS8Call time drift to the median time drift of all stations heard in the last 90 transmit cycles (15 minutes with the default *fast* JS8Call modem speed).

        When a station callsign or group designator is specified the time drift is set per the time delta of the last heard message from that callsign or group.

        Args:
            station (str): Station callsign or group designator to sync to, defaults to None
            min_delta (float): Minimum time delta before performing a sync, defaults to 1.0

        Returns:
            bool: True if sync occured, False otherwise 
        '''
        max_age = self._client.get_tx_window_duration() * 90

        if station is None:
            # sync against all recent activity
            spots = self._client.get_station_spots(age = max_age)
        elif station[0] == '@':
            # sync against recent group activity
            spots = self._client.get_station_spots(group = station, age = max_age)
        else:
            # sync against last station message
            spots = self._client.get_station_spots(station = station)

        if len(spots) == 0:
            return False

        if station is None or station[0] == '@':
            delta = statistics.median([spot.tdrift for spot in spots if spot.get('tdrift')])
        else:
            # last heard station or group time delta in seconds
            delta = spots[-1].tdrift

        if delta >= min_delta:
            # js8call time drift in milliseconds
            delta = int(delta * 1000) * -1
            self.set_drift(delta)
            # restart to utilize new time drift setting
            self._client.restart()
            return True
        else:
            return False
























