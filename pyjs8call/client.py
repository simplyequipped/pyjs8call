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

'''Main JS8Call API interface.

Includes many functions for reading/writing settings and sending various types of messages.

Typical usage example:
    
    ```
    js8call = pyjs8call.Client()
    js8call.register_rx_callback(rx_func)
    js8call.start()
    
    js8call.send_directed_message('KT1RUN', 'Great content thx')
    ```
'''

__docformat__ = 'google'


import time
import atexit
import threading

import pyjs8call
from pyjs8call import Message


class Client:
    '''JS8Call API client.

    Attributes:
        js8call (pyjs8call.js8call): Low-level object managing the JS8Call application and associated TCP socket communication
        spot_monitor (pyjs8call.spotmonitor): Low-level object monitoring station spots and associated callbacks
        window_monitor (pyjs8call.windowmonitor): Low-level object monitoring the transmit window of the JS8Call application
        offset_monitor (pyjs8call.offsetmonitor): Low-level object monitoring the offset frequency and activity in the pass band
        tx_monitor (pyjs8call.txmonitor): Low-level object monitoring the transmit text of the JS8Call application
        config (pyjs8call.confighandler): JS8Call configuration file handler object
        clean_directed_text (bool): Parse incoming directed message text (ex. msg.text) to remove JS8Call callsigns and symbols
        monitor_directed_tx (bool): Automatically monitor outgoing directed message status (see pyjs8call.txmonitor)
        host (str): IP address matching the JS8Call *TCP Server Hostname* setting
        port (int): Port number matching the JS8Call *TCP Server Port* setting
        headless (bool): Run JS8Call headless using xvfb (linux only, requires xvfb to be installed)
    '''
    
    def __init__(self, host='127.0.0.1', port=2442, headless=False, config_path=None):
        '''Initialize JS8Call API client.

        Registers the Client.stop function with the atexit module.

        Args:
            host (str): JS8Call TCP address setting, defaults to '127.0.0.1'
            port (int): JS8Call TCP port setting, defaults to 2442
            headless (bool): Run JS8Call headless using xvfb (linux only, requires xvfb to be installed), defaults to False
            config_path (str): Non-standard JS8Call.ini configuration file path, defaults to None

        Returns:
            pyjs8call.client.Client: Constructed client object
        '''
        self.host = host
        self.port = port
        self.headless = headless
        self.clean_directed_text = True
        self.monitor_directed_tx = True
        self.online = False

        self.js8call = None
        self.spot_monitor = None
        self.window_monitor = None
        self.offset_monitor = None
        self.tx_monitor = None

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
        '''Set active JS8Call configuration profile in the JS8Call.ini file.

        Restarts the JS8Call client (self) if already online.

        Args:
            profile (str): Profile name

        Raises:
            Exception: Given profile name does not exist (see pyjs8call.confighandler.ConfigHandler.create_new_profile)
        '''
        if profile not in self.config.get_profile_list():
            raise Exception('Config profile ' + profile + ' does not exist')

        # set the profile as active
        self.config.change_profile(profile)

        # restart the app to apply new profile if already running
        if self.online:
            self.restart()

    def start(self, debug=False):
        '''Start and connect to the the JS8Call application.

        Starts monitoring objects and associated threads:
        - Spot monitor (see pyjs8call.spotmonitor)
        - Window monitor (see pyjs8call.windowmonitor)
        - Offset monitor (see pyjs8call.offsetmonitor)
        - Tx monitor (see pyjs8call.txmonitor)

        Args:
            debug (bool): Print rx and tx messages to the console for debugging, defaults to False
        '''
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
        '''Stop all threads, close the TCP socket, and kill the JS8Call application.'''
        self.online = False
        try:
            self.js8call.stop()
        except:
            pass

    def restart(self):
        '''Stop and restart all threads, the JS8Call application, and the TCP socket.

        Dial frequency, offset frequency, and all callback functions are preserved.
        '''
        # save callback settings
        tx_monitor_status_change_callback = self.tx_monitor._status_change_callback
        spot_monitor_new_spot_callback = self.spot_monitor._new_spot_callback
        spot_monitor_watch_callback = self.spot_monitor._watch_callback
        window_monitor_window_callback = self.window_monitor._window_callback

        # save freq and offset
        freq = self.get_freq()
        offset = self.get_offset()

        self.stop()
        self.js8call._socket.close()
        time.sleep(1)
        self.start(debug = self.js8call._debug)

        # restore callback settings
        self.tx_monitor._status_change_callback = tx_monitor_status_change_callback
        self.spot_monitor._new_spot_callback = spot_monitor_new_spot_callback
        self.spot_monitor._watch_callback = spot_monitor_watch_callback
        self.window_monitor._window_callback = window_monitor_window_callback

        # restore freq and offset
        self.set_offset(offset)
        self.set_freq(freq)

    def register_rx_callback(self, callback, message_type=Message.RX_DIRECTED):
        '''Register a rx callback function.

        Callback functions are associated with specific message types. The directed message type is assumed unless otherwise specified. See pyjs8call.message for specific message types.

        Args:
            callback (func): Callback function object with the signature func(msg) where msg is a pyjs8call.message object
            message_type (str): The message type to associate with the callback funtion
        '''
        if message_type not in self.callbacks.keys():
            self.callbacks[message_type] = []

        self.callbacks[message_type].append(callback)

    def _rx(self):
        '''Rx thread function.'''
        while self.online:
            msg = self.js8call.get_next_message()

            if msg != None and msg.type in self.callbacks.keys():
                for callback in self.callbacks[msg.type]:
                    callback(msg)

            time.sleep(0.1)

    def connected(self):
        '''Get the state of the connection to the JS8Call application.

        Returns:
            bool: State of connection to JS8Call application
        '''
        return self.js8call.connected

    def send_message(self, message):
        '''Send a raw JS8Call message.

        Args:
            message (str): Message text to send

        Returns:
            pyjs8call.message: Constructed message object
        '''
        # msg.type = Message.TX_SEND_MESSAGE by default
        msg = Message(value = message)
        self.js8call.send(msg)
        return msg
    
    def send_directed_message(self, destination, message):
        '''Send a directed JS8Call message.

        The constructed message object is passed to the tx monitor (see pyjs8call.txmonitor) if Client.monitor_directed_tx is True (default).

        Args:
            destination (str): Callsign to direct the message to
            message (str): Message text to send

        Returns:
            pyjs8call.message: Constructed message object
        '''
        # msg.type = Message.TX_SEND_MESSAGE by default
        msg = Message(destination = destination, value = message)

        if self.monitor_directed_tx:
            self.tx_monitor.monitor(msg)

        self.js8call.send(msg)
        return msg

    def clean_rx_message_text(self, msg):
        '''Clean rx message text.

        Remove origin callsign, remove destination callsign or group, and strip whitespace and end-of-message characters. This leaves only the message text.
        The Message.text attribute stores the cleaned text while the Message.value attribute is unchanged.

        Args:
            message (pyjs8call.message): Message object to clean

        Returns:
            pyjs8call.message: Cleaned message object
        '''
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
        '''Send a JS8Call heartbeat message.

        If no grid square is given the configured JS8Call grid square is used.

        Args:
            grid (str): Grid square (truncated to 4 characters) to include with the heartbeat message, defaults to None

        Returns:
            pyjs8call.message: Constructed messsage object
        '''
        if grid == None:
            grid = self.get_station_grid()
        if grid == None:
            grid = ''
        if len(grid) > 4:
            grid = grid[:4]

        return self.send_message('@HB HEARTBEAT ' + grid)

    def send_aprs_grid(self, grid=None):
        '''Send a JS8Call message with APRS grid square.

        If no grid square is given the configured JS8Call grid square is used.

        Args:
            grid (str): Grid square (trucated to 4 characters) to include with the heartbeat message, defaults to None

        Returns:
            pyjs8call.message: Constructed messsage object

        Raises:
            Exception: Grid square not given and JS8Call grid square not set
        '''
        if grid == None:
            grid = self.get_station_grid()
        if grid == None or grid == '':
            raise Exception('Grid square cannot be None when sending an APRS grid message')
        if len(grid) > 4:
            grid = grid[:4]

        return self.send_message('@APRSIS GRID ' + grid)

    def send_aprs_sms(self, phone, message):
        '''Send a JS8Call APRS message via a SMS gateway.

        Args:
            phone (str): Phone number to send SMS message to
            message (str): Message to be sent via SMS message

        Returns:
            pyjs8call.message: Constructed message object
        '''
        phone = str(phone).replace('-', '')
        return self.send_message('@APRSIS CMD :SMSGATE   :@' + phone + ' ' + message)
    
    def send_aprs_email(self, email, message):
        '''Send a JS8Call APRS message via an e-mail gateway.

        Args:
            email (str): Email address to send message to
            message (str): Message to be sent via email

        Returns:
            pyjs8call.message: Constructed message object
        '''
        return self.send_message('@APRSIS CMD :EMAIL-2   :' + email + ' ' + message)
    
    def send_aprs_pota_spot(self, park, freq, mode, message, callsign=None):
        '''Send JS8Call APRS POTA spot message.

        JS8Call configured callsign is used if no callsign is given.

        Args:
            park (str): Name of park being activated
            freq (int): Frequency (in kHz) being used for park activation
            mode (str): Radio operating mode used for park activation
            message (str): Message to be sent with POTA spot
            callsign (str): Callsign of operator activating the park, defaults to None

        Returns:
            pyjs8call.message: Constructed message object
        '''
        if callsign == None:
            callsign = self.get_station_callsign()

        return self.send_message('@APRSIS CMD :POTAGW   :' + callsign + ' ' + park + ' ' + str(freq) + ' ' + mode + ' ' + message)
    
    def get_inbox_messages(self):
        '''Get JS8Call inbox messages.

        Each inbox message (dict) has the following keys:
        - id
        - time
        - origin
        - destination
        - path
        - text

        Returns:
            list: List of messages where each message is a dictionary object
        '''
        msg = Message()
        msg.type = Message.INBOX_GET_MESSAGES
        self.js8call.send(msg)
        messages = self.js8call.watch('inbox')
        return messages

    def send_inbox_message(self, destination, message):
        '''Send JS8Call inbox message.

        Args:
            destination (str): Callsign to direct inbox message to
            message (str): Message text to send

        Returns:
            pyjs8call.message: Constructed message object
        '''
        value = destination + ' MSG ' + message
        return self.send_message(value)

    def forward_inbox_message(self, destination, forward, message):
        '''Send JS8Call inbox message to be forwarded.

        Args:
            destination (str): Callsign to direct inbox message to
            forward (str): Callsign to forward inbox message to
            message (str): Message text to send

        Returns:
            pyjs8call.message: Constructed message object
        '''
        value = destination + ' MSG TO:' + forward + ' ' + message
        return self.send_message(value)

    def store_local_inbox_message(self, destination, message):
        '''Store local JS8Call inbox message for future retrieval.

        Args:
            destination (str): Callsign to direct inbox message to
            message (str): Message text to send

        Returns:
            pyjs8call.message: Constructed message object
        '''
        msg = Message()
        msg.set('type', Message.INBOX_STORE_MESSAGE)
        msg.set('params', {'CALLSIGN': destination, 'TEXT': message})
        self.js8call.send(msg)
        time.sleep(self._set_get_delay)
        return self.get_inbox_messages()

    def query_call(self, destination, callsign):
        '''Send JS8Call callsign query.

        Args:
            destination (str): Callsign to direct query to
            callsign (str): Callsign to query for

        Returns:
            pyjs8call.message: Constructed message object
        '''
        message = 'QUERY CALL ' + callsign + '?'
        return self.send_directed_message(destination, message)

    def query_messages(self, destination):
        '''Send JS8Call stored message query.

        Args:
            destination (str): Callsign to direct query to

        Returns:
            pyjs8call.message: Constructed message object
        '''
        return self.send_directed_message(destination, 'QUERY MSGS')

    def query_message_id(self, destination, msg_id):
        '''Send JS8Call stored message ID query.

        Args:
            destination (str): Callsign to direct query to
            msg_id (str): Message ID to query for

        Returns:
            pyjs8call.message: Constructed message object
        '''
        message = 'QUERY MSG ' + msg_id
        return self.send_directed_message(destination, message)

    def query_heard(self, destination):
        '''Send JS8Call heard query.

        Args:
            destination (str): Callsign to direct query to

        Returns:
            pyjs8call.message: Constructed message object
        '''
        return self.send_directed_message(destination, 'HEARD?')

    def relay_message(self, destination, relay, message):
        '''Send JS8Call directed message via relay.

        Args:
            destination (str): Callsign to direct message to
            relay (str or list): Callsign acting as relay, or ordered list of callsigns acting as relays
            message (str): Message text to send

        Returns:
            pyjs8call.message: Constructed message object
        '''
        if isinstance(relay, str):
            relay = [relay]
        
        value = relay.append(destination)
        value = value.append(message)
        message = '>'.join(value)
        return self.send_message(message)

    def get_station_spots(self, station=None, max_age=0):
        '''Get list of spotted messages.

        Spots are *pyjs8call.message* objects. All spots are returned if no filter criteria is given.

        Args:
            station (str): Filter spots by station callsign
            max_age (int): Filter spots by maximum age in seconds

        Returns:
            list: List of spotted messages matching given criteria
        '''
        spots = []
        for spot in self.js8call.spots:
            if (max_age == 0 or spot.age() < max_age) and (station == None or station == spot.origin):
                spots.append(spot)

        return spots

    def get_freq(self):
        '''Get JS8Call dial frequency.

        Returns:
            int: Dial frequency in Hz.
        '''
        msg = Message()
        msg.type = Message.RIG_GET_FREQ
        self.js8call.send(msg)
        freq = self.js8call.watch('dial')
        return freq

    def get_offset(self):
        '''Get JS8Call offset frequency.

        Returns:
            int: Offset frequency in Hz.
        '''
        msg = Message()
        msg.type = Message.RIG_GET_FREQ
        self.js8call.send(msg)
        offset = self.js8call.watch('offset')
        return offset

    def set_freq(self, freq):
        '''Set JS8Call dial frequency.

        Args:
            freq (int): Dial frequency in Hz.

        Returns:
            int: Dial frequency in Hz.
        '''
        msg = Message()
        msg.set('type', Message.RIG_SET_FREQ)
        msg.set('params', {'DIAL': freq, 'OFFSET': self.js8call.state['offset']})
        self.js8call.send(msg)
        time.sleep(self._set_get_delay)
        return self.get_freq()

    def set_offset(self, offset):
        '''Set JS8Call offset frequency.

        Args:
            offset (int): Offset frequency in Hz.

        Returns:
            int: Offset frequency in Hz.
        '''
        msg = Message()
        msg.set('type', Message.RIG_SET_FREQ)
        msg.set('params', {'DIAL': self.js8call.state['freq'], 'OFFSET': offset})
        self.js8call.send(msg)
        time.sleep(self._set_get_delay)
        return self.get_offset()

    def get_station_callsign(self):
        '''Get JS8Call callsign.

        Returns:
            str: JS8Call configured callsign
        '''
        msg = Message()
        msg.type = Message.STATION_GET_CALLSIGN
        self.js8call.send(msg)
        callsign = self.js8call.watch('callsign')
        return callsign

    def set_station_callsign(self, callsign):
        '''Set JS8Call callsign.

        Callsign must be a maximum of 9 characters and contain at least one number.

        The JS8Call callsign can only be set via the config file. The Client is restarted if online to utilize the updated config file.

        Args:
            callsign (str): Callsign to set

        Returns:
            str: JS8Call configured callsign
        '''
        callsign = callsign.upper()

        if len(callsign) <= 9 and any(char.isdigit() for char in callsign):
            self.config.set('Configuration', 'MyCall', callsign)
            # restart to apply new config if already running
            if self.online:
                self.restart()
        else:
            raise ValueError('callsign must be <= 9 characters in length and contain at least 1 number')

    def get_station_grid(self):
        '''Get JS8Call grid square.

        Returns:
            str: JS8Call configured grid square
        '''
        msg = Message()
        msg.type = Message.STATION_GET_GRID
        self.js8call.send(msg)
        grid = self.js8call.watch('grid')
        return grid

    def set_station_grid(self, grid):
        '''Set JS8Call grid square.

        Args:
            grid (str): Grid square to set

        Returns:
            str: JS8Call configured grid square
        '''
        grid = grid.upper()
        msg = Message()
        msg.type = Message.STATION_SET_GRID
        msg.value = grid
        self.js8call.send(msg)
        time.sleep(self._set_get_delay)
        return self.get_station_grid()

    def get_station_info(self):
        '''Get JS8Call station information.

        Returns:
            str: JS8Call configured station information
        '''
        msg = Message()
        msg.type = Message.STATION_GET_INFO
        self.js8call.send(msg)
        info = self.js8call.watch('info')
        return info

    def set_station_info(self, info):
        '''Set JS8Call station information.

        Args:
            info (str): Station information to set

        Returns:
            str: JS8Call configured station information
        '''
        msg = Message()
        msg.type = Message.STATION_SET_INFO
        msg.value = info
        self.js8call.send(msg)
        time.sleep(self._set_get_delay)
        return self.get_station_info()

    def get_call_activity(self):
        '''Get JS8Call call activity.

        Each call activity item (dict) has the following keys:
        - origin
        - grid
        - snr
        - time

        Returns:
            list: List of dictionaries where each dictionary is a call activity item
        '''
        msg = Message()
        msg.type = Message.RX_GET_CALL_ACTIVITY
        self.js8call.send(msg)
        call_activity = self.js8call.watch('call_activity')
        return call_activity

    def get_band_activity(self):
        '''Get JS8Call band activity.

        Each band activity item (dict) has the following keys:
        - freq
        - offset
        - snr
        - time
        - text

        Returns:
            list: List of dictionaries where each dictionary is a band activity item
        '''
        msg = Message()
        msg.type = Message.RX_GET_BAND_ACTIVITY
        self.js8call.send(msg)
        band_activity = self.js8call.watch('band_activity')
        return band_activity

    def get_selected_call(self):
        '''Get JS8Call selected callsign.

        Returns:
            str: Callsign selected on the JS8Call user interface
        '''
        msg = Message()
        msg.type = Message.RX_GET_SELECTED_CALL
        self.js8call.send(msg)
        selected_call = self.js8call.watch('selected_call')
        return selected_call

    def get_rx_text(self):
        '''Get JS8Call rx text.

        Returns:
            str: Text from the JS8Call rx text field
        '''
        msg = Message()
        msg.type = Message.RX_GET_TEXT
        self.js8call.send(msg)
        rx_text = self.js8call.watch('rx_text')
        return rx_text
        
    def get_tx_text(self):
        '''Get JS8Call tx text.

        Returns:
            str: Text from the JS8Call tx text field
        '''
        msg = Message()
        msg.set('type', Message.TX_GET_TEXT)
        self.js8call.send(msg)
        tx_text = self.js8call.watch('tx_text')
        return tx_text

    def set_tx_text(self, text):
        '''Set JS8Call tx text.

        Args:
            text (str): Text to set

        Returns:
            str: Text from the JS8Call tx text field
        '''
        msg = Message()
        msg.set('type', Message.TX_SET_TEXT)
        msg.set('value', text)
        time.sleep(self._set_get_delay)
        return self.get_tx_text()

    def get_speed(self, update=True, speed=None):
        '''Get JS8Call modem speed or map known speed from an integer to text.

        This function has two use cases:
        1. get_speed() without arguments: get JS8Call configured speed
        2. get_speed(speed=1) with given speed as an int: get speed as text

        Possible speed settings as str and (int):
        - slow (4)
        - normal (0)
        - fast (1)
        - turbo (2)

        Args:
            update (bool): Request speed from JS8Call or use current setting, defaults to True
            speed (int): Speed integer to map to appropriate speed text, defaults to None

        Returns:
            str: Speed setting as text
        '''
        if speed == None:
            if update or self.js8call.state['speed'] == None:
                msg = Message()
                msg.set('type', Message.MODE_GET_SPEED)
                self.js8call.send(msg)
                speed = self.js8call.watch('speed')

            else:
                while self.js8call._watching == 'speed':
                    time.sleep(0.1)

                speed = self.js8call.state['speed']

        # map integer to text
        speeds = {4:'slow', 0:'normal', 1:'fast', 2:'turbo'}

        if speed in speeds.keys():
            return speeds[int(speed)]
        else:
            raise ValueError('Invalid speed ' + str(speed))

    def set_speed(self, speed):
        '''Set JS8Call modem speed.

        **NOTE: The JS8Call API only sets the modem speed in the UI menu without changing the configured modem speed, which makes this function useless. This is a JS8Call API issue.**

        Possible speed settings are:
        - slow
        - normal
        - fast
        - turbo

        Args:
            speed (str): Speed to set

        Returns:
            *str:* JS8Call configured speed
        '''
        if isinstance(speed, str):
            speeds = {'slow':4, 'normal':0, 'fast':1, 'turbo':2}
            if speed in speeds.keys():
                speed = speeds[speed]
            else:
                raise ValueError('Invalid speed: ' + str(speed))

        msg = Message()
        msg.set('type', Message.MODE_SET_SPEED)
        msg.set('params', {'SPEED': speed})
        self.js8call.send(msg)
        time.sleep(self._set_get_delay)
        return self.get_speed()

    def get_bandwidth(self, speed=None):
        '''Get JS8Call signal bandwidth based on speed.

        Uses JS8Call configured speed if no speed is given.

        Possible speed settings and corresponding bandwidths:
        - slow (25 Hz)
        - normal (50 Hz)
        - fast (80 Hz)
        - turbo (160 Hz)

        Args:
            speed (str): Speed setting, defaults to None

        Returns:
            int: Bandwidth of JS8Call signal
        '''
        if speed == None:
            speed = self.get_speed(update = False)
        elif isinstance(speed, int):
            speed = self.get_speed(speed = speed)

        bandwidths = {'slow':25, 'normal':50, 'fast':80, 'turbo':160}

        if speed in bandwidths.keys():
            return bandwidths[speed]
        else:
            raise ValueError('Invalid speed: ' + speed)

    def get_tx_window_duration(self, speed=None):
        '''Get JS8Call tx window duration based on speed.

        Uses JS8Call configured speed if no speed is given.

        Possible speed settings and corresponding tx window durations:
        - slow (30 seconds)
        - normal (15 seconds)
        - fast (10 seconds)
        - turbo (5 seconds)

        Args:
            speed (str): Speed setting, defaults to None

        Returns:
            int: Duration of JS8Call tx window in seconds
        '''
        if speed == None:
            speed = self.get_speed(update = False)
        elif isinstance(speed, int):
            speed = self.get_speed(speed = speed)

        duration = {'slow': 30, 'normal': 15, 'fast': 10, 'turbo': 5}
        return duration[speed]

    def raise_window(self):
        '''Raise the JS8Call application window.'''
        msg = Message()
        msg.type = Message.WINDOW_RAISE
        self.js8call.send(msg)

    def get_rx_messages(self, own=True):
        '''Get a list of JS8Call messages from the rx text field.

        Each message (dict) has the following keys:
        - time
        - offset
        - origin
        - text

        Args:
            own (bool): Include tx messages listed in the rx text field, defaults to True

        Returns:
            list: List of messages from the rx text field
        '''
        rx_text = self.get_rx_text()
        mycall = self.get_station_callsign()
        msgs = rx_text.split('\n')
        msgs = [m.strip() for m in msgs if len(m.strip()) > 0]

        rx_messages = []
        for msg in msgs:
            parts = msg.split('-')
            data = {
                #TODO convert time format
                'time' : parts[0].strip(),
                'offset' : int(parts[1].strip(' \n()')),
                'origin' : parts[2].split(':')[0].strip(),
                'text' : parts[2].split(':')[1].strip(' \n' + Message.EOM)
            }

            if not own and data['callsign'] == mycall:
                continue

            rx_messages.append(data)

        return rx_messages

