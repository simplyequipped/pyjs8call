import time
import threading

import pyjs8call

class OffsetMonitor:
    def __init__(self, client):
        self.client = client
        self.min_offset = 1000
        self.max_offset = 2500
        self.heard_station_age = 100 # seconds
        self.bandwidth = self.client.get_bandwidth()
        self.bandwidth_safety_factor = 1.25
        self.offset = self.client.get_offset()
        self.enabled = True

        # start monitoring thread
        monitor_thread = threading.Thread(target=self._monitor)
        monitor_thread.setDaemon(True)
        monitor_thread.start()

    def min_signal_freq(self, offset, bandwidth):
        return int(offset)

    def max_signal_freq(self, offset, bandwidth):
        return int(offset + bandwidth)

    def signal_overlapping(self, offset, bandwidth):
        # get min/max frequencies
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
                # assume worst case bandwidth: turbo mode = 160 Hz
                 signal = (spot['offset'], 160)
            else:
                # map signal speed to signal bandwidth
                bandwidth = self.client.get_bandwidth(speed = spot['speed'])
                signal = (spot['offset'], bandwidth)

            signals.append(signal)
        
        # sort signals in ascending order by offset
        signals.sort(key = lambda signal: signal[0])
        return signals

    def find_unused_spectrum(self, signals):
        unused_spectrum = []

        for i in range(len(signals)):
            min_signal_freq = self.min_signal_freq(*signals[i])
            min_signal_freq = self.min_signal_freq(*signals[i])
            max_signal_freq = self.max_signal_freq(*signals[i])
            lower_limit_below = None
            upper_limit_below = None
            lower_limit_above = None
            upper_limit_above = None

            # signal outside min/max offset range
            if max_signal_freq < self.min_offset or min_signal_freq > self.max_offset:
                continue

            # only one signal
            if len(signals) ==  1:
                # use minimum offset as lower edge of unused section
                lower_limit_below = self.min_offset
                # use current signal's lower edge as upper edge of unused section
                upper_limit_below = min_signal_freq
                # use current signal's upper edge as lower edge of unused section
                lower_limit_above = max_signal_freq
                # use maximum offset as upper edge of unused section
                upper_limit_above = self.max_offset
                
            # first signal in list
            elif i == 0:
                # use minimum offset as lower edge of unused section
                lower_limit_below = self.min_offset
                # use current signal's lower edge as upper edge of unused section
                upper_limit_below = min_signal_freq

            # last signal in list
            elif i == len(signals) - 1:
                # use previous signal's upper edge as lower edge of unused section
                lower_limit_below = self.max_signal_freq(*signals[i-1])
                # use current signal's lower edge as upper edge of unused section
                upper_limit_below = min_signal_freq
                # use current signal's upper edge as lower edge of unused section
                lower_limit_above = max_signal_freq
                # use maximum offset as upper edge of unused section
                upper_limit_above = self.max_offset

            # signal somwhere else in the list
            else:
                # use previous signal's upper edge as lower edge of unused section
                lower_limit_below = self.max_signal_freq(*signals[i-1])
                # use current signal's lower edge as upper edge of unused section
                upper_limit_below = min_signal_freq


            safe_bandwidth = self.bandwidth * self.bandwidth_safety_factor
            
            # unused section below is wide enough for current speed setting
            if (
                lower_limit_below != None and
                upper_limit_below != None and
                (upper_limit_below - lower_limit_below) >= safe_bandwidth
            ):
                unused_spectrum.append( (lower_limit_below, upper_limit_below) )

            # unused section above is wide enough for current speed setting
            if (
                lower_limit_above != None and
                upper_limit_above != None and
                (upper_limit_above - lower_limit_above) >= safe_bandwidth
            ):
                unused_spectrum.append( (lower_limit_above, upper_limit_above) )

        return unused_spectrum

    def find_new_offset(self, unused_spectrum):
        # calculate distance from the current offset to each unused section
        distance = []

        i = 0
        for lower_limit, upper_limit in unused_spectrum:
            if upper_limit < self.offset:
                # below the current offset
                distance.append( (i, self.offset - upper_limit) )
            elif lower_limit > self.offset:
                # above the current offset
                distance.append( (i, lower_limit - self.offset) )

            i += 1

        # sort by distance from current offset
        distance.sort(key = lambda dist: dist[1])
        # index of nearest unused section
        nearest = distance[0][0]

        # use nearest unused section
        lower_limit = unused_spectrum[nearest][0]
        upper_limit = unused_spectrum[nearest][1]

        safe_bandwidth = self.bandwidth * self.bandwidth_safety_factor

        # move offset up the spectrum to the beginning of the next unused section
        if lower_limit > self.offset:
            return int(lower_limit + (safe_bandwidth - self.bandwidth))

        # move offset down the spectrum to the end of the next unused section
        elif upper_limit < self.offset:
            return int(upper_limit - safe_bandwidth)

        else:
            return None
            
    def _monitor(self):
        while self.client.online and self.enabled:
            # wait until 0.5 seconds before the end of the tx window
            delay = self.client.window_monitor.next_window_end() - time.time() - 0.5

            # next window end == 0 until first tx frame
            if delay < 0:
                delay = 5

            time.sleep(delay)

            # wait until tx_text is not being 'watched'
            # tx_monitor requests tx_text every second
            while self.client.js8call._watching == 'tx_text':
                time.sleep(0.1)
            
            # skip processing if actively sending a message
            if self.client.js8call.state['tx_text'] != '':
                continue

            # get recent spots
            activity = self.client.get_station_spots(max_age = self.heard_station_age) 

            # skip processing if there is no activity
            if len(activity) == 0:
                continue

            # process activity into signal tuples (min_freq, max_freq)
            signals = self.parse_activity(activity)

            # get the current settings
            self.bandwidth = self.client.get_bandwidth()
            current_offset = self.client.get_offset()

            if int(current_offset) != int(self.offset):
                self.offset = current_offset

            # check for signals overlapping our signal
            overlap = False
            for signal in signals:
                if self.signal_overlapping(*signal):
                    overlap = True
                    break

            if overlap:
                # find unused spectrum (between heard signals)
                unused_spectrum = self.find_unused_spectrum(signals)
                # find nearest unused spectrum and determine new offset
                new_offset = self.find_new_offset(unused_spectrum)

                if new_offset != None:
                    # set new offset
                    self.offset = new_offset
                    self.client.set_offset(self.offset)

