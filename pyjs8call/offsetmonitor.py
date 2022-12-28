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

'''Manage offset frequency based on activity in the pass band.

The offset frequency is automatically moved to an unused portion of the pass band if a recently heard signal overlaps with the current offset. Signal bandwidth is calculated based on the speed of each heard signal.

Only decoded signal data is available from the JS8Call API so other QRM cannot be handled.
'''

__docformat__ = 'google'


import time
import threading


class OffsetMonitor:
    '''Monitor offset frequency based on activity in the pass band.

    Attributes:
    - min_offset (int): Minimum offset for adjustment and recent activity monitoring
    - max_offset (int): Maximum offset for adjustment and recent activity monitoring
    - heard_station_age (int): Maximum age of a heard station to be considered recent activity
    - bandwidth (int): JS8Call tx signal bandwidth (see pyjs8call.client.Client.get_bandwidth)
    - bandwidth_safety_factor (float): Safety factor to apply to tx bandwidth when looking for an unused portion of the pass band
    - offset (int): Current JS8Call offset frequency in Hz
    - enabled (bool): Whether to enable the offset monitor and automatically adjust the offset frequency, defaults to True
    '''

    def __init__(self, client):
        '''Initialize offset monitor.

        Args:
            client (pyjs8call.client): Parent client object

        Returns:
            pyjs8call.offsetmonitor: Constructed offset monitor object
        '''
        self._client = client
        self.min_offset = 1000
        self.max_offset = 2500
        self.heard_station_age = 100 # seconds
        self.bandwidth = self._client.get_bandwidth()
        self.bandwidth_safety_factor = 1.25
        self.offset = self._client.get_offset()
        self.enabled = True

        # start monitoring thread
        monitor_thread = threading.Thread(target=self._monitor)
        monitor_thread.setDaemon(True)
        monitor_thread.start()

    def _min_signal_freq(self, offset, bandwidth):
        '''Get lower edge of signal.

        Args:
            offset (int): Signal offset frequency in Hz
            bandwidth (int): Signal bandwidth in Hz

        Returns:
            int: Minimum frequency of the signal in Hz
        '''
        return int(offset)

    def _max_signal_freq(self, offset, bandwidth):
        '''Get upper edge of signal.

        Args:
            offset (int): Signal offset frequency in Hz
            bandwidth (int): Signal bandwidth in Hz

        Returns:
            int: Maximum frequency of the signal in Hz
        '''
        return int(offset + bandwidth)

    def signal_overlapping(self, offset, bandwidth):
        '''Determine if signal overlaps with current offset.

        Args:
            offset (int): Signal offset frequency in Hz
            bandwidth (int): Signal bandwidth in Hz

        Returns:
            bool: Whether the given signal overlaps with the current offset frequency
        '''
        # get min/max frequencies
        other_min_freq = self._min_signal_freq(offset, bandwidth)
        other_max_freq = self._max_signal_freq(offset, bandwidth)
        own_min_freq   = self._min_signal_freq(self.offset, self.bandwidth)
        own_max_freq   = self._max_signal_freq(self.offset, self.bandwidth)

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
        '''Parse recent activity into signal data.

        Recent spot data is processed to generate tuples of the following structure: (offset, bandwidth). The returned list of tuples is sorted by in ascending order by offset frequency.

        Args:
            activity (list): List of recent spots to parse

        Returns:
            list: List of signal tuples
        '''
        signals = []

        # build list of offsets and associated bandwidths
        for spot in activity:
            if spot.speed == None:
                # assume worst case bandwidth: turbo mode = 160 Hz
                 signal = (spot.offset, 160)
            else:
                # map signal speed to signal bandwidth
                bandwidth = self._client.get_bandwidth(speed = spot.speed)
                signal = (spot.offset, bandwidth)

            signals.append(signal)
        
        # sort signals in ascending order by offset
        signals.sort(key = lambda signal: signal[0])
        return signals

    def find_unused_spectrum(self, signals):
        '''Find available pass band sections.

        Available sections of the pass band are sections that are wide enough for a transmitted signal based on the configured bandwidth (i.e. configured JS8Call modem speed) plus a safety margin. The returned tuples represent the lower and upper limits of available pass band sections.

        Args:
            signals (list): List of signal tuples

        Returns:
            list: A list of tuples of the following structure: (lower_freq, upper_freq)
        '''
        unused_spectrum = []

        for i in range(len(signals)):
            min_signal_freq = self._min_signal_freq(*signals[i])
            min_signal_freq = self._min_signal_freq(*signals[i])
            max_signal_freq = self._max_signal_freq(*signals[i])
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
                lower_limit_below = self._max_signal_freq(*signals[i-1])
                # use current signal's lower edge as upper edge of unused section
                upper_limit_below = min_signal_freq
                # use current signal's upper edge as lower edge of unused section
                lower_limit_above = max_signal_freq
                # use maximum offset as upper edge of unused section
                upper_limit_above = self.max_offset

            # signal somwhere else in the list
            else:
                # use previous signal's upper edge as lower edge of unused section
                lower_limit_below = self._max_signal_freq(*signals[i-1])
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
        '''Get new offset frequency.

        Find a new offset based on available sections in the pass band. The new offset is always moved to the next closed available section of the pass band.

        Args:
            unused_spectrum (list): List of tuples of available sections

        Returns:
            int or None: New offset frequency in Hz, or None if there are no available sections
        '''
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
        '''Offset monitor thread.

        Update activity 0.5 seconds before the end of the current tx window. This allows a new offset to be selected before the next tx window if new activity overlaps with the current offset. Activity is not updated if a message is being sent (i.e. there is text in the tx text box).
        '''
        while self._client.online and self.enabled:
            # wait until 0.5 seconds before the end of the tx window
            delay = self._client.window_monitor.next_window_end() - time.time() - 0.5

            # next window end == 0 until first tx frame
            if delay < 0:
                delay = 5

            time.sleep(delay)

            # wait until tx_text is not being 'watched'
            # tx_monitor requests tx_text every second
            while self._client.js8call._watching == 'tx_text':
                time.sleep(0.1)
            
            # skip processing if actively sending a message
            if self._client.js8call.state['tx_text'] != '':
                continue

            # get recent spots
            activity = self._client.get_station_spots(max_age = self.heard_station_age) 

            # skip processing if there is no activity
            if len(activity) == 0:
                continue

            # process activity into signal tuples (min_freq, max_freq)
            signals = self.parse_activity(activity)

            # get the current settings
            self.bandwidth = self._client.get_bandwidth()
            current_offset = self._client.get_offset()

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
                    self._client.set_offset(self.offset)

