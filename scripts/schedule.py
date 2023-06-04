#!/bin/python3

import sys
import time
import datetime
import threading

import pyjs8call


class Schedule:
    def __init__(self, profile, start, freq, speed):
        self.profile = profile
        self.start = start
        self.freq = freq
        self.speed = speed
        self.active = False
        self.run = False

    def __eq__(self, schedule):
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
    def __init__(self, client, verbose=False):
        '''Initialize schedule monitor.

        Args:
            client (pyjs8call.client): pyjs8call client object reference
            verbose (bool): Print schedule changes if True, print nothing if False
        '''
        self._client = client
        self._verbose = verbose
        self._active_schedule = None
        self._schedule = []
        self._schedule_lock = threading.Lock()

        thread = threading.Thread(target=self._monitor)
        thread.daemon = True
        thread.start()

    # start_time format is 24-hour time (ex. '18:30')
    def add(self, profile, start_time, freq=None, speed=None):
        '''Add new schedule.

        Args:
            profile (str): Configuration profile name
            start_time (str): Start time in 24-hour format (ex. '18:30')
            freq (int): Dial frequency in Hz, defaults to current frequency
            speed (str): Modem speed ('slow', 'normal', 'fast', 'turbo'), defaults to current speed
        '''
        start_time = datetime.datetime.strptime(start_time, '%H:%M').time()

        if freq is None:
            freq = self._client.settings.get_freq()

        if speed is None:
            speed = self._client.settings.get_speed()

        new_schedule = Schedule(profile, start_time, freq, speed)

        if new_schedule in self._schedule:
            return

        with self._schedule_lock:
            self._schedule.append(new_schedule)

    def remove(self, profile, start_time=None):
        '''Remove existing schedule.

        If *start_time* is not given, all schedules with profile name *profile* are removed.

        Args:
            profile (str): Configuration profile name
            start_time (str): Start time in 24-hour format (ex. '18:30'), defaults to None
        '''
        for schedule in self._schedule.copy():
            if schedule.profile == profile and start_time in [None, schedule.start]:
                self._schedule.remove(schedule)

    def show(self):
        '''Show all existing schedules.'''
        with self._schedule_lock:
            schedules = self._schedule

        if len(schedules) == 0:
            print('No schedules\n')
            return

        schedules.sort(key=lambda s:s.start)

        print('Schedule:\n')

        for schedule in schedules:
            print(schedule.profile + '\t    time: ' + schedule.start.strftime('%H:%M') +
            '    freq: ' + str(schedule.freq/1000000) + ' MHz    speed: ' + schedule.speed)

        print('')

    def _restart_required(self, schedule_a, schedule_b):
        if schedule_a is None or schedule_b is None:
            return True
        elif schedule_a.profile == schedule_b.profile and schedule_a.speed == schedule_b.speed:
            return False
        else:
            return True

    def _monitor(self):
        reset_run = False
        last_time = 0
        now = datetime.datetime.now().time()

        while self._client.online:
            # delay until one second after next minute roll over
            current = datetime.datetime.now().time()
            time.sleep(61 - datetime.timedelta(seconds=current.second, microseconds=current.microsecond).total_seconds())

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
                    if self._active_schedule is not None and schedule != self._active_schedule:
                        schedule.active = False

                    # reset run state at midnight
                    if reset_run:
                        schedule.run = False

                    # skip invalid profiles
                    if schedule.profile not in profile_list:
                        continue

                    if not schedule.run and not schedule.active and schedule.start < now:
                        if self._verbose:
                            datetime_str = datetime.datetime.now().strftime('%m/%d/%y %H:%M')
                            print('[' + datetime_str + '] Changing to ' + schedule.profile +
                                ' (' + str(schedule.freq) + ', ' + schedule.speed + ')')

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

            reset_run = False


if __name__ == '__main__':
    if '-v' in sys.argv:
        verbose = True
    else:
        verbose = False

    js8call = pyjs8call.Client()
    js8call.start()
    schedule = ScheduleMonitor(js8call, verbose)

    # add schedules here
    # schedule.add('Default', '20:00') # uses current freq and speed
    # schedule.add('Default', '21:00', freq=7078000, speed='normal')

    schedule.show()

