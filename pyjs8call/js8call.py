import time
import json
import socket
import threading
from datetime import datetime, timezone

import pyjs8call
from pyjs8call import Message


class JS8Call:
    
    def __init__(self, host='localhost', port=2442, debug=False):
        self._host = host
        self._port = port
        self._rx_queue = []
        self._tx_queue = []
        self._socket = socket.socket()
        self._watch_timeout = 3 # seconds
        self._last_rx_timestamp = 0
        self._socket_heartbeat_delay = 60 * 5 # seconds
        self._app = None
        self._debug = debug
        self.pending = False # rx pending
        self.connected = False
        self.online = False
        self.spots = []
        self._recent_spots = []

        self.state = {
            'ptt' : None,
            'dial': None,
            'freq' : None,
            'offset' : None,
            'callsign' : None,
            'speed' : None,
            'grid' : None,
            'info' : None,
            'rx_text' : None,
            'tx_text' : None,
            'inbox': None,
            'call_activity' : None,
            'band_activity' : None,
            'selected_call' : None,
        }

        #self._start_app()
        self._connect()
        self.online = True
        
        tx_thread = threading.Thread(target=self._tx)
        tx_thread.setDaemon(True)
        tx_thread.start()

        rx_thread = threading.Thread(target=self._rx)
        rx_thread.setDaemon(True)
        rx_thread.start()

        hb_thread = threading.Thread(target=self._hb)
        hb_thread.setDaemon(True)
        hb_thread.start()

        # get callsign
        msg = Message()
        msg.type = Message.STATION_GET_CALLSIGN
        self.send(msg)
        self.watch('callsign')

    def stop(self):
        self.online = False

        if self._app != None:
            self._app.terminate()

    def _start_app(self):
        #TODO start js8call application
        self._app = subprocess.Popen(['js8call'])
        time.sleep(3)

    def _connect(self):
        try:
            self._socket.connect((self._host, int(self._port)))
            self._socket.settimeout(1)
        except:
            #TODO handle
            pass

    def send(self, msg):
        packed = msg.pack()
        self._tx_queue.append(packed)

    def get(self):
        if len(self._rx_queue) > 0:
            return self._rx_queue.pop(0)

    def watch(self, item):
        if item not in self.state.keys():
            return None

        last_state = self.state[item]
        self.state[item] = None
        timeout = time.time() + self._watch_timeout

        while timeout > time.time():
            if self.state[item] != None:
                break
            time.sleep(0.001)

        # timeout occurred, revert to last state
        if self.state[item] == None:
            self.state[item] = last_state
        
        return self.state[item]

    def spot(self, msg):
        new_spot = {
            'from'      : msg['from'],
            'to'        : msg['to'],
            'freq'      : msg['dial'],
            'offset'    : msg['offset'],
            'time'      : msg['time'],
            'grid'      : msg['grid'],
            'snr'       : msg['snr']
        }
        
        if new_spot['time'] == None or new_spot['time'] == '':
            new_spot['time'] = datetime.now(timezone.utc).timestamp()

        duplicate = False
        for i in range(len(self._recent_spots)):
            recent_spot = self._recent_spots.pop(0)
            # remove spots older than 10 seconds
            if recent_spot['time'] > (datetime.now(timezone.utc).timestamp() - 10):
                self._recent_spots.append(recent_spot)  

            # prevent duplicate spots
            if (
                recent_spot['from'] == new_spot['from'] and
                recent_spot['offset'] == new_spot['offset'] and
                recent_spot['snr'] == new_spot['snr']
            ):
                duplicate = True

        if not duplicate:
            self._recent_spots.append(new_spot)
            self.spots.append(new_spot)

    def _hb(self):
        while self.online:
            # if no recent rx,check the connection by making a request
            timeout = self._last_rx_timestamp + self._socket_heartbeat_delay
            if time.time() > timeout:
                self.connected = False
                msg = Message()
                msg.type = Message.STATION_GET_CALLSIGN
                self.send(msg)
                
            time.sleep(1)

    def _tx(self):
        while self.online:
            while len(self._tx_queue) == 0:
                time.sleep(0.1)

            for i in range(len(self._tx_queue)):
                item = self._tx_queue.pop(0)
                self._socket.sendall(item)
                time.sleep(0.25)
                
    def _rx(self):
        while self.online:
            data = b''
            data_str = ''

            try:
                data += self._socket.recv(65535)
            except socket.timeout:
                # if rx from socket fails, stop processing
                continue

            try: 
                data_str = data.decode('utf-8')
            except:
                # if decode fails, stop processing
                continue

            # if rx data is empty, stop processing
            if len(data_str) == 0:
                continue

            self._last_rx_timestamp = time.time()
            self.connected = True

            #split received data into messages
            msgs = data_str.split('\n')

            for msg_str in msgs:
                # if message is empty, stop processing
                if len(msg_str) == 0:
                    continue

                try:
                    msg = Message().parse(msg_str)
                except Exception as e:
                    # if parsing message fails, stop processing
                    #TODO
                    raise e
                    continue

                # if error in message value, stop processing
                if msg['value'] != None and pyjs8call.Message.ERR in msg['value']:
                    continue

                # print each msg in debug mode
                if self._debug:
                    #print(msg_str)
                    print(msg)

                self._process_message(msg)

        if len(self._rx_queue) > 0:
            self.pending = True
        else:
            self.pending = False

        time.sleep(0.1)


    def _process_message(self, msg):
        # command handling

        if msg['cmd'] == Message.CMD_HEARING:
            #TODO validate response structure
            # spot message
            self.spot(msg)
            #if not pyjs8call.Message.ERR in msg.params['TEXT']:
            #    hearing = msg.params['TEXT'].split()[3:]
            #    for station in hearing:
            #        if station not in self.spots[msg.params['FROM']].keys():
            #            self.spots[msg.params['FROM']][station] = []
            #        self.spots[msg.params['FROM']][station].append(msg)
            # receive message
            self._rx_queue.append(msg)

        #TODO no example, test response and update code
        #elif msg.params['CMD'] == 'QUERY CALL':
        #    # spot message
        #    self.spot(msg)
        #    #receive message
        #    self._rx_queue.append(msg)
                
        elif msg['cmd'] in Message.COMMANDS:
            # spot message
            self.spot(msg)
            # receive message
            self._rx_queue.append(msg)

        # message type handling

        if msg['type'] == Message.INBOX_MESSAGES:
            self.state['inbox'] = msg['messages']

        elif msg['type'] == Message.RX_SPOT:
            # spot message
            self.spot(msg)

        elif msg['type'] == Message.RX_DIRECTED:
            # spot message
            self.spot(msg)
            # receive message
            self._rx_queue.append(msg)

        elif msg['type'] == Message.RIG_FREQ:
            self.state['dial'] = msg['dial']
            self.state['freq'] = msg['freq']
            self.state['offset'] = msg['offset']

        elif msg['type'] == Message.RIG_PTT:
            if msg['value'] == 'on':
                self.state['ptt'] = True
            else:
                self.state['ptt'] = False

        elif msg['type'] == Message.STATION_CALLSIGN:
            self.state['callsign'] = msg['value']

        elif msg['type'] == Message.STATION_GRID:
            self.state['grid'] = msg['value']

        elif msg['type'] == Message.STATION_INFO:
            self.state['info'] = msg['value']

        elif msg['type'] == Message.MODE_SPEED:
            self.state['speed'] = msg['speed']

        elif msg['type'] == Message.TX_TEXT:
            self.state['tx_text'] = msg['value']

        elif msg['type'] == Message.RX_TEXT:
            self.state['rx_text'] = msg['value']

        elif msg['type'] == Message.RX_SELECTED_CALL:
            self.state['selected_call'] = msg['value']

        elif msg['type'] == Message.RX_CALL_ACTIVITY:
            self.state['call_activity'] = msg['call_activity']

        elif msg['type'] == Message.RX_BAND_ACTIVITY:
            self.state['band_activity'] = msg['band_activity']

        #TODO should this be used? use RX.BAND_ACTIVITY for now
        #TODO note, RX.SPOT received immediately after RX.ACTIVITY in some cases
        elif msg['type'] == Message.RX_ACTIVITY:
            pass




