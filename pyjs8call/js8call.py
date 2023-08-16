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

'''Manage TCP socket communication and local state associated with the JS8Call application.

This module is initialized by pyjs8call.client.
'''

__docformat__ = 'google'


import os
import time
import json
import socket
import threading

import pyjs8call
from pyjs8call import Message


class JS8Call:
    '''Low-level JS8Call TCP socket and local state management.

    Receives and transmits pyjs8call.message objects, and generally manages the local state representation of the JS8Call application.

    Initializes pyjs8call.appmonitor as well as rx, tx, logging, application ping, and local state monitoring threads.

    Note: *last_band_change* is set to the current time when *pyjs8call* is started.
    
    Attributes:
        app (pyjs8call.appmonitor): Application monitor object
        connected (bool): Whether the JS8Call TCP socket is connected
        max_spot_age (int): Maximum age (in seconds) of spots to store before dropping old spots, defaults to 7 days
        last_incoming (float): Timestamp of last incoming user message, defaults to 0 (zero)
        last_outgoing (float): Timestamp of last outgoing user message, defaults to 0 (zero)
        last_band_change (float): Timestamp of last frequency band change
    '''

    def __init__(self, client, host='127.0.0.1', port=2442):
        '''Initialize JS8Call TCP socket and local state.

        Args:
            client (pyjs8call.client): Parent client object
            host (str): JS8Call TCP address setting, defaults to '127.0.0.1'
            port (int): JS8Call TCP port setting, defaults to 2442

        Returns:
            pyjs8call.js8call: Constructed js8call object
        '''
        self._client = client
        self._host = host
        self._port = port
        self._rx_queue = []
        self._rx_queue_lock = threading.Lock()
        self._tx_queue = []
        self._tx_queue_lock = threading.Lock()
        self._socket = None
        self._socket_ping_delay = 60 # seconds
        self.connected = False

        self._debug = False
        self._debug_all = False
        self._log = False
        self._log_all = False
        self._log_path = os.path.join(os.path.expanduser('~'), 'pyjs8call.log')
        self._log_queue = ''
        self._log_queue_lock = threading.Lock()
        self._debug_log_type_blacklist = [
            Message.TX_GET_TEXT,        # every second for outgoing monitor
            Message.TX_TEXT,            # every second for outgoing monitor
            Message.RIG_PTT,            # too frequent, not useful
            Message.TX_FRAME,           # start of outgoing message, not useful
            Message.STATION_STATUS,     # too frequent
            Message.RIG_GET_FREQ,       # every window transition for offset monitor
            Message.RIG_FREQ            # every window transition for offset monitor
        ]

        self._spots = []
        self.max_spot_age = 7 * 24 * 60 * 60 # 7 days 
        self._recent_spots = []
        self._spots_lock = threading.Lock()

        self._last_incoming_by_band = dict()
        self._last_outgoing_by_band = dict()
        self.last_incoming = 0
        self.last_outgoing = 0
        self.last_band_change = time.time()
        self._last_incoming_api_msg = 0
        
        self._watching = None
        self._watch_timeout = 3 # seconds

        # update frequency:
        #   positive value: update every X seconds
        #   zero value:     update at window transition
        #   negative value: update abs(X) seconds before window transition
        #
        # minimum update frequency is 0.5 seconds
        self._state = {
            'ptt' : {
                'value': False,
                'update_frequency': None,
                'last_update': 0,
                'last_update_request': 0,
                'msg_type': None
            },
            'dial': {
                'value': None,
                'update_frequency': None,
                'last_update': 0,
                'last_update_request': 0,
                'msg_type': Message.RIG_GET_FREQ
            },
            'freq' : {
                'value': None,
                'update_frequency': None,
                'last_update': 0,
                'last_update_request': 0,
                'msg_type': Message.RIG_GET_FREQ
            },
            # offset monitor: runs 1 sec before window transition
            # hb network:     runs 1 sec before window transition
            'offset' : {
                'value': None,
                'update_frequency': -1.25,
                'last_update': 0,
                'last_update_request': 0,
                'msg_type': Message.RIG_GET_FREQ
            },
            'callsign' : {
                'value': None,
                'update_frequency': None,
                'last_update': 0,
                'last_update_request': 0,
                'msg_type': Message.STATION_GET_CALLSIGN
            },
            'speed' : {
                'value': None,
                'update_frequency': None,
                'last_update': 0,
                'last_update_request': 0,
                'msg_type': Message.MODE_GET_SPEED
            },
            'grid' : {
                'value': None,
                'update_frequency': None,
                'last_update': 0,
                'last_update_request': 0,
                'msg_type': Message.STATION_GET_GRID
            },
            'info' : {
                'value': None,
                'update_frequency': None,
                'last_update': 0,
                'last_update_request': 0,
                'msg_type': Message.STATION_GET_INFO
            },
            'rx_text' : {
                'value': None,
                'update_frequency': None,
                'last_update': 0,
                'last_update_request': 0,
                'msg_type': Message.RX_GET_TEXT
            },
            # outgoing monitor: runs every 0.5 secs
            'tx_text' : {
                'value': None,
                'update_frequency': 0.5,
                'last_update': 0,
                'last_update_request': 0,
                'msg_type': Message.GET_TX_TEXT
            },
            'inbox': {
                'value': None,
                'update_frequency': None,
                'last_update': 0,
                'last_update_request': 0,
                'msg_type': Message.INBOX_GET_MESSAGES
            },
            'call_activity' : {
                'value': None,
                'update_frequency': None,
                'last_update': 0,
                'last_update_request': 0,
                'msg_type': Message.RX_GET_CALL_ACTIVITY
            },
            'band_activity' : {
                'value': None,
                'update_frequency': None,
                'last_update': 0,
                'last_update_request': 0,
                'msg_type': Message.RX_GET_BAND_ACTIVITY
            },
            'selected_call' : {
                'value': None,
                'update_frequency': None,
                'last_update': 0,
                'last_update_request': 0,
                'msg_type': Message.RX_GET_SELECTED_CALL
            }
        }
        
        self.app = pyjs8call.AppMonitor(self)

    def start(self, headless=False, args = None):
        '''Start the JS8Call application.

        This function is blocking until the JS8Call application responds to a network command which ensures that the application is operational before continuing. This handles slower computers such as Raspberry Pi.

        Used internally by client.start().

        Args:
            headless (bool): Run JS8Call headless using xvfb (Linux only), defaults to False
            args (list): Command line arguments (see appmonitor.start), defaults to empty list

        Raises:
            RuntimeError: JS8Call application failed to start
        '''
        if args is None:
            args = []
        
        self.online = True
        self.app.start(headless=headless, args = args)

        tx_thread = threading.Thread(target=self._tx)
        tx_thread.daemon = True
        tx_thread.start()

        rx_thread = threading.Thread(target=self._rx)
        rx_thread.daemon = True
        rx_thread.start()

        log_thread = threading.Thread(target=self._log_monitor)
        log_thread.daemon = True
        log_thread.start()

        time.sleep(1)
        timeout = time.time() + 60

        # wait for application to respond
        while True:
            time.sleep(0.01)
            
            try:
                # value error while application is still starting (i.e. raspberry pi)
                self._client.settings.get_speed()
                # no errors, application responded
                break
            except ValueError:
                pass

            if time.time() > timeout:
                RuntimeError('JS8Call application failed to start')

        ping_thread = threading.Thread(target=self._ping)
        ping_thread.daemon = True
        ping_thread.start()
        
        state_thread = threading.Thread(target=self._state_monitor)
        state_thread.daemon = True
        state_thread.start()

    def reinitialize(self, settings):
        '''Re-initialize internal settings after restart.

        Used internally.

        Args:
            settings (dict): Settings to re-initialize
        '''
        for setting, value in settings.items():
            setattr(self, setting, value)

    def restart_settings(self):
        '''Get certain internal settings.

        Used internally.

        Returns:
            dict: Settings used to re-initialize on restart
        '''
        settings = [
            '_state',
            '_spots',
            'max_spot_age',
            '_tx_queue',
            '_debug',
            '_debug_all',
            '_debug_log_type_blacklist',
            '_log',
            '_log_all',
            '_last_incoming_by_band',
            '_last_outgoing_by_band',
            'last_incoming',
            'last_outgoing',
            'last_band_change'
        ]

        return {setting: getattr(self, setting) for setting in settings}

    def stop(self):
        '''Stop threads and JS8Call application.'''
        self.online = False
        self._socket.close()
        self.app.stop()

    def enable_debugging(self, debug_all=False):
        '''Print incoming and outgoing messages to console.

        Args:
            debug_all (bool): Print all messages, including nusance ones
        '''
        self._debug = True
        
        if debug_all:
            self._debug_all = True

    def enable_logging(self, log_all=False):
        '''Log incoming and outgoing messages.

        Log file location: *~/pyjs8call.log*

        Args:
            log_all (bool): Log all messages, including nusance messages
        '''
        self._log = True
        
        if log_all:
            self._log_all = True

    def process_freq_change(self, previous_freq, current_freq=None):
        '''Manage last incoming/outgoing timestamps on band change.

        This function is called internally when the local frequency state is updated. If a band change has occured, last incoming and outgoing timestamps for the previous band are stored, and last incoming and outgoing timestamps for the current band of loaded (if available).

        Note: Changing from one out-of-band frequency to another out-of-band frequency is not considered a band change.

        Args:
            previous_freq (int): Previous frequency in Hz
            current_freq (int): Current frequency in Hz, defaults to current frequency
        '''
        if previous_freq is None:
            # freq initialization on start, no band change
            return

        if current_freq is None:
            current_freq = self._client.settings.get_freq()

        current_band = pyjs8call.Client.freq_to_band(current_freq)
        previous_band = pyjs8call.Client.freq_to_band(previous_freq)

        if current_band == previous_band:
            # no band change
            return

        self._last_incoming_by_band[previous_band] = self.last_incoming
        self._last_outgoing_by_band[previous_band] = self.last_outgoing
        self.last_band_change = time.time()

        if current_band in self._last_incoming_by_band:
            self.last_incoming = self._last_incoming_by_band[current_band]
        else:
            self.last_incoming = 0

        if current_band in self._last_outgoing_by_band:
            self.last_outgoing = self._last_outgoing_by_band[current_band]
        else:
            self.last_outgoing = 0

    def activity(self, age=0):
        '''Whether there is outgoing activity.
        
        Args:
            age (int): Maximum age in seconds of outgoing activity to consider active, defaults to 0

        Returns:
            bool: True if text in the tx text field, queued outgoing messages, or recent activity, False otherwise
        '''
        activity_age = bool(time.time() - self.last_outgoing <= age)
        outgoing_text = bool(self.get_state('tx_text') not in (None, ''))

        with self._tx_queue_lock:
            # count of queued outgoing user msgs
            queued_outgoing = bool(len([msg for msg in self._tx_queue if msg.type in Message.USER_MSG_TYPES]) > 0)

        return any((outgoing_text, queued_outgoing, activity_age))
    
    def block_until_inactive(self, age=0):
        '''Block until not outgoing activity.
        
        See *activity()* for more details.
        
        Args:
            age (int): Maximum age in seconds of outgoing activity to consider active, defaults to 0
        '''
        while self.activity(age = age):
            time.sleep(0.1)

    def connect(self):
        '''Connect to the TCP socket of the JS8Call application.

        This function is for internal use only.
        '''
        self._socket = socket.socket()
        self._socket.connect((self._host, int(self._port)))
        self._socket.settimeout(1)

    def send(self, msg):
        '''Queue message for transmission to the JS8Call application.

        Sets the status of the message object to *queued* (see pyjs8call.message statuses).

        Args:
            msg (pyjs8call.message): Message object to be transmitted
        '''
        msg.status = Message.STATUS_QUEUED
        msg.set('profile', self._client.settings.get_profile())

        with self._tx_queue_lock:
            self._tx_queue.append(msg)
        
    def append_to_rx_queue(self, msg):
        '''Queue received message from the JS8Call application for handling.

        Sets the status of the message object to *queued* (see pyjs8call.message statuses).

        Args:
            msg (pyjs8call.message): Message object to be handled
        '''
        msg.status = Message.STATUS_QUEUED

        with self._rx_queue_lock:
            self._rx_queue.append(msg)

    def get_next_message(self):
        '''Get next received message from the queue.

        Sets the status of the message object to *received* (see pyjs8call.message statuses).

        Returns:
            pyjs8call.message: Message to be handled
        '''
        if len(self._rx_queue) > 0:
            with self._rx_queue_lock:
                msg = self._rx_queue.pop(0)

            msg.status = Message.STATUS_RECEIVED
            return msg

    def get_state(self, state):
        '''Get asynchronous state value.

        Waits for state to stop being watched before returning.

        Internal state settings:
        - ptt
        - dial 
        - freq
        - offset
        - callsign
        - speed
        - grid
        - info
        - rx_text
        - tx_text
        - inbox 
        - call_activity
        - band_activity
        - selected_call

        Args:
            state (str): State value to get

        Returns:
            Returned type varies depending on the specified state value.
        '''
        while self.watching(state):
            time.sleep(0.1)

        return self._state[state]['value']

    def _set_state(self, item, value):
        '''Set local state value.

        Args:
            item (str): State item name (ex. \'freq\')
            value (varies): New value of the state item
        '''
        if item in self._state:
            self._state[item]['value'] = value
            self._state[item]['last_update'] = time.time()
    
    def watching(self, state=None):
        '''Get internal asynchronous setting state.

        See *get_state()* for a list of internal state settings.

        Args:
            state (str): State to check, defaults to None

        Returns:
            str: Name of internal setting waiting for async JS8Call response, if *state* is None
            bool: Whether *state* is waiting for async JS8Call response, if *state* is specified
        '''
        if state is None:
            return self._watching
        else:
            return bool(state == self._watching)

    def watch(self, item):
        '''Watch local state variable for updating based on a response from the JS8Call application.

        The JS8Call application responds to requests asynchronously, which means responses may not be received in the same order as the requests or in a reasonable timeframe following the request. To handle these asynchronous reponses, the responses set local state variables as they are received. The process is as follows:
        - Send a request to the JS8Call application
        - Set local state variable associated with anticipated response to a known value (None)
        - Wait for a response, timing out if a response is not received within 3 seconds
        - Detect a change in the local state variable indicating that a response has been received
        - Return the response (i.e. the current value of the updated local state variable)

        If a timeout occurs while waiting for a response the local state variable is set back to its previous value.

        Args:
            item (str): Name of the local state variable to watch

        Returns:
            The value of the given local state variable
        '''
        if item not in self._state:
            return None

        self._watching = item
        last_state = self._state[item]['value']
        self._state[item]['value'] = None
        timeout = time.time() + self._watch_timeout

        while timeout > time.time():
            if self._state[item]['value'] is not None:
                break
            time.sleep(0.001)

        if self._state[item]['value'] is None:
            # timeout occurred, revert to last state
            self._state[item]['value'] = last_state
        
        self._watching = None
        return self._state[item]['value']

    def get_spots(self):
        '''Get spotted message objects.
        
        Returns:
            list: spot message objects
        '''
        with self._spots_lock:
             return self._spots

    def get_spots_str(self):
        '''Get spotted message objects as json string.

         Used with *set_spots_str* to save spot messages for later use.

        Returns:
            str: json.dumps of each spot dictionary representation, joined with newlines
        '''
        spots = [spot.dump() for spot in self.get_spots()]
        return '\n'.join(spots)

    def set_spots(self, spots, append=True):
        '''Set spotted message objects.

        Args:
            spots (list): list of spot message objects
            append (bool): append to spot list if True, replace spots if False, defaults to True
        '''
        with self._spots_lock:
            if append:
                self._spots.append(spots)
            else:
                self._spots = spots

    def set_spots_str(self, spots, append=True):
        '''Set spotted message objects from json string.

         Used with *get_spots_str* to load previously saved spot messages.

        Args:
            spots (str): json string of spot message dictionaries, separated with newlines
            append (bool): append to spots if True, replace spots if False, defaults to True
        '''
        spots = [Message().load(spot.strip()) for spot in spots.split('\n')]
        self.set_spots(spots, append)

    def _spot(self, msg):
        '''Store a message when a station is heard.

        The message is compared to a list of recent messages (heard within the last 10 seconds) to prevent duplicate spots from multiple JS8Call API messages associated with the same station event.

        The list of stored messages is culled once the maximum age set by *max_spot_age* by dropping aged messages.

        See pyjs8call.spotmonitor to utilize spots.

        Args:
            msg (pyjs8call.message): Message to spot
        '''
        # cull recent spots
        self._recent_spots = [spot for spot in self._recent_spots if spot.age() < 10]

        with self._spots_lock:
            if msg not in self._recent_spots:
                self._recent_spots.append(msg)
                self._spots.append(msg)
    
            # cull spots
            while len(self._spots) > 0 and self._spots[0].age() > self.max_spot_age:
                self._spots.pop(0)

    def _log_msg(self, msg):
        '''Add message to log queue.'''
        if msg.type in Message.TX_TYPES:
            msg_type = 'TX'
        elif msg.type in Message.RX_TYPES:
            msg_type = 'RX'

        msg_time = time.strftime('%x %X', time.localtime(msg.timestamp))

        with self._log_queue_lock:
            self._log_queue += msg_time + '  ' + msg_type + '  ' + msg.dump() + '\n'

    def _log_monitor(self):
        '''Log queue monitor thread.'''
        while self.online:
            if len(self._log_queue) > 0:
                with self._log_queue_lock:
                    with open(self._log_path, 'a', encoding='utf-8') as fd:
                        fd.write(self._log_queue)
                    self._log_queue = ''
            time.sleep(1)

    def _ping(self):
        '''JS8Call application ping thread.

        If no messages have been received from the JS8Call in the last minute, a request is issued to the application to make sure it is still connected and functioning as expected.
        '''
        while self.online:
            # if no recent api msgs, check the connection by making a request
            timeout = self._last_incoming_api_msg + self._socket_ping_delay

            if time.time() > timeout:
                self.connected = False
                msg = Message()
                msg.type = Message.STATION_GET_CALLSIGN
                self.send(msg)
                
            time.sleep(5)

    def _state_monitor(self):
        '''Local state monitor thread.

        Minimum update frequency is 0.5 seconds.
        '''
        # allow initial api messages and requests to initialize state
        time.sleep(5)
        
        while self.online:
            time.sleep(0.05)
            
            for item in self._state:
                update = False
                now = time.time()
                
                update_frequency = self._state[item]['update_frequency'] # seconds
                last_update = self._state[item]['last_update'] # timestamp
                last_update_request = self._state[item]['last_update_request'] # timestamp
                msg_type = self._state[item]['msg_type']
                
                # skip updating in the following cases:
                if (self.watching(item) or # state is currently being updated
                    update_frequency is None or # do not update
                    msg_type is None or # no assocaited message type
                    now - last_update_request < 0.5 # update requested recently
                ):
                    continue
                
                # positive, update every X seconds
                if update_frequency > 0 and now - last_update >= update_frequency:
                    update = True
                # zero, update at end of rx/tx window
                elif update_frequency == 0 and self._client.window.next_transition_seconds() < 0.1:
                    update = True
                # negative, update abs(X) seconds before end of rx/tx window
                elif update_frequency < 0 and self._client.window.next_transition_seconds() <= abs(update_frequency):
                    update = True

                if update:
                    msg = Message()
                    msg.set('type', msg_type)
                    self.send(msg)
                    
                    self._state[item]['last_update_request'] = now
    
    def _tx(self):
        '''JS8Call application transmit thread.

        The JS8Call tx text field is read every second by pyjs8call.txmonitor. This is utilized to reduce additional socket traffic by reading the local state variable directly without requesting additional updates from the application.

        When processing the transmit message queue, if a transmission is in process (i.e. there is text in the tx text field) then transmission of additional messages is prevented until the current transmission is complete.

        If debugging or logging is enabled then each message sent over the TCP socket is printed to the console or to file respectively. By default not all messages are printed or logged (see pyjs8call.js8call.JS8Call._debug_log_type_blacklist). Frequently sent and received messages used internal to pyjs8call are not printed or logged.
        '''
        tx_text = False
        active_tx_state = False

        while self.online:
            # TxMonitor updates tx_text every second
            if self._state['tx_text']['value'] == '':
                tx_text = False
            else:
                tx_text = True
                active_tx_state = False

            with self._tx_queue_lock:
                for msg in self._tx_queue.copy():
                    # hold off on sending messages while there is something being sent (text in the tx text field)
                    if msg.type in Message.USER_MSG_TYPES and (tx_text or active_tx_state):
                        continue
            
                    packed = msg.pack()
                    
                    if self._debug and (self._debug_all or (msg.type not in self._debug_log_type_blacklist)):
                        print('TX: ' + packed.decode('utf-8').strip())
    
                    if self._log and (self._log_all or (msg.type not in self._debug_log_type_blacklist)):
                        self._log_msg(msg)
    
                    try:
                        self._socket.sendall(packed)
                        self._tx_queue.remove(msg)

                        if msg.type in Message.USER_MSG_TYPES:
                            self.last_outgoing = time.time()
                            # make sure the next queued msg doesn't get sent before the tx text state updates
                            active_tx_state = True

                    except (BrokenPipeError, ValueError, OSError):
                        # BrokenPipeError may happen when restarting due to closed socket
                        # ValueError may happen when restarting, tx_queue.remove fails (possibly due to PEP 475)
                        # OSError may happen when stopping during msg processing, socket.sendall fails
                        pass

                    if not self.online:
                        return
    
                    time.sleep(0.1)
    
            time.sleep(0.1)

    def _rx(self):
        '''JS8Call application receive thread.

        A byte string is read from the TCP socket and parsed into a pyjs8call.message. Socket data is discarded in the following cases:
            - Failure to decode received byte string to UTF-8 (likely due to corrupted or incomplete data)
            - Length of received byte string is zero (no data received)
            - Failure to parse received data into a pyjs8call.message (likely due to corrupted or incomplete data)
            - Parsed message value contains the JS8Call error character (defaults to an ellipsis)

        Received data that is successfully parsed is passed to *_process_message()* for further processing. 

        If debugging is enabled (see pyjs8call.client.Client.start) then the byte string of each message sent over the TCP socket is printed to the console. By default not all messages are printed in debug mode (see pyjs8call.js8call.JS8Call._debug_type_blacklist). Frequently sent and received messages used internal to pyjs8call are not printed.
        '''
        while self.online:
            data = b''
            data_str = ''

            try:
                data += self._socket.recv(65535)
            except socket.timeout:
                # if rx from socket fails continue trying
                continue
            except OSError:
                # OSError occurs while app is restarting
                self.connected = False
                continue

            try: 
                data_str = data.decode('utf-8')
            except UnicodeDecodeError:
                # if decode fails, stop processing
                continue

            # if rx data is empty, stop processing
            if len(data_str) == 0:
                continue

            # restore connected state after being disconnected
            self.connected = True

            # split received data into messages
            msgs = data_str.split('\n')

            for msg_str in msgs:
                # if message is empty, stop processing
                if len(msg_str) == 0:
                    continue

                try:
                    msg = Message().parse(msg_str)
                except Exception as e:
                    if self._debug or self._debug_all:
                        raise e
                    else:
                        # if parsing message fails, stop processing
                        continue

                if msg.type in Message.USER_MSG_TYPES:
                    self.last_incoming = time.time()

                msg.status = Message.STATUS_RECEIVED
                self._last_incoming_api_msg = time.time()
                
                # print msg in debug mode
                if self._debug and (self._debug_all or (msg.type not in self._debug_log_type_blacklist)):
                    print('RX: ' + json.dumps(msg.dict()))

                # log msg
                if self._log and (self._log_all or (msg.type not in self._debug_log_type_blacklist)):
                    self._log_msg(msg)

                self._process_message(msg)

        time.sleep(0.1)

    def _process_message(self, msg):
        '''Process received message.

        Messages are processed based on their command and/or their type (see pyjs8call.message for commands and types). Messages are spotted when appropriate. Responses to JS8Call setting and state requests are handled to update the associated local state variables.

        Automatic cleaning of directed message text is handled if enabled (see pyjs8call.client).

        Args:
            msg (pyjs8call.message): Message to process
        '''
        # try to get distance and bearing
        if msg.get('grid') not in (None, ''):
            try:
                # raises ValueError for incorrect grid format
                distance, units, bearing = self._client.grid_distance(msg.get('grid'))
                msg.set('distance', distance)
                msg.set('distance_units', units)
                msg.set('bearing', bearing)
            except ValueError:
                pass

        # set active profile for spot filtering
        msg.set('profile', self._client.settings.get_profile())
        
        
        ### command handling ###

        if msg.cmd in Message.COMMANDS:
            self._spot(msg)


        ### message type handling ###

        if msg.type == Message.INBOX_MESSAGES:
            self._set_state('inbox', msg.messages)

        elif msg.type == Message.RX_SPOT:
            self._spot(msg)

        elif msg.type == Message.RX_DIRECTED:
            # custom processing of incoming messages
            if self._client.process_incoming is not None:
                msg = self._client.process_incoming(msg)

                if msg is None:
                    return
            
            # clean msg text to remove callsigns, etc
            if self._client.clean_directed_text:
                msg = self._client.clean_rx_message_text(msg)

            self._spot(msg)

        elif msg.type == Message.RIG_FREQ:
            previous_freq = self._state['dial']['value']

            self._set_state('dial', msg.dial)
            self._set_state('freq', msg.freq)
            self._set_state('offset', msg.offset)

            self.process_freq_change(previous_freq)

        elif msg.type == Message.RIG_PTT:
            if msg.value == 'on':
                self._set_state('ptt', True)
            else:
                self._set_state('ptt', False)

        elif msg.type == Message.STATION_STATUS:
            previous_freq = self._state['dial']['value']

            self._set_state('dial', msg.dial)
            self._set_state('freq', msg.freq)
            self._set_state('offset', msg.offset)
            self._set_state('speed', msg.speed)

            self.process_freq_change(previous_freq)

        elif msg.type == Message.STATION_CALLSIGN:
            self._set_state('callsign', msg.value)

        elif msg.type == Message.STATION_GRID:
            self._set_state('grid', msg.value)

        elif msg.type == Message.STATION_INFO:
            self._set_state('info', msg.value)

        elif msg.type == Message.MODE_SPEED:
            self._set_state('speed', msg.speed)

        elif msg.type == Message.TX_TEXT:
            self._set_state('tx_text', msg.value)

        elif msg.type == Message.RX_TEXT:
            self._set_state('rx_text', msg.value)

        elif msg.type == Message.RX_SELECTED_CALL:
            self._set_state('selected_call', msg.value)

        elif msg.type == Message.RX_CALL_ACTIVITY:
            self._set_state('call_activity', msg.call_activity)

        elif msg.type == Message.RX_BAND_ACTIVITY:
            self._set_state('band_activity', msg.band_activity)

        elif msg.type == Message.RX_ACTIVITY:
            pass

        elif msg.type == Message.TX_FRAME:
            pass
            
        self.append_to_rx_queue(msg)
