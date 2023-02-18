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

Includes many functions for reading/writing settings and sending various types
of messages.

Typical usage example:

    ```
    js8call = pyjs8call.Client()
    js8call.callback.register_incoming(incoming_callback_function)
    js8call.start()

    js8call.send_directed_message('KT7RUN', 'Great content thx')
    ```
'''

__docformat__ = 'google'


import time
import atexit
import threading
from datetime import datetime, timezone
from math import radians, sin, cos, acos, atan2, pi

import pyjs8call
from pyjs8call import Message


class Client:
    '''JS8Call API client.

    Attributes:
        js8call (pyjs8call.js8call): Manages JS8Call application and TCP socket communication
        spots (pyjs8call.spotmonitor): Monitors station activity and issues callbacks
        window (pyjs8call.windowmonitor): Monitors the JS8Call transmit window
        offset (pyjs8call.offsetmonitor): Manages JS8Call offset frequency
        outgoing (pyjs8call.outgoingmonitor): Monitors JS8Call outgoing message text
        drift (pyjs8call.timemonitor): Monitors JS8Call time drift
        time_master (pyjs8call.timemonitor): Manages time master outgoing messages
        inbox (pyjs8call.inboxmonitor): Monitors JS8Call inbox messages
        config (pyjs8call.confighandler): Manages JS8Call configuration file
        heartbeat (pyjs8call.hbnetwork): Manages heartbeat outgoing messages
        callback (pyjs8call.client.Callbacks): Callback function reference object
        settings (pyjs8call.client.Settings): Configuration setting function reference object
        clean_directed_text (bool): Remove JS8Call callsign structure from incoming messages, defaults to True
        monitor_outgoing (bool): Monitor outgoing message status (see pyjs8call.outgoingmonitor), defaults to True
        online (bool): Whether the JS8Call application and pyjs8call interface are online
        host (str): IP address matching JS8Call *TCP Server Hostname* setting
        port (int): Port number matching JS8Call *TCP Server Port* setting
    '''

    def __init__(self, host='127.0.0.1', port=2442, config_path=None):
        '''Initialize JS8Call API client.

        Registers the Client.stop function with the atexit module.
        
        Configures the following settings:
        - enable autoreply at startup
        - disable autoreply confirmation
        - enable transmit

        Args:
            host (str): JS8Call TCP address setting, defaults to '127.0.0.1'
            port (int): JS8Call TCP port setting, defaults to 2442
            config_path (str): Non-standard JS8Call.ini configuration file path, defaults to None

        Returns:
            pyjs8call.client: Constructed client object
        '''
        self.host = host
        self.port = port
        self.clean_directed_text = True
        self.monitor_outgoing = True
        self.online = False

        self.js8call = None
        self.spots = None
        self.window = None
        self.offset = None
        self.outgoing = None
        self.drift = None
        self.time_master = None
        self.inbox = None
        self.heartbeat = None

        # delay between setting value and getting updated value
        self._set_get_delay = 0.1 # seconds

        self.config = pyjs8call.ConfigHandler(config_path = config_path)
        self.settings = Settings(self)
        self.callback = Callbacks()

        # stop application and client at exit
        atexit.register(self.stop)
        
    def start(self, headless=False, debugging=False, logging=False):
        '''Start and connect to the the JS8Call application.

        Initializes sub-module objects:
        - Spot monitor (see pyjs8call.spotmonitor)
        - Window monitor (see pyjs8call.windowmonitor)
        - Offset monitor (see pyjs8call.offsetmonitor)
        - Outgoing monitor (see pyjs8call.outgoingmonitor)
        - Time drift monitor (see pyjs8call.timemonitor)
        - Time master (see pyjs8call.timemonitor)
        - Heartbeat networking (see pyjs8call.hbnetwork)
        - Inbox master (see pyjs8call.inboxmonitor)

        Adds the @TIME group to JS8Call via the config file to enable drift monitor features.

        If logging is enabled the log file will be stored in the current user's *HOME* directory.

        Args:
            headless (bool): Run JS8Call headless via xvfb (Linux only)
            debugging (bool): Print message data to the console, defaults to False
            logging (bool): Print message data to ~/pyjs8call.log, defaults to False

        Raises:
            RuntimeError: JS8Call config file section does not exist (likely because JS8Call has not been run and configured after installation)
        '''
        try:
            self.settings.enable_autoreply_startup()
            self.settings.disable_autoreply_confirmation()
            self.settings.enable_transmit()
            # enable JS8Call TCP connection
            self.config.set('Configuration', 'TCPEnabled', 'true')
            self.config.set('Configuration', 'TCPServer', self.host)
            self.config.set('Configuration', 'TCPServerPort', str(self.port))
            self.config.set('Configuration', 'AcceptTCPRequests', 'true')
            # support pyjs8call.timemonitor features
            self.config.add_group('@TIME')
            self.config.write()
        except RuntimeError as e:
            raise RuntimeError('Try launching JS8Call, configuring audio and CAT interfaces as needed, '
                               'and then exiting the application normally. When the application '
                               'exits normally the first time it will initialize the config file.') from e

        self.js8call = pyjs8call.JS8Call(self, self.host, self.port)
        self.js8call.start(headless = headless)
        self.online = True

        if debugging:
            self.js8call.enable_debugging()

        if logging:
            self.js8call.enable_logging()

        rx_thread = threading.Thread(target=self._rx)
        rx_thread.daemon = True
        rx_thread.start()
        time.sleep(1)

        self.window = pyjs8call.WindowMonitor(self)
        self.spots = pyjs8call.SpotMonitor(self)
        self.offset = pyjs8call.OffsetMonitor(self)
        self.outgoing = pyjs8call.OutgoingMonitor(self)
        self.drift = pyjs8call.DriftMonitor(self)
        self.time_master = pyjs8call.TimeMaster(self)
        self.heartbeat = pyjs8call.HeartbeatNetworking(self)
        self.inbox = pyjs8call.InboxMonitor(self)
        
        self.window.enable_monitoring()
        self.spots.enable_monitoring()
        self.offset.enable_monitoring()
        self.outgoing.enable_monitoring()

    def stop(self):
        '''Stop all threads, close the TCP socket, and kill the JS8Call application.'''
        self.online = False
        
        try:
            return self.js8call.stop()
        except Exception:
            pass

    def restart(self):
        '''Stop and restart the JS8Call application and the associated TCP socket.

        pyjs8call.js8call settings are preserved.
        '''
        # write any pending config file changes, convience
        self.config.write()
        # save settings
        settings = self.js8call.restart_settings()
        headless = self.js8call.app.headless

        # stop
        self.stop()
        time.sleep(0.25)

        # start
        self.js8call = pyjs8call.JS8Call(self, self.host, self.port)
        self.js8call.start(headless = headless)
        self.online = True

        rx_thread = threading.Thread(target=self._rx)
        rx_thread.daemon = True
        rx_thread.start()
        time.sleep(0.5)

        # restore settings
        self.js8call.reinitialize(settings)

    def restart_when_inactive(self, age=0):
        '''Restart the JS8Call application once there is no outgoing activity.
        
        This function is non-blocking due to the use of *threading.Thread* internally.
        
        See *pyjs8call.js8call.activity()* for more details.
        
        Args:
            age (int): Maximum age of outgoing activity to consider active, defaults to 0
        '''
        thread = threading.Thread(target=self._restart_when_inactive, args=(age,))
        thread.daemon = True
        thread.start()
        
    def _restart_when_inactive(self, age):
        '''Thread function to restart once there is no outgoing activity.'''
        self.js8call.block_until_inactive(age = age)
        self.restart()
        
    def activity(self, age=0):
        '''Whether there is outgoing activity.

        This is a convenience function that calls *pyjs8call.js8call.activity()*.
        
        Args:
            age (int): Maximum age of outgoing activity to consider active, defaults to 0 (disabled)

        Returns:
            bool: True if text in the tx text field, queued outgoing messages, or recent activity, False otherwise
        '''
        return self.js8call.activity(age)

    def _rx(self):
        '''Rx thread function.'''
        while self.online:
            msg = self.js8call.get_next_message()

            if msg is not None:
                for callback in self.callback.incoming_type(msg.type):
                    thread = threading.Thread(target=callback, args=[msg])
                    thread.daemon = True
                    thread.start()

            time.sleep(0.1)

    def connected(self):
        '''Get the state of the connection to the JS8Call application.

        Returns:
            bool: State of connection to JS8Call application
        '''
        return self.js8call.connected

    def identities(self):
        '''Get identities associated with local stations.
        
        Returns:
            list: Configured callsign and custom groups
        '''
        ids = self.config.get_groups()
        ids.append(self.settings.get_station_callsign())
        return ids
    
    def msg_is_to_me(self, msg):
        '''Determine if specified message is addressed to local station.
        
        Utilizes *msg.is_directed_to()* and *client.identities()* internally.
        
        Args:
            msg (pyjs8call.message): Message object to evaluate
            
        Returns:
            bool: True if *msg* is addressed to the local station, False otherwise
        '''
        
        return msg.is_directed_to(self.identities())
    
    def clean_rx_message_text(self, msg):
        '''Clean incoming message text.

        Remove origin callsign, destination callsign or group (including relays), whitespace, and end-of-message characters. This leaves only the message text.
        
        The *pyjs8call.message.text* attribute stores the cleaned text while the *pyjs8call.message.value* attribute is unchanged.

        Args:
            message (pyjs8call.message): Message object to clean

        Returns:
            pyjs8call.message: Cleaned message object
        '''
        if msg is None:
            return msg
        # nothing to clean
        elif msg.value in (None, ''):
            return msg
        # already cleaned
        elif msg.value != msg.text:
            return msg

        message = msg.value

        # remove origin callsign
        # avoid other semicolons in message text
        message = ':'.join(message.split(':')[1:]).strip()

        # handle no spaces between relay path and message text
        # avoid other relay character in message text
        last_relay_index = message.rfind(Message.CMD_RELAY, 0, message.find(' '))

        if last_relay_index > 0:
            # remove relay path
            message = message[last_relay_index + 1:]
        else:
            # remove destination callsign or group
            message = ' '.join(message.split(' ')[1:])
        
        # strip remaining spaces and end-of-message symbol
        message = message.strip(' ' + Message.EOM)

        msg.set('text', message)
        return msg
    
    def send_message(self, message):
        '''Send a raw JS8Call message.
        
        Message format: *MESSAGE*

        The constructed message object is passed to pyjs8call.txmonitor internally if *Client.monitor_outgoing* is True (default).

        Args:
            message (str): Message text to send

        Returns:
            pyjs8call.message: Constructed message object
        '''
        # msg.type = Message.TX_SEND_MESSAGE by default
        msg = Message(value = message)

        if self.monitor_outgoing:
            self.outgoing.monitor(msg)

        self.js8call.send(msg)
        return msg

    def send_directed_command_message(self, destination, command, message=None):
        '''Send a directed JS8Call command message.

        Message format: *DESTINATION**COMMAND* *MESSAGE*

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.txmonitor internally if *Client.monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the message to
            command (str): Command to include in message (see *pyjs8call.message* static commands)
            message (str): Message text to send, defaults to None
        '''
        # msg.type = Message.TX_SEND_MESSAGE by default
        msg = Message(destination, command, message)

        if self.monitor_outgoing:
            self.outgoing.monitor(msg)

        self.js8call.send(msg)
        return msg
    
    def send_directed_message(self, destination, message):
        '''Send a directed JS8Call message.
        
        Message format: *DESTINATION* *MESSAGE*

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.txmonitor internally if *Client.monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the message to
            message (str): Message text to send

        Returns:
            pyjs8call.message: Constructed message object
        '''
        # msg.type = Message.TX_SEND_MESSAGE by default
        msg = Message(destination = destination, value = message)

        if self.monitor_outgoing:
            self.outgoing.monitor(msg)

        self.js8call.send(msg)
        return msg

    def send_heartbeat(self, grid=None):
        '''Send a JS8Call heartbeat message.

        Note that JS8Call will only transmit API messages at the selected offset. Heartbeat messages can still be sent, but will not be in the heartbeat sub-band.

        Message format: @HB HEARTBEAT *GRID*

        If no grid square is given the configured JS8Call grid square is used.

        The constructed message object is passed to pyjs8call.txmonitor internally if *Client.monitor_outgoing* is True (default).

        Args:
            grid (str): Grid square (truncated to 4 characters), defaults to None

        Returns:
            pyjs8call.message: Constructed messsage object
        '''
        if grid is None:
            grid = self.settings.get_station_grid()

        if grid is None:
            grid = ''

        if len(grid) > 4:
            grid = grid[:4]

        return self.send_directed_command_message('@HB', Message.CMD_HEARTBEAT, grid)

    def send_aprs_grid(self, grid=None):
        '''Send a JS8Call message with APRS grid square.
        
        Message format: @APRSIS GRID *GRID*

        If no grid square is given the configured JS8Call grid square is used.

        The constructed message object is passed to pyjs8call.txmonitor internally if *Client.monitor_outgoing* is True (default).

        Args:
            grid (str): Grid square (trucated to 4 characters), defaults to None

        Returns:
            pyjs8call.message: Constructed messsage object

        Raises:
            ValueError: Grid square not specified and JS8Call grid square not set
        '''
        if grid is None:
            grid = self.settings.get_station_grid()
        if grid in (None, ''):
            raise ValueError('Grid square cannot be None when sending an APRS grid message')
        if len(grid) > 4:
            grid = grid[:4]

        return self.send_directed_command_message('@APRSIS', Message.CMD_GRID, grid)

    def send_aprs_sms(self, phone, message):
        '''Send a JS8Call APRS message via a SMS gateway.
        
        Message format: @APRSIS CMD :SMSGATE&nbsp;&nbsp;&nbsp;:@1234567890 *MESSAGE*

        The constructed message object is passed to pyjs8call.txmonitor internally if *Client.monitor_outgoing* is True (default).

        Args:
            phone (str): Phone number to send SMS message to
            message (str): Message to be sent via SMS message

        Returns:
            pyjs8call.message: Constructed message object
        '''
        phone = str(phone).replace('-', '').replace('.', '').replace('(', '').replace(')', '')
        message = ':SMSGATE   :@' + phone + ' ' + message
        return self.send_directed_command_message('@APRSIS', Message.CMD_CMD, message)
    
    def send_aprs_email(self, email, message):
        '''Send a JS8Call APRS message via an e-mail gateway.
        
        Message format: @APRSIS CMD :EMAIL-2&nbsp;&nbsp;&nbsp;:EMAIL@DOMAIN.COM *MESSAGE*

        The constructed message object is passed to pyjs8call.txmonitor internally if *Client.monitor_outgoing* is True (default).

        Args:
            email (str): Email address to send message to
            message (str): Message to be sent via email

        Returns:
            pyjs8call.message: Constructed message object
        '''
        message = ':EMAIL-2   :' + email + ' ' + message
        return self.send_directed_command_message('@APRSIS', Message.CMD_CMD, message)
    
    def send_aprs_pota_spot(self, park, freq, mode, message, callsign=None):
        '''Send JS8Call APRS POTA spot message.
        
        Message format: @APRSIS CMD :POTAGW&nbsp;&nbsp;&nbsp;:*CALLSIGN* *PARK* *FREQ* *MODE* *MESSAGE*

        JS8Call configured callsign is used if no callsign is given.

        The constructed message object is passed to pyjs8call.txmonitor internally if *Client.monitor_outgoing* is True (default).

        Args:
            park (str): Name of park being activated
            freq (int): Frequency (in kHz) being used for park activation
            mode (str): Radio operating mode used for park activation
            message (str): Message to be sent with POTA spot
            callsign (str): Callsign of operator activating the park, defaults to None

        Returns:
            pyjs8call.message: Constructed message object
        '''
        if callsign is None:
            callsign = self.settings.get_station_callsign()

        message = ':POTAGW   :' + callsign + ' ' + park + ' ' + str(freq) + ' ' + mode + ' ' + message
        return self.send_directed_command_message('@APRSIS', Message.CMD_CMD, message)
    
    def get_inbox_messages(self, unread=True):
        '''Get JS8Call inbox messages.

        Args:
            unread (bool): Get unread messages only if True, all messages if False

        Each inbox message is a *dict* with the following keys:

        | Key | Value Type |
        | -------- | -------- |
        | cmd | *str* |
        | freq | *int* | 
        | offset | *int* | 
        | snr | *int* |
        | speed | *int* |
        | time | *str* |
        | origin | *str* |
        | destination | *str* |
        | path | *str* |
        | text | *str* |
        | type | *str* |
        | value | *str* |
        | status | *str* |
        | unread | *bool* |
        | stored | *bool* |
        
        Returns:
            list: List of inbox messages
        '''
        msg = Message()
        msg.type = Message.INBOX_GET_MESSAGES
        self.js8call.send(msg)
        messages = self.js8call.watch('inbox')

        if messages is not None and len(messages) > 0 and unread:
            messages = [msg for msg in messages if msg['unread']]
            
        return messages

    def send_inbox_message(self, destination, message):
        '''Send JS8Call inbox message.

        Message format: *DESTINATION* MSG *MESSAGE*

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.txmonitor internally if *Client.monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the message to
            message (str): Message text to send

        Returns:
            pyjs8call.message: Constructed message object
        '''
        return self.send_directed_command_message(destination, Message.CMD_MSG, message)

    def store_remote_inbox_message(self, remote, destination, message):
        '''Send JS8Call inbox message to be forwarded.

        Message format: *REMOTE* MSG TO:*DESTINATION* *MESSAGE*

        If *remote* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.txmonitor internally if *Client.monitor_outgoing* is True (default).

        Args:
            remote (str, list): Callsign of intermediate station storing the message
            destination (str): Callsign of message recipient
            message (str): Message text to send

        Returns:
            pyjs8call.message: Constructed message object
        '''
        message = destination + ' ' + message
        return self.send_directed_command_message(remote, Message.CMD_MSG_TO, message)

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
        
        Message format: *DESTINATION* QUERY CALL *CALLSIGN*?

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.txmonitor internally if *Client.monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the query to
            callsign (str): Callsign to query for

        Returns:
            pyjs8call.message: Constructed message object
        '''
        message = callsign + Message.CMD_Q
        return self.send_directed_command_message(destination, Message.CMD_QUERY_CALL, message)

    def query_messages(self, destination='@ALLCALL'):
        '''Send JS8Call stored message query.
        
        Message format: *DESTINATION* QUERY MSGS

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.txmonitor internally if *Client.monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the query to, defaults to '@ALLCALL'

        Returns:
            pyjs8call.message: Constructed message object
        '''
        return self.send_directed_command_message(destination, Message.CMD_QUERY_MSGS)

    def query_message_id(self, destination, msg_id):
        '''Send JS8Call stored message ID query.
        
        Message format: *DESTINATION* QUERY MSG *ID*

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.txmonitor internally if *Client.monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the query to
            msg_id (str): Message ID to query for

        Returns:
            pyjs8call.message: Constructed message object
        '''
        cmd = Message.CMD_QUERY + Message.CMD_MSG
        return self.send_directed_command_message(destination, cmd, str(msg_id))

    def query_hearing(self, destination):
        '''Send JS8Call hearing query.
        
        Message format: *DESTINATION* HEARING?

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.txmonitor internally if *Client.monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the query to

        Returns:
            pyjs8call.message: Constructed message object
        '''
        return self.send_directed_command_message(destination, Message.CMD_HEARING_Q)

    def query_snr(self, destination):
        '''Send JS8Call SNR query.
        
        Message format: *DESTINATION* SNR?

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.txmonitor internally if *Client.monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the query to

        Returns:
            pyjs8call.message: Constructed message object
        '''
        return self.send_directed_command_message(destination, Message.CMD_SNR_Q)

    def query_grid(self, destination):
        '''Send JS8Call grid query.
        
        Message format: *DESTINATION* GRID?

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.txmonitor internally if *Client.monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the query to

        Returns:
            pyjs8call.message: Constructed message object
        '''
        return self.send_directed_command_message(destination, Message.CMD_GRID_Q)

    def query_info(self, destination):
        '''Send JS8Call info query.
        
        Message format: *DESTINATION* INFO?

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.txmonitor internally if *Client.monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the query to

        Returns:
            pyjs8call.message: Constructed message object
        '''
        return self.send_directed_command_message(destination, Message.CMD_INFO_Q)

    def query_status(self, destination):
        '''Send JS8Call status query.
        
        Message format: *DESTINATION* STATUS?

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.txmonitor internally if *Client.monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the query to

        Returns:
            pyjs8call.message: Constructed message object
        '''
        return self.send_directed_command_message(destination, Message.CMD_STATUS_Q)

    def get_call_activity(self, age=60):
        '''Get JS8Call call activity.

        Each call activity item is a dictionary with the following keys:

        | Key | Value Type |
        | -------- | -------- |
        | origin | str |
        | grid | str |
        | snr | int |
        | time (UTC) | int |
        | hearing | list |

        Args:
            age (int): Maximum activity age in minutes, defaults to 60

        Returns:
            list: Call activity items
        '''
        msg = Message()
        msg.type = Message.RX_GET_CALL_ACTIVITY
        self.js8call.send(msg)
        call_activity = self.js8call.watch('call_activity')

        hearing = self.hearing(age = age)
        age *= 60 # minutes to seconds
        now = datetime.now(timezone.utc).timestamp()

        for i in range(len(call_activity)):
            origin = call_activity[i]['origin']
            item_age = now - call_activity[i]['time']

            if item_age > age:
                continue

            if origin in hearing:
                call_activity[i]['hearing'] = hearing[origin]

        return call_activity

    def get_band_activity(self):
        '''Get JS8Call band activity.

        Each band activity item is a dictionary with the following keys:

        | Key | Value Type |
        | -------- | -------- |
        | freq (Hz) | int |
        | offset (Hz) | int |
        | snr | int |
        | time (UTC) | int |
        | text | str |

        Returns:
            list: Band activity items
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

    def raise_window(self):
        '''Raise the JS8Call application window.'''
        msg = Message()
        msg.type = Message.WINDOW_RAISE
        self.js8call.send(msg)

    def get_rx_messages(self, own=True):
        '''Get list of messages from the JS8Call rx text field.

        Each message is a dictionary object with the following keys:
        - time
        - offset
        - origin
        - text

        Args:
            own (bool): Include outgoing messages listed in the rx text field, defaults to True

        Returns:
            list: Messages from the rx text field
        '''
        rx_text = self.get_rx_text()
        callsign = self.settings.get_station_callsign()
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

            if not own and data['callsign'] == callsign:
                continue

            rx_messages.append(data)

        return rx_messages
    
    def hearing(self, age=60):
        '''Get information on which stations other stations are hearing.

        Args:
            age (int): Maximum message age in minutes, defaults to 60

        Returns:
            dict: Example format *{'station': ['station', ...], ...}*
        '''
        age *= 60
        callsign = self.settings.get_station_callsign()
        hearing = {}
        
        for spot in self.spots.filter(age = age):
            # only process msgs with directed commands
            if spot.cmd is None:
                continue

            # stations we are hearing
            if callsign not in hearing:
                hearing[callsign] = [spot.origin]
            elif spot.origin not in hearing[callsign]:
                hearing[callsign].append(spot.origin)
                
            if spot.cmd == Message.CMD_HEARING and spot.hearing is not None:
                if spot.origin not in hearing:
                    hearing[spot.origin] = spot.hearing
                else:
                    spot_hearing = [station for station in spot.hearing if station not in hearing[spot.origin]]
                    hearing[spot.origin].extend(spot_hearing)
            
            if spot.cmd in (Message.CMD_ACK, Message.CMD_HEARTBEAT_SNR):
                if spot.origin not in hearing:
                    hearing[spot.origin] = []

                if isinstance(spot.path, list):
                    # handle relay path
                    #TODO review if path list should be reversed
                    relay_path = Message.CMD_RELAY.join(spot.path)

                    if relay_path not in hearing[spot.origin]:
                        hearing[spot.origin].append(relay_path)

                elif spot.destination != '@ALLCALL' and spot.destination not in hearing[spot.origin]:
                    hearing[spot.origin].append(spot.destination)

        return hearing

#TODO
#    def heard_by(self, age=60):
#        '''Get information on which stations are heard other stations.
#        
#        '''
#        callsign = self.settings.get_station_callsign()
#        heard = {}
        
    def grid_distance(self, grid_a, grid_b=None, miles=True):
        '''Calculate great circle distance and bearing between grid squares.

        If *grid_b* is *None* the JS8Call grid square is used.

        Bearing is calculated from *grid_b* to *grid_a*.

        *grid* must be a 4 or 6 character Maidenhead grid square (ex. EM19 or EM19es). If *grid* is longer than 6 characters it will be truncated to 6 characters.

        Reference: https://www.movable-type.co.uk/scripts/latlong.html

        Args:
            grid_a (str): First grid square
            grid_b (str): Second grid square, defaults to None
            miles (bool): Calculate distance in miles if True, in km if False, defaults to True

        Returns:
            tuple (int, int): Distance/bearing pair (ex. (1194, 312))

        Raises:
            ValueError: *grid_b* is *None* and JS8Call grid square is not set
        '''
        earth_radius_km = 6371
        earth_radius_mi = 3958.756

        if grid_b is None:
            grid_b = self.settings.get_station_grid()

        if grid_b in (None, ''):
            raise ValueError('Second grid square required and JS8Call grid square not set.')

        lat_a, lon_a = self.grid_to_lat_lon(grid_a)
        lat_b, lon_b = self.grid_to_lat_lon(grid_b)
        # convert degrees to radians
        lat_a, lon_a, lat_b, lon_b = map(radians, [lat_a, lon_a, lat_b, lon_b])

        # calculate great circle distance
        gcd = acos(sin(lat_a) * sin(lat_b) + cos(lat_a) * cos(lat_b) * cos(lon_b - lon_a))
        
        if miles:
            distance = int(round(earth_radius_mi * gcd, 0))
        else:
            distance = int(round(earth_radius_km * gcd, 0))

        # calculate bearing
        y = sin(lon_a - lon_b) * cos(lat_a)
        x = cos(lat_b) * sin(lat_a) - sin(lat_b) * cos(lat_a) * cos(lon_a - lon_b)
        angle = atan2(y, x)
        bearing = (angle * 180 / pi + 360) % 360
        bearing = int(round(bearing, 0))

        return (distance, bearing)

    def grid_to_lat_lon(self, grid):
        '''Convert grid square to latitude/longitude.

        *grid* must be a 4 or 6 character Maidenhead grid square (ex. EM19 or EM19es). If *grid* is longer than 6 characters it will be truncated to 6 characters.

        Latitude and longitude are rounded to 3 decimal places.

        Reference: http://www.w8bh.net/grid_squares.pdf

        Args:
            grid (str): Grid square to convert to latitude/longitude

        Returns:
            tuple (float, float): Latitude/longitude pair (ex. (39.750, -97.667))

        Raises:
            ValueError: Invalid grid square format
        '''
        if len(grid) > 6:
            grid = grid[:6]

        if len(grid) not in (4, 6):
            raise ValueError('Grid must contain 4 or 6 characters (ex. EM19 or EM19es)')

        grid = grid.upper()

        field_map = ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R']
        sub_square_map = ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X']
        field_lon_deg = 20
        field_lat_deg = 10
        square_lon_deg = 2
        square_lat_deg = 1
        sub_square_lon_deg = 1/12
        sub_square_lat_deg = 1/24

        grid_lon = [grid[i] for i in range(0, len(grid), 2)]
        grid_lat = [grid[i] for i in range(1, len(grid), 2)]

        try:
            lon = field_map.index(grid_lon[0]) * field_lon_deg
            lon += int(grid_lon[1]) * square_lon_deg

            if len(grid_lon) == 3:
                lon += sub_square_map.index(grid_lon[2]) * sub_square_lon_deg

            lon -= 180
            lon = round(lon, 3)

            lat = field_map.index(grid_lat[0]) * field_lat_deg
            lat += int(grid_lat[1]) * square_lat_deg

            if len(grid_lat) == 3:
                lat += sub_square_map.index(grid_lat[2]) * sub_square_lat_deg

            lat -= 90
            lat = round(lat, 3)

        except ValueError as e:
            raise ValueError('Invalid grid square format. Field and sub-square must be letters A-R '
                             '(case insensitive), and square must be numbers 0-9 (ex. EM19es).') from e

        return (lat, lon)



class Settings:
    '''Settings function container.
    
    This class is initilized by pyjs8call.client.Client.
    '''
    
    def __init__(self, client):
        '''Initialize settings object.

        Returns:
            pyjs8call.client.Settings: Constructed setting object
        '''
        self._client = client

    def enable_heartbeat_networking(self):
        '''Enable heartbeat networking via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        
        Note that this function disables JS8Call application heartbeat networking via the config file. To enable the pyjs8call heartbeat network messaging module see pyjs8call.hbnetwork.HeartbeatNetworking.enable_networking().
        '''
        self._client.config.set('Common', 'SubModeHB', 'true')

    def disable_heartbeat_networking(self):
        '''Disable heartbeat networking via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        
        Note that this function disables JS8Call application heartbeat networking via the config file. To disable the pyjs8call heartbeat network messaging module see pyjs8call.hbnetwork.HeartbeatNetworking.disable_networking().
        '''
        self._client.config.set('Common', 'SubModeHB', 'false')

    def enable_heartbeat_acknowledgements(self):
        '''Enable heartbeat acknowledgements via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Common', 'SubModeHBAck', 'true')

    def disable_heartbeat_acknowledgements(self):
        '''Disable heartbeat acknowledgements via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Common', 'SubModeHBAck', 'false')

    def enable_multi_decode(self):
        '''Enable multi-speed decoding via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Common', 'SubModeHBMultiDecode', 'true')

    def disable_multi_decode(self):
        '''Disable multi-speed decoding via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Common', 'SubModeMultiDecode', 'false')

    def enable_autoreply_startup(self):
        '''Enable autoreply on start-up via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'AutoreplyOnAtStartup', 'true')

    def disable_autoreply_startup(self):
        '''Disable autoreply on start-up via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'AutoreplyOnAtStartup', 'false')

    def enable_autoreply_confirmation(self):
        '''Enable autoreply confirmation via config file.
        
        When running headless the autoreply confirmation dialog box will be inaccessible.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'AutoreplyConfirmation', 'true')

    def disable_autoreply_confirmation(self):
        '''Disable autoreply confirmation via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'AutoreplyConfirmation', 'false')

    def enable_allcall(self):
        '''Enable @ALLCALL participation via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'AvoidAllcall', 'false')

    def disable_allcall(self):
        '''Disable @ALLCALL participation via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'AvoidAllcall', 'true')

    def enable_reporting(self):
        '''Enable PSKReporter reporting via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'PSKReporter', 'true')

    def disable_reporting(self):
        '''Disable PSKReporter reporting via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'PSKReporter', 'false')

    def enable_transmit(self):
        '''Enable transmitting via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'TransmitOFF', 'false')

    def disable_transmit(self):
        '''Disable transmitting via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'TransmitOFF', 'true')

    def set_profile(self, profile):
        '''Set active JS8Call configuration profile via config file.
        
        This is a convenience function. See pyjs8call.confighandler for other configuration profile related functions.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.

        Args:
            profile (str): Profile name

        Raises:
            ValueError: Specified profile name does not exist
        '''
        if profile not in self._client.config.get_profile_list():
            raise ValueError('Config profile \'' + profile + '\' does not exist')

        # set the profile as active
        self._client.config.change_profile(profile)

    def submode_to_speed(self, submode):
        '''Map submode *int* to speed *str*.

        | Submode | Speed |
        | -------- | -------- |
        | 0 | normal |
        | 1 | fast |
        | 2 | turbo |
        | 4 | slow |
        | 8 | ultra |

        Args:
            submode (int): Submode to map to text

        Returns:
            str: Speed as text
        '''
        # map integer to text
        speeds = {4:'slow', 0:'normal', 1:'fast', 2:'turbo', 8:'ultra'}

        if submode is not None and int(submode) in speeds:
            return speeds[int(submode)]
        else:
            raise ValueError('Invalid submode \'' + str(submode) + '\'')

    def get_speed(self, update=False):
        '''Get JS8Call modem speed.

        Possible modem speeds:
        - slow
        - normal
        - fast
        - turbo
        - ultra

        Args:
            update (bool): Update speed if True or use local state if False, defaults to False

        Returns:
            str: JS8call modem speed setting
        '''
        speed = self._client.js8call.get_state('speed')

        if update or speed is None:
            msg = Message()
            msg.set('type', Message.MODE_GET_SPEED)
            self._client.js8call.send(msg)
            speed = self._client.js8call.watch('speed')

        return self.submode_to_speed(speed)

    def set_speed(self, speed):
        '''Set JS8Call modem speed via config file.

        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.

        Possible modem speeds:
        - slow
        - normal
        - fast
        - turbo
        - ultra

        Args:
            speed (str): Speed to set

        Returns:
            str: JS8Call modem speed setting

        '''
        if isinstance(speed, str):
            speeds = {'slow':4, 'normal':0, 'fast':1, 'turbo':2, 'ultra':8}
            if speed in speeds:
                speed = speeds[speed]
            else:
                raise ValueError('Invalid speed: ' + str(speed))

        return self._client.config.set('Common', 'SubMode', speed)

#        TODO this code sets speed via API, which doesn't work as of JS8Call v2.2
#        msg = Message()
#        msg.set('type', Message.MODE_SET_SPEED)
#        msg.set('params', {'SPEED': speed})
#        self._client.js8call.send(msg)
#        time.sleep(self._client._set_get_delay)
#        return self.get_speed()

    def get_freq(self, update=False):
        '''Get JS8Call dial frequency.

        Args:
            update (bool): Update if True or use local state if False, defaults to False

        Returns:
            int: Dial frequency in Hz
        '''
        freq = self._client.js8call.get_state('dial')

        if update or freq is None:
            msg = Message()
            msg.type = Message.RIG_GET_FREQ
            self._client.js8call.send(msg)
            freq = self._client.js8call.watch('dial')

        return freq

    def set_freq(self, freq):
        '''Set JS8Call dial frequency.

        Args:
            freq (int): Dial frequency in Hz

        Returns:
            int: Dial frequency in Hz
        '''
        msg = Message()
        msg.set('type', Message.RIG_SET_FREQ)
        msg.set('params', {'DIAL': freq, 'OFFSET': self._client.js8call.state['offset']})
        self._client.js8call.send(msg)
        time.sleep(self._client._set_get_delay)
        return self.get_freq(update = True)

    def get_offset(self, update=False):
        '''Get JS8Call offset frequency.

        Args:
            update (bool): Update if True or use local state if False, defaults to False

        Returns:
            int: Offset frequency in Hz
        '''
        offset = self._client.js8call.get_state('offset')
        
        if update or offset is None:
            msg = Message()
            msg.type = Message.RIG_GET_FREQ
            self._client.js8call.send(msg)
            offset = self._client.js8call.watch('offset')

        return offset

    def set_offset(self, offset):
        '''Set JS8Call offset frequency.

        Args:
            offset (int): Offset frequency in Hz

        Returns:
            int: Offset frequency in Hz
        '''
        msg = Message()
        msg.set('type', Message.RIG_SET_FREQ)
        msg.set('params', {'DIAL': self._client.js8call.state['dial'], 'OFFSET': offset})
        self._client.js8call.send(msg)
        time.sleep(self._client._set_get_delay)
        return self.get_offset(update = True)

    def get_station_callsign(self, update=False):
        '''Get JS8Call callsign.

        Args:
            update (bool): Update if True or use local state if False, defaults to False

        Returns:
            str: JS8Call configured callsign
        '''
        callsign = self._client.js8call.get_state('callsign')

        if update or callsign is None:
            msg = Message()
            msg.type = Message.STATION_GET_CALLSIGN
            self._client.js8call.send(msg)
            callsign = self._client.js8call.watch('callsign')

        return callsign

    def set_station_callsign(self, callsign):
        '''Set JS8Call callsign.

        Callsign must be a maximum of 9 characters and contain at least one number.

        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.

        Args:
            callsign (str): Callsign to set

        Returns:
            str: JS8Call configured callsign
        '''
        callsign = callsign.upper()

        if len(callsign) <= 9 and any(char.isdigit() for char in callsign):
            return self.config.set('Configuration', 'MyCall', callsign)
        else:
            raise ValueError('callsign must be <= 9 characters in length and contain at least 1 number')

    def get_station_grid(self, update=False):
        '''Get JS8Call grid square.

        Args:
            update (bool): Update if True or use local state if False, defaults to False

        Returns:
            str: JS8Call configured grid square
        '''
        grid = self._client.js8call.get_state('grid')

        if update or grid is None:
            msg = Message()
            msg.type = Message.STATION_GET_GRID
            self._client.js8call.send(msg)
            grid = self._client.js8call.watch('grid')

        return grid

    def set_station_grid(self, grid):
        '''Set JS8Call grid square.

        Args:
            grid (str): Grid square

        Returns:
            str: JS8Call configured grid square
        '''
        grid = grid.upper()
        msg = Message()
        msg.type = Message.STATION_SET_GRID
        msg.value = grid
        self._client.js8call.send(msg)
        time.sleep(self._client._set_get_delay)
        return self.get_station_grid(update = True)

    def get_station_info(self, update=False):
        '''Get JS8Call station information.

        Args:
            update (bool): Update if True or use local state if False, defaults to False

        Returns:
            str: JS8Call configured station information
        '''
        info = self._client.js8call.get_state('info')

        if update or info is None:
            msg = Message()
            msg.type = Message.STATION_GET_INFO
            self._client.js8call.send(msg)
            info = self._client.js8call.watch('info')

        return info

    def set_station_info(self, info):
        '''Set JS8Call station information.

        Args:
            info (str): Station information

        Returns:
            str: JS8Call configured station information
        '''
        msg = Message()
        msg.type = Message.STATION_SET_INFO
        msg.value = info
        self._client.js8call.send(msg)
        time.sleep(self._client._set_get_delay)
        return self.get_station_info(update = True)

    def get_bandwidth(self, speed=None):
        '''Get JS8Call signal bandwidth based on modem speed.

        Uses JS8Call configured speed if no speed is given.

        | Speed | Bandwidth |
        | -------- | -------- |
        | slow | 25 Hz |
        | normal | 50 Hz |
        | fast | 80 Hz |
        | turbo | 160 Hz |
        | ultra | 250 Hz |

        Args:
            speed (str): Speed setting, defaults to None

        Returns:
            int: Bandwidth of JS8Call signal
        '''
        if speed is None:
            speed = self.get_speed()
        elif isinstance(speed, int):
            speed = self.submode_to_speed(speed)

        bandwidths = {'slow':25, 'normal':50, 'fast':80, 'turbo':160, 'ultra':250}

        if speed in bandwidths:
            return bandwidths[speed]
        else:
            raise ValueError('Invalid speed \'' + speed + '\'')

    def get_window_duration(self, speed=None):
        '''Get JS8Call rx/tx window duration based on modem speed.

        Uses JS8Call configured speed if no speed is given.

        | Speed | Duration |
        | -------- | -------- |
        | slow | 30 seconds |
        | normal | 15 seconds |
        | fast | 10 seconds |
        | turbo | 6 seconds |
        | ultra | 4 seconds |

        Args:
            speed (str): Speed setting, defaults to None

        Returns:
            int: Duration of JS8Call rx/tx window in seconds
        '''
        if speed is None:
            speed = self.get_speed()
        elif isinstance(speed, int):
            speed = self.submode_to_speed(speed)

        duration = {'slow': 30, 'normal': 15, 'fast': 10, 'turbo': 6, 'ultra':4}
        return duration[speed]



class Callbacks:
    '''Callback functions container.
    
    This class is initilized by pyjs8call.client.Client.

    Attributes:
        incoming (dict): Incoming message callback function lists organized by message type
        outgoing (func): Outgoing message status change callback function, defaults to None
        spots (func): New spots callback funtion, defaults to None
        station_spot (func): Watched station spot callback function, defaults to None
        group_spot (func): Watched group spot callback function, defaults to None
        window (func): Transmit window transition callback function, defaults to None

    *incoming* structure: *{type: [callback, ...], ...}*
    - *type* is an incoming  message type (see pyjs8call.message for information on message types)
    - *callback* function signature: *func(msg)* where *msg* is a pyjs8call.message object

    *outgoing* callback signature: *func(msg)* where *msg* is a pyjs8call.message object
    - Called by pyjs8call.txmonitor

    *spots* callback signature: *func( list(msg, ...) )* where *msg* is a pyjs8call.message object
    - Called by pyjs8call.spotmonitor

    *station_spot* callback signature: *func(msg)* where *msg* is a pyjs8call.message object
    - Called by pyjs8call.spotmonitor

    *group_spot* callback signature: *func(msg)* where *msg* is a pyjs8call.message object
    - Called by pyjs8call.spotmonitor

    *window* callback signature: *func()*
    - Called by pyjs8call.windowmonitor

    *inbox* callback signature: *func(msgs)* where *msgs* is a list of *dict* message items
    - See *client.get_inbox_messages()* for message item *dict* key details
    - Called by pyjs8call.inboxmonitor
    '''

    def __init__(self):
        '''Initialize callback object.

        Returns:
            pyjs8call.client.Callbacks: Constructed callback object
        '''
        self.outgoing = None
        self.spots = None
        self.station_spot = None
        self.group_spot = None
        self.window = None
        self.inbox = None
        self.incoming = {
            Message.RX_DIRECTED: [],
        }

    def register_incoming(self, callback, message_type=Message.RX_DIRECTED):
        '''Register incoming message callback function.

        Incoming message callback functions are associated with specific message types. The directed message type is assumed unless otherwise specified. See pyjs8call.message for more information on message types.

        Note that pyjs8call internal modules may register callback functions for specific message type handling.

        Args:
            callback (func): Callback function object
            message_type (str): Associated message type, defaults to RX_DIRECTED

        *callback* function signature: *func(msg)* where *msg* is a pyjs8call.message object

        Raises:
            TypeError: An invaid message type is specified
        '''
        if message_type not in Message.RX_TYPES:
            raise TypeError('Invalid message type \'' + str(message_type) + '\', see pyjs8call.Message.RX_TYPES')

        if message_type not in self.incoming:
            self.incoming[message_type] = []

        self.incoming[message_type].append(callback)

    def remove_incoming(self, callback, message_type=None):
        '''Remove incoming message callback function.
    
        If *message_type* is None *callback* is removed from all message types.

        Args:
            callback (func): Function to remove
            message_type (str): Message type to remove function from, defaults to None
        '''
        for msg_type, callbacks in self.incoming.items():
            if message_type in (None, msg_type) and callback in callbacks:
                self.incoming[msg_type].remove(callback)

    def incoming_type(self, message_type=Message.RX_DIRECTED):
        '''Get incoming message callback functions.
        
        See pyjs8call.message for more information on message types.
        
        Args:
            message_type (str): Message type, defaults to RX_DIRECTED
        
        Returns:
            list: Callback functions associated with the specified message type
        '''
        if message_type in self.incoming:
            return self.incoming[message_type]
        else:
            return []

