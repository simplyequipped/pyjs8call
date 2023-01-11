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

    There are 3 sources of time drift information:
    - recently heard stations in a group (ex. @TIME)
    - a single station
    - all recently heard stations

    Attributes:
        interval (int): Number of minutes between syncronizations, defaults to 60
        source (str): Time drift sync source, defaults to '@TIME'
        minimum_drift (float): Minimum time drift in seconds required before performing a sync, defaults to 0.5
    '''
    def __init__(self, client):
        '''Initialize drift monitor object.

        Adds the group @TIME to JS8Call groups via the configuration file.

        Args:
            client (pyjs8call.cient): Parent client object

        Returns:
            pyjs8call.timemonitor.DriftMonitor: Constructed drift monitor object
        '''
        self._client = client
        self._enabled = False
        self._search_spots = []
        self.interval = 60
        self.source = '@TIME'
        self.minimum_drift = 0.5
        
        # ensure time group is enabled in config
        self._client.add_group('@TIME')

    def get_drift(self):
        '''Get current time drift.

        Returns:
            int: Current time drift per the JS8Call configuration file
        '''
        return self._client.config.get('MainWindow', 'TimeDrift', value_type=int())

    def set_drift(self, drift):
        '''Set time drift.

        Note that this function only sets the time drift in the JS8Call configuration file. To utilize the new setting the application must be restarted using `client.restart()`.

        Note that a stations time drift reported from a *pyjs8call.message* object is in seconds. See *set_drift_from_tdrift()*.

        If a stations time drift is positive then the corresponding JS8Call time drift will be negative, and vice vera.

        Args:
            drift (float): New time drift in milliseconds

        Returns:
            int: Current time drift per the JS8Call configuration file
        '''
        self._client.config.get('MainWindow', 'TimeDrift', int(drift))
        self._client.config.write()
        return self.get_drift()

    def set_drift_from_tdrift(self, tdrift):
        '''Set time drift from *Message.tdrift* parameter.

        Note that this function only sets the time drift in the JS8Call configuration file. To utilize the new setting the appliation must be restarted using `client.restart()`.

        Args:
            tdrift (float): Station time drift from *Message.tdrift*
        '''
        # convert station time drift in seconds to JS8Call time drift in milliseconds
        drift = int(float(tdrift) * 1000) * -1
        self.set_drift(drift)

    def enable(self):
        if self._enabled:
            return
        
        self._enabled = True
        
        thread = threading.Thread(target=self._monitor)
        thread.daemon = True
        thread.start()

    def disable(self):
        self._enabled = False
        
    #TODO confirm that max time drift is plus or minus 2 seconds, not just plus
    def search(self, timeout=7):
        '''Search for correct time drift to decode stations.

        Automatically find the correct time drift when accurate time sources are unavailable and the time difference between other stations is too large for JS8Call to decode messages. JS8Call can decode messages with a maximum time drift of +/- 2 seconds

        The time drift is incremented by 0.5 every 6 transmit cycles (1 minute with the default *fast* JS8Call modem speed) until stations are heard or the search times out. Once the time drift reaches 2 seconds it loops around to -2 and continues incrementing. With a maximum functional time drift of 2 seconds, and a rate of 0.5 seconds per minutes (minus the initial time drift state), a worst case search will take a little over 6 minutes. Once stations are heard, a sync against all recently heard stations is performed.

        Checks for stations heard in the last 90 transmit cycles (15 minutes with the default *fast* JS8Call modem speed) before searching. If found, a sync against all recently heard stations is performed.

        Args:
            timeout (int): Search timeout in minutes, defaults to 7
        '''
        thread = threading.Thread(target=self._search, args=(timeout,))
        thread.daemon = True
        thread.start()

    def _search(self, timeout):
        '''Time drift search thread.'''
        timeout = time.time() + (timeout * 60)
        window_duration = self._client.get_tx_window_duration()
        # 1 minute with fast modem speed
        search_interval = window_duration * 6
        initial_drift = self.get_drift()
        initial_spots = self._client.spots()
        recent_age = window_duration * 90

        # avoid searching if there are recent spots
        if len(initial_spots) > 0 and initial_spots[-1].age() <= recent_age:
            source = self.source
            self.source = None
            self.sync()
            self.source = source
            return

        # round to nearest 0.5
        drift = round(initial_drift * 2) / 2

        if drift < -2:
            drift = -2

        while True:
            drift += 0.5

            if drift > 2:
                drift = -2

            self.set_drift(drift * 1000)
            self._client.restart()
            time.sleep(1)
            last_drift_change = time.time()

            while last_drift_change + search_interval < time.time():
                time.sleep(1)

                # new spots, sync and end search
                if len(self._client.spots()) > len(initial_spots):
                    source = self.source
                    self.source = None
                    self.sync()
                    self.source = source
                    return

                # search timed out
                if time.time() > timeout:
                    return

    def sync(self, source=self.source):
        '''Synchronize time drift.

        Note that the JS8Call API does not support changing the time drift. The application will be restarted to apply the new time drift via the configuration file.

        Note that only JS8Call transmit/receive window timing relative to other stations is synchronized. Clock time is not effected.

        When *source* is a group designator (begins with '@') the median time drift of all stations associated with the specified group that were heard in the last 90 transmit cycles (15 minutes with the default *fast* JS8Call modem speed) is used. Use this option to decode as many stations as possible in a specific group, or to utilize master time sources (see pyjs8call.timemonitor.TimeMaster).

        When *source* is a station callsign the time drift is set per the last message from that station.
    
        When *source* is *None* the median time drift of all stations heard in the last 90 transmit cycles (15 minutes with the default *fast* JS8Call modem speed) is used. Use this option to decode as many stations as possible.

        Args:
            source (str): Time drift sync source, defaults to DriftMonitor.source

        Returns:
            bool: True if sync occured, False otherwise
            
            A sync will not occur if:
            - there are no spots for the specified time source
            - the calculated time drift is less than the minimum drift
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
            # no activity to get time drift from
            return False

        if self._is_group(self.source) or self.source is None:
            # calculate median time drift for recent activity in seconds
            drift = statistics.median([spot.tdrift for spot in spots if spot.get('tdrift')] is not None)
        else:
            # last heard station message time drift in seconds
            drift = spots[-1].tdrift

        if drift >= self.minimum_drift:
            self.set_drift_from_tdrift(drift)
            # restart to utilize new time drift setting
            self._client.restart()
            return True
        else:
            return False

    def _is_group(self, designator):
        return bool(designator[0] == '@')

    #TODO monitor outgoing activity to delay app restart
    def _monitor(self):
        '''Auto time drift sync thread.'''
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
    
    In order for other stations to synchronize with the time master station they will need to configure *client.drift_monitor.source* to the same group designator as the time masters destination. This is the default configuration.
    
    Note that *destination* can technically be set to a specific callsign. However, this may prevent other stations from synchronizing with the master station.
    
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














