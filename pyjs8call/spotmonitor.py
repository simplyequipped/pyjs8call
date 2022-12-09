from datetime import datetime, timezone
import threading
import time


class SpotMonitor:
    def __init__(self, client):
        self._client = client
        self._new_spots = []
        self._last_spot_update_timestamp = 0
        self._new_spot_callback = None
        self.spot_update_delay = 3 # seconds

        self._station_watch_list = []
        self._watch_callback = None

        monitor_thread = threading.Thread(target=self._monitor)
        monitor_thread.setDaemon(True)
        monitor_thread.start()

    def set_new_spot_callback(self, callback):
        self._new_spot_callback = callback

    def set_watch_callback(self, callback):
        self._watch_callback = callback

    def add_station_watch(self, station):
        if station not in self._station_watch_list:
            self._station_watch_list.append(station)

    def remove_station_watch(self, station):
        if station in self._station_watch_list:
            self._station_watch_list.remove(station)

    def _monitor(self):
        while self._client.online:
            self._new_spots = self._client.get_station_spots(since_timestamp = self._last_spot_update_timestamp)
            self._last_spot_update_timestamp = datetime.now(timezone.utc).timestamp()
            if len(self._new_spots) > 0:
                if self._new_spot_callback != None:
                    self._new_spot_callback(self._new_spots)

                if self._watch_callback != None:
                    for spot in self._new_spots:
                        if spot.origin in self._station_watch_list:
                            self._watch_callback(spot)

            time.sleep(self.spot_update_delay)
                    

