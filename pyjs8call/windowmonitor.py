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

'''Monitor transition of next tx window.

JS8Call tx frames and speed setting are used to calculate the start and end of the next tx window.
'''

__docformat__ = 'google'


import time
import threading

import pyjs8call


class WindowMonitor:
    '''Monitor transition of next tx window.

    The JS8Call API sends a tx frame message immediately at the beginning of a tx cycle when a message is being sent. The timestamp of the tx frame message is used to calculate the beginning and end of future tx windows. The lenght of the tx window is based on the JS8Call modem speed setting (see pyjs8call.client.Client.get_tx_window_duration).

    Since a tx frame is only sent by the JS8Call API when a message is being sent, the timing of the tx window is unknown until a message is sent.
    '''
    def __init__(self, client):
        '''Initialize window monitor.

        Args:
            client (pyjs8call.client): Parent client object

        Returns:
            pyjs8call.windowmonitor: Constructed window monitor object
        '''
        self._client = client
        self._last_tx_frame_timestamp = 0
        self._next_window_timestamp = 0
        self._window_duration = self._client.get_tx_window_duration()

        monitor_thread = threading.Thread(target = self._monitor)
        monitor_thread.setDaemon(True)
        monitor_thread.start()

    def _callback(self):
        '''Window transition callback function handling.'''
        if self._client.callback.window != None:
            self.client.callback.window()

    def process_tx_frame(self, msg):
        '''Process received tx frame message.

        Args:
            msg (pyjs8call.message): Tx frame message object
        '''
        self._last_tx_frame_timestamp = msg.timestamp

    def next_window_start(self):
        '''Get timestamp of next tx window start.

        Returns:
            float: Timestamp of next tx window start, or 0 (zero) if a tx frame has not been received
        '''
        if self._last_tx_frame_timestamp == 0:
            return 0

        return self._next_window_timestamp

    def next_window_end(self):
        '''Get timestamp of next tx window end.

        Returns:
            float: Timestamp of next tx window end, or 0 (zero) if a tx frame has not been received
        '''
        if self._last_tx_frame_timestamp == 0:
            return 0

        return self._next_window_timestamp + self._window_duration

    def _monitor(self):
        '''Window monitor thread.'''
        while self._client.online:
            # wait for first tx frame
            if self._last_tx_frame_timestamp == 0:
                pass
            elif self._next_window_timestamp < time.time():
                self._callback()

                self._window_duration = self._client.get_tx_window_duration()

                if self._next_window_timestamp == 0:
                    self._next_window_timestamp = self._last_tx_frame_timestamp + self._window_duration
                else:
                    self._next_window_timestamp += self._window_duration

            time.sleep(0.001)

