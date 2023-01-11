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

    Note that the JS8Call API does not support changing the time drift. The application will be restarted to apply new time drift settings via the configuration file.

    Note that only JS8Call transmit/receive window timing relative to other stations is effected. Clock time is not effected.
        
    There are 3 sources of time drift information:
    - recently heard stations in a group (ex. @TIME)
    - a single station
    - all recently heard stations

    Attributes:
        interval (int): Number of minutes between sync attempts, defaults to 60
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
        return self.set_drift(drift)
    
    def search(self, timeout=10):
        '''Search for correct time drift to decode activity.

        Automatically find the correct time drift when accurate time sources are unavailable and the time difference between other stations is too large for JS8Call to decode messages. JS8Call can decode messages with a maximum time delta of 2 seconds.

        Time drift is incremented by 1 second every 6 transmit cycles (1 minute with the default *fast* JS8Call modem speed) until stations are heard, all time drift intervals have been searched, or the search times out. With a transmit/receive window duration of 10 seconds a worst case search will take approximately 8 minutes. Once stations are heard, a sync against all recently heard stations is performed.

        Checks for stations heard in the last 90 transmit cycles (15 minutes with the default *fast* JS8Call modem speed) before searching. If found, a sync against all recently heard stations is performed.
        
        This function returns immediately because searching utilizes *threading.Thread*.

        Args:
            timeout (int): Search timeout in minutes, defaults to 10
        '''
        thread = threading.Thread(target=self._search, args=(timeout,))
        thread.daemon = True
        thread.start()

    def _search(self, timeout):
        '''Time drift search thread.'''
        timeout = time.time() + (timeout * 60)
        window_duration = self._client.get_tx_window_duration()
        initial_spots = self._client.spots()

        # avoid searching if there are recent spots
        if len(initial_spots) and initial_spots[-1].age() <= (window_duration * 90):
            self.sync_to_all()
            return

        for drift in range(1, window_duration - 1):
            # convert from seconds to milliseconds
            self.set_drift(drift * 1000)
            self._client.restart()
            time.sleep(1)
            last_drift_change = time.time()

            # wait for spots before incrementing time drift
            while last_drift_change + (window_duration * 6) < time.time():
                # new spots, sync and end search
                if len(self._client.spots()) > len(initial_spots):
                    self.sync_to_all()
                    return

                # search timed out
                if time.time() > timeout:
                    return

                time.sleep(1)

    def sync_to_activity(self, threshold=0.5):
        '''Synchronize time drift to recent activity.
        
        Syncing to recent activity will decode as many stations as possible. Syncs to the median time drift of stations heard in the last 90 transmit cycles (15 minutes with the default *fast* JS8Call modem speed).
        
        Args:
            threshold (float): Median time drift in seconds to exceed before syncing, defaults to 0.5
            
        Returns:
            bool: True if sync occured, False otherwise
        '''
        max_age = self._client.get_tx_window_duration() * 90
        # sync against all recent activity
        spots = self._client.get_station_spots(age = max_age)

        if len(spots) == 0:
            # no activity to get time drift from
            return False

       drift = statistics.median([spot.tdrift for spot in spots if spot.get('tdrift')] is not None)

        if drift >= threshold:
            self.set_drift_from_tdrift(drift)
            # restart to utilize new time drift setting
            self._client.restart()
            return True
        else:
            return False

    def sync_to_group(self, group, threshold=0.5):
        '''Synchronize time drift to recent group activity.
        
        Syncing to a group will decode as many stations as possible in a specific group, or utilize master stations (see *sync()* and pyjs8call.timemonitor.TimeMaster). Syncs to the median time drift of stations heard in the last 90 transmit cycles (15 minutes with the default *fast* JS8Call modem speed).
        
        Args:
            group (str): Group designator to sync time drift to
            threshold (float): Median time drift in seconds to exceed before syncing, defaults to 0.5
            
        Returns:
            bool: True if sync occured, False otherwise
        '''
        if not group[0] == '@':
            raise ValueError('Group designators must begin with \'@\'')
            
        # sync against recent group activity
        max_age = self._client.get_tx_window_duration() * 90
        spots = self._client.get_station_spots(group = group, age = max_age)

        if len(spots) == 0:
            # no activity to get time drift from
            return False

        drift = statistics.median([spot.tdrift for spot in spots if spot.get('tdrift')] is not None)

        if drift >= threshold:
            self.set_drift_from_tdrift(drift)
            # restart to utilize new time drift setting
            self._client.restart()
            return True
        else:
            return False

    def sync_to_station(self, station, threshold=0.5):
        '''Synchronize time drift to single station.
        
        Syncing to a station callsign will ensure time drift alignment with that station only. Time drift is based on the most recent message from the specified station.
        
        Args:
            station (str): Station callsign to sync time drift to
            threshold (float): Time drift in seconds to exceed before syncing, defaults to 0.5
            
        Returns:
            bool: True if sync occured, False otherwise
        '''
        # sync against last station message
        spots = self._client.get_station_spots(station = station)

        if len(spots) == 0:
            # no activity to get time drift from
            return False
        
        # last heard station message time drift in seconds
        drift = spots[-1].tdrift

        if drift >= threshold:
            self.set_drift_from_tdrift(drift)
            # restart to utilize new time drift setting
            self._client.restart()
            return True
        else:
            return False
        
    def sync(self, threshold=0.5):
        '''Synchronize time drift to @TIME group.
        
        Convenience function to sync to the @TIME group. See *sync_to_group* for more details.
        
        Args:
            threshold (float): Median time drift in seconds to exceed before syncing, defaults to 0.5
        '''
        returns self.sync_to_group('@TIME', threshold = threshold)

    def enable(self, station=None, group='@TIME', interval=60, threshold=0.5):
        '''Enable automatic time drift monitor.
        
        Uses *sync_to_group()* if *group* is specified (default).
        
        Uses *sync_to_station()* if *station* is specified.
        
        Uses *sync_to_all()* if *group* and *station* are both None.
        
        Args:
            station (str): Station callsign to sync time drift to, defaults to None
            group (str): Group designator to sync time drift to, defaults to '@TIME'
            interval (int): Number of minutes between sync attempts, defaults to 60
            threshold (float): Time drift in seconds to exceed before syncing, defaults to 0.5
        '''
        if self._enabled:
            return
        
        self._enabled = True
        
        thread = threading.Thread(target=self._monitor, args=(station, group, interval, threshold))
        thread.daemon = True
        thread.start()

    def disable(self):
        '''Disable automatic time drift monitor.'''
        self._enabled = False
        
    #TODO monitor outgoing activity to delay app restart
    def _monitor(self, station, group, interval, threshold):
        '''Auto time drift sync thread.'''
        # sync as soon as loop starts
        last_sync_timestamp = 0
        
        while self._enabled:
            if (last_sync_timestamp + (interval * 60)) < time.time():
                if group is not None:
                    self.sync_to_group(group, threshold = threshold)
                elif station is not None:
                    self.sync_to_station(station, threshold = threshold)
                else:
                    self.sync_to_activity(threshold = threshold)
                
                last_sync_timestamp = time.time()
                
            time.sleep(1)

            
class TimeMaster:
    '''Time master monitor.
    
    i.e. stations with internet or GPS time sync capability, 
    
    The time master object sends messages on a set interval that listening stations (see pyjs8call.timemonitor.DriftMonitor) can sync to. By default outgoing messages target the @TIME group.
    
    In order for listening stations to utilize a time master station they will need to sync to the same group designator as the time master's destination. This is the default configuration for pyjs8call.timemonitor.DriftMonitor and pyjs8call.timemonitor.TimeMaster.
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

    def enable(self, destination='@TIME', message='', interval=60):
        '''Enable automatic time master outgoing messages.
    
        Note that *destination* can technically be set to a specific callsign. However, this may prevent other stations from synchronizing with the master station.
        '''
        if self._enabled:
            return

        self._enabled = True

        thread = threading.Thread(target=self._monitor, args=(destination, message, interval))
        thread.daemon = True
        thread.start()

    def disable(self):
        self._enabled = False
        
    def _monitor(self, destination, message, interval):
        '''Time master message transmit thread.'''
        # send message as soon as loop starts
        last_message_timestamp = 0
        
        while self._enabled:
            if (last_message_timestamp + (interval * 60)) < time.time():
                message = destination + ' ' + message
                    
                self._client.send_message(message.strip())
                last_message_timestamp = time.time()

            time.sleep(1)
