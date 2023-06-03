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

'''Monitor configuration profile schedule.
'''

__docformat__ = 'google'


import threading
import time


class ConfigProfile:
    def __init(self, name, start, freq, speed):
        self.name = None
        self.active = False
        self.start = None
        self.freq = None
        self.speed = None


class ProfileMonitor:
    '''Monitor configuration profile schedule.'''

    def __init__(self, client):
        '''Initialize profile monitor.

        Args:
            client (pyjs8call.client): Parent client object

        Returns:
            pyjs8call.profilemonitor: Constructed profile monitor object
        '''
        self._client = client
        self._enabled = False
        self._paused = False
        self._profile_schedule = []
        self._profile_schedule_lock = threading.Lock()

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
        '''Enable profile schedule monitoring.'''
        if self._enabled:
            return

        self._enabled = True

        thread = threading.Thread(target=self._monitor)
        thread.daemon = True
        thread.start()

    def disable(self):
        '''Disable profile monitoring.'''
        self._enabled = False

    def pause(self):
        '''Pause profile monitoring.'''
        self._paused = True

    def resume(self):
        '''Resume profile monitoring.'''
        self._paused = False

    def set_profile_schedule_utc(self, name, start_utc, freq=None, speed=None):
        '''
        '''
        if freq is None:
            freq = self._client.settings.get_freq()

        if speed is None:
            speed = self._client.settings.get_speed()

        new_profile_schedule = ConfigProfile(name, start_utc, freq, speed)

        for profile in self._profile_schedule.copy():
            if profile.name == name and profile.start == start_utc:
                self._profile_schedule.remove(profile)

        self._profile_schedule.append(new_profile_schedule)

    

    def _callback(self, profile):
        '''Profile transition callback function handling.

        Calls the *pyjs8call.client.callback.profile* callback function using *threading.Thread*.

        Args:
            profile (str): Profile name
        '''
        if self._client.callback.profile is not None:
            thread = threading.Thread(target=self._client.callback.profile, args=(profile,))
            thread.daemon = True
            thread.start()

    def _monitor(self):
        '''Profile monitor thread.'''
        while self._enabled:
            if self._paused:
                continue

            now = datetime.now(timezone.utc).timestamp()
            active_profile = self._client.settings.get_profile()

            for profile in self._profile_schedule:
                if (
                    profile.name != active_profile and
                    profile.start > now and
                    profile.name in self._client.settings.get_profile_list()
                ):
                    # change config file settings
                    self._callback(profile_name)
                    self._client.settings.set_profile(profile.name)
                    self._client.settings.set_speed(profile.speed)
                    # restart when inactive
                    self._client.js8call.block_until_inactive(age = 7)
                    self._client.restart()
                    # after restart, set dial freq
                    self._client.settings.set_freq(profile.freq)

            time.sleep(60)
























