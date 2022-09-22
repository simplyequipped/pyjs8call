import time
import json
import socket
import threading

import pyjs8call
from pyjs8call import Message


class JS8Call:
    
    def __init__(self, host='localhost', port=2442):
        self._host = host
        self._port = port
        self._rx_queue = []
        self._tx_queue = []
        self._socket = socket.socket()
        #TODO
        self._watch_timeout = 1 # seconds
        self._last_rx_timestamp = 0
        self._socket_heartbeat_delay = 60 * 1 # seconds
        self.pending = False # rx pending
        self.connected = False
        self.online = False

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
            'messages': None,
            'call_activity' : None,
            'band_activity' : None,
            'selected_call' : None
        }

        self._start_app()
        self._connect()

        self.online = True
        
    def _start_app(self):
        #TODO start js8call application
        pass

    def _connect(self):
        try:
            self._socket.connect((self._host, int(self._port)))
            self._socket.settimeout(1)
        except:
            #TODO handle
            pass
        
        tx_thread = threading.Thread(target=self._tx)
        tx_thread.setDaemon()
        tx_thread.start()

        rx_thread = threading.Thread(target=self._rx)
        rx_thread.setDaemon()
        rx_thread.start()

        hb_thread = threading.Thread(target=self._hb)
        hb_thread.setDaemon()
        hb_thread.start()

        time.sleep(1)
        self.online = True

    def send(self, msg):
        packed = msg.pack()
        self._tx_queue.append(packed)

    def get(self):
        if len(self._rx_queue) > 0:
            return self._rx_queue.pop(0)

    def watch(self, item):
        if item not in self.state.keys():
            return None

        self.last_state = self.state[item]
        self.state[item] = None
        timeout = time.time() + self._watch_timeout

        while timeout > time.time():
            if self.state[item] != None:
                break
            time.sleep(0.001)

        # timeout occurred, revert to last state
        if self.state[item] == None:
            self.state[item] = self.last_state
        
        return self.state[item]

    def _hb(self):
        while self.online:
            # if no recent rx,check the connection by making a request
            timeout = self._last_rx_timestamp + self._socket_heartbeat_delay
            if timeout > time.time():
                msg = Message()
                msg.type = Message.STATION_GET_CALLSIGN
                self.send(msg)
                
            time.sleep(1)

    def _tx(self):
        while self.online:
            if len(self._tx_queue) == 0:
                time.sleep(0.1)

            for item in self._tx_queue:
                self.socket.sendall(item)
                time.sleep(0.25)
                
    #TODO review original process_message code to make sure all cases are covered
    def _rx(self):
        data = b''
        data_str = ''
        while self.online:
            try:
                data += self.socket.recv(65535)
            except socket.timeout:
                # if rx from socket fails, stop processing
                self.connected = False
                time.sleep(1)
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

            msgs = data_str.split('\n')
            for m in msgs:
                # if message is empty, stop processing
                if len(m) == 0:
                    continue

                processed = False

                try:
                    msg = json.loads(m)
                    msg = Message().parse(msg)
                except:
                    # if loading json or parsing message fails, stop processing
                    continue

                if msg['type'] == 'RIG.FREQ':
                    self.state['dial'] = msg['params']['DIAL']
                    self.state['freq'] = msg['params']['FREQ']
                    self.state['offset'] = msg['params']['OFFSET']
                    processed = True
                if msg['type'] == 'RIG.PTT':
                    if msg['value'] == 'on':
                        self.state['ptt'] = True
                    else:
                        self.state['ptt'] = False
                    processed = True
                if msg['type'] == 'STATION.CALLSIGN':
                    self.state['callsign'] = msg['value']
                    processed = True
                if msg['type'] == 'STATION.GRID':
                    self.state['grid'] = msg['value']
                    processed = True
                if msg['type'] == 'STATION.INFO':
                    self.state['info'] = msg['value']
                    processed = True
                if msg['type'] == 'STATION.SPEED':
                    self.state['speed'] = msg['params']['SPEED']
                    processed = True
                if msg['type'] == 'TX.TEXT':
                    self.state['tx_text'] = msg['value']
                if msg['type'] == 'RX.TEXT':
                    self.state['rx_text'] = msg['value']
                #TODO correct type?
                if msg['type'] == 'RX.CALL_SELECTED':
                    self.state['selected_call'] = msg['value']
                    processed = True
                #TODO correct type?
                if msg['type'] == 'RX.CALL_ACTIVITY':
                    self.state['call_activity'] = msg['value']
                    processed = True
                #TODO correct type?
                if msg['type'] == 'RX.BAND_ACTIVITY':
                    self.state['band_activity'] = msg['value']
                    processed = True

                if not processed:
                    rx_queue.append(msg)
                
        if len(rx_queue) > 0:
            self.pending = True
        else:
            self.pending = False

        time.sleep(0.1)



