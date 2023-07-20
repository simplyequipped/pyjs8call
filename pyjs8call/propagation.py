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

'''Propagation analysis based on spot data.

This module is initialized by pyjs8call.client.
'''

__docformat__ = 'google'


import time
import threading
import statistics


class Propagation:
    '''
    '''
    
    def __init__(self, client):
        '''
        '''
        self._client = client
        self._enabled = False
        self._paused = False
        self._last_analysis = 0
        self._propagation_data = {}
        self._propagation_data_lock = threading.Lock()
        
        self.interval = 10 * 60 # minutes
        self.wait_cycles = 5

    def enabled(self):
        '''Get enabled status.

        Returns:
            bool: True if enabled, False if disabled
        '''
        return self._enabled

    def paused(self):
        '''Get paused status.

        Returns
            bool: True if paused, False if running
        '''
        return self._paused

    def enable(self):
        '''Enable propagation analysis.
        '''
        if self._enabled:
            return

        self._enabled = True
        self._client.settings.set_heartbeat_interval(self.interval)
        self._client.heartbeat.enable()

        thread = threading.Thread(target=self._monitor)
        thread.daemon = True
        thread.start()

    def disable(self):
        '''Disable propagation analysis.'''
        self._enabled = False

    def pause(self):
        '''Pause propagation analysis.'''
        self._paused = True

    def resume(self):
        '''Resume propagation analysis.'''
        self._paused = False
    def get_data(self, age=0, count=1):
        '''Get propagation analysis data set.

        If *age* is greater than zero, count is ignored.

        Args:
            age (int): propagation data age in minutes, defaults to 0 (zero)
            count (int): number of data sets to return, defaults to 1
            
        Returns:
            dict or None: {'grids': {'GRID': SNR, ...}, 'origins': {'GRID': SNR, ...}}, or None if no data
        '''
        if len(self._propagation_data) == 0:
            return None

        with self._propagation_data_lock:
            if age == 0:
                # age ignored, return *count* data sets
                if len(self._propagation_data) <= count:
                    return self._propagation_data
                    
                timestamps = self._propagation_data.keys()
                timestamps = timestamps[:count]
                return {timestamp: value for timestamp, value in self._propagation_data.items() if timestamp in timestamps}
            else:
                age *= 60 # minutes to seconds
                return {timestamp: value for timestamp, value in self._propagation_data.items() if timestamp > time.time() - age}
        
    def get_data_median(self, age=60, count=0):
        '''Get median propagation analysis data.

        Args:
            age (int): maximum data set age in minutes, defaults to 60
            count (int): number of data sets to return, defaults to 1
            
        Returns:
            dict or None: {'grids': {'GRID': SNR, ...}, 'origins': {'GRID': SNR, ...}}, or None if no data
        '''
        data_sets = self.get_data_set(age, count)
        
        if data_sets is None:
            return None
        
        grids = {}
        origins = {}

        # build lists of snr data for each grid and origin callsign
        for timestamp, data in data_sets:
            for grid, snr in data['grids']:
                if grid in grids:
                    grids[grid].append(snr)
                else:
                    grids[grid] = [snr]

            for origin, snr in data['origins']:
                if origin in origins:
                    origins[origin].append(snr)
                else:
                    origins[origin] = [snr]
                        
        # calculate median snr for each grid and origin callsign
        grids = {grid: statistics.median(snrs) for grid, snrs in grids.items()}
        origins = {origin: statistics.median(snrs) for origin, snrs in origin.items()}
        return {'grids': grids, 'origins': origins}

    def get_grid_snr(self, grid):
        '''Get recent SNR for specified grid square.

        The returned SNR may not be from the most recent analysis interval if the specified grid square is not found in the most recent interval data.

        Args:
            grid (str): Grid square to find

        Returns:
            tuple or None: tuple like (SNR, timestamp) if grid is found, None otherwise
        '''
        if len(grid) < 4:
            raise ValueError('Grid must be at least 4 characters')
        elif len(grid) > 4:
            grid = grid[:4]
            
        with self._propagation_data_lock:
            for timestamp in self._propagation_data:
                for _grid in self._propagation_data[timestamp]['grids']:
                    if _grid == grid:
                        return (self._propagation_data[timestamp]['grids'][grid], timestamp)
    
    def get_origin_snr(self, origin):
        '''Get recent SNR for specified origin callsign.
        
        The returned SNR may not be from the most recent analysis interval if the specified origin is not found in the most recent interval data.

        Args:
            origin (str): Origin callsign to find

        Returns:
            tuple or None: tuple like (SNR, timestamp) if origin is found, None otherwise
        '''
        with self._propagation_data_lock:
            for timestamp in self._propagation_data:
                for _origin in self._propagation_data[timestamp]['origins']:
                    if _origin == origin:
                        return (self._propagation_data[timestamp]['origins'][origin], timestamp)

    def _monitor(self):
        ''''''
        while self._enabled:
            self._client.window.sleep_until_next_transition()
            last_heartbeat = self._client.heartbeat.last_heartbeat
            response_duration = self._client.get_window_duration() * self.wait_cycles # seconds
            spot_age = self.interval + response_duration

            # allow heartbeat responses before performing propagation analysis
            if last_heartbeat + response_duration < time.time():
                continue

            spots = self._client.spots.filter(age = spot_age)
            
            if len(spots) == 0:
                continue
                
            grids = {}
            origins = {}

            # build lists of snr data for each grid and origin callsign
            for spot in spots:
                if spot.grid is not None:
                    if spot.grid in grids:
                        grids[spot.grid].append(spot.snr)
                    else:
                        grids[spot.grid] = [spot.snr]

                if spot.origin is not None:
                    if spot.origin in origins:
                        origins[spot.origin].append(spot.snr)
                    else:
                        origins[spot.origin] = [spot.snr]

            # calculate median snr for each grid and origin callsign
            grids = {grid: statistics.median(snrs) for grid, snrs in grids.items()}
            origins = {origin: statistics.median(snrs) for origin, snrs in origin.items()}
            timestamp = int(time.time())
            
            with self._propagation_data_lock:
                self._propagation_data[timestamp] = {'grids': grids, 'origins': origins}
    
                # sort propagation data to find most recent data first when searching
                timestamps = self._propagation_data.keys()
                timestamps.sort(reverse = True)
                self._propagation_data = {timestamp: unsorted_data[timestamp] for timestamp in timetamps}
