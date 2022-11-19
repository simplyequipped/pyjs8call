import time
import json
import socket
import threading
from datetime import datetime, timezone

import pyjs8call
from pyjs8call import Message

#TODO cull spots occasionally?

class JS8Call:

    def __init__(self, client, host='127.0.0.1', port=2442, headless=False):
        self._client = client
        self._host = host
        self._port = port
        self._rx_queue = []
        self._rx_queue_lock = threading.Lock()
        self._tx_queue = []
        self._tx_queue_lock = threading.Lock()
        self._socket = None
        self._watch_timeout = 3 # seconds
        self._watching = None
        self._last_rx_timestamp = 0
        self._socket_heartbeat_delay = 60 * 5 # seconds
        self._app = None
        self._debug = False
        self.connected = False
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

        self.online = True

        # start the application monitor
        self.app_monitor = pyjs8call.AppMonitor(self)
        self.app_monitor.start(headless=headless)
        
        tx_thread = threading.Thread(target=self._tx)
        tx_thread.setDaemon(True)
        tx_thread.start()

        rx_thread = threading.Thread(target=self._rx)
        rx_thread.setDaemon(True)
        rx_thread.start()

        hb_thread = threading.Thread(target=self._hb)
        hb_thread.setDaemon(True)
        hb_thread.start()

    def stop(self):
        self.online = False
        self.app_monitor.stop()

    def _connect(self):
        self._socket = socket.socket()
        self._socket.connect((self._host, int(self._port)))
        self._socket.settimeout(1)

    def send(self, msg):
        self._tx_queue_lock.acquire()
        self._tx_queue.append(msg)
        self._tx_queue_lock.release()
        
    def append_to_rx_queue(self, msg):
        self._rx_queue_lock.acquire()
        self._rx_queue.append(msg)
        self._rx_queue_lock.release()

    def get_next_message(self):
        msg = None

        if len(self._rx_queue) > 0:
            self._rx_queue_lock.acquire()
            msg = self._rx_queue.pop(0)
            self._rx_queue_lock.release()

        return msg

    def watch(self, item):
        if item not in self.state.keys():
            return None

        self._watching = item
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
        
        self._watching = None
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

        try:
            new_spot['speed'] = msg['speed']
        except:
            new_spot['speed'] = None
        
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
        tx_text = False
        force_tx_text = False

        while self.online:
            # TxMonitor updates tx_text every second
            # do not attempt to update while value is being watched (i.e. updated)
            if self._watching != 'tx_text' and self.state['tx_text'] != None:
                if len(self.state['tx_text'].strip()) > 0:
                    tx_text = True
                    force_tx_text = False
                else:
                    tx_text = False

            self._tx_queue_lock.acquire()

            for msg in self._tx_queue.copy():

                #TODO other msg types?
                # hold off on sending messages while there is something being sent (text in the tx text field)
                if msg.type == Message.TX_SEND_MESSAGE and (tx_text or force_tx_text):
                    next
                else:
                    # pack and send msg via socket

                    #TODO
                    #self._socket.sendall(msg.pack())
                    packed = msg.pack()
                    print(packed)
                    self._socket.sendall(packed)

                    # remove msg from queue
                    self._tx_queue.remove(msg)

                    # make sure the next queued msg doesn't get sent before the tx text state updates
                    if msg.type == Message.TX_SEND_MESSAGE:
                        force_tx_text = True

                    time.sleep(0.1)

            self._tx_queue_lock.release()
            time.sleep(0.1)

    def _rx(self):
        while self.online:
            data = b''
            data_str = ''

            try:
                data += self._socket.recv(65535)
            except (socket.timeout, OSError):
                # if rx from socket fails, stop processing
                # OSError occurs while app is restarting
                continue

            try: 
                data_str = data.decode('utf-8')
            except Exception as e:
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
                    continue

                # if error in message value, stop processing
                if msg['value'] != None and Message.ERR in msg['value']:
                    continue

                # print msg in debug mode, without None values
                if self._debug:
                    min_msg = {key:value for key, value in msg.items() if value != None}
                    print(min_msg)

                self._process_message(msg)

        time.sleep(0.1)

    def _process_message(self, msg):

        ### command handling

        if msg['cmd'] == Message.CMD_HEARING:
            #TODO validate response structure
            #if not Message.ERR in msg.params['TEXT']:
            #    hearing = msg.params['TEXT'].split()[3:]
            #    for station in hearing:
            #        if station not in self.spots[msg.params['FROM']].keys():
            #            self.spots[msg.params['FROM']][station] = []
            #        self.spots[msg.params['FROM']][station].append(msg)

            # spot message
            self.spot(msg)

        #TODO no example, test response and update code
        #elif msg.params['CMD'] == 'QUERY CALL':
        #    # spot message
        #    self.spot(msg)
                
        elif msg['cmd'] in Message.COMMANDS:
            # spot message
            self.spot(msg)

        ### message type handling

        if msg['type'] == Message.INBOX_MESSAGES:
            self.state['inbox'] = msg['messages']

        elif msg['type'] == Message.RX_SPOT:
            # spot message
            self.spot(msg)

        elif msg['type'] == Message.RX_DIRECTED:
            # clean msg text to remove callsigns, etc
            if self._client.clean_directed_text:
                msg = self._client.clean_rx_message_text(msg)

            # spot message
            self.spot(msg)

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

        elif msg['type'] == Message.TX_FRAME:
            self._client.window_monitor.process_tx_frame(msg)

        self._rx_queue_lock.acquire()
        self._rx_queue.append(msg)
        self._rx_queue_lock.release()

