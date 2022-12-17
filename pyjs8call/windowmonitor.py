import time
import threading

import pyjs8call

class WindowMonitor:
    def __init__(self, client):
        self.client = client
        self.last_tx_frame_timestamp = 0
        self.next_window_timestamp = 0
        self.window_duration = self.client.get_tx_window_duration()
        self.window_callback = None
        self.locked = False

        monitor_thread = threading.Thread(target = self._monitor)
        monitor_thread.setDaemon(True)
        monitor_thread.start()

    def set_window_callback(self, callback):
        self.window_callback = callback

    def process_tx_frame(self, msg):
        self.last_tx_frame_timestamp = msg.time

    def next_window_start(self):
        if self.last_tx_frame_timestamp == 0:
            return 0

        return self.next_window_timestamp

    def next_window_end(self):
        if self.last_tx_frame_timestamp == 0:
            return 0

        return self.next_window_timestamp + self.window_duration

    def _monitor(self):
        while self.client.online:
            # wait for first tx frame
            if self.last_tx_frame_timestamp == 0:
                pass

            # within 1 millisecond of window start
            elif self.next_window_timestamp < time.time():
                if self.window_callback != None:
                    self.window_callback()

                self.window_duration = self.client.get_tx_window_duration()

                if self.next_window_timestamp == 0:
                    self.next_window_timestamp = self.last_tx_frame_timestamp + self.window_duration
                else:
                    self.next_window_timestamp += self.window_duration

            time.sleep(0.001)

