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

__docformat__ = 'google'


import time
import threading

import pyjs8call


class WindowMonitor:
    def __init__(self, client):
        self._client = client
        self._last_tx_frame_timestamp = 0
        self._next_window_timestamp = 0
        self._window_duration = self._client.get_tx_window_duration()
        self._window_callback = None

        monitor_thread = threading.Thread(target = self._monitor)
        monitor_thread.setDaemon(True)
        monitor_thread.start()

    def set_window_callback(self, callback):
        self._window_callback = callback

    def process_tx_frame(self, msg):
        self._last_tx_frame_timestamp = msg.timestamp

    def next_window_start(self):
        if self._last_tx_frame_timestamp == 0:
            return 0

        return self._next_window_timestamp

    def next_window_end(self):
        if self._last_tx_frame_timestamp == 0:
            return 0

        return self._next_window_timestamp + self._window_duration

    def _monitor(self):
        while self._client.online:
            # wait for first tx frame
            if self._last_tx_frame_timestamp == 0:
                pass

            # within 1 millisecond of window start
            elif self._next_window_timestamp < time.time():
                if self._window_callback != None:
                    self._window_callback()

                self._window_duration = self._client.get_tx_window_duration()

                if self._next_window_timestamp == 0:
                    self._next_window_timestamp = self._last_tx_frame_timestamp + self._window_duration
                else:
                    self._next_window_timestamp += self._window_duration

            time.sleep(0.001)

