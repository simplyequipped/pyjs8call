import time
import threading

import pyjs8call

class OffsetMonitor:
    def __init__(self, client):
        self.client = client
        self.min_offset = 1000
        self.max_offset = 2500
        self.heard_station_age = 3 * 60 # seconds
        self.bandwidth = self.client.get_bandwidth()
        self.bandwidth_safety_factor = 1.25
        self.offset = self.client.get_offset()
        self.previous_offset = self.offset
        self.enabled = True

        # start monitoring thread
        monitor_thread = threading.Thread(target=self._monitor)
        monitor_thread.setDaemon(True)
        monitor_thread.start()

    def min_signal_freq(self, offset, bandwidth):
        return offset - (bandwidth / 2)

    def max_signal_freq(self, offset, bandwidth):
        return offset + (bandwidth / 2)

    def signal_overlapping(self, offset, bandwidth):
        other_min_freq = self.min_signal_freq(offset, bandwidth)
        other_max_freq = self.max_signal_freq(offset, bandwidth)
        own_min_freq   = self.min_signal_freq(self.offset, self.bandwidth)
        own_max_freq   = self.max_signal_freq(self.offset, self.bandwidth)

        if (
            # signal offset within our signal bandwidth
            (offset > own_min_freq and offset < own_max_freq) or
            # signal overlapping from above
            (other_min_freq > own_min_freq and other_min_freq < own_max_freq) or
            # signal overlapping from below
            (other_max_freq > own_min_freq and other_max_freq < own_max_freq)
        ):
            return True
        else:
            return False

    def parse_activity(self, activity):
        signals = []

        # build list of offsets and associated bandwidths
        for spot in activity:
            if spot['speed'] == None:
                # assume worst case bandwidth: turbo mode
                 signal = (spot['offset'], 160)
            else:
                bandwidth = self.client.get_bandwidth(speed = spot['speed'])
                signal = (spot['offset'], bandwidth)

            signals.append(signal)

        signals.sort(key = lambda signal: signal[0])
        return signals

    def find_unused_spectrum(self, signals):
        unused_spectrum = []

        for i in range(len(signals)):
            min_signal_freq = self.min_signal_freq(*signals[i])
            max_signal_freq = self.max_signal_freq(*signals[i])

            # signal outside min/max offset range
            if max_signal_freq < self.min_offset or min_signal_freq > self.max_offset:
                continue

            # handle first signal in list
            if i == 0:
                # use minimum offset as lower edge of unused section
                lower_limit = self.min_offset
            else:
                # use previous signal's upper edge as lower edge of unused section
                lower_limit = self.get_max_signal_freq(*signals[i-1])

            # handle last signal in list
            if i == len(signals) - 1:
                # use maximum offset as upper edge of unused section
                upper_limit = self.max_offset
            else:
                # use next signal's lower edge as upper edge of unused section
                upper_limit = self.get_min_signal_freq(*signals[i+1])

            # unused section is wide enough for current speed setting plus safety factor
            if (upper_limit - lower_limit) >= (self.bandwidth * self.bandwidth_safety_factor):
                unused_spectrum.append((lower_limit, upper_limit))

        return unused_spectrum

    def find_new_offset(self, unused_spectrum):
        # calculate distance from the current offset to each unused section
        for i in range(len(unused_spectrum)):
            if upper_limit < self.offset:
                # below the current offset
                unused_spectrum[i] += (self.offset - upper_limit, )
            elif lower_limit > self.offset:
                # above the current offset
                unused_spectrum[i] += (lower_limit - self.offset, )

        # sort by distance from current offset
        unused_spectrum.sort(key = lambda section: section[2])

        # use nearest unused section
        lower_limit = unused_spectrum[0][0]
        upper_limit = unused_spectrum[0][1]

        # move offset up the spectrum to the beginning of the next unused section
        if lower_limit > self.offset:
            return lower_limit + ((self.bandwidth * self.bandwidth_safety_factor) / 2)

        # move offset down the spectrum to the end of the next unused section
        elif upper_limit < self.offset:
            return upper_limit - ((self.bandwidth * self.bandwidth_safety_factor) / 2)

        else:
            return None
            
    def _monitor(self):
        while self.client.online and self.enabled:
            # wait until the end of the tx window
            delay = self.client.window_monitor.next_window_end() - time.time()

            # next window end = 0 until first tx frame
            if delay < 0:
                delay = 5

            time.sleep(delay)

            # get recent spots
            timestamp = time.time() - self.heard_station_age
            activity = self.client.get_station_spots(since_timestamp = timestamp) 

            if len(activity) == 0:
                continue

            signals = self.parse_activity(activity)
            self.bandwidth = self.client.get_bandwidth()
            overlap = False

            for signal in signals:
                if self.signal_overlapping(*signal):
                    overlap = True
                    break

            if overlap:
                unused_spectrum = self.find_unused_spectrum(signals)
                new_offset = self.find_new_offset(unused_spectrum)

                if new_offset != None:
                    self.previous_offset = self.offset
                    self.offset = new_offset
                    self.client.set_offset(self.offset)

