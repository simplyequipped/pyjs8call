import time
import threading

import pyjs8call

class OffsetMonitor:
    def __init__(self, client):
        self.client = client
        self.min_offset = 1000
        self.max_offset = 2500
        self.enabled = False

        self.enable()

    def enable(self):
        if self.enabled:
            return None

        self.enabled = True
        # current auto offset
        self.offset = self.client.get_offset()
        # last auto offset
        self.previous_offset = self.offset
        # offset before auto offset was enabled
        self.original_offset = self.offset

        monitor_thread = threading.Thread(target=self._monitor)
        monitor_thread.setDaemon(True)
        monitor_thread.start()

    def disable(self):
        if not self.enabled:
            return None

        self.enabled = False
        # reset offset
        self.client.set_offset(self.original_offset)

    def do_change_offset(self, offset):
        # half of the max bandwidth (160Hz @ turbo speed)
        half_bw = 80

        # station offset equals the current offset
        if offset == self.offset:
            return True
        # station overlapping from just below the current offset
        elif offset < self.offset and (offset + half_bw) > (self.offset - half_bw):
            return True
        # station overlapping from just above the current offset
        elif offset > self.offset and (offset - half_bw) < (self.offset + half_bw):
            return True
        else:
            return False

    def process_activity(self, activity):
        offsets = [station['offset'] for station in activity]
        offsets.sort()
        offset_data = []

        for i in range(len(offsets)):
            # station offset outide min/max offset range
            if offsets[i] < self.min_offset or offset[i] > self.max_offset:
                continue

            if i == 0:
                previous_offset = self.min_offset
            else:
                previous_offset = offsets[i-1]

            if i == len(offsets):
                next_offset = self.max_offset
            else:
                next_offset = offsets[i+1]

            distance = offsets[i] - self.offset
            offset = offsets[i]

            data = {
                'offset' : offset,
                'distance' : distance,
                'previous' : previous_offset,
                'next' : next_offset,
            }

            offset_data.append(data)

        offset_data.sort(key=lambda offset: abs(offset['distance']))

        return offset_data

    def find_offset_data(self, offset, offsets):
        for o in offsets:
            if o['offset'] == offset:
                return o

    def search_up(self, offset, offsets):
        # find the next offset pair with at least 200Hz in betweeen
        # 160Hz (max bandwidth in turbo mode) * 125% = 200Hz
        offset_data = self.find_offset_data(offset)
        next_offset = offset_data['next']

        while (next_offset - offset) < 200 and next_offset < self.max_offset:
            offset_data = self.find_offset_data(next_offset)
            next_offset = offset_data['next']

        # quit searching if the last offset pair doesn't suit either
        if (next_offset - offset) < 200 and next_offset < self.max_offset:
            return None
        
        # return the next available offset
        return offset_data['offset'] + 200
            
    def search_down(self, offset, offsets):
        # find the next offset pair with at least 200Hz in betweeen
        # 160Hz (max bandwidth in turbo mode) * 125% = 200Hz
        offset_data = self.find_offset_data(offset)
        previous_offset = offset_data['previous']

        while (offset - previous_offset) < 200 and previous_offset > self.min_offset:
            offset_data = self.find_offset_data(previous_offset)
            previous_offset = offset_data['previous']

        # quit searching if the last offset pair doesn't suit either
        if (offset - previous_offset) < 200 and previous_offset > self.min_offset:
            return None
        
        # return the next available offset
        return offset_data['offset'] - 200
            
    def _monitor(self):
        while self.client.online and self.enabled:
            # wait until the end of the tx window
            delay = self.client.window_monitor.next_window_end() - time.time()

            # next window end = 0 until first tx frame
            if delay < 0:
                delay = 5

            time.sleep(delay)

            if not self.enabled:
                break

            # get spots in the last 3 minutes
            timestamp = time.time() - (60 * 3)
            activity = self.client.get_station_spots(since_timestamp = timestamp) 

            if len(activity) == 0:
                continue

            offsets = self.process_activity(activity)
            new_offset = None

            for offset in offsets:
                if self.do_change_offset(offset['offset']):
                    # first search the opposite direction of the last offset change
                    if self.previous_offset > self.offset:
                        # search up for a free offset
                        new_offset = search_up(offset, offsets)

                        # search up failed, search down for a free offset
                        if new_offset == None:
                            new_offset = search_down(offset, offsets)

                        # searching up and down both failed, abort offset change
                        if new_offset == None:
                            break
                    
                    # first search the opposite direction of the last offset change
                    elif self.previous_offset < self.offset:
                        # search down for a free offset
                        new_offset = search_down(offset, offsets)

                        # search down failed, search up for a free offset
                        if new_offset == None:
                            new_offset = search_up(offset, offsets)

                        # searching up and down both failed, abort offset change
                        if new_offset == None:
                            break

            if new_offset != None:
                self.previous_offset = self.offset
                self.offset = new_offset




                








