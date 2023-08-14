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

Only decoded signal data is available from the JS8Call API, so other QRM cannot be handled.
'''

__docformat__ = 'google'


import threading
import random


class OffsetMonitor:
    '''Monitor offset frequency based on activity in the pass band.

    Attributes:
        min_offset (int): Minimum offset for adjustment and recent activity monitoring, defaults to 1000
        max_offset (int): Maximum offset for adjustment and recent activity monitoring, defaults to 2500
        bandwidth (int): Outgoing signal bandwidth, defaults to bandwidth assocaited with JS8Call configured speed
        bandwidth_safety_factor (float): Safety factor to apply around outgoing signal bandwith, defaults to 1.25
        offset (int): Current JS8Call offset frequency in Hz
        before_transition (int, float): Seconds before the rx/tx window transition to process activity, defaults to 1
        activity_cycles (int, float): rx/tx cycles to consider recent activity, defaults to 2.5
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
        self.activity_cycles = 2.5
        self._enabled = False
        self._paused = False
        self._hb = False

        self._recent_signals = []
        self._recent_signals_lock = threading.Lock()

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
        self._client.callback.register_incoming(self.process_rx_activity, message_type = Message.RX_ACTIVITY)

        thread = threading.Thread(target=self._monitor)
        thread.daemon = True
        thread.start()

    def disable(self):
        '''Disable offset monitoring.'''
        self._enabled = False
        self._client.callback.remove_incoming(self.process_rx_activity)

    def pause(self):
        '''Pause offset monitoring.'''
        self._paused = True

    def resume(self):
        '''Resume offset monitoring.'''
        self._paused = False

    def process_rx_activity(self, activity):
        '''Process recent incoming activity.

        Note: This function is called internally when activity is received.

        Args:
            object (pyjs8call.Message): RX.ACTIVITY message from JS8Call
        '''
        # ignore activity outside the specified pass band
        if activity.offset < self.min_offset or activity.offset > self.max_offset:
            return
            
        if activity.speed is None:
            # assume worst case bandwidth: turbo mode = 160 Hz
            signal = (activity.offset, 160, activity.timestamp)
        else:
            # map signal speed to signal bandwidth
            bandwidth = self._client.settings.get_bandwidth(speed = activity.speed)
            signal = (activity.offset, bandwidth, activity.timestamp)

        with self._recent_signals_lock:
            self._recent_signals.append(signal)
            # sort signals in ascending order by offset
            self._recent_signals.sort(key = lambda signal: signal[0])

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

    def _activity_overlapping(self, activity):
        '''Check for received signals overlapping station transmit region.

        Args:
            activity (list): Recent activity signal data

        Returns:
            bool: True if a recently received signal is overlapping, False otherwise
        '''
        if len(activity) == 0:
            return False
        
        for signal in activity:
            if self._signal_overlapping(*signal):
                return True

        return False

    def _signal_overlapping(self, offset, bandwidth, timestamp):
        '''Determine if signal overlaps with current offset.

        Args:
            offset (int): Signal offset frequency in Hz
            bandwidth (int): Signal bandwidth in Hz
            timestamp (float): Received timestamp in seconds

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

    def _find_unused_spectrum(self, signals):
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

    def _find_new_offset(self, activity):
        '''Get new offset frequency.

        Find a new offset based on available sections in the pass band. The new offset is always moved to the closed available section of the pass band.

        Args:
            signals (list): List of signal tuples

        Returns:
            int: New offset frequency in Hz
            None: no unused specturm is available
        '''
        # find unused spectrum (between heard signals)
        unused_spectrum = self._find_unused_spectrum(activity)

        if len(unused_spectrum) == 0:
            return None
            
        # calculate distance from the current offset to each unused section
        distance = []

        # keep track of unused_spectrum position after distance sort
        i = 0
        for lower_limit, upper_limit in unused_spectrum:
            # distance tuple index 0 = unused spectrum index
            # distance tuple index 1 = distance from current offset
            # distance tuple index 2 = direction from current offset
            if upper_limit <= (self.offset + self.bandwidth):
                # below the current offset
                distance.append( (i, self.offset - upper_limit, 'down') )
            elif lower_limit >= self.offset:
                # above the current offset
                distance.append( (i, lower_limit - self.offset, 'up') )

            i += 1

        if len(distance) == 0:
            return None

        # sort by distance from current offset
        distance.sort(key = lambda dist: dist[1])
        # index of nearest unused spectrum
        nearest = distance[0][0]
        # direction to nearest unused spectrum from current offset
        direction = distance[0][2]
        # nearest unused section limits
        lower_limit = unused_spectrum[nearest][0]
        upper_limit = unused_spectrum[nearest][1]
        safe_bandwidth = self.bandwidth * self.bandwidth_safety_factor

        if direction == 'up':
            # move offset up the spectrum to the beginning of the next unused section
            return int(lower_limit + (safe_bandwidth - self.bandwidth))
        elif direction == 'down':
            # move offset down the spectrum to the end of the next unused section
            return int(upper_limit - safe_bandwidth)
        else:
            return None

    def _cull_recent_activity(self):
        '''Remove aged signal activity.

        Must be called from within self._recent_activity_lock context.
        '''
        recent_activity = []
        offsets = []
        max_age = int(self.activity_cycles * self._client.settings.get_window_duration())
        
        # sort recent signals in descending order by timestamp,
        # causes the most recent activity on the same offset to be kept while culling
        self._recent_activity.sort(key = lambda signal: signal[2], reverse = True)
        
        now = time.time()
        
        for signal in self._recent_activity:
            if signal[0] not in offsets and now - signal[2] <= max_age:
                # keep recent signals with a unique offset
                recent_activity.append(signal)
                offsets.append(signal[0])
                
        self._recent_activity = recent_activity
    
    def _monitor(self):
        '''Offset monitor thread.

        Update activity just before the end of the current tx window. This allows a new offset to be selected before the next rx/tx window if new activity overlaps with the current offset. Activity is not updated if a message is being sent (i.e. there is text in the tx text box).
        '''
        while self._enabled:
            # wait until just before the end of the rx/tx window
            self._client.window.sleep_until_next_transition(before = self.before_transition)
            new_offset = None

            if self._paused:
                continue

            # skip processing if actively sending a message
            if self._client.js8call.activity():
                continue

            # get current settings
            self.bandwidth = self._client.settings.get_bandwidth()
            self.offset = self._client.settings.get_offset(update=True)

            # force offset into specified pass band
            if self.offset < self.min_offset or self.offset > (self.max_offset - self.bandwidth):
                if self._hb:
                    # random offset in heartbeat sub-band
                    self.offset = random.randrange(self.min_offset, self.max_offset - self.bandwidth)
                else:
                    # middle of pass band
                    self.offset = ((self.max_offset - self.min_offset) / 2) + self.min_offset

            with self._recent_activity_lock:
                self._cull_recent_activity()
                # check for signal overlap with transmit region
                if self._activity_overlapping(self._recent_activity):
                    new_offset = self._find_new_offset(self._recent_activity)

            # set new offset
            if new_offset is not None:
                self.offset = self._client.settings.set_offset(new_offset)
            elif self.offset != self._client.settings.get_offset():
                # offset needs changed to be in specified band
                self.offset = self._client.settings.set_offset(self.offset)

            # loop runs before the end of the window, ensure loop only runs once
            self._client.window.sleep_until_next_transition()
