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


import time
import threading
import statistics

#TODO document adding @TIME to groups before starting pyjs8call

class TimeMonitor:

    def __init__(self, client):
        self._client = client
        self._time_station = False
        self._auto_sync = False
        self._time_station_interval = 3600 # 1 hour
        self._auto_sync_interval = 3600 # 1 hour

    def get_drift(self):
        return self._client.config.get('MainWindow', 'TimeDrift', value_type=int())

    def set_drift(self, drift):
        #TODO js8call must be restarted to utilize new drift settings
        self._client.config.get('MainWindow', 'TimeDrift', drift)
        self._client.config.write()
        return self.get_drift()

    def enable_auto_sync(self, station=None, min_delta=0.5):
        self._auto_sync = True
        
        thread = threading.Thread(target=self._auto_sync_monitor, args=(station, min_delta))
        thread.daemon = True
        thread.start()

    def disable_auto_sync(self):
        self._auto_sync = False

    def set_auto_sync_interval(self, interval):
        self._auto_sync_interval = interval

    def enable_time_station(self, station='@TIME'):
        '''Enable time station.

        *station* is intended to be a group designator, but can technically be a station callsign if needed.

        Args:
            station (str): Group designator for outgoing messages
        '''
        self._time_station = True
        
        thread = threading.Thread(target=self._time_station_monitor, args=(station,))
        thread.daemon = True
        thread.start()
        
    def disable_time_station(self):
        self._time_station = False

    def set_time_station_interval(self, interval):
        self._time_station_interval = interval
        
    def search(self):
        '''Repeatedly adjust time drift until signals are found.'''
        pass

    def sync(self, station=None, min_delta=0.5):
        '''Synchronize time drift.

        Note that since the JS8Call time delta cannot be set via API the application will be restarted in order to apply the time delta setting from the config file.

        Note that only JS8Call transmit/receive window timing relative to other heard stations is synchronized. Clock time is not effected.

        There are 3 sources of time drift information:
        - a specific station callsign
        - a specific group designator (ex. @TIME)
        - all recently heard stations

        When no arguments are specified the median time drift of all stations heard in the last 90 transmit cycles (15 minutes with the default *fast* JS8Call modem speed) is used. This source is used to decode as many stations as possible.

        When *station* is a group designator (begins with '@') the median time drift of all stations associated with the specified group that were heard in the last 90 transmit cycles (15 minutes with the default *fast* JS8Call modem speed) is used. This source is used to decode as many stations as possible in a specific group, or to utilize 'master' time sources that can change over time (i.e. stations with internet or GPS time sync capability).

        When *station* is a station callsign the time drift is set to the time delta of the last heard message from that station.

        Args:
            station (str): Station callsign or group designator to sync to, defaults to None
            min_delta (float): Minimum time delta in seconds required before performing a sync, defaults to 0.5

        Returns:
            bool: True if sync occured, False otherwise
            
        A sync will not occur (return False) when:
        - there are no spots for the specified time source
        - the calculated time delta is less than the minimum delta
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
            # no activity to get time delta from
            return False

        if station is None or station[0] == '@':
            # calculate median time delta for all or group specific activity in seconds
            delta = statistics.median([spot.tdrift for spot in spots if spot.get('tdrift')])
        else:
            # last heard station message time delta in seconds
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

    #TODO monitor outgoing activity to delay app restart
    def _auto_sync_monitor(self, station, time_delta):
        '''Auto time delta sync thread.'''
        while self._auto_sync:
            self.sync(station = station, min_delta = min_delta)
            time.sleep(self._auto_sync_interval)

    def _time_station_monitor(self, station):
        '''Time station thread.'''
        while self._time_station:
            self._client.send_directed_message(station, 'SYNC')
            time.sleep(self._time_station_interval)





















