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
    
    MODE_MEDIAN = 'median'
    MODE_RAW    = 'raw'

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
        self.interval = self._client.settings.get_heartbeat_interval()
        self.max_data_age = 3 * (24 * 60 * 60) # 3 days
        self.mode = Propagation.MODE_RAW

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

    def get_dataset(self, age=30, count=0):
        '''Get propagation analysis dataset.

        If *age* is greater than zero, count is ignored.

        Args:
            age (int): propagation data age in minutes, defaults to 30
            count (int): number of data entries to return, defaults to 0 (zero)
            
        Returns:
            dict or None: dict structed as shown below, or None if no spot messages found
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

            *ORIGIN* is the origin callsign
            *GRID* is the grid square
            *SNR* is the median SNR of ORIGIN or GRID over the specified time interval
            *timestamp* is the local timestamp of the most recent spot of ORIGIN or GRID
        '''
        age *= 60 # minutes to seconds
        timestamps = self.get_data_timestamps()

        if len(timestamps) == 0:
            return None
        
        if age == 0:
            # age ignored, return *count* data entries
            if len(timestamps) > count:
                timestamps = timestamps[:count]
            
            return self.get_data_by_timestamp(timestamps)
            
        else:
            now = time.time()
            timestamps = [timestamp for timestamp in timestamps if (now - timestamp) <= age]
            return self.get_data_by_timestamp(timestamps)
        
    def get_dataset_median(self, age=30, count=0):
        '''Get median propagation analysis data.

        Args:
            age (int): maximum data age in minutes, defaults to 30
            count (int): number of datasets to return, defaults to 0 (zero)
            
        Returns:
            dict or None: dict structed as shown below, or None if no spot messages found
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

            *ORIGIN* is the origin callsign
            *GRID* is the grid square
            *SNR* is the median SNR of ORIGIN or GRID over the specified time interval
            *timestamp* is the local timestamp of the most recent spot of ORIGIN or GRID
        '''
        dataset = self.get_dataset(age, count)
        
        if dataset is None:
            return None
            
        grids = {}
        origins = {}

        # build lists of snr data for each grid and origin
        for entry in dataset['grids']:
            if entry[0] not in grids:
                grids[entry[0]] = {'snrs': [], 'timestamp': 0}
                
            grids[entry[0]]['snrs'].append(entry[1])

            # keep only most recent timestamp
            if entry[2] > grids[entry[0]]['timestamp']:
                grids[entry[0]]['timestamp'] = entry[2]

        for entry in dataset['origins']:
            if entry[0] not in origins:
                origins[entry[0]] = {'snrs': [], 'timestamp': 0}
                
            origins[entry[0]]['snrs'].append(entry[1])

            # keep only most recent timestamp
            if entry[2] > origins[entry[0]]['timestamp']:
                origins[entry[0]]['timestamp'] = entry[2]

        # calculate median snr for each grid and origin callsign
        grids = [(grid, round(statistics.median(data['snrs'])), data['timestamp']) for grid, data in grids.items()]
        origins = [(origin, round(statistics.median(data['snrs'])), data['timestamp']) for origin, data in origins.items()]
        
        return {'grids': grids, 'origins': origins}

    def get_all_grid_data(self, grid):
        '''Get all SNR data for specified grid square.

        *grid* must be at least four characters in length. If *grid* is longer than four characters it is truncated.
        
        Args:
            grid (str): grid square to find

        Returns:
            list: list of tuples like (GRID, SNR, timestamp)

            *GRID* is the grid square
            *SNR* is the SNR of GRID
            *timestamp* is the local timestamp
        '''
        grid = grid.upper()

        if len(grid) < 4:
            raise ValueError('Grid must be at least 4 characters')
        elif len(grid) > 4:
            grid = grid[:4]
            
        with self._propagation_data_lock:
            return [entry for entry in self._propagation_data['grids'] if entry[0] == grid]

    def get_recent_grid_snr(self, grid):
        '''Get recent SNR for specified grid square.

        *grid* must be at least four characters in length. If *grid* is longer than four characters it is truncated.
        
        Args:
            grid (str): grid square to find in most recent dataset

        Returns:
            tuple or None: tuple like (GRID, SNR, timestamp) if *grid* in most recent dataset, otherwise None

            *GRID* is the grid square
            *SNR* is the median SNR of GRID over the specified time interval
            *timestamp* is the local timestamp of the most recent spot of GRID
        '''
        grid = grid.upper()

        if len(grid) < 4:
            raise ValueError('Grid must be at least 4 characters')
        elif len(grid) > 4:
            grid = grid[:4]
            
        timestamps = self.get_data_timestamps()
            
        if len(timestamps) == 0:
            return None
                
        recent_grids = self.get_data_by_timestamp(timestamps[0])['grids']

        for entry in recent_grids:
            if entry[0] == grid:
                return entry
    
    def get_median_grid_snr(self, grid, age=30):
        '''Get median SNR for specified grid square.

        *grid* must be at least four characters in length. If *grid* is longer than four characters it is truncated.
        
        Args:
            grid (str): grid square to find
            age (int): maximum dataset age in minutes, defaults to 30

        Returns:
            tuple or None: tuple like (GRID, SNR, timestamp) if *grid* is found, otherwise None

            *GRID* is the grid square
            *SNR* is the median SNR of GRID over the specified time interval
            *timestamp* is the local timestamp of the most recent spot of GRID
        '''
        grid = grid.upper()

        if len(grid) < 4:
            raise ValueError('Grid must be at least 4 characters')
        elif len(grid) > 4:
            grid = grid[:4]
        
        dataset = self.get_dataset_median(age = age)

        for entry in dataset['grids']:
            if entry[0] == grid:
                return entry

    def get_all_origin_data(self, origin):
        '''Get all SNR data for specified origin callsign.

        Args:
            origin (str): origin callsign to find

        Returns:
            list: list of tuples like (ORIGIN, SNR, timestamp)

            *ORIGIN* is the origin callsign
            *SNR* is the SNR of ORIGIN
            *timestamp* is the local timestamp
        '''
        origin = origin.upper()
            
        with self._propagation_data_lock:
            return [entry for entry in self._propagation_data['origins'] if entry[0] == origin]

    def get_recent_origin_snr(self, origin):
        '''Get recent SNR for specified origin callsign.

        Args:
            origin (str): origin callsign to find in most recent dataset

        Returns:
            tuple or None: tuple like (ORIGIN, SNR, timestamp) if *origin* in most recent dataset, otherwise None

            *ORIGIN* is the origin callsign
            *SNR* is the median SNR of ORIGIN over the specified time interval
            *timestamp* is the local timestamp of the most recent spot of ORIGIN
        '''
        origin = origin.upper()
        timestamps = self.get_data_timestamps()
            
        if len(timestamps) == 0:
            return None
                
        recent_origins = self.get_data_by_timestamp(timestamps[0])['origins']

        for entry in recent_origins:
            if entry[0] == origin:
                return entry

    def get_median_origin_snr(self, origin, age=30):
        '''Get median SNR for specified origin callsign.

        Args:
            origin (str): origin callsign to find
            age (int): maximum dataset age in minutes, defaults to 30

        Returns:
            tuple or None: tuple like (ORIGIN, SNR, timestamp) if *origin* is found, otherwise None

            *ORIGIN* is the origin callsign
            *SNR* is the median SNR of ORIGIN over the specified time interval
            *timestamp* is the local timestamp of the most recent spot of ORIGIN
        '''
        origin = origin.upper()
        dataset = self.get_dataset_median(age = age)

        for entry in dataset['origins']:
            if entry[0] == origin:
                return entry

    def analyze_raw(self, age=None):
        '''Parse recent spot messages into median SNR dataset.

        Note: This function differs from other functions in this module since spot messages are processed instead of periodic propagation data.

        Args:
            age (int): Age of spot messages in minutes to include in dataset, defaults to *Propagation.interval*

        Returns:
            dict or None: dict structed as shown below, or None if no spot messages found
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

            *ORIGIN* is the origin callsign
            *GRID* is the grid square
            *SNR* is the median SNR of ORIGIN or GRID over the specified time interval
            *timestamp* is the local timestamp of the most recent spot of ORIGIN or GRID
        '''
        if age is None:
            age = self.interval

        age *= 60 # minutes to seconds
        spots = self._client.spots.filter(age = age)
        
        if len(spots) == 0:
            return None

        grids = []
        origins = []

        for spot in spots:
            if spot.grid not in (None, ''):
                grids.append( (spot.grid, spot.snr, spot.timestamp) )

            
            if spot.origin not in (None, ''):
                origins.append( (spot.origin, spot.snr, spot.timestamp) )

        return {'grids': grids, 'origins': origins}

    def analyze_median(self, age=None):
        '''Parse recent spot messages into median SNR dataset.

        Note: This function differs from other functions in this module since spot messages are processed instead of periodic propagation data.

        Args:
            age (int): Age of spot messages in minutes to include in dataset, defaults to *Propagation.interval*

        Returns:
            dict or None: dict structed as shown below, or None if no spot messages found
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

            *ORIGIN* is the origin callsign
            *GRID* is the grid square
            *SNR* is the median SNR of ORIGIN or GRID over the specified time interval
            *timestamp* is the local timestamp of the most recent spot of ORIGIN or GRID
        '''
        if age is None:
            age = self.interval

        age *= 60 # minutes to seconds
        spots = self._client.spots.filter(age = age)
        
        if len(spots) == 0:
            return None

        grids = {}
        origins = {}
        
        # build lists of snr data for each grid and origin
        for spot in spots:
            if spot.grid not in (None, ''):
                if spot.grid not in grids:
                    grids[spot.grid] = {'snrs': [], 'timestamp': 0}
                    
                grids[spot.grid]['snrs'].append(spot.snr)

                # keep only most recent timestamp
                if spot.timestamp > grids[spot.grid]['timestamp']:
                    grids[spot.grid]['timestamp'] = spot.timestamp

            if spot.origin not in (None, ''):
                if spot.origin not in origins:
                    origins[spot.origin] = {'snrs': [], 'timestamp': 0}
                    
                origins[spot.origin]['snrs'].append(spot.snr)

                # keep only most recent timestamp
                if spot.timestamp > origins[spot.origin]['timestamp']:
                    origins[spot.origin]['timestamp'] = spot.timestamp

        # calculate median snr for each grid and origin callsign
        grids = [(grid, round(statistics.median(data['snrs'])), data['timestamp']) for grid, data in grids.items()]
        origins = [(origin, round(statistics.median(data['snrs'])), data['timestamp']) for origin, data in origins.items()]
        
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

    def get_data_by_timestamp(self, timestamp):
        ''''''
        if isinstance(timestamp, int) or isinstance(timestamp, float):
            timestamps = [timestamp]
        elif isinstance(timestamp, list):
            timestamps = timestamp
        else:
            raise TypeError('timestamp must be of type int or list, {} given'.format(type(timestamp)))
        
        with self._propagation_data_lock:
            grids = [entry for entry in self._propagation_data['grids'] if entry[2] in timestamps]
            origins = [entry for entry in self._propagation_data['origins'] if entry[2] in timestamps]

        return {'grids': grids, 'origins': origins}

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
                self.interval = self._client.settings.get_heartbeat_interval()

            # one analysis per time interval
            if time.time() - self._last_analysis < self.interval * 60:
                continue

            if self.mode == Propagation.MODE_MEDIAN:
                dataset = self.analyze_median(self.interval)
            elif self.mode == Propagation.MODE_RAW:
                dataset = self.analyze_raw(self.interval)

            if dataset is None:
                continue

            timestamps = self.get_data_timestamps(cull = True)
    
            with self._propagation_data_lock:
                # cull old grid and origin data
                self._propagation_data['grids'] = [entry for entry in self._propagation_data['grids'] if entry[2] in timestamps]
                self._propagation_data['origins'] = [entry for entry in self._propagation_data['origins'] if entry[2] in timestamps]
                # record new interval data
                self._propagation_data['grids'].extend(dataset['grids'])
                self._propagation_data['origins'].extend(dataset['origins'])

            self._last_analysis = time.time()
            self._callback(dataset)
            
