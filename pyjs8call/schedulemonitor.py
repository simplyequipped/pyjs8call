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

'''Monitor and activate schedule entries.

The schedule is a daily schedule. The run state of each entry is reset at midnight.

The JS8Call application is restarted when necessary to implement configuration file changes associated with profile name or modem speed. A restart only occurs after a period of inactivity.

**Hint**: To return to the current configuration at a later time, set the "return" schedule first using the current settings. Example: `schedule.add('16:00')`

Set *client.callback.schedule* to receive schedule change activity.

Examples:
    ```
    js8call.schedule.add('18:30') # use current freq, speed, and profile
    js8call.schedule.add('8:00', 7078000, 'normal', 'Field Ops')
    js8call.schedule.remove('18:30')
    js8call.schedule.add('2:00', restart=True) # restart application daily at 2am
    ```
'''

__docformat__ = 'google'


import time
import datetime
import threading
import json


class ScheduleEntry:
    '''Schedule entry container object.

    Do not use this object to create a schedule entry directly. See ScheduleMonitor.add().

    This object is passed to the *callbacks.Callbacks.schedule* callback function when a schedule entry is activated.
    
    String (str) format:
        {time}L | {state: <8} | {freq_mhz: <11} | {speed: <6} | {profile}
        
        Examples:
            '18:30L | inactive | 7.078 MHz   | normal | Default'
            '10:00L | active   | 14.078 MHz  | fast   | FT857'
    
    Representation (repr) format:
        <ScheduleEntry {time}L : {freq_mhz} : {speed} : {profile}>
        
        Examples:
            '<ScheduleEntry 18:30L : 7.078 MHz : normal : Default>'
            '<ScheduleEntry 10:00L : 14.078 MHz : fast : FT857>'
    '''

    def __init__(self, start, freq, speed, profile, restart):
        '''Initialize schedule entry.

        Args:
            start (str): Start time as *datetime.time* object
            freq (int): Dial frequency in Hz
            speed (str): Modem speed ('slow', 'normal', 'fast', 'turbo')
            profile (str): Configuration profile name
            restart (bool): Whether to forece application restart

        Returns:
            pyjs8call.schedulemonitor.ScheduleEntry: Constructed schedule entry
        '''
        self.profile = profile
        '''str: JS8Call configuration profile to set when activated'''
        self.start = start
        '''datetime.time: Local start time'''
        self.freq = freq
        '''int: Frequency in Hz to set when activated'''
        self.speed = speed
        '''str: JS8Call modem speed to set when activated'''
        self.restart = restart
        '''bool: Whether to force a restart of JS8Call when activated'''
        self.active = False
        '''bool: Whether this schedule entry is currently activated'''
        self.run = False
        '''bool: Whether this schedule entry has been run today'''
    
    def dict(self):
        '''Get dictionary representation of shedule entry.
        
        Returns:
            Dictionary of schedule entry object with the following keys:
            - start (datetime.time)
            - time (str): Local time in 24-hour format, ex. '18:30'
            - freq (int): Frequency in Hz, ex. 7078000
            - freq_mhz (str): Frequency in MHz with 3 decimal places, ex. '7.078 MHz'
            - speed (str): Modem speed, ('slow', 'normal', 'fast', or 'turbo')
            - restart (bool): Whether application is forced to restart
            - profile (str): Configuration profile name, ex. 'Default'
            - active (bool): True if entry is the active schedule, False otherwise
            - state (str): 'active' if self.active is True, 'inactive' otherwise
            - run (bool): True if entry has been run today, False otherwise
        '''
        return {
            'start': self.start,
            'time': self.start.strftime('%H:%M'),
            'freq': self.freq,
            'freq_mhz': '{:.3f} MHz'.format(self.freq / 1000000),
            'speed': self.speed,
            'restart': self.restart,
            'profile': self.profile,
            'active': self.active,
            'state': 'active' if self.active else 'inactive',
            'run': self.run
        }

    def __eq__(self, schedule):
        '''Equality test.'''
        return bool(
            self.profile == schedule.profile and
            self.start == schedule.start and
            self.freq == schedule.freq and
            self.speed == schedule.speed and
            self.restart == schedule.restart
        )
    
    def __repr__(self):
        '''Get schedule entry object representation.'''
        return '<ScheduleEntry {0[time]}L : {0[freq_mhz]} : {0[speed]} : {0[profile]} : {0[restart]}>'.format(self.dict())
            
    def __str__(self):
        '''Get schedule entry string.'''
        return '{0[time]}L | {0[state]: <8} | {0[freq_mhz]: <11} | {0[speed]: <6} | {0[restart] <5} | {0[profile]}'.format(self.dict())


class ScheduleMonitor:
    '''Monitor and activate schedule entries.'''

    def __init__(self, client):
        '''Initialize schedule monitor.

        Args:
            client (pyjs8call.client): Parent client object

        Returns:
            pyjs8call.schedulemonitor: Constructed schedule monitor object
        '''
        self._client = client
        self._active_schedule = None
        self._schedule = []
        self._schedule_lock = threading.Lock()
        self._enabled = False
        self._paused = False

        config_schedules = self._client.config.get('Configuration', 'pyjs8callSchedule')

        if config_schedules is not None and config_schedules != 'None':
            config_schedules = config_schedules.replace('""', '"')
            config_schedules = json.loads(config_schedules)

            for schedule in config_schedules:
                self.add(*schedule)

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

    def enable(self):
        '''Enable schedule monitoring.

        Past schedule entries are marked as run to prevent them from running when enabled. The last past schedule entry is not marked as run (to get back on schedule).
        '''
        if self._enabled:
            return

        self._enabled = True

        # prevent unnessary restarts on first schedule change
        if self._active_schedule is None:
            profile = self._client.settings.get_profile()
            freq = self._client.settings.get_freq()
            speed = self._client.settings.get_speed()

            self._active_schedule = ScheduleEntry(None, freq, speed, profile, False)

        # prevent running past schedule entries when re-enabled
        with self._schedule_lock:
            self._schedule.sort(key=lambda sch: sch.start)
            now = datetime.datetime.now().time()
            
            for i in range(len(self._schedule)):
                # set past schedule entries as run, except the last past schedule entry
                # let the last past schedule entry run to get back on schedule
                if i < (len(self._schedule) - 1) and self._schedule[i + 1].start < now:
                    self._schedule[i].run = True
            
        thread = threading.Thread(target=self._monitor)
        thread.daemon = True
        thread.start()

    def disable(self):
        '''Disable schedule monitoring.'''
        self._enabled = False

    def pause(self):
        '''Pause schedule monitoring.'''
        self._paused = True

    def resume(self):
        '''Resume schedule monitoring.'''
        self._paused = False

    def add(self, start_time, freq=None, speed=None, profile=None, restart=False):
        '''Add new schedule entry.

        Args:
            start_time (str): Local start time in 24-hour format (ex. '18:30')
            freq (int): Dial frequency in Hz, defaults to current frequency
            speed (str): Modem speed ('slow', 'normal', 'fast', 'turbo'), defaults to current speed
            profile (str): Configuration profile name, defaults to the current profile
            restart (bool): Whether to force an application restart, defaults to False

        Returns:
            ScheduleEntry: New schedule entry object
        '''
        start_time = datetime.datetime.strptime(start_time, '%H:%M').time()
        now = datetime.datetime.now().time()

        if freq is None:
            freq = self._client.settings.get_freq()

        if speed is None:
            speed = self._client.settings.get_speed()

        if profile is None:
            profile = self._client.settings.get_profile()

        new_schedule = ScheduleEntry(start_time, int(freq), speed, profile, restart)

        # avoid running past schedule entry immediately after creation
        if new_schedule.start < now:
            new_schedule.run = True

        if new_schedule in self._schedule:
            return new_schedule

        with self._schedule_lock:
            self._schedule.append(new_schedule)

        self._save_to_config()
        return new_schedule

    def remove(self, start_time=None, profile=None, schedule=None):
        '''Remove existing schedule entry.

        If *start_time* is not given, all schedule entries with profile name *profile* are removed. If *profile* is not given, all schedule entries with start time *start_time* are removed. If *schedule* is set to a *schedulemonitor.ScheduleEntry* object, *start_time* and *profile* are set via *schedule*.

        Args:
            start_time (str): Local start time in 24-hour format (ex. '18:30'), defaults to None
            profile (str): Configuration profile name, defaults to None
            schedule (ScheduleEntry): Schedule entry object to source *start_time* and *profile* from, defaults to None
        '''
        if schedule is not None and isinstance(schedule, ScheduleEntry):
            start_time = schedule.start.strftime('%H:%M')
            profile = schedule.profile
        
        if start_time is not None:
            start_time = datetime.datetime.strptime(start_time, '%H:%M').time()

        with self._schedule_lock:
            for schedule in self._schedule.copy():
                if (
                    (start_time is None and profile == schedule.profile) or
                    (profile is None and start_time == schedule.start) or
                    (profile == schedule.profile and start_time == schedule.start)
                ):
                    self._schedule.remove(schedule)

        self._save_to_config()

    def get_schedule(self):
        '''Get all schedule entries.

        Schedule entries are sorted by start time.

        Returns:
            list: list of Schedule objects (see schedulemonitor.Schedule)
        '''
        with self._schedule_lock:
            schedule = self._schedule.copy()
            
        schedule.sort(key=lambda sch: sch.start)
        return schedule

    def _save_to_config(self):
        '''Save schedule to configuration file.'''
        with self._schedule_lock:
            schedule = [ [sch.start.strftime('%H:%M'), sch.freq, sch.speed, sch.profile, sch.restart] for sch in self._schedule]
            
        schedule = json.dumps(schedule).replace('"', '""')
        self._client.config.set('Configuration', 'pyjs8callSchedule', schedule)

    def _restart_required(self, schedule_a, schedule_b):
        '''Whether schedule changes require restart.'''
        if schedule_a is None or schedule_b is None:
            return True
        elif schedule_a.profile == schedule_b.profile and schedule_a.speed == schedule_b.speed:
            return False
        else:
            return True

    def _callback(self, schedule):
        '''Callback handling function.'''
        if self._client.callback.schedule is not None:
            thread = threading.Thread(target=self._client.callback.schedule, args=(schedule,))
            thread.daemon = True
            thread.start()

    def _monitor(self):
        '''Schedule monitor loop.'''
        reset_run = False
        last_time = 0
        now = datetime.datetime.now().time()

        while self._enabled:
            # delay until one second after next minute roll over
            current = datetime.datetime.now().time()
            time.sleep(61 - datetime.timedelta(seconds=current.second, microseconds=current.microsecond).total_seconds())

            if self._paused:
                continue

            last_time = now
            now = datetime.datetime.now().time()

            # time roll over at midnight (23:59 -> 00:00)
            if last_time > now:
                reset_run = True

            profile_list = self._client.settings.get_profile_list()

            with self._schedule_lock:
                for schedule in self._schedule:
                    # deactivate previous schedules
                    if schedule != self._active_schedule:
                        schedule.active = False

                    # reset run state at midnight
                    if reset_run:
                        schedule.run = False

                    # skip invalid profiles
                    if schedule.profile not in profile_list:
                        continue

                    if not schedule.run and not schedule.active and schedule.start < now:
                        if schedule.restart or self._restart_required(schedule, self._active_schedule):
                            # window duration based on current speed setting
                            window = self._client.settings.get_window_duration()
                            
                            # change config file settings
                            self._client.settings.set_profile(schedule.profile)
                            self._client.settings.set_speed(schedule.speed)
                            # restart when inactive
                            self._client.js8call.block_until_inactive(age = window * 2)
                            self._client.restart()

                        # set dial freq
                        self._client.settings.set_freq(schedule.freq)

                        schedule.active = True
                        schedule.run = True
                        self._active_schedule = schedule
                        self._callback(schedule)

            reset_run = False
