import time
import threading

import pyjs8call
from pyjs8call import Message



class Modem:
    
    def __init__(self, host='127.0.0.1', port=2442):
        self.js8call = pyjs8call.JS8Call(host, port)
        self.freq = 7078000
        self.offset = 2000
        self.rx_callback = None
        self.online = False

        # delay between setting value and getting updated value
        self._set_get_delay = 0.1 # seconds
        
        rx_thread = threading.Thread(target=self._rx)
        rx_thread.setDaemon(True)
        rx_thread.start()

        self.online = True

    def set_rx_callback(self, callback):
        self.rx_callback = callback

    def _rx(self):
        if self.js8call.pending and self.rx_callback != None:
            msg = self.js8call.get()
            #TODO any pre-processing for certain message types?
            self.rx_callback(msg)

        time.sleep(0.1)

    def stop(self):
        self.online = False

    def send_message(self, message):
        msg = Message()
        msg.type = Message.TX_SEND_MESSAGE
        msg.value = message
        self.js8call.send(msg)
    
    def send_directed_message(self, destination, message):
        msg = Message()
        msg.type = Message.TX_SEND_MESSAGE
        msg.value = destination + ' ' + message
        self.js8call.send(msg)
    
    def send_heartbeat(self, grid=None):
        if grid == None:
            grid = self.get_grid()
        if len(grid) > 4:
            grid = grid[:4]

        callsign = self.get_callsign()
        self.send_message(callsign + ': @HB HEARTBEAT ' + grid)

    def send_aprs_grid(self, grid):
        self.send_message('@APRSIS GRID ' + grid)

    def send_aprs_sms(self, phone, message):
        phone = str(phone).replace('-', '')
        self.send_message('@APRSIS CMD :SMSGATE   :@' + phone + ' ' + message)
    
    def send_aprs_email(self, email, message):
        self.send_message('@APRSIS CMD :EMAIL-2   :' + email + ' ' + message)
    
    # freq in kHz
    def send_aprs_pota_spot(self, park, freq, mode, message):
        callsign = self.get_callsign()
        self.send_message('@APRSIS CMD :POTAGW   :' + callsign + ' ' + park + ' ' + str(freq) + ' ' + mode+ ' ' + message)
    
    def get_inbox_messages(self):
        msg = Messages()
        msg.type = Message.INBOX_GET_MESSAGES
        self.js8call.send(msg)
        messages = self.js8call.watch('messages')
        return messages

    def send_inbox_message(self, destination, message):
        value = destination + ' MSG ' + message
        self.send_message(value)

    def forward_inbox_message(self, destination, forward, message):
        value = destination + ' MSG TO:' + forward + ' ' + message
        self.send_message(value)

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
        self.send_directed_message(destination, message)

    def query_messages(self, destination):
        self.send_directed_message(destination, 'QUERY MSGS')

    def query_message_id(self, destination, msg_id):
        message = 'QUERY MSG ' + msg_id
        self.send_directed_message(destination, message)

    def query_heard(self, destination):
        self.send_directed_message(destination, 'HEARD?')

    # destinations is a list of callsigns in order (first relay, second relay, ...)
    def relay_message(self, destinations, message):
        destinations = '>'.join(destinations)
        self.send_directed_message(destinations, message)

    def get_station_spots(self, station, since_timestamp=0):
        spots = []
        
        if station in self.js8call.spots.keys():
            for destination, msgs in self.js8call.spots[station].items():
                for msg in msgs:
                    if msg.time >= since_timestamp:
                        if 'SNR' in msg.params:
                            snr = msg.params['SNR']
                        else:
                            snr = None

                        spot = {
                            'from' : station,
                            'to' : destination,
                            'message' : msg,
                            'snr' : snr,
                        }

                        spots.append(spot)
        return spots

    def get_freq(self):
        msg = Message()
        msg.type = Message.RIG_GET_FREQ
        self.js8call.send(msg)
        self.js8call.watch('dial')
        freq = {
            'freq' : self.js8call.state['dial'],
            'offset' : self.js8call.state['offset']
        }
        return freq

    def set_freq(self, freq=None, offset=None):
        if freq == None:
            freq = self.js8call.state['dial']
        if offset == None:
            offset = self.js8call.state['offset']

        msg = Message()
        msg.type = Message.RIG_SET_FREQ
        msg.params['DIAL'] = freq
        msg.params['OFFSET'] = offset
        self.js8call.send(msg)
        time.sleep(self._set_get_delay)
        return self.get_freq()

    def get_callsign(self):
        msg = Message()
        msg.type = Message.STATION_GET_CALLSIGN
        self.js8call.send(msg)
        callsign = self.js8call.watch('callsign')
        return callsign

    def get_grid(self):
        msg = Message()
        msg.type = Message.STATION_GET_GRID
        self.js8call.send(msg)
        grid = self.js8call.watch('grid')
        return grid

    def set_grid(self, grid):
        msg = Message()
        msg.type = Message.STATION_SET_GRID
        msg.value = grid
        self.js8call.send(msg)
        time.sleep(self._set_get_delay)
        return self.get_grid()

    def get_info(self):
        msg = Message()
        msg.type = Message.STATION_GET_INFO
        self.js8call.send(msg)
        info = self.js8call.watch('info')
        return info

    def set_info(self, info):
        msg = Message()
        msg.type = Message.STATION_SET_INFO
        msg.value = info
        self.js8call.send(msg)
        time.sleep(self._set_get_delay)
        return self.get_info()

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

    def get_speed(self):
        msg = Message()
        msg.type = Message.MODE_GET_SPEED
        self.js8call.send(msg)
        speed = self.js8call.watch('speed')
        return speed

    # speed: slow, normal, fast, turbo
    def set_speed(self, speed):
        speeds = {'slow':4, 'normal':0, 'fast':1, 'turbo':2}
        if isinstance(speed, str):
            speed = speeds[speed]

        msg = Message()
        msg.type = Message.MODE_SET_SPEED
        msg.params['SPEED'] = speed
        self.js8call.send(msg)
        time.sleep(self._set_get_delay)
        return self.get_speed()

    def raise_window(self):
        msg = Message()
        msg.type = Message.WINDOW_RAISE
        self.js8call.send(msg)

    def get_rx_messages(self, own=True):
        rx_text = self.get_rx_text()
        mycall = self.get_callsign()
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


    
    
    
    
    
    
    
    
    
    
    
    
        
        
