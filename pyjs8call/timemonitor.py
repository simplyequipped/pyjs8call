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


class DriftMonitor:
    ''''''
    def __init__(self, client):
        self._client = client
        self._enabled = False
        self.interval = 60
        self.origin = None
        self.minimum_delta = 0.5
        
        # make sure time group is enabled in config
        self._client.add_group('@TIME')

    def get_drift(self):
        return self._client.config.get('MainWindow', 'TimeDrift', value_type=int())

    def set_drift(self, drift):
        #TODO js8call must be restarted to utilize new drift settings
        self._client.config.get('MainWindow', 'TimeDrift', drift)
        self._client.config.write()
        return self.get_drift()

    def enable(self):
        if self._enabled:
            return
        
        self._enabled = True
        
        thread = threading.Thread(target=self._monitor)
        thread.daemon = True
        thread.start()

    def disable(self):
        self._enabled = False
        
    def search(self):
        '''Repeatedly adjust time drift until signals are found.'''
        pass

    def sync(self):
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
            spots = self._client.get_station_spots(group = self.origin, age = max_age)
        else:
            # sync against last station message
            spots = self._client.get_station_spots(station = self.origin)

        if len(spots) == 0:
            # no activity to get time delta from
            return False

        if self.origin is None or self.origin[0] == '@':
            # calculate median time delta for all or group-specific activity in seconds
            delta = statistics.median([spot.tdrift for spot in spots if spot.get('tdrift')])
        else:
            # last heard station message time delta in seconds
            delta = spots[-1].tdrift

        if delta >= self.minimum_delta:
            # js8call time drift in milliseconds
            delta = int(delta * 1000) * -1
            self.set_drift(delta)
            # restart to utilize new time drift setting
            self._client.restart()
            return True
        else:
            return False

    #TODO monitor outgoing activity to delay app restart
    def _monitor(self):
        '''Auto time delta sync thread.'''
        while self._enabled:
            # allow interval change while waiting
            while (self._last_sync_timestamp + (self.interval * 60)) < time.time():
                time.sleep(1)

                # allow disable while waiting
                if not self._enabled:
                    return

            self.sync()
            self._last_sync_timestamp = time.time()
            
class TimeMaster:
    ''''''
    #TODO docs, when changing destination make sure group is added to configured groups, restart
    self.__init__(self, client):
        self._client = client
        self._enabled = False
        self._last_message_timestamp = 0
        self.interval = 60 # minutes
        self.message_destination = '@TIME'
        #TODO can this be empty? test
        self.message_text = ''

    def enable(self):
        if self._enabled:
            return

        self._enabled = True

        thread = threading.Thread(target=self._monitor)
        thread.daemon = True
        thread.start()

    def disable(self):
        self._enabled = False

    def _monitor(self):
        '''Time master monitor thread.'''
        while self._enabled:
            # allow interval change while waiting
            while (self._last_message_timestamp + (self.interval * 60)) < time.time():
                time.sleep(1)

                # allow disable while waiting
                if not self._enabled:
                    return

            self._client.send_directed_message(self.message_destination, self.message_text)
            self._last_message_timestamp = time.time()

















