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

The JS8Call application is restarted when necessary to implement configuration file changes associated with profile name or modem speed. A restart only occurs after a period of rx/tx inactivity.

Set *client.callback.schedule* to receive schedule change activity.

Examples:
    ```
    js8call.schedule.add('Default', '18:30') # use current freq and speed
    js8call.schedule.add('Field Ops', '8:00', 7078000, 'normal')
    js8call.schedule.remove('Default', '18:30')
    ```
'''

__docformat__ = 'google'


import time
import datetime
import threading


class Schedule:
    '''Schedule entry container object.

    This object is passed to the *client.callback.schedule* callback function when a schedule entry is activated.
    '''

    def __init__(self, start, freq, speed, profile):
        '''Initialize schedule entry.

        Args:
            start (str): Start time as *datetime.time* object
            freq (int): Dial frequency in Hz
            speed (str): Modem speed ('slow', 'normal', 'fast', 'turbo')
            profile (str): Configuration profile name

        Returns:
            pyjs8call.schedulemonitor.Schedule: Constructed schedule entry
        '''
        self.profile = profile
        self.start = start
        self.freq = freq
        self.speed = speed
        self.active = False
        self.run = False

    def __eq__(self, schedule):
        '''Equality test.'''
        if (
            self.profile == schedule.profile and
            self.start == schedule.start and
            self.freq == schedule.freq and
            self.speed == schedule.speed
        ):
            return True
        else:
            return False


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
        '''Enable schedule monitoring.'''
        if self._enabled:
            return

        self._enabled = True

        # prevent unnessary restarts on first schedule change
        if self._active_schedule is None:
            profile = self._client.settings.get_profile()
            freq = self._client.settings.get_freq()
            speed = self._client.settings.get_speed()

            self._active_schedule = Schedule(None, freq, speed, profile)

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

    def add(self, start_time, freq=None, speed=None, profile=None):
        '''Add new schedule entry.

        Args:
            start_time (str): Start time in 24-hour format (ex. '18:30')
            freq (int): Dial frequency in Hz, defaults to current frequency
            speed (str): Modem speed ('slow', 'normal', 'fast', 'turbo'), defaults to current speed
            profile (str): Configuration profile name, defaults to the current profile
        '''
        start_time = datetime.datetime.strptime(start_time, '%H:%M').time()

        if freq is None:
            freq = self._client.settings.get_freq()

        if speed is None:
            speed = self._client.settings.get_speed()

        if profile is None:
            profile = self._client.settings.get_profile()

        new_schedule = Schedule(start_time, freq, speed, profile)

        if new_schedule in self._schedule:
            return

        with self._schedule_lock:
            self._schedule.append(new_schedule)

    def remove(self, start_time=None, profile=None):
        '''Remove existing schedule entry.

        If *start_time* is not given, all schedule entries with profile name *profile* are removed.

        if *profile* is not given, all schedule entries with start time *start_time* are removed.

        Args:
            start_time (str): Start time in 24-hour format (ex. '18:30'), defaults to None
            profile (str): Configuration profile name, defaults to None
        '''
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

    def get_schedule(self):
        '''Get all schedule entries.

        Schedule entries are sorted by start time.

        Returns:
            list: list of Schedule objects (see pyjs8call.schedulemonitor.Schedule)
        '''
        with self._schedule_lock:
            schedule = self._schedule.copy()
            
        schedule.sort(key=lambda sch: sch.start)
        return schedule

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
        if self._client.callback.schedule is None:
            return

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

            active_profile = self._client.settings.get_profile()
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
                        if self._restart_required(schedule, self._active_schedule):
    
                            # change config file settings
                            self._client.settings.set_profile(schedule.profile)
                            self._client.settings.set_speed(schedule.speed)
                            # restart when inactive
                            self._client.js8call.block_until_inactive(age = 7)
                            self._client.restart()

                        # set dial freq
                        self._client.settings.set_freq(schedule.freq)

                        schedule.active = True
                        schedule.run = True
                        self._active_schedule = schedule
                        self._callback(schedule)

            reset_run = False
