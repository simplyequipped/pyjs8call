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
    '''Time drift monitor.

    There are 3 sources of relative time delta information:
    - group messages (ex. @TIME)
    - single station
    - all recently heard stations

    When *source* is set to None the median time drift of all stations heard in the last 90 transmit cycles (15 minutes with the default *fast* JS8Call modem speed) is used. Use this option to decode as many stations as possible.

    When *station* is a group designator (begins with '@') the median time drift of all stations associated with the specified group that were heard in the last 90 transmit cycles (15 minutes with the default *fast* JS8Call modem speed) is used. Use this option to decode as many stations as possible in a specific group, or to utilize master time sources (see pyjs8call.timemonitor.TimeMaster).

    When *station* is a station callsign the time drift is set to the time delta of the last heard message from that station.
    
    Attributes:
        interval (int): Number of minutes between sync events, defaults to 60
        source (str): Time sync source, defaults to '@TIME'
        minimum_delta (float): Minimum time delta in seconds required before performing a sync, defaults to 0.5
    '''
    def __init__(self, client):
        self._client = client
        self._enabled = False
        self.interval = 60
        self.source = '@TIME'
        self.minimum_delta = 0.5
        
        # ensure time group is enabled in config
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

        Note that the JS8Call API does not support changing the time drift. The application will be restarted to apply the new time delta via the configuration file.

        Note that only JS8Call transmit/receive window timing relative to other heard stations is synchronized. Clock time is not effected.

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

        if self._is_group(self.source):
            # sync against recent group activity
            spots = self._client.get_station_spots(group = self.source, age = max_age)
        elif self.source is not None:
            # sync against last station message
            spots = self._client.get_station_spots(station = self.source)
        else:
            # sync against all recent activity
            spots = self._client.get_station_spots(age = max_age)

        if len(spots) == 0:
            # no activity to get time delta from
            return False

        if self._is_group(self.source) or self.source is None:
            # calculate median time delta for recent activity in seconds
            delta = statistics.median([spot.tdrift for spot in spots if spot.get('tdrift')] is not None)
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

    def _is_group(self, designator):
        return bool(designator[0] == '@')

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
    '''Time master monitor.
    
    i.e. stations with internet or GPS time sync capability, 
    
    The time master object sends messages on a set interval that other stations can identify and synchronize against (see pyjs8call.timemonitor.DriftMonitor). By default outgoing messages target the custom @TIME group, but can be set to any group designation.
    
    In order for other stations to synchronize with the master station they will need to configure *client.drift_monitor.source* to the same group designator as the time masters destination. This is the default configuration.
    
    Note that *destination* can technically be set to a specific callsign. However, this will prevent other stations from synchronizing with the master station.
    
    Attributes:
        interval (int): Number of minutes between outgoing messages, defaults to 60
        destination (str): Outgoing message destination, defaults to @TIME
        text (str): Text to include with each outgoing message, defaults to '' (empty string)
    '''
    #TODO docs, when changing destination make sure group is added to configured groups, restart
    self.__init__(self, client):
        '''Initialize time master object.
        
        Args:
            client (pyjs8call.client): Parent client object
            
        Returns:
            pyjs8call.timemonitor.TimeMaster: Constructed time master object
        '''
        self._client = client
        self._enabled = False
        self._last_message_timestamp = 0
        self.interval = 60 # minutes
        self.destination = '@TIME'
        #TODO can this be empty? test
        self.text = ''

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
                
            self._client.send_directed_message(self.destination, self.text)
            self._last_message_timestamp = time.time()














