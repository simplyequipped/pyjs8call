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

    Send heartbeat messages automatically on a time interval. The JS8Call offset frequency will automatically change to an available offset in the heartbeat sub-band (500 - 1000 Hz) during transmit, and back to the previous offset at the end of the rx/tx cycle. If no frequency is determined to be available, the highest frequency in the heartbeat sub-band is used.
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
        self._last_hb_timestamp = 0
        self._offset = None

    def enable_networking(self, interval=10):
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
        self._offset.pause_monitoring()
        self._offset.enable_monitoring()

        thread = threading.Thread(target=self._monitor, args=(interval,))
        thread.daemon = True
        thread.start()

    def disable_networking(self):
        '''Disable heartbeat monitoring.'''
        self._enabled = False
        self._offset.disable_networking()

    def pause_networking(self):
        '''Pause heartbeat monitoring.'''
        self._paused = True

    def resume_networking(self):
        '''Resume heartbeat monitoring.'''
        self._last_hb_timestamp = time.time()
        self._paused = False

    def _monitor(self, interval):
        '''Heartbeat monitor thread.'''
        interval *= 60
        self._last_hb_timestamp = time.time()

        while self._enabled:
            time.sleep(1)

            # wait for accurate window timing
            if self._client.window.next_transition_seconds() is None:
                continue

            if (self._last_hb_timestamp + interval) > time.time() or self._paused:
                continue

            # outgoing activity, reset interval timer
            if self._client.js8call.active():
                self._last_hb_timestamp = time.time()
                continue

            # if we made it this far we are ready to send a heartbeat
            # offset monitor processes new activity 1 second before transition
            # toggle main and hb offset monitors 2 seconds before transition

            self._client.window.sleep_until_next_transition(before = 2)
            
            # allow disable as late as possible
            if not self._enabled:
                return

            # allow pause as late as possible
            if self._paused:
                continue

            # pause main offset monitor
            main_offset_was_paused = self._client.offset.paused()
            self._client.offset.pause_monitoring()
            last_offset = self._client.settings.get_offset()
            # resume hb offset monitor
            self._offset.resume_monitoring()
            self._client.window.sleep_until_next_transition(before = 0.5)

            # no free hb offset or no activity, use max hb offset
            #TODO consider whether a random hb offset should be used
            max_offset = self._offset.max_offset - self._offset.bandwidth

            if self._client.settings.get_offset() > max_offset:
                safe_bandwidth = self._offset.bandwidth_safety_factor * self._offset.bandwidth
                offset = self._offset.max_offset - safe_bandwidth
                self._client.settings.set_offset(offset)
                
            # send heartbeat on next cycle
            self._client.window.ignore_next_tx_frame()
            self._client.send_heartbeat()
            self._last_hb_timestamp = time.time()
            
            # wait until the end of the following cycle
            self._client.window.sleep_until_next_transition(within = 1, before = 1)
            # pause hb offset monitor
            self._offset.pause_monitoring()
            # restore main offset
            self._client.settings.set_offset(last_offset)
            time.sleep(3)
                
            if not main_offset_was_paused:
                self._client.offset.resume_monitoring()
            
