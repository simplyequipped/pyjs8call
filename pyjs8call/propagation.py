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

Set `client.callback.propagation` to receive new propagation analysis datasets.
'''

__docformat__ = 'google'


import time
import threading
import statistics

from pyjs8call import Message


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
        self._propagation_data = {'grids': [], 'origins': []}
        self._propagation_data_lock = threading.Lock()
        
        # default to heartbeat interval
        self.use_heartbeat_interval = True
        self.interval = self._client.settings.get_heartbeat_interval() * 60 # minutes to seconds
        self.max_data_age = 3 * (24 * 60 * 60) # 3 days

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
            dict: {'grids': {'GRID': SNR, ...}, 'origins': {'ORIGIN': SNR, ...}}

            Returns None if there is no propagation data.
        '''
        age *= 60 # minutes to seconds

        with self._propagation_data_lock:
            if len(self._propagation_data) == 0:
                return None
            
            if age == 0:
                # age ignored, return *count* data sets
                if len(self._propagation_data) <= count:
                    return self._propagation_data
                    
                timestamps = list(self._propagation_data.keys())[:count]
                return {timestamp: value for timestamp, value in self._propagation_data.items() if timestamp in timestamps}
            else:
                return {timestamp: value for timestamp, value in self._propagation_data.items() if timestamp > time.time() - age}
        
    def get_data_median(self, age=30, count=0):
        '''Get median propagation analysis data.

        Args:
            age (int): maximum data set age in minutes, defaults to 30
            count (int): number of data sets to return, defaults to 1
            
        Returns:
            dict: {'grids': {'GRID': SNR, ...}, 'origins': {'ORIGIN': SNR, ...}}

            Returns None if there is no propagation data.
        '''
        data_sets = self.get_data(age, count)
        
        if data_sets is None:
            return None
        
        grids = {}
        origins = {}

        # build lists of snr data for each grid and origin callsign
        for timestamp, data in data_sets.items():
            for grid, snr in data['grids'].items():
                if grid in grids:
                    grids[grid].append(snr)
                else:
                    grids[grid] = [snr]

            for origin, snr in data['origins'].items():
                if origin in origins:
                    origins[origin].append(snr)
                else:
                    origins[origin] = [snr]
                        
        # calculate median snr for each grid and origin callsign
        grids = {grid: round(statistics.median(snrs)) for grid, snrs in grids.items()}
        origins = {origin: round(statistics.median(snrs)) for origin, snrs in origins.items()}
        return {'grids': grids, 'origins': origins}

    def get_grid_snr(self, grid):
        '''Get recent SNR for specified grid square.

        *grid* must be at least four characters in length. If *grid* is longer than four characters it is truncated.
        
        Args:
            grid (str): grid square to find in most recent dataset

        Returns:
            tuple or None: tuple like (GRID, SNR, timestamp) if *grid* in most recent dataset, otherwise None
        '''
        if len(grid) < 4:
            raise ValueError('Grid must be at least 4 characters')
        elif len(grid) > 4:
            grid = grid[:4]
            
        with self._propagation_data_lock:
            timestamps = self.get_data_timestamps()
            
            if len(timestamps) == 0:
                return None

            recent_timestamp = timestamps[0]
            recent_grids = [entry for entry in self._propagation_data['grids'] if entry[2] == recent_timestamp]

            for entry in recent_grids:
                if entry[0] == grid:
                    return entry
    
    def get_origin_snr(self, origin):
        '''Get recent SNR for specified origin callsign.

        Args:
            origin (str): origin callsign to find in most recent dataset

        Returns:
            tuple or None: tuple like (ORIGIN, SNR, timestamp) if *origin* in most recent dataset, otherwise None
        '''
        with self._propagation_data_lock:
            timestamps = self.get_data_timestamps()
            
            if len(timestamps) == 0:
                return None

            recent_timestamp = timestamps[0]
            recent_origins = [entry for entry in self._propagation_data['origins'] if entry[2] == recent_timestamp]

            for entry in recent_origins:
                if entry[0] == origin:
                    return entry

    def analyze(self, age=None):
        '''Parse recent spot messages into median SNR dataset.

        Args:
            age (int): Age of spot messages in minutes to include in dataset, defaults to *Propagation.interval*

        Returns:
            dict or None: dict structed as shown below, or None no spot messages found
            ```
            {
            'grids':
                [
                    (GRID, SNR, timestamp),
                    ...
                ],
            'origins':
                [
                    (ORIGIN, SNR, timestamp),
                    ...
                ]
            }
            ```
        '''
        if age is None:
            age = self.interval

        age *= 60 # minutes to seconds
        spots = self._client.spots.filter(age = age)
        
        if len(spots) == 0:
            return None
            
        grids = {}
        origins = {}

        # build lists of snr data for each grid and origin callsign
        for spot in spots:
            if spot.grid not in (None, ''):
                if spot.grid in grids:
                    grids[spot.grid].append(spot.snr)
                else:
                    grids[spot.grid] = [spot.snr]

            if spot.origin not in (None, ''):
                if spot.origin in origins:
                    origins[spot.origin].append(spot.snr)
                else:
                    origins[spot.origin] = [spot.snr]

        # calculate median snr for each grid and origin callsign
        timestamp = int(time.time())
        grids = [(grid, round(statistics.median(snrs)), timestamp) for grid, snrs in grids.items()]
        origins = [(origin, round(statistics.median(snrs)), timestamp) for origin, snrs in origins.items()]
        return {'grids': grids, 'origins': origins}

    def get_data_timestamps(self, cull=False):
        '''Get unique timestamps in propagation data.
        '''
        timestamps = []
        now = time.time()
        
        with self._propagation_data_lock:
            for entry in self._propagation_data['grids']:
                timestamp = entry[2]
                if timestamp not in timestamps:
                    if cull and timestamp < (now - self.max_data_age):
                        continue
                    timestamps.append(timestamp)
            
            for entry in self._propagation_data['origins']:
                timestamp = entry[2]
                if timestamp not in timestamps:
                    if cull and timestamp < (now - self.max_data_age):
                        continue
                    timestamps.append(timestamp)

        timestamps.sort(reverse = True)
        return timestamps

    def _callback(self, dataset):
        '''Call new propagation dataset callback function.'''
        if self._client.callback.propagation is not None:
            thread = threading.Thread(target = self._client.callback.propagation, args=(dataset,))
            thread.daemon = True
            thread.start()

    def _monitor(self):
        '''Monitor time interval and perform propagation analysis.'''
        while self._enabled:
            self._client.window.sleep_until_next_transition()
            
            if not self._enabled:
                return

            if self._paused:
                continue

            if self.use_heartbeat_interval:
                self.interval = self._client.settings.get_heartbeat_interval() * 60 # minutes to seconds

            # one analysis per time interval
            now = time.time()
            if self._last_analysis + self.interval > now:
                continue

            dataset = self.analyze(self.interval)

            if dataset is None:
                continue

            timestamps = self.get_data_timestamps(cull = True)
    
            with self._propagation_data_lock:
                # cull old grid and origin data
                self._propagation_data['grids'] = [entry for entry in self._propagation_data['grids'] if entry[2] in timestamps]
                self._propagation_data['origins'] = [entry for entry in self._propagation_data['origins'] if entry[2] in timestamps]
                # record new interval data
                self._propagation_data['grids'].append(dataset['grids'])
                self._propagation_data['origins'].append(dataset['origins'])

            self._last_analysis = time.time()
            self._callback(dataset)
            
