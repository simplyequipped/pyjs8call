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

'''Restart JS8Call periodically to avoid idle timeout.

Make sure you understand your local laws regarding unattended stations before enabling this feature.
'''


__docformat__ = 'google'


import time
import threading

class IdleMonitor:
    '''Restart JS8Call periodially to avoid idle timeout'''
    def __init__(self, client):
        '''Initialize idle timeout monitor object.

        Args:
            client (pyjs8call.client): Parent client object

        Returns:
            pyjs8call.idlemonitor: Constructed idle monitor object
        '''
        self._client = client
        self._enabled = False

    def enable_monitoring(self):
        '''Enable idle timeout monitoring.'''
        if self._enabled:
            return

        self._enabled = True

        thread = threading.Thread(target=self._monitor)
        thread.daemon = True
        thread.start()

    def enabled(self):
        return self._enabled

    def disable_monitoring(self):
        '''Disable idle timeout monitoring.'''
        self._enabled = False

    def _monitor(self):
        '''Idle timeout monitor thread.'''
        timeout = self._client.settings.get_idle_timeout() * 60 * 0.9
        start_time = self._client.js8call.app.start_time()
        
        while self._enabled:
            time.sleep(1)

            if start_time + timeout < time.time():
                window_duration = self._client.settings.get_window_duration()
                self._client.restart_when_inactive(age = window_duration * 2)
                return

