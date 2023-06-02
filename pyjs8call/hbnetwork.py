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

'''Manage outgoing heartbeat network messaging.

Heartbeat networking cannot be started while running JS8Call headless. This module recreates basic outgoing heartbeat network messaging while running headless. This module only sends heartbeat messages on a time interval in the heartbeat sub-band. Automatic replies such as heartbeat acknowledgements are handled by the JS8Call application.
'''

__docformat__ = 'google'


import time
import threading
import random

from pyjs8call import OffsetMonitor

class HeartbeatNetworking:
    '''Manage outgoing heartbeat network messaging.

    Send heartbeat messages automatically on a time interval. The JS8Call offset frequency will automatically change to an available offset in the heartbeat sub-band (500 - 1000 Hz) during transmit, and back to the previous offset at the end of the rx/tx cycle. If no frequency is determined to be available, or if there is no recent activity, a random frequency in the heartbeat sub-band is used.

    Outgoing activity via pyjs8call will reset the timer for the next heartbeat message. Activity not handled by pyjs8call (ex. JS8Call autoreplies) will not reset the interval timer.
    '''
    def __init__(self, client):
        '''Initialize heartbeat networking object.

        Args:
            client (pyjs8call.client): Parent client object

        Returns:
            pyjs8call.hbnetwork: Constructed heartbeat object
        '''
        self._client = client
        self._enabled = False
        self._paused = False
        self._last_outgoing = 0
        self._offset = None

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

    def enable(self, interval=10):
        '''Enable heartbeat networking.

        Args:
            interval (int): Number of minutes between outgoing messages, defaults to 10
        '''
        if self._enabled:
            return

        self._enabled = True

        self._offset = OffsetMonitor(self._client)
        self._offset.min_offset = 500
        self._offset.max_offset = 1000
        self._offset.bandwidth_safety_factor = 1.1
        self._offset.activity_cycles = 4
        self._offset.before_transition = 0.5
        self._offset.pause()
        self._offset.enable()

        thread = threading.Thread(target=self._monitor, args=(interval,))
        thread.daemon = True
        thread.start()

    def disable(self):
        '''Disable heartbeat monitoring.'''
        self._enabled = False
        self._offset.disable()

    def pause(self):
        '''Pause heartbeat monitoring.'''
        self._paused = True

    def resume(self):
        '''Resume heartbeat monitoring.'''
        self._last_outgoing = time.time()
        self._paused = False

    def _monitor(self, interval):
        '''Heartbeat monitor thread.'''
        interval *= 60
        self._last_outgoing = time.time()

        while self._enabled:
            time.sleep(1)

            # outgoing activity, reset interval timer
            if self._client.js8call.activity(age = interval):
                self._last_outgoing = self._client.js8call.last_outgoing
                continue

            # wait for accurate window timing
            if self._client.window.next_transition_seconds() is None:
                continue

            if (self._last_outgoing + interval) > time.time() or self._paused:
                continue

            # if we made it this far we are ready to send a heartbeat

            self._client.window.sleep_until_next_transition(before = 0.75)
            
            # allow disable as late as possible
            if not self._enabled:
                return

            # allow pause as late as possible
            if self._paused:
                continue

            # pause main offset monitor
            main_offset_is_paused = self._client.offset.paused()
            self._client.offset.pause()
            last_offset = self._client.settings.get_offset()

            # if no free hb offset or no activity, use pre-set random offset
            max_offset = self._offset.max_offset - self._offset.bandwidth
            hb_offset = random.randrange(self._offset.min_offset, max_offset)
            self._client.settings.set_offset(hb_offset)
            # resume hb offset monitor
            self._offset.resume()

            # send heartbeat on next cycle
            #TODO self._client.window.ignore_next_tx_frame()
            self._client.send_heartbeat()
            
            # wait until the end of the following cycle
            self._client.window.sleep_until_next_transition(within = 1, before = 1)
            self._last_outgoing = time.time()
            self._offset.pause()
            self._client.settings.set_offset(last_offset)
                
            if not main_offset_is_paused:
                self._client.offset.resume()
            
