from datetime import datetime, timezone


class Spot:
    def __init__(self, msg):
        self.msg_id = msg.id
        self.origin = msg.origin
        self.destination = msg.destination
        self.freq = msg.freq
        self.offset = msg.offset
        self.time = msg.time
        self.grid = self.grid
        self.snr = self.snr
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
        now = datetime.now(timezone.utc).timestamp()
        return now - self.time

