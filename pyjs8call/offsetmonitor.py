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

'''Monitor offset frequency based on activity in the pass band.

The offset frequency is automatically moved to an unused portion of the pass band if a recently heard signal overlaps with the current offset. Signal bandwidth is calculated based on the speed of each heard signal.

Only decoded signal data is available from the JS8Call API so other QRM cannot be handled.
'''

__docformat__ = 'google'


import threading


class OffsetMonitor:
    '''Monitor offset frequency based on activity in the pass band.

    Attributes:
        min_offset (int): Minimum offset for adjustment and recent activity monitoring, defaults to 1000
        max_offset (int): Maximum offset for adjustment and recent activity monitoring, defaults to 2500
        bandwidth (int): Outgoing signal bandwidth, defaults to bandwidth assocaited with JS8Call configured speed
        bandwidth_safety_factor (float): Safety factor to apply around outgoing signal bandwith, defaults to 1.25
        offset (int): Current JS8Call offset frequency in Hz
        before_transition (int, float): Seconds before the rx/tx window transition to process activity, defaults to 1
        activity_cycles (int, float): rx/tx cycles to consider recent activity, defaults to 1.5
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
        self.bandwidth = self._client.settings.get_bandwidth()
        self.bandwidth_safety_factor = 1.25
        self.offset = self._client.settings.get_offset()
        self.before_transition = 1
        self.activity_cycles = 1.5
        self._enabled = False
        self._paused = False

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
        '''Enable offset monitoring.'''
        if self._enabled:
            return

        self._enabled = True

        thread = threading.Thread(target=self._monitor)
        thread.daemon = True
        thread.start()

    def disable(self):
        '''Disable offset monitoring.'''
        self._enabled = False

    def pause(self):
        '''Pause offset monitoring.'''
        self._paused = True

    def resume(self):
        '''Resume offset monitoring.'''
        self._paused = False

    def _min_signal_freq(self, offset, bandwidth):
        '''Get lower edge of signal.

        Args:
            offset (int): Signal offset frequency in Hz
            bandwidth (int): Signal bandwidth in Hz

        Returns:
            int: Minimum frequency of the signal in Hz
        '''
        # bandwidth unused, included to support expanding tuple into args
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
            bool: Whether the given signal overlaps with the transmit signal space
        '''
        # get min/max frequencies
        other_min_freq = self._min_signal_freq(offset, bandwidth)
        other_max_freq = self._max_signal_freq(offset, bandwidth)
        other_center_freq = ((other_max_freq - other_min_freq) / 2) + other_min_freq
        own_min_freq = self._min_signal_freq(self.offset, self.bandwidth)
        own_max_freq = self._max_signal_freq(self.offset, self.bandwidth)

        # signal center freq within transmit bandwidth
        inside = bool(own_min_freq < other_center_freq < own_max_freq)
        # signal overlapping from above
        above = bool(own_min_freq < other_min_freq < own_max_freq)
        # signal overlapping from below
        below = bool(own_min_freq < other_max_freq < own_max_freq)

        return any([inside, above, below])

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
            if spot.speed is None:
                # assume worst case bandwidth: turbo mode = 160 Hz
                signal = (spot.offset, 160)
            else:
                # map signal speed to signal bandwidth
                bandwidth = self._client.settings.get_bandwidth(speed = spot.speed)
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
                lower_limit_below is not None and
                upper_limit_below is not None and
                (upper_limit_below - lower_limit_below) >= safe_bandwidth
            ):
                unused_spectrum.append( (lower_limit_below, upper_limit_below) )

            # unused section above is wide enough for current speed setting
            if (
                lower_limit_above is not None and
                upper_limit_above is not None and
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

        # keep track of unused_spectrum position after distance sort
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

        try:
            # index of nearest unused section
            nearest = distance[0][0]
        except IndexError:
            return None

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

        Update activity just before the end of the current tx window. This allows a new offset to be selected before the next rx/tx window if new activity overlaps with the current offset. Activity is not updated if a message is being sent (i.e. there is text in the tx text box).
        '''
        while self._enabled:
            # wait until 1 second before the end of the rx/tx window
            self._client.window.sleep_until_next_transition(before = self.before_transition)

            if self._paused:
                continue

            # skip processing if actively sending a message
            if self._client.js8call.activity():
                continue

            # get the current settings
            self.bandwidth = self._client.settings.get_bandwidth()
            current_offset = self._client.settings.get_offset(update=True)

            if current_offset != self.offset:
                self.offset = current_offset

            # force offset into specified pass band
            if self.offset < self.min_offset or self.offset > self.max_offset:
                mid_range = ((self.max_offset - self.min_offset) / 2) + self.min_offset
                self._client.settings.set_offset(mid_range)

            # get recent spots
            activity_age = int(self.activity_cycles * self._client.settings.get_window_duration())
            activity = self._client.spots.filter(age = activity_age) 

            # skip processing if there is no activity
            if len(activity) == 0:
                continue

            # process activity into signal tuples (min_freq, max_freq)
            signals = self.parse_activity(activity)

            # check for signals overlapping our signal
            overlap = False
            for signal in signals:
                if self.signal_overlapping(*signal):
                    overlap = True
                    break

            if overlap:
                # find unused spectrum (between heard signals)
                unused_spectrum = self.find_unused_spectrum(signals)

                # if no unused spectrum, stop processing
                if len(unused_spectrum) == 0:
                    continue

                # find nearest unused spectrum and determine new offset
                new_offset = self.find_new_offset(unused_spectrum)

                if new_offset is not None:
                    # set new offset
                    self.offset = self._client.settings.set_offset(new_offset)

