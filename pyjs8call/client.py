import time
import atexit
import threading

import pyjs8call
from pyjs8call import Message



class Client:
    
    def __init__(self, host='127.0.0.1', port=2442, headless=False, config_path=None):
        self.host = host
        self.port = port
        self.headless = headless
        self.clean_directed_text = True
        self.monitor_directed_tx = True
        self.online = False

        # delay between setting value and getting updated value
        self._set_get_delay = 0.1 # seconds

        # initialize the config file handler
        self.config = pyjs8call.ConfigHandler(config_path = config_path)

        self.callbacks = {
            Message.RX_DIRECTED: [],
        }

        # stop application and client at exit
        atexit.register(self.stop)
        
    def set_config_profile(self, profile):
        if profile not in self.config.get_profile_list():
            raise Exception('Config profile ' + profile + ' does not exist')

        # set the profile as active
        self.config.change_profile(profile)

        # restart the app to apply new profile if already running
        if self.online:
            self.restart()

    def start(self, debug=False):
        # enable TCP connection
        self.config.set('Configuration', 'TCPEnabled', 'true')
        self.config.set('Configuration', 'TCPServer', self.host)
        self.config.set('Configuration', 'TCPServerPort', str(self.port))
        self.config.set('Configuration', 'AcceptTCPRequests', 'true')
        self.config.write()

        # start js8call app and TCP interface
        self.js8call = pyjs8call.JS8Call(self, self.host, self.port, headless=self.headless)
        self.online = True

        if debug:
            self.js8call._debug = True

        # initialize rx thread
        rx_thread = threading.Thread(target=self._rx)
        rx_thread.setDaemon(True)
        rx_thread.start()

        time.sleep(0.5)

        # start station spot monitor
        self.spot_monitor = pyjs8call.SpotMonitor(self)
        # start tx window monitor
        self.window_monitor = pyjs8call.WindowMonitor(self)
        # start auto offset monitor
        self.offset_monitor = pyjs8call.OffsetMonitor(self)
        # start tx monitor
        self.tx_monitor = pyjs8call.TxMonitor(self)

    def stop(self):
        self.online = False
        try:
            self.js8call.stop()
        except:
            pass

    def restart(self):
        self.stop()
        self.js8call._socket.close()
        time.sleep(1)
        self.start(debug = self.js8call._debug)

    def register_rx_callback(self, callback, message_type=Message.RX_DIRECTED):
        if message_type not in self.callbacks.keys():
            self.callbacks[message_type] = []

        self.callbacks[message_type].append(callback)

    def _rx(self):
        while self.online:
            msg = self.js8call.get_next_message()

            if msg != None and msg.type in self.callbacks.keys():
                for callback in self.callbacks[msg.type]:
                    callback(msg)

            time.sleep(0.1)

    def connected(self):
        return self.js8call.connected

    def send_message(self, message):
        # msg.type = Message.TX_SEND_MESSAGE by default
        msg = Message(value = message)
        self.js8call.send(msg)
        return msg
    
    def send_directed_message(self, destination, message):
        # msg.type = Message.TX_SEND_MESSAGE by default
        msg = Message(destination = destination, value = message)

        if self.monitor_directed_tx:
            self.tx_monitor.monitor(msg)

        self.js8call.send(msg)
        return msg

    def clean_rx_message_text(self, msg):
        if msg == None:
            return None
        elif msg.value == None or msg.value == '':
            # nothing to clean
            return msg
        # already cleaned
        elif msg.value != msg.text:
            return msg

        message = msg.value
        # remove origin callsign
        message = message.split(':')[1].strip()
        # remove destination callsign or group
        message = ' '.join(message.split(' ')[1:])
        # strip remaining spaces and end-of-message symbol
        message = message.strip(' ' + Message.EOM)

        msg.set('text', message)
        return msg
    
    def send_heartbeat(self, grid=None):
        if grid == None:
            grid = self.get_station_grid()
        if len(grid) > 4:
            grid = grid[:4]

        return self.send_message('@HB HEARTBEAT ' + grid)

    def send_aprs_grid(self, grid):
        return self.send_message('@APRSIS GRID ' + grid)

    def send_aprs_sms(self, phone, message):
        phone = str(phone).replace('-', '')
        return self.send_message('@APRSIS CMD :SMSGATE   :@' + phone + ' ' + message)
    
    def send_aprs_email(self, email, message):
        return self.send_message('@APRSIS CMD :EMAIL-2   :' + email + ' ' + message)
    
    # freq in kHz
    def send_aprs_pota_spot(self, park, freq, mode, message):
        callsign = self.get_callsign()
        return self.send_message('@APRSIS CMD :POTAGW   :' + callsign + ' ' + park + ' ' + str(freq) + ' ' + mode + ' ' + message)
    
    def get_inbox_messages(self):
        msg = Message()
        msg.type = Message.INBOX_GET_MESSAGES
        self.js8call.send(msg)
        messages = self.js8call.watch('inbox')
        return messages

    def send_inbox_message(self, destination, message):
        value = destination + ' MSG ' + message
        return self.send_message(value)

    def forward_inbox_message(self, destination, forward, message):
        value = destination + ' MSG TO:' + forward + ' ' + message
        return self.send_message(value)

    def store_local_inbox_message(self, destination, message):
        msg = Message()
        msg.type = Message.INBOX_STORE_MESSAGE
        msg.params['CALLSIGN'] = destination
        msg.params['TEXT'] = message
        self.js8call.send(msg)
        time.sleep(self._set_get_delay)
        return self.get_inbox_messages()

    def query_call(self, destination, callsign):
        message = 'QUERY CALL ' + callsign + '?'
        return self.send_directed_message(destination, message)

    def query_messages(self, destination):
        return self.send_directed_message(destination, 'QUERY MSGS')

    def query_message_id(self, destination, msg_id):
        message = 'QUERY MSG ' + msg_id
        return self.send_directed_message(destination, message)

    def query_heard(self, destination):
        return self.send_directed_message(destination, 'HEARD?')

    # destinations is a list of callsigns in order (first relay, second relay, ...)
    def relay_message(self, destinations, message):
        destinations = '>'.join(destinations)
        return self.send_directed_message(destinations, message)

    def get_station_spots(self, station=None, max_age=0):
        spots = []
        for spot in self.js8call.spots:
            if (max_age == 0 or spot.age() < max_age) and (station == None or station == spot.origin):
                spots.append(spot)

        return spots

    def get_freq(self):
        msg = Message()
        msg.type = Message.RIG_GET_FREQ
        self.js8call.send(msg)
        freq = self.js8call.watch('dial')
        return freq

    def get_offset(self):
        msg = Message()
        msg.type = Message.RIG_GET_FREQ
        self.js8call.send(msg)
        offset = self.js8call.watch('offset')
        return offset

    def set_freq(self, freq):
        msg = Message()
        msg.type = Message.RIG_SET_FREQ
        msg.params['DIAL'] = freq
        msg.params['OFFSET'] = self.js8call.state['offset']
        self.js8call.send(msg)
        time.sleep(self._set_get_delay)
        return self.get_freq()

    def set_offset(self, offset):
        msg = Message()
        msg.type = Message.RIG_SET_FREQ
        msg.params['DIAL'] = self.js8call.state['freq']
        msg.params['OFFSET'] = offset
        self.js8call.send(msg)
        time.sleep(self._set_get_delay)
        return self.get_offset()

    def get_station_callsign(self):
        msg = Message()
        msg.type = Message.STATION_GET_CALLSIGN
        self.js8call.send(msg)
        callsign = self.js8call.watch('callsign')
        return callsign

    def set_station_callsign(self, callsign):
        callsign = callsign.upper()

        if len(callsign) <= 9 and any(char.isdigit() for char in callsign):
            self.config.set('Configuration', 'MyCall', callsign)
            # restart the app to apply new config if already running
            if self.online:
                freq = self.get_freq()
                offset = self.get_offset()

                self.stop()
                time.sleep(0.25)
                self.start()

                self.set_offset(offset)
                self.set_freq(freq)
        else:
            raise ValueError('callsign must be <= 9 characters in length and contain at least 1 number')

    def get_station_grid(self):
        msg = Message()
        msg.type = Message.STATION_GET_GRID
        self.js8call.send(msg)
        grid = self.js8call.watch('grid')
        return grid

    def set_station_grid(self, grid):
        grid = grid.upper()
        msg = Message()
        msg.type = Message.STATION_SET_GRID
        msg.value = grid
        self.js8call.send(msg)
        time.sleep(self._set_get_delay)
        return self.get_station_grid()

    def get_station_info(self):
        msg = Message()
        msg.type = Message.STATION_GET_INFO
        self.js8call.send(msg)
        info = self.js8call.watch('info')
        return info

    def set_station_info(self, info):
        msg = Message()
        msg.type = Message.STATION_SET_INFO
        msg.value = info
        self.js8call.send(msg)
        time.sleep(self._set_get_delay)
        return self.get_station_info()

    def get_call_activity(self):
        msg = Message()
        msg.type = Message.RX_GET_CALL_ACTIVITY
        self.js8call.send(msg)
        call_activity = self.js8call.watch('call_activity')
        return call_activity

    def get_band_activity(self):
        msg = Message()
        msg.type = Message.RX_GET_BAND_ACTIVITY
        self.js8call.send(msg)
        band_activity = self.js8call.watch('band_activity')
        return band_activity

    def get_selected_call(self):
        msg = Message()
        msg.type = Message.RX_GET_SELECTED_CALL
        self.js8call.send(msg)
        selected_call = self.js8call.watch('selected_call')
        return selected_call

    def get_rx_text(self):
        msg = Message()
        msg.type = Message.RX_GET_TEXT
        self.js8call.send(msg)
        rx_text = self.js8call.watch('rx_text')
        return rx_text
        
    def get_tx_text(self):
        msg = Message()
        msg.type = Message.TX_GET_TEXT
        self.js8call.send(msg)
        tx_text = self.js8call.watch('tx_text')
        return tx_text

    def set_tx_text(self, text):
        msg = Message()
        msg.type = Message.TX_SET_TEXT
        msg.value = text
        time.sleep(self._set_get_delay)
        return self.get_tx_text()

    # speed: slow, normal, fast, turbo
    def get_speed(self, update=True, speed=None):
        if update or self.js8call.state['speed'] == None:
            msg = Message()
            msg.type = Message.MODE_GET_SPEED
            self.js8call.send(msg)
            speed = self.js8call.watch('speed')

        else:
            while self.js8call._watching == 'speed':
                time.sleep(0.1)

            speed = self.js8call.state['speed']

        # map integer to useful text
        speeds = {4:'slow', 0:'normal', 1:'fast', 2:'turbo'}

        if speed in speeds.keys():
            return speeds[int(speed)]
        else:
            raise ValueError('Invalid speed ' + str(speed))

    # speed: slow, normal, fast, turbo
    def set_speed(self, speed):
        if isinstance(speed, str):
            speeds = {'slow':4, 'normal':0, 'fast':1, 'turbo':2}
            if speed in speeds.keys():
                speed = speeds[speed]
            else:
                raise ValueError('Invalid speed: ' + str(speed))

        msg = Message()
        msg.type = Message.MODE_SET_SPEED
        msg.params['SPEED'] = speed
        self.js8call.send(msg)
        time.sleep(self._set_get_delay)
        return self.get_speed()

    def get_bandwidth(self, speed=None):
        if speed == None:
            speed = self.get_speed(update = False)
        elif isinstance(speed, int):
            speeds = {4:'slow', 0:'normal', 1:'fast', 2:'turbo'}
            speed = speeds[speed]

        bandwidths = {'slow':25, 'normal':50, 'fast':80, 'turbo':160}

        if speed in bandwidths.keys():
            return bandwidths[speed]
        else:
            raise ValueError('Invalid speed: ' + speed)

    def get_tx_window_duration(self):
        speed = self.get_speed(update = False)

        if speed == 'slow':
            duration = 30
        elif speed == 'normal':
            duration = 15
        elif speed == 'fast':
            duration = 10
        elif speed == 'turbo':
            duration = 6

        return duration

    def raise_window(self):
        msg = Message()
        msg.type = Message.WINDOW_RAISE
        self.js8call.send(msg)

    def get_rx_messages(self, own=True):
        rx_text = self.get_rx_text()
        mycall = self.get_station_callsign()
        msgs = rx_text.split('\n')
        msgs = [m.strip() for m in msgs if len(m.strip()) > 0]

        rx_messages = []
        for msg in msgs:
            parts = msg.split('-')
            data = {
                #TODO convert time format?
                'time' : parts[0].strip(),
                'offset' : int(parts[1].strip(' \n()')),
                'callsign' : parts[2].split(':')[0].strip(),
                'message' : parts[2].split(':')[1].strip(' \n' + Message.EOM)
            }

            if not own and data['callsign'] == mycall:
                continue

            rx_messages.append(data)

        return rx_messages

