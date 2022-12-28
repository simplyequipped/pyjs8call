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

'''Spot object for spotting heard stations.'''

__docformat__ = 'google'


import time


class Spot:
    '''Spot object for spotting heard stations.

    A station spot is constructed from a pyjs8call.message and copies attributes from the message.

    Attributes:
        msg_id (str): ID of the message
        origin (str): Origin callsign of the message
        destination (str): Destination callsign of the message
        freq (int): Dial frequency of the message in Hz
        offset (int): Offset frequency of the message in Hz
        time (float): UTC timestamp of the message
        timestamp (float): Local timestamp of the message
        grid (str): Grid square of the message
        snr (int): Signal-to-noise ratio of the message
        speed (str): JS8Call modem speed of the messsage
    '''
    def __init__(self, msg):
        '''Initialize spot.

        Args:
            msg (pyjs8call.message): Message used to construct the spot

        Returns:
            pyjs8call.spot: Constructed spot object
        '''
        self.msg_id = msg.id
        self.origin = msg.origin
        self.destination = msg.destination
        self.freq = msg.freq
        self.offset = msg.offset
        self.time = msg.time
        self.timestamp = msg.timestamp
        self.grid = msg.grid
        self.snr = msg.snr
        self.speed = msg.speed

    def __eq__(self, spot):
        '''Whether another spot is considered equal to self.

        There are two cases where spots are considered equal:
        - When both spots have the same UTC timestamps (literally the same spot)
        - When both spots have the same origin, offset frequency, and snr (same station event reported by differnt JS8Call API messages at slightly differnt times) 

        Args:
            spot (pyjs8call.spot): Spot to compare

        Returns:
            bool: Whether the two spots are considered equal
        '''
        # comparing origin, offset, and snr allows equating the same message sent more than once
        # from the js8call application (likely as different message types) at slightly different
        # times (milliseconds apart)
        if (
            self.time == spot.time or
            (spot.origin == self.origin and spot.offset == self.offset and spot.snr == self.snr)
        ):
            return True
        else:
            return False

    def __lt__(self, spot):
        '''Whether another spot is less than self.

        UTC timestamps are compared.

        Args:
            spot (pyjs8call.spot): Spot to compare

        Returns:
            bool: Whether self.time is less than the specified spot.time 
        '''
        return bool(self.time < spot.time)

    def __gt__(self, spot):
        '''Whether another spot is greater than self.

        UTC timestamps are compared.

        Args:
            spot (pyjs8call.spot): Spot to compare

        Returns:
            bool: Whether self.time is greater than the specified spot.time 
        '''
        return bool(self.time > spot.time)

    def age(self):
        '''Age of the spot.

        Returns:
            float: Spot age in seconds
        '''
        return time.time() - self.timestamp

