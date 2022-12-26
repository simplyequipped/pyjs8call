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

__docformat__ = 'google'


import time


class Spot:
    def __init__(self, msg):
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
        return bool(self.time < spot.time)

    def __gt__(self, spot):
        return bool(self.time > spot.time)

    def age(self):
        return time.time() - self.timestamp

