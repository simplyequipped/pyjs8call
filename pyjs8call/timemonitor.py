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

'''Monitor time drift and manage time master messaging.'''

__docformat__ = 'google'


import time
import threading
import statistics

from pyjs8call import Message


class DriftMonitor:
    '''Monitor time drift.

    Note that the JS8Call API does not support changing the time drift. The application will be restarted to apply new time drift settings via the configuration file.

    Note that only JS8Call rx/tx window timing relative to other stations is effected. Clock time is not effected.
        
    There are 3 sources of time drift information:
    - recently heard stations in a group (ex. @TIME)
    - a single station
    - all recently heard stations

    Typical application example:
    ```
    # manual sync to @TIME group
    client.drift.sync()

    # manual sync to specific station
    client.drift.sync_to_station('KT7RUN')

    # automatic sync to @TIME group every hour
    client.drift.enable_auto_sync()

    # find appropriate time drift to decode messages
    client.drift.search()
    ```

    '''
    def __init__(self, client):
        '''Initialize drift monitor object.

        Args:
            client (pyjs8call.cient): Parent client object

        Returns:
            pyjs8call.timemonitor.DriftMonitor: Constructed drift monitor object
        '''
        self._client = client
        self._enabled = False
        self._paused = False
        self._searching = False
        self._search_activity = []
        self._drift = self._client.config.get('MainWindow', 'TimeDrift', value_type=int)

    def enabled(self):
        '''Get enabled status.

        Returns:
            bool: True if enabled, False if disabled
        '''
        return self._enabled

    def paused(self):
        '''Get paused status.

        Returns:
            bool: True if paused, False if running
        '''
        return self._paused

    def enable(self, station=None, group='@TIME', interval=60, threshold=0.5, age=15):
        '''Enable automatic time drift monitoring.
        
        Uses *sync_to_group()* if *group* is specified (default).
        
        Uses *sync_to_station()* if *station* is specified.
        
        Uses *sync_to_activity()* if *group* and *station* are both None.
        
        Args:
            station (str): Station callsign to sync time drift to, defaults to None
            group (str): Group designator to sync time drift to, defaults to '@TIME'
            interval (int): Number of minutes between sync attempts, defaults to 60
            threshold (float): Time drift in seconds to exceed before syncing, defaults to 0.5
            age (int): Maximum age of activity in minutes, defaults to 15
        '''
        if self._enabled:
            return
        
        self._enabled = True
        
        thread = threading.Thread(target=self._monitor, args=(station, group, interval, threshold, age))
        thread.daemon = True
        thread.start()

    def disable(self):
        '''Disable automatic time drift monitoring.'''
        self._enabled = False

    def pause(self):
        '''Pause automatic time drift monitoring.'''
        self._paused = True
        
    def resume(self):
        '''Resume automatic time drift monitoring.'''
        self._paused = False
        
    def get_drift(self):
        '''Get current time drift.

        Time drift changes are tracked internally when *set_drift()* is called.

        Note that if time drift is changed via the JS8Call user interface this function will return the incorrect time drift. Time drift information is only saved to the configuration file on exit and is not available via the JS8Call API while the application is running.

        Returns:
            int: Current time drift setting
        '''
        return self._drift

    def set_drift(self, drift):
        '''Set time drift.

        Note that this function is blocking until the JS8Call application restarts and the new time drift setting is applied. On resource restricted platforms such as Raspberry Pi it may take several seconds to restart.

        Note that a stations time drift reported from a *pyjs8call.message* object is in seconds. See *set_drift_from_tdrift()*.

        If a stations time drift is positive then the corresponding JS8Call time drift adjustment will be negative, and vice vera.

        Args:
            drift (int): New time drift in milliseconds

        Returns:
            int: Current time drift per the JS8Call configuration file
        '''
        self._drift = self._client.config.set('MainWindow', 'TimeDrift', int(drift))
        self._client.config.write()
        self._restart_client()
        return self._drift

    def set_drift_from_message(self, msg):
        '''Set time drift from *Message*.

        Args:
            msg (pyjs8call.message): Message object to get time drift from

        Returns:
            int: Current time drift per the JS8Call configuration file
        '''
        return self.set_drift_from_tdrift(msg.tdrift)

    def set_drift_from_tdrift(self, tdrift):
        '''Set time drift from *Message.tdrift* attribute.

        Note that this function is blocking until the JS8Call application restarts and the new time drift setting is applied. On resource restricted platforms such as Raspberry Pi it may take several seconds to restart.

        Args:
            tdrift (float): Station time drift from *Message.tdrift*

        Returns:
            int: Current time drift per the JS8Call configuration file
        '''
        # convert seconds to milliseconds
        tdrift = int(float(tdrift) * 1000)
        # adjust relative to current drift
        drift = self.get_drift() - tdrift
        return self.set_drift(drift)
    
    def search(self, timeout=10, until_activity=False, wait_cycles=3):
        '''Search for correct time drift to decode activity.

        Automatically find the correct time drift when accurate time sources are unavailable and the time difference between other stations is too large for JS8Call to decode messages. JS8Call can decode messages with a maximum time delta of 2 seconds.

        Checks for activity in the last hour before searching. If recent activity is found a sync is performed against recently heard stations (see *sync_to_activity()*).
        
        One search iteration is defined as incrementing the time drift by 1 second and waiting *wait_cycles* rx/tx window cycles for activity.

        One search pass is defined as cycling though all search iterations. If *until_activity* is True additional search passes are made until activity is heard (*timeout* is ignored). See *stop_search()*. Once activity is heard a sync is performed against all recently heard stations (see *sync_to_activity*).

        With a rx/tx window duration of 10 seconds, and 3 rx/tx window cycles per iteration, a worst case search would take approximately 4 minutes (plus time for the application to restart during each iteration). Once activity is heard a sync is performed against all recently heard stations (see *sync_to_activity*).

        Searching utilizes *threading.Thread* and is therefore non-blocking.

        Args:
            timeout (int): Search timeout in minutes, defaults to 10
            until_activity (bool): Search until activity is heard, defaults to False
            wait_cycles (int): Number of rx/tx window cycles to wait for activity, defaults to 3
        '''
        self._searching = True
        self._search_activity = []

        # set incoming message callbacks
        self._client.callback.register_incoming(self.process_search_activity, message_type = Message.RX_DIRECTED)
        self._client.callback.register_incoming(self.process_search_activity, message_type = Message.RX_ACTIVITY)

        thread = threading.Thread(target=self._search, args=(timeout, until_activity, wait_cycles))
        thread.daemon = True
        thread.start()

    def stop_search(self):
        '''Stop active search.'''
        self._searching = False
        self._client.callback.remove_incoming(self.process_search_activity)

    def process_search_activity(self, msg):
        '''Activity callback.

        Used internally to detect activity while searching.

        Args:
            msg (pyjs8call.message) Message object to process
        '''
        if self._searching:
            self._search_activity.append(msg)

    def _search(self, timeout, until_activity, wait_cycles):
        '''Time drift search thread.'''
        timeout *= 60
        initial_drift = self.get_drift()

        if until_activity:
            timeout = None
        else:
            timeout = time.time() + timeout

        # avoid searching if spots in the last 15 minutes
        spots = self._client.spots.filter(age = 15 * 60)
        if len(spots) > 0:
            self.sync_to_activity()
            self.stop_search()
            return

        while self._searching:
            try:
                self._search_single_pass(timeout, wait_cycles)

                if not until_activity:
                    # single pass only
                    self.stop_search()

            except TimeoutError:
                # search timed out
                self.stop_search()
            except StopIteration:
                # activity found
                self.stop_search()
                self.sync_to_activity(activity = self._search_activity)
                return

        self.set_drift(initial_drift)

    def _search_single_pass(self, timeout, wait_cycles):
        '''Perform a single time drift search pass.'''
        window_duration = self._client.settings.get_window_duration()
        interval = window_duration * wait_cycles

        for drift in range(1, window_duration):
            # convert seconds to milliseconds
            self.set_drift(drift * 1000)
            last_drift_change = time.time()
    
            # wait for activity before incrementing time drift
            while last_drift_change + interval > time.time():
                if len(self._search_activity) > 0:
                    raise StopIteration
    
                elif timeout is not None and time.time() > timeout:
                    raise TimeoutError

                elif not self._searching:
                    return
    
                time.sleep(1)

    def sync_to_activity(self, threshold=0.5, age=15, activity=None):
        '''Synchronize time drift to recent activity.
        
        Note that this function is blocking until the JS8Call application restarts and the new time drift setting is applied (if required). On resource restricted platforms such as Raspberry Pi it may take several seconds to restart.

        Syncing to recent activity will decode as many stations as possible. Syncs to the average time drift of stations heard in the last *age* minutes.
        
        If *activity* is None recent spot activity is utilized.
        
        Args:
            threshold (float): Median time drift in seconds to exceed before syncing, defaults to 0.5
            age (int): Maximum age of activity in minutes, defaults to 15
            activity (list): pyjs8call.message objects to use as activity, defaults to None
            
        Returns:
            bool: True if sync occured, False otherwise
        '''
        age *= 60
        
        if activity is None:
            # sync against all recent activity
            spots = self._client.spots.filter(age = age)
        else:
            spots = activity

        if len(spots) == 0:
            # no activity to get time drift from
            return False

        drift = statistics.mean([spot.tdrift for spot in spots if spot.get('tdrift') is not None])

        if abs(drift) >= threshold:
            self.set_drift_from_tdrift(drift)
            return True
        else:
            return False

    def sync_to_group(self, group, threshold=0.5, age=15):
        '''Synchronize time drift to recent group activity.

        Note that this function is blocking until the JS8Call application restarts and the new time drift setting is applied (if required). On resource restricted platforms such as Raspberry Pi it may take several seconds to restart.

        Syncing to a group will decode as many stations as possible in a specific group, or utilize master stations (see *sync()* and pyjs8call.timemonitor.TimeMaster). Syncs to the average time drift of stations heard in the last *age* minutes.

        Note that setting *age* shorter than the time master outgoing message interval (defaults to 10 minutes) will prevent syncing to the time master station.
        
        Args:
            group (str): Group designator to sync time drift to
            threshold (float): Median time drift in seconds to exceed before syncing, defaults to 0.5
            age (int): Maximum age of activity in minutes, defaults to 15
            
        Returns:
            bool: True if sync occured, False otherwise
        '''
        age *= 60

        if not group[0] == '@':
            raise ValueError('Group designators must begin with \'@\'')
            
        # sync against recent group activity
        spots = self._client.spots.filter(destination = group, age = age)

        if len(spots) == 0:
            # no activity to get time drift from
            return False

        drift = statistics.mean([spot.tdrift for spot in spots if spot.get('tdrift') is not None])

        if abs(drift) >= threshold:
            self.set_drift_from_tdrift(drift)
            return True
        else:
            return False

    def sync_to_station(self, station, threshold=0.5):
        '''Synchronize time drift to single station.
        
        Note that this function is blocking until the JS8Call application restarts and the new time drift setting is applied (if required). On resource restricted platforms such as Raspberry Pi it may take several seconds to restart.

        Syncing to a station callsign will ensure time drift alignment with that station only. Time drift is based on the most recent message from the specified station.
        
        Args:
            station (str): Station callsign to sync time drift to
            threshold (float): Time drift in seconds to exceed before syncing, defaults to 0.5
            
        Returns:
            bool: True if sync occured, False otherwise
        '''
        # sync against last station message
        spots = self._client.spots.filter(origin = station, count = 1)

        if len(spots) == 0:
            # no activity to get time drift from
            return False
        
        # last heard station message
        msg = spots[0]

        if msg.get('tdrift') is not None and abs(msg.tdrift) >= threshold:
            self.set_drift_from_msg(msg)
            return True
        else:
            return False
        
    def sync(self, threshold=0.5, age=15):
        '''Synchronize time drift to @TIME group.
        
        Convenience function to sync to the @TIME group. See *sync_to_group()* for more details.
        
        Note that this function is blocking until the JS8Call application restarts and the new time drift setting is applied (if required). On resource restricted platforms such as Raspberry Pi it may take several seconds to restart.

        Args:
            threshold (float): Median time drift in seconds to exceed before syncing, defaults to 0.5
            age (int): Maximum age of activity in minutes, defaults to 15
        '''
        return self.sync_to_group('@TIME', threshold = threshold, age = age)

    def _restart_client(self):
        '''Restart client when there is no activity.'''
        self._client.js8call.block_until_inactive()
        self._client.restart()

    def _monitor(self, station, group, interval, threshold, age):
        '''Auto time drift sync thread.'''
        interval *= 60
        # sync as soon as loop starts
        last_sync_timestamp = 0
        
        while self._enabled:
            time.sleep(1)

            if last_sync_timestamp + interval < time.time():
                if self._paused:
                    continue

                if group is not None:
                    self.sync_to_group(group, threshold = threshold, age = age)
                elif station is not None:
                    self.sync_to_station(station, threshold = threshold)
                else:
                    self.sync_to_activity(threshold = threshold, age = age)
                
                last_sync_timestamp = time.time()
                
            
class TimeMaster:
    '''Manage time master messaging.
    
    **It is recommended that you not configure your station as a time master station unless you understand what you are doing and why.**

    The time master object sends messages on a set interval that listening stations (see pyjs8call.timemonitor.DriftMonitor) can sync to. By default outgoing messages target the @TIME group.
    
    A time master station is intended to be a station with internet or GPS time sync capability. However, since JS8Call time syncing only needs to be relative to the rx/tx window of other stations, using time master stations is still effective even if the time master station does not have access to accurate clock time.
    
    In order for listening stations to utilize a time master station they will need to sync to the same group designator as the time master's destination. This is the default configuration. See pyjs8call.confighandler for more information on adding and removing groups.
    '''
    def __init__(self, client):
        '''Initialize time master object.
        
        Args:
            client (pyjs8call.client): Parent client object
            
        Returns:
            pyjs8call.timemonitor.TimeMaster: Constructed time master object
        '''
        self._client = client
        self._enabled = False
        self._paused = False

    def enabled(self):
        '''Get enabled status.

        Returns:
            bool: True if enabled, False if disabled
        '''
        return self._enabled

    def paused(self):
        '''Get paused status.
        
        Returns:
            bool: True if paused, False if running
        '''
        return self._paused

    def enable(self, destination='@TIME', message='SYNC', interval=10):
        '''Enable automatic time master messaging.
    
        Note that *destination* can technically be set to a specific callsign. However, this may prevent other stations from synchronizing with the master station.
        
        Note that receiving stations will recognize incoming messages as a directed message (which result in a spot) unless a message is included.

        Args:
            destination (str): Outgoing message destination, defaults to '@TIME'
            message (str): Outgoing message text, defaults to 'SYNC'
            interval (int): Number of minutes between outgoing messages, defaults to 10
        '''
        if self._enabled:
            return

        self._enabled = True

        thread = threading.Thread(target=self._monitor, args=(destination, message, interval))
        thread.daemon = True
        thread.start()

    def disable(self):
        '''Disable time master messaging.'''
        self._enabled = False

    def pause(self):
        '''Pause time master.'''
        self._paused = True

    def resume(self):
        '''Resume time master.'''
        self._paused = False
        
    def _monitor(self, destination, message, interval):
        '''Time master message transmit thread.

        See *TimeMaster.enable()* for argument details.
        '''
        interval *= 60
        last_outgoing_timestamp = 0
        
        while self._enabled:
            if last_outgoing_timestamp + interval < time.time() and not self._paused:
                text = destination + ' ' + message
                self._client.send_message(text.strip())
                last_outgoing_timestamp = time.time()

            time.sleep(1)
