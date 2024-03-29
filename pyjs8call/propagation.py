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

'''Propagation analysis based on spot data.'''

__docformat__ = 'google'


import time
import statistics
from datetime import datetime


class Propagation:
    '''Parse spots into propagation data.'''

    def __init__(self, client):
        '''Initialize propagation.

        Args:
            client (pyjs8call.client): Parent client object

        Returns:
            pyjs8call.propagation: Constructed propagation object
        '''
        self._client = client
    
    def grids_dataset(self, max_age=30, min_age=0, start_time=None, end_time=None):
        '''Parse spot messages into propagation dataset for grid squares.

        If *max_age* and *min_age* are zero, all stored spots are used to build the dataset.

        *start_time* and *end_time* can be a Unix timestamp (like *time.time()*) or a *datetime.datetime* object. If *start_time* is set, the dataset age will be calculated based on *start_time* and *end_time*. If *start_time* is set and *end_time* is not set, the minimum age is set to zero.
        
        Args:
            max_age (int): Maximum age of spot messages in minutes, defaults to 30
            min_age (int): Minimum age of spot messages in minutes, defaults to 0
            start_time (float, datetime.datetime): Dataset starting time, defaults to None
            end_time (float, datetime.datetime): Dataset ending time, defaults to None

        Returns:
            list: `[ (GRID, SNR, timestamp), ... ]`

            *GRID* is the grid square of the spot
            *SNR* is the SNR of the spot
            *timestamp* is the local timestamp of when the spot occured
        '''
        if start_time is not None:
            if isinstance(start_time, datetime):
                start_time = datetime.timestamp(start_time)
                
            max_age = time.time() - start_time
            
            if end_time is None:
                min_age = 0
            else:
                if isinstance(end_time, datetime):
                    end_time = datetime.timestamp(end_time)
                
                min_age = time.time() - end_time
        else:
            min_age *= 60 # minutes to seconds
            max_age *= 60 # minutes to seconds
            
        spots = self._client.spots.filter(age = max_age)
        dataset = []

        for spot in spots:
            if spot.age() > min_age and spot.grid not in (None, ''):
                dataset.append( (spot.grid, spot.snr, spot.timestamp) )

        return dataset

    def grids_median_dataset(self, max_age=30, min_age=0, start_time=None, end_time=None):
        '''Parse spot messages into median propagation dataset for grid squares.

        If *max_age* and *min_age* are zero, all stored spots are used to build the dataset.

        *start_time* and *end_time* can be a Unix timestamp (like *time.time()*) or a *datetime.datetime* object. If *start_time* is set, the dataset age will be calculated based on *start_time* and *end_time*. If *start_time* is set and *end_time* is not set, the minimum age is set to zero.
        
        Args:
            max_age (int): Maximum age of spot messages in minutes, defaults to 30
            min_age (int): Minimum age of spot messages in minutes, defaults to 0
            start_time (float, datetime.datetime): Dataset starting time, defaults to None
            end_time (float, datetime.datetime): Dataset ending time, defaults to None

        Returns:
            list: `[ (GRID, SNR, timestamp), ... ]`

            *GRID* is the grid square of the spot
            *SNR* is the median SNR of GRID spots over the specified time period
            *timestamp* is the most recent local timestamp of GRID spots
        '''
        if start_time is not None:
            if isinstance(start_time, datetime):
                start_time = datetime.timestamp(start_time)
                
            max_age = time.time() - start_time
            
            if end_time is None:
                min_age = 0
            else:
                if isinstance(end_time, datetime):
                    end_time = datetime.timestamp(end_time)
                
                min_age = time.time() - end_time
        else:
            min_age *= 60 # minutes to seconds
            max_age *= 60 # minutes to seconds
            
        spots = self._client.spots.filter(age = max_age)
        dataset = {}

        for spot in spots:
            if spot.age() > min_age and spot.grid not in (None, ''):
                if spot.grid not in dataset:
                    dataset[spot.grid] = {'snrs': [], 'timestamp': 0}
                    
                dataset[spot.grid]['snrs'].append(spot.snr)

                # keep only most recent timestamp
                if spot.timestamp > dataset[spot.grid]['timestamp']:
                    dataset[spot.grid]['timestamp'] = spot.timestamp

        return [(grid, round(statistics.median(data['snrs'])), data['timestamp']) for grid, data in dataset.items()]

    def grid_median_snr(self, grid, max_age=30, min_age=0, start_time=None, end_time=None):
        '''Parse spot messages into median SNR for specified grid square.

        If *max_age* and *min_age* are zero, all stored spots are used to build the dataset.

        *start_time* and *end_time* can be a Unix timestamp (like *time.time()*) or a *datetime.datetime* object. If *start_time* is set, the dataset age will be calculated based on *start_time* and *end_time*. If *start_time* is set and *end_time* is not set, the minimum age is set to zero.
        
        Args:
            grid (str): 4 or 6 character grid square to match
            max_age (int): Maximum age of spot messages in minutes, defaults to 30
            min_age (int): Minimum age of spot messages in minutes, defaults to 0
            start_time (float, datetime.datetime): Dataset starting time, defaults to None
            end_time (float, datetime.datetime): Dataset ending time, defaults to None

        Returns:
            tuple: `(SNR, timestamp)`

            *SNR* is the median SNR of *grid* spots over the specified time period
            *timestamp* is the most recent local timestamp of *grid* spots
        '''
        if start_time is not None:
            if isinstance(start_time, datetime):
                start_time = datetime.timestamp(start_time)
                
            max_age = time.time() - start_time
            
            if end_time is None:
                min_age = 0
            else:
                if isinstance(end_time, datetime):
                    end_time = datetime.timestamp(end_time)
                
                min_age = time.time() - end_time
        else:
            min_age *= 60 # minutes to seconds
            max_age *= 60 # minutes to seconds
            
        spots = self._client.spots.filter(grid = grid, age = max_age)
        snrs = []
        timestamp = 0

        for spot in spots:
            if spot.age() > min_age:
                snrs.append(spot.snr)

                # keep only most recent timestamp
                if spot.timestamp > timestamp:
                    timestamp = spot.timestamp

        return (round(statistics.median(snrs)), timestamp)
        
    def origins_dataset(self, max_age=30, min_age=0, start_time=None, end_time=None):
        '''Parse spot messages into propagation dataset for origin callsigns.

        If *max_age* and *min_age* are zero, all stored spots are used to build the dataset.

        *start_time* and *end_time* can be a Unix timestamp (like *time.time()*) or a *datetime.datetime* object. If *start_time* is set, the dataset age will be calculated based on *start_time* and *end_time*. If *start_time* is set and *end_time* is not set, the minimum age is set to zero.
        
        Args:
            max_age (int): Maximum age of spot messages in minutes, defaults to 30
            min_age (int): Minimum age of spot messages in minutes, defaults to 0
            start_time (float, datetime.datetime): Dataset starting time, defaults to None
            end_time (float, datetime.datetime): Dataset ending time, defaults to None

        Returns:
            list: `[ (ORIGIN, SNR, timestamp), ... ]`

            *ORIGIN* is the origin callsign of the spot
            *SNR* is the SNR of the spot
            *timestamp* is the local timestamp of when the spot occured
        '''
        if start_time is not None:
            if isinstance(start_time, datetime):
                start_time = datetime.timestamp(start_time)
                
            max_age = time.time() - start_time
            
            if end_time is None:
                min_age = 0
            else:
                if isinstance(end_time, datetime):
                    end_time = datetime.timestamp(end_time)
                
                min_age = time.time() - end_time
        else:
            min_age *= 60 # minutes to seconds
            max_age *= 60 # minutes to seconds
            
        spots = self._client.spots.filter(age = max_age)
        dataset = []

        for spot in spots:
            if spot.age() > min_age and spot.origin not in (None, ''):
                dataset.append( (spot.origin, spot.snr, spot.timestamp) )

        return dataset

    def origins_median_dataset(self, max_age=30, min_age=0, start_time=None, end_time=None):
        '''Parse spot messages into median propagation dataset for origin callsigns.

        If *max_age* and *min_age* are zero, all stored spots are used to build the dataset.

        *start_time* and *end_time* can be a Unix timestamp (like *time.time()*) or a *datetime.datetime* object. If *start_time* is set, the dataset age will be calculated based on *start_time* and *end_time*. If *start_time* is set and *end_time* is not set, the minimum age is set to zero.
        
        Args:
            max_age (int): Maximum age of spot messages in minutes, defaults to 30
            min_age (int): Minimum age of spot messages in minutes, defaults to 0
            start_time (float, datetime.datetime): Dataset starting time, defaults to None
            end_time (float, datetime.datetime): Dataset ending time, defaults to None

        Returns:
            list: `[ (ORIGIN, SNR, timestamp), ... ]`

            *ORIGIN* is the origin callsign of the spot
            *SNR* is the median SNR of ORIGIN spots over the specified time period
            *timestamp* is the most recent local timestamp of ORIGIN spots
        '''
        if start_time is not None:
            if isinstance(start_time, datetime):
                start_time = datetime.timestamp(start_time)
                
            max_age = time.time() - start_time
            
            if end_time is None:
                min_age = 0
            else:
                if isinstance(end_time, datetime):
                    end_time = datetime.timestamp(end_time)
                
                min_age = time.time() - end_time
        else:
            min_age *= 60 # minutes to seconds
            max_age *= 60 # minutes to seconds
            
        spots = self._client.spots.filter(age = max_age)
        dataset = {}

        for spot in spots:
            if spot.age() > min_age and spot.origin not in (None, ''):
                if spot.origin not in dataset:
                    dataset[spot.origin] = {'snrs': [], 'timestamp': 0}
                    
                dataset[spot.origin]['snrs'].append(spot.snr)

                # keep only most recent timestamp
                if spot.timestamp > dataset[spot.origin]['timestamp']:
                    dataset[spot.origin]['timestamp'] = spot.timestamp

        return [(origin, round(statistics.median(data['snrs'])), data['timestamp']) for origin, data in dataset.items()]

    def origin_median_snr(self, origin, max_age=30, min_age=0, start_time=None, end_time=None):
        '''Parse spot messages into median SNR for specified origin callsign.

        If *max_age* and *min_age* are zero, all stored spots are used to build the dataset.

        *start_time* and *end_time* can be a Unix timestamp (like *time.time()*) or a *datetime.datetime* object. If *start_time* is set, the dataset age will be calculated based on *start_time* and *end_time*. If *start_time* is set and *end_time* is not set, the minimum age is set to zero.
        
        Args:
            origin (str): Origin callsign to match
            max_age (int): Maximum age of spot messages in minutes, defaults to 30
            min_age (int): Minimum age of spot messages in minutes, defaults to 0
            start_time (float, datetime.datetime): Dataset starting time, defaults to None
            end_time (float, datetime.datetime): Dataset ending time, defaults to None

        Returns:
            tuple: `(SNR, timestamp)`

            *SNR* is the median SNR of *origin* spots over the specified time period
            *timestamp* is the most recent local timestamp of *origin* spots
        '''
        if start_time is not None:
            if isinstance(start_time, datetime):
                start_time = datetime.timestamp(start_time)
                
            max_age = time.time() - start_time
            
            if end_time is None:
                min_age = 0
            else:
                if isinstance(end_time, datetime):
                    end_time = datetime.timestamp(end_time)
                
                min_age = time.time() - end_time
        else:
            min_age *= 60 # minutes to seconds
            max_age *= 60 # minutes to seconds
            
        spots = self._client.spots.filter(origin = origin, age = max_age)
        snrs = []
        timestamp = 0

        for spot in spots:
            if spot.age() > min_age:
                snrs.append(spot.snr)

                # keep only most recent timestamp
                if spot.timestamp > timestamp:
                    timestamp = spot.timestamp

        return (round(statistics.median(snrs)), timestamp)
