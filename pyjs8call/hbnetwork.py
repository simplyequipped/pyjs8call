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

JS8Call heartbeat networking cannot be started while running the application headless, since a button click on the user intefrace is required. This module recreates basic outgoing heartbeat network messaging while running headless. This module only sends heartbeat messages on a time interval in the heartbeat sub-band. Automatic replies such as heartbeat acknowledgements are handled by the JS8Call application.
'''

__docformat__ = 'google'


import time
import threading
import random

from pyjs8call import OffsetMonitor, Message

class HeartbeatNetworking:
    '''Manage outgoing heartbeat network messaging.

    Send heartbeat messages automatically on a time interval. The JS8Call offset frequency will automatically change to an available offset in the heartbeat sub-band (500 - 1000 Hz) during transmit, and back to the previous offset at the end of the transmission. If no frequency is determined to be available (lots of recent activity), or if there is no recent activity, a random frequency in the heartbeat sub-band is selected. This is consistent with JS8Call heartbeat offset frequency selection.

    The heartbeat time interval is read from the JS8Call config file. See *Client.settings.set_heartbeat_interval()* to set the time interval. The time interval can be changed while pyjs8call heartbeat networking is enabled.

    Outgoing message activity (including JS8Call autoreplies) will reset the timer for the next heartbeat message. This is consistent with JS8Call funtionality.

    Heartbeat messages are not sent if JS8Call modem speed is set to turbo. This is consistent with JS8Call funtionality.
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
        self._offset = None
        self._outgoing_msg = None

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
        '''Enable heartbeat networking.'''
        if self._enabled:
            return

        self._enabled = True

        self._offset = OffsetMonitor(self._client, hb = True)
        self._offset.min_offset = 500
        self._offset.max_offset = 1000
        self._offset.bandwidth_safety_factor = 1.1
        self._offset.activity_cycles = 4
        self._offset.pause()
        self._offset.enable()

        thread = threading.Thread(target=self._monitor)
        thread.daemon = True
        thread.start()

    def disable(self):
        '''Disable heartbeat networking.'''
        self._enabled = False
        
        if self._offset is not None:
            self._offset.disable()

    def pause(self):
        '''Pause heartbeat networking.'''
        self._paused = True

    def resume(self):
        '''Resume heartbeat networking.'''
        self._last_outgoing = time.time()
        self._paused = False

    def outgoing_msg(self, msg):
        '''Process outgoing heartbeat message state.

        Note: this function is called internally by the outgoing monitor.

        Args:
            msg (pyjs8call.Message): outgoing message object
        '''
        self._outgoing_msg = msg

    def _monitor(self):
        '''Heartbeat interval monitor thread.'''
        while self._enabled:
            time.sleep(1)
            
            # wait for accurate window timing
            if self._client.window.next_transition_seconds() is None:
                continue
                
            # wait for end of rx/tx window,
            # offset monitor runs 1 sec before transition, so it needs to be paused before it runs
            self._client.window.sleep_until_next_transition(before = 1.5)
                
            if not self._enabled:
                return
                
            # update interval from config
            interval = self._client.settings.get_heartbeat_interval() * 60 # minutes to seconds
            # subtract window duration to prevent bumping to next window after interval
            interval -= self._client.settings.get_window_duration() + 1 # 1 = offset monitor before-transition time

            # update heartbeat during qso from config
            pause_heartbeat_during_qso = self._client.settings.heartbeat_during_qso_paused()
            # whether callsign is selected on js8call ui
            callsign_selected = not self._client.get_selected_call() is None

            now = time.time()

            # skip heartbeating in the following cases:
            if (
                self._paused or
                self._client.settings.get_speed() == 'turbo' or # no hb in turbo mode
                (pause_heartbeat_during_qso and callsign_selected) or # callsign selected on js8call ui
                self._client.js8call.activity(age = interval) or # recent activity, including text in the text box and queued outgoing msgs
                (self._client.js8call.last_outgoing + interval) > now or # hb interval has not passed since last outgoing msg
                (self._client.js8call.last_band_change + interval) > now # hb interval has not passed since last band change (including start)
            ):
                continue

            # ready to send a heartbeat

            # pause main offset monitor
            main_offset_paused = self._client.offset.paused()
            self._client.offset.pause()
            last_offset = self._client.settings.get_offset()

            # resume heartbeat offset monitor, runs 1 second before transition
            self._offset.resume()
            # hb offset should be set by 0.25 sec before transition
            self._client.window.sleep_until_next_transition(before = 0.25)

            # send heartbeat on next rx/tx window
            hb_msg = self._client.send_heartbeat()

            # wait for sent or failed msg status of outgoing heartbeat msg
            while (
                self._outgoing_msg is None or
                self._outgoing_msg.id != hb_msg.id or
                self._outgoing_msg.status not in (Message.STATUS_SENT, Message.STATUS_FAILED)
            ):
                time.sleep(0.1)

            self._offset.pause()
            self._client.settings.set_offset(last_offset)
                
            if not main_offset_paused:
                self._client.offset.resume()
            
