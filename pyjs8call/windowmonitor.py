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

'''Monitor transition of next rx/tx window.

JS8Call incoming and outgoing messages are used to calculate the next rx/tx window transition.

Set `client.callback.window` to know when a rx/tx window transition occurs. See pyjs8call.client.Callbacks for *window* callback function details.

'''

__docformat__ = 'google'


import time
import threading

from pyjs8call import Message


class WindowMonitor:
    '''Monitor rx/tx window transitions.

    Incoming and outgoing messages trigger JS8Call API messages that can be used to calculate the start or end of a transmit window. The length of the rx/tx window is based on the JS8Call modem speed setting.

    JS8Call API messages for incoming messages or other activity are sent approximately two seconds before the end of the transmit window. The timestamp of the received message is used to calculate the end of the current rx/tx window. Messages of type RX_DIRECTED and RX_ACTIVITY are monitored.

    JS8Call API tx frames for outgoing messages are sent immediately at the beginning of the transmit window. The timestamp of the tx frame message is used to calculate the beginning of the current rx/tx window. Note that JS8Call allows an outgoing message to be transmitted if sent within one second of the beginning of the rx/tx window, which may result in a tx frame that is not aligned with the beginning of the rx/tx window and a window transition calculation that is temporarily incorrect by a maximum of one second. The calculation will be corrected automatically once the next message is sent or received normally.


    Note that the rx/tx window transition cannot be calculated until a message is sent or received.
    '''
    def __init__(self, client):
        '''Initialize window monitor.

        Args:
            client (pyjs8call.client): Parent client object

        Returns:
            pyjs8call.windowmonitor: Constructed window monitor object
        '''
        self._client = client
        self._enabled = False
        self._last_rig_ptt_timestamp = 0
        self._last_rx_msg_timestamp = 0
        self._next_window_timestamp = 0
        self._timestamp_lock = threading.Lock()

    def enabled(self):
        '''Get enabled status.

        Returns:
            bool: True if enabled, False if disabled
        '''
        return self._enabled

    def enable(self):
        '''Enable rx/tx window monitoring.'''
        if self._enabled:
            return

        self._enabled = True
        
        self._client.callback.register_incoming(self.process_rig_ptt, message_type = Message.RIG_PTT)
        self._client.callback.register_incoming(self.process_rx_msg, message_type = Message.RX_DIRECTED)
        self._client.callback.register_incoming(self.process_rx_msg, message_type = Message.RX_ACTIVITY)

        thread = threading.Thread(target = self._monitor)
        thread.daemon = True
        thread.start()

    def disable(self):
        '''Disable rx/tx window monitoring.

        **Caution**: Many internal modules depend on the window monitor to function. Only disable this module if you understand what you are doing.
        '''
        self._enabled = False
        self._client.callback.remove_incoming(self.process_rx_msg)
        self._client.callback.remove_incoming(self.process_rig_ptt)

    def reset(self):
        '''Reset rx/tx window monitoring timestamps.

        This function is used internally during restart.
        '''
        self._next_window_timestamp = 0
        self._last_rig_ptt_timestamp = 0
        self._last_rx_msg_timestamp = 0

    def _callback(self):
        '''Window transition callback function handling.

        Calls the *pyjs8call.client.callback.window* callback function using *threading.Thread*.
        '''
        if self._client.callback.window is not None:
            thread = threading.Thread(target = self._client.callback.window)
            thread.daemon = True
            thread.start()

    def process_rig_ptt(self, msg):
        '''Process rig ptt message.

        This function is for internal use only.

        Use the timestamp of a PTT API message to mark the rx/tx window transition.

        Args:
            msg (pyjs8call.message): Rig PTT message object
        '''
        # ignore ptt off messages
        if not msg.ptt:
            return

        window_duration = self._client.settings.get_window_duration()

        with self._timestamp_lock:
            self._last_rig_ptt_timestamp = msg.timestamp
            self._next_window_timestamp = msg.timestamp + window_duration

    def process_rx_msg(self, msg):
        '''Process incoming message.

        This function is for internal use only.

        Use the timestamp of an incoming message to calculate the rx/tx window transition.

        Args:
            msg (pyjs8call.message): Received message object
        '''
        # only process the first incoming message per rx/tx cycle
        window_duration = self._client.settings.get_window_duration()

        if (msg.timestamp - self._last_rx_msg_timestamp) > (window_duration / 2):
            with self._timestamp_lock:
                self._last_rx_msg_timestamp = msg.timestamp
                # message rx occurs approximately 2 second before the end of the tx window
                self._next_window_timestamp = msg.timestamp + 2

    def next_transition_timestamp(self, cycles=0, default=None):
        '''Get timestamp of next rx/tx window transition.

        The returned timestamp is rounded to three decimal places.

        Args:
            cycles (int): Number of rx/tx cycles ahead to calculate, defaults to 0 (zero)
            default (int, float): Value to return if the next transition is unknown, defaults to None

        Returns:
            float: Timestamp of the next window transition, or *default* if no messages have been sent or received
        '''
        if self._next_window_timestamp == 0:
            return default
        else:
            window_duration = self._client.settings.get_window_duration()
            return round(self._next_window_timestamp + (window_duration * cycles), 3)

    def next_transition_seconds(self, cycles=0, default=None):
        '''Get number of seconds until next rx/tx window transition.

        The returned number of seconds is reduced by 0.1 seconds to allow time for program execution without missing the next window transition.  The returned number of seconds is also rounded to one decimal place.

        Args:
            cycles (int): Number of rx/tx cycles ahead to calculate, defaults to 0 (zero)
            default (int, float): Value to return if the next transition is unknown, defaults to None

        Returns:
            float: Number of seconds until the next window transition, or *default* if no messages have been sent or received
        '''
        transition = self.next_transition_timestamp(cycles = cycles, default = default)

        if transition == default:
            return default
        else:
            return round(transition - time.time() - 0.01, 1)

    def sleep_until_next_transition(self, cycles=0, before=0, within=0, default=None):
        '''Sleep until next rx/tx window transition.

        This function is blocking via the *time.sleep()* function.

        If the next transtion occurs within *before* seconds, the following transition is assumed.
        Args:
            cycles (int): Number of rx/tx cycles ahead to sleep, defaults to 0 (zero)
            before (int, float): Number of seconds before the transition to return
            within (int, float): Seconds from next transition to assume the following transition, defaults to 0
            default (int, float): Seconds to sleep if the next transition is unknown, defaults to (window duration / 2)

        Examples:

        The next transition: 
        `client.window.sleep_until_next_transition()`

        One second before the next transition:
        `client.window.sleep_until_next_transition(before = 1)`

        The following transition if within 0.5 seconds of the next transition:
        `client.window.sleep_until_next_transition(within = 0.5)`
        '''
        next_transition = self.next_transition_seconds()

        if next_transition is None:
            if default is None:
                try:
                    # errors immediately after start when application does not respond with speed setting fast enough
                    delay = self._client.settings.get_window_duration() / 2
                except ValueError:
                    delay = 5
            else:
                delay = default

        elif cycles == 0 and (next_transition < before or next_transition <= within):
            delay = self.next_transition_seconds(cycles = 1) - before
        else:
            delay = self.next_transition_seconds(cycles = cycles) - before

        if delay <= 0:
            return

        time.sleep(delay)

    def _monitor(self):
        '''Window monitor thread.'''
        while self._enabled:
            with self._timestamp_lock:
                if self._next_window_timestamp != 0 and self._next_window_timestamp < time.time():
                    # window transiton notification via callback function
                    self._callback()
                    # update window duration in case speed setting changed
                    window_duration = self._client.settings.get_window_duration()
                    # increament the window timestamp
                    self._next_window_timestamp += window_duration

            time.sleep(0.01)

