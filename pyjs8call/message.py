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

'''Message object for incoming and outgoing messages.

Incoming and outgoing types, commands, and statuses are defined statically.
'''

__docformat__ = 'google'


import json
import time
import math
import base64
import secrets
from datetime import datetime, timezone


BASE64_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
'''Base64 characters for mapping to JS8Call supported characters'''
JS8CALL_BASE64_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ,.-"?!)(~:_&$%#@*><[]{}|;^0123456789+/'
'''JS8Call supported characters for mapping to Base64 characters'''
BASE64_TO_JS8CALL_TRANSLATION_TABLE = str.maketrans(BASE64_ALPHABET, JS8CALL_BASE64_ALPHABET)
'''Translation table from JS8Call supported characters to Base64 characters'''
JS8CALL_TO_BASE64_TRANSLATION_TABLE = str.maketrans(JS8CALL_BASE64_ALPHABET, BASE64_ALPHABET)
'''Translation table from Base64 characters to JS8Call supported characters'''

class Message:
    '''Message object for incoming and outgoing messages.

    Most attributes with a default value of None are included so messages can be handled internally without worrying about the nuances of JS8Call API message attributes, which vary greatly.

    Attributes:
        id (str): Random url-safe text string, 16 bytes in length
        type (str): Message type (see static types), defaults to TX_SEND_MESSAGE
        destination (str): Destination callsign
        value (str): Message contents
        timestamp (float): Epoch timestamp (always referenced to UTC)
        utc_time_str (float): UTC time string (ex. '21:42 UTC')
        local_time_str (str): Local time string (ex. '21:42L')
        tdrift (float): Time drift specified by JS8call, defaults to None
        params (dict): Message parameters used by certain JS8Call API messages
        attributes (list): Attributes for internal use (see *Message.set*)
        status (str): Message status (see static statuses), defaults to STATUS_CREATED
        raw (str): Raw message string passed to *Message.parse*, defaults to None
        packed (bytes): Byte string returned from *pack()*, defaults to None
        freq (str): Dial frequency plus offset frequency in Hz, defaults to None
        dial (str): Dial frequency in Hz, defaults to None
        offset (str): Passband offset frequency in Hz, defaults to None
        call (str): Callsign, used by certain JS8Call API messages, defaults to None
        grid (str): Grid square, default to None
        path (list): Parsed relay path, defaults to None
        snr (str): Signal-to-noise ratio, defaults to None
        from (str): Origin callsign, defaults to None
        origin (str): Origin callsign, defaults to None
        utc (str): UTC date/time string, defaults to None
        cmd (str): JS8Call command (see static commands), defaults to None
        text (str): Used by certain JS8Call API messages, defaults to None
        speed (str): JS8Call modem speed of received signal
        extra (str): Used by certain JS8Call API messages, defaults to None
        hearing (list): Response to HEARING? query, defaults to None
        messages (list): Inbox messages, defaults to None
        band_activity (list): JS8Call band activity items, defaults to None
        call_activity (list): JS8Call call activity items, defaults to None
        distance (int): Distance from JS8Call grid square to message grid square, defaults to None
        distance_units (str): Distance units (mi/km) of *distance*, defaults to None
        bearing (int): Bearing from JS8Call grid square to message grid square, defaults to None
        profile (str): Active configuration profile when message was received, defaults to None
        error (str): Error message, defaults to None

    *text* is also used to store 'cleaned' incoming message text, see *pyjs8call.client.clean_rx_message_text()*.
    '''

    # outgoing message types
    RX_GET_TEXT             = 'RX.GET_TEXT'
    RX_GET_CALL_ACTIVITY    = 'RX.GET_CALL_ACTIVITY'
    RX_GET_BAND_ACTIVITY    = 'RX.GET_BAND_ACTIVITY'
    RX_GET_SELECTED_CALL    = 'RX.GET_CALL_SELECTED'
    TX_SEND_MESSAGE         = 'TX.SEND_MESSAGE'
    TX_GET_TEXT             = 'TX.GET_TEXT'
    TX_SET_TEXT             = 'TX.SET_TEXT'
    MODE_GET_SPEED          = 'MODE.GET_SPEED'
    MODE_SET_SPEED          = 'MODE.SET_SPEED'
    STATION_GET_INFO        = 'STATION.GET_INFO'
    STATION_SET_INFO        = 'STATION.SET_INFO'
    STATION_GET_GRID        = 'STATION.GET_GRID'
    STATION_SET_GRID        = 'STATION.SET_GRID'
    STATION_GET_CALLSIGN    = 'STATION.GET_CALLSIGN'
    INBOX_GET_MESSAGES      = 'INBOX.GET_MESSAGES'
    INBOX_STORE_MESSAGE     = 'INBOX.STORE_MESSAGE'
    RIG_GET_FREQ            = 'RIG.GET_FREQ'
    RIG_SET_FREQ            = 'RIG.SET_FREQ'
    WINDOW_RAISE            = 'WINDOW.RAISE'
    PING                    = 'PING'

    # incoming message types
    MESSAGES                = 'MESSAGES'
    INBOX_MESSAGE           = 'INBOX.MESSAGE'
    INBOX_MESSAGES          = 'INBOX.MESSAGES'
    RX_SPOT                 = 'RX.SPOT'
    RX_DIRECTED             = 'RX.DIRECTED'
    RX_DIRECTED_ME          = 'RX.DIRECTED.ME'     # commented out in JS8Call source
    RX_SELECTED_CALL        = 'RX.CALL_SELECTED'
    RX_CALL_ACTIVITY        = 'RX.CALL_ACTIVITY'
    RX_BAND_ACTIVITY        = 'RX.BAND_ACTIVITY'
    RX_ACTIVITY             = 'RX.ACTIVITY'
    RX_TEXT                 = 'RX.TEXT'
    TX_TEXT                 = 'TX.TEXT'
    TX_FRAME                = 'TX.FRAME'
    RIG_FREQ                = 'RIG.FREQ'
    RIG_PTT                 = 'RIG.PTT'
    STATION_CALLSIGN        = 'STATION.CALLSIGN'
    STATION_GRID            = 'STATION.GRID'
    STATION_INFO            = 'STATION.INFO'
    STATION_STATUS          = 'STATION.STATUS'
    MODE_SPEED              = 'MODE.SPEED'
    LOG_QSO                 = 'LOG.QSO'
    
    TX_TYPES = [RX_GET_TEXT, RX_GET_CALL_ACTIVITY, RX_GET_BAND_ACTIVITY, RX_GET_SELECTED_CALL, TX_SEND_MESSAGE, TX_GET_TEXT, TX_SET_TEXT, MODE_GET_SPEED,
        MODE_SET_SPEED, STATION_GET_INFO, STATION_SET_INFO, STATION_GET_GRID, STATION_SET_GRID, STATION_GET_CALLSIGN, INBOX_GET_MESSAGES, INBOX_STORE_MESSAGE,
        RIG_GET_FREQ, RIG_SET_FREQ, WINDOW_RAISE]
    
    RX_TYPES = [MESSAGES, INBOX_MESSAGE, INBOX_MESSAGES, RX_SPOT, RX_DIRECTED, RX_DIRECTED_ME, RX_SELECTED_CALL, RX_CALL_ACTIVITY, RX_BAND_ACTIVITY,
        RX_ACTIVITY, RX_TEXT, TX_TEXT, TX_FRAME, RIG_FREQ, RIG_PTT, STATION_CALLSIGN, STATION_GRID, STATION_INFO, STATION_STATUS, MODE_SPEED, LOG_QSO]

    TYPES = TX_TYPES + RX_TYPES
    DIRECTED_TYPES = [RX_DIRECTED, RX_DIRECTED_ME]
    USER_MSG_TYPES = DIRECTED_TYPES + [TX_SEND_MESSAGE]

    # command types
    CMD_HB                  = ' HB'
    CMD_HEARTBEAT           = ' HEARTBEAT'
    CMD_HEARTBEAT_SNR       = ' HEARTBEAT SNR'
    CMD_CQ                  = ' CQ'
    CMD_SNR                 = ' SNR'
    CMD_SNR_Q               = ' SNR?'
    CMD_GRID_Q              = ' GRID?'
    CMD_GRID                = ' GRID'
    CMD_INFO_Q              = ' INFO?'
    CMD_INFO                = ' INFO'
    CMD_STATUS_Q            = ' STATUS?'
    CMD_STATUS              = ' STATUS'
    CMD_HEARING_Q           = ' HEARING?'
    CMD_HEARING             = ' HEARING'
    CMD_HW_CPY_Q            = ' HW CPY?'
    CMD_MSG                 = ' MSG'
    CMD_MSG_TO              = ' MSG TO:'
    CMD_QUERY               = ' QUERY'
    CMD_QUERY_MSGS          = ' QUERY MSGS'
    CMD_QUERY_MSGS_Q        = ' QUERY MSGS?'
    CMD_QUERY_CALL          = ' QUERY CALL'
    CMD_NO                  = ' NO'
    CMD_YES                 = ' YES'
    CMD_AGN_Q               = ' AGN?'
    CMD_ACK                 = ' ACK'
    CMD_NACK                = ' NACK'
    CMD_DIT_DIT             = ' DIT DIT'
    CMD_FB                  = ' FB'
    CMD_SK                  = ' SK'
    CMD_RR                  = ' RR'
    CMD_QSL                 = ' QSL'
    CMD_QSL_Q               = ' QSL?'
    CMD_CMD                 = ' CMD'
    CMD_73                  = ' 73'
    CMD_RELAY               = '>'
    CMD_Q                   = '?'
    CMD_FREETEXT            = ' '
    '''1x space'''
    CMD_FREETEXT_2          = '  '
    '''2x space'''

    COMMANDS = [CMD_HB, CMD_HEARTBEAT, CMD_HEARTBEAT_SNR, CMD_CQ, CMD_SNR_Q, CMD_Q, CMD_GRID_Q, CMD_GRID, CMD_INFO_Q, CMD_INFO, CMD_STATUS_Q,
        CMD_STATUS, CMD_HEARING_Q, CMD_HEARING, CMD_HW_CPY_Q, CMD_MSG, CMD_MSG_TO, CMD_QUERY, CMD_QUERY_MSGS, CMD_QUERY_MSGS_Q, CMD_QUERY_CALL,
        CMD_NO, CMD_YES, CMD_AGN_Q, CMD_ACK, CMD_NACK, CMD_DIT_DIT, CMD_FB, CMD_SK, CMD_RR, CMD_QSL, CMD_QSL_Q, CMD_CMD, CMD_SNR, CMD_73,
        CMD_RELAY, CMD_FREETEXT, CMD_FREETEXT_2]

    QUERY_COMMANDS = [CMD_SNR_Q, CMD_Q, CMD_HEARING_Q, CMD_GRID_Q, CMD_STATUS_Q, CMD_MSG, CMD_MSG_TO, CMD_QUERY, CMD_QUERY_MSGS,
        CMD_QUERY_MSGS_Q, CMD_QUERY_CALL, CMD_INFO_Q, CMD_AGN_Q, CMD_QSL_Q, CMD_HW_CPY_Q]

    AUTOREPLY_COMMANDS = [CMD_HEARTBEAT_SNR, CMD_SNR, CMD_GRID, CMD_INFO, CMD_STATUS, CMD_HEARING, CMD_NO, CMD_YES, CMD_ACK, CMD_NACK]

    CHECKSUM_COMMANDS = [CMD_RELAY, CMD_MSG, CMD_MSG_TO, CMD_QUERY, CMD_QUERY_CALL, CMD_CMD]

    # status types
    STATUS_CREATED          = 'created'
    STATUS_QUEUED           = 'queued'
    STATUS_SENDING          = 'sending'
    STATUS_SENT             = 'sent'
    STATUS_FAILED           = 'failed'
    STATUS_RECEIVED         = 'received'
    STATUS_ERROR            = 'error'

    STATUSES = [STATUS_CREATED, STATUS_QUEUED, STATUS_SENDING, STATUS_SENT, STATUS_FAILED, STATUS_RECEIVED, STATUS_ERROR]

    EOM = '♢'
    '''End-of-message character'''
    ERR = '…'
    '''Error character (ellipsis)'''

    # special group callsigns
    SPECIAL_GROUPS = [
        "@ALLCALL",
        "@JS8NET",
        "@DX/NA",
        "@DX/SA",
        "@DX/EU",
        "@DX/AS",
        "@DX/AF",
        "@DX/OC",
        "@DX/AN",
        "@REGION/1",
        "@REGION/2",
        "@REGION/3",
        "@GROUP/0",
        "@GROUP/1",
        "@GROUP/2",
        "@GROUP/3",
        "@GROUP/4",
        "@GROUP/5",
        "@GROUP/6",
        "@GROUP/7",
        "@GROUP/8",
        "@GROUP/9",
        "@COMMAND",
        "@CONTROL",
        "@NET",
        "@NTS",
        "@RESERVE/0",
        "@RESERVE/1",
        "@RESERVE/2",
        "@RESERVE/3",
        "@RESERVE/4",
        "@APRSIS",
        "@RAGCHEW",
        "@JS8",
        "@EMCOMM",
        "@ARES",
        "@MARS",
        "@AMRRON",
        "@RACES",
        "@RAYNET",
        "@RADAR",
        "@SKYWARN",
        "@CQ",
        "@HB",
        "@QSO",
        "@QSOPARTY",
        "@CONTEST",
        "@FIELDDAY",
        "@SOTA",
        "@IOTA",
        "@POTA",
        "@QRP",
        "@QRO"
    ]

    CQS = [
        "CQ CQ CQ",
        "CQ DX",
        "CQ QRP",
        "CQ CONTEST",
        "CQ FIELD",
        "CQ FD",
        "CQ CQ",
        "CQ"
    ]

    def __init__(self, destination=None, cmd=None, value=None, origin=None):
        '''Initialize message.

        For outgoing messages, *origin* is used to calculate number of frames.

        Args:
            destination (bool): Callsign to send the message to, defaults to None
            cmd (str): Command to use in message, defaults to None (see static commands)
            value (str): Message text to send, defaults to None
            origin (str): Local station callsign, defaults to None

        Returns:
            pyjs8call.message: Constructed message object
        '''
        self.attributes = []
        '''List of attributes set using Message.set()'''
        self.raw = None
        '''Raw incoming message string, defaults to None, not used for outgoing messages'''
        self.is_packed = False
        '''Whether message has been packed, defaults to False, not used for incoming messages'''
        self.packed = None
        '''Packed outgoing message string, defaults to None, not used for incoming messages'''
        self.packed_dict = None
        '''Packed outgoing message dictionary, defaults to None, not used for incoming messages'''
        self._bytes = None

        # initialize common msg fields
        common = [
            'freq',
            'dial',
            'offset',
            'tdrift',
            'call',
            'grid',
            'snr',
            'from',
            'origin',
            'utc',
            'path',
            'text',
            'speed',
            'extra',
            'hearing',
            'messages',
            'band_activity',
            'call_activity',
            'distance',
            'distance_units',
            'bearing',
            'profile',
            'error'
        ]

        for attribute in common:
            self.set(attribute, None)
        
        dt_utc = datetime.now(timezone.utc)

        self.set('id', secrets.token_urlsafe(16))
        self.set('type', Message.TX_SEND_MESSAGE)
        self.set('destination', destination)
        self.set('cmd', cmd)
        self.set('value', value)
        self.set('origin', origin)
        self.set('timestamp', dt_utc.timestamp())
        self.set('utc_time_str', '{} UTC'.format(dt_utc.strftime('%X')))
        self.set('local_time_str', '{}L'.format(dt_utc.astimezone().strftime('%X')))
        self.set('params', {})
        self.set('status', Message.STATUS_CREATED)

    def set(self, attribute, value):
        '''Set message attribute value.

        Uses *setattr* internally to add attributes to the message object. Added attributes are tracked in the *attributes* attribute. Attributes are converted to lowercase for consistency.

        Special attribute handling for consistency:
        - *call*: set *from* to the same value if *call* is not None and *from* is None
        - *from*: set *origin* to the same value
        - *to*: set *destination* to the same value
        - *value*: uppercase and set *text* to the same value if type *str*
        - *destination*: uppercase if type *str*, uppercase all items if type *list*

        **Note:** attempting to access *Message.from* directly results in an error since *from* is a keyword in Python.

        Args:
            attribute (str): Name of attribute to set
            value (any): Value of attribute to set
        '''
        attribute = attribute.lower()
        setattr(self, attribute, value)

        if attribute not in self.attributes:
            self.attributes.append(attribute)

        if attribute == 'call' and value is not None and self.get('from') is None:
            # set 'from' = 'call' for consistency
            self.set('from', value)

        elif attribute == 'from':
            # Message.from cannot be called directly, use origin instead
            self.set('origin', value)

        elif attribute == 'to':
            # set 'destination' = 'to' for consistency
            self.set('destination', value)

        elif attribute == 'value' and isinstance(value, str):
            # uppercase so tx monitor can compare to tx text field
            self.value = value.upper()
            self.set('text', value.upper())

        # uppercase so tx monitor can compare to tx text field
        elif attribute == 'destination' and isinstance(value, list):
            # handle relay
            self.destination = [dest.upper() for dest in value]
            
        elif attribute == 'destination' and isinstance(value, str):
            self.destination = value.upper()

    def get(self, attribute):
        '''Get message attribute value.

        Uses *getattr* internally.

        Args:
            attribute (str): Name of attribute to get

        Returns:
            Value of specified attribute, or None if the attribute does not exist
        '''
        return getattr(self, attribute, None)

    def dict(self, exclude=None):
        '''Get dictionary representation of message object.

        Message attributes set to None are not included in the returned dictionary.

        Special attribute handling:
        *value*
        - If None, set to '' (empty string)
        - For directed messages join *destination*, *cmd*, and *value* appropriately

        Args:
            exclude (list): Attribute names to exclude (see *pack*), defaults to *[]*

        Returns:
            dict: Message attributes and values
        '''
        if exclude is None:
            exclude = []

        data = {}
        for attribute in self.attributes:
            # skip attribues excluded or already in dict
            if attribute in exclude or attribute in data:
                continue

            value = self.get(attribute)

            # handle special cases
            if attribute == 'value':
                # 'value' is always included
                if value is None:
                    value = ''

                # directed message
                if self.type == Message.TX_SEND_MESSAGE and self.destination is not None:
                    if isinstance(self.destination, list):
                        # handle relay
                        destination = Message.CMD_RELAY.join(self.destination)
                    else:
                        destination = self.destination
                    
                    if self.cmd is None:
                        # directed message without command
                        # note: double space!
                        value = '{}  {}'.format(destination, value)
                    else:
                        # directed message with command
                        value = '{}{} {}'.format(destination, self.cmd, value)

                value = value.strip()

            # add to dict if value is set
            if value is not None:
                data[attribute] = value

        return data

    def pack(self, exclude=None):
        '''Pack message for transmission over TCP socket.

        If message is already packed, packed value is returned without repacking.

        The following attributes are excluded by default:
        - id
        - destination
        - origin
        - cmd
        - from
        - timestamp
        - utc_time_str
        - local_time_str
        - text
        - status
        - profile
        - error

        Args:
            exclude (list): Attribute names to exclude, defaults to None
            
        Returns:
            UTF-8 encoded byte string. A dictionary representation of the message attributes is converted to a string using *json.dumps* before encoding.
        '''
        if self.is_packed:
            return self.packed
            
        if exclude is None:
            exclude = [] 

        exclude.extend(['id', 'destination', 'cmd', 'timestamp', 'utc_time_str', 'local_time_str', 'from', 'origin', 'text', 'status', 'profile', 'error'])

        self.packed_dict = self.dict(exclude = exclude)
        # convert dict to json string
        packed = json.dumps(self.packed_dict) + '\r\n'
        self.packed = packed.encode('utf-8')
        self.is_packed = True
        
        return self.packed

    def parse(self, msg_str):
        '''Load message string into message object.
        
        Supports usage like `Message().parse(raw_incoming_string)`

        *Message.parse* should be called inside a try/except block to handle parsing errors.

        Args:
            msg_str (str): Received message string to parse

        Returns:
            pyjs8call.message: self
        '''
        self.raw = msg_str
        msg = json.loads(msg_str)
        
        # parse top level message fields
        self.type = msg['type'].strip()
        
        if 'value' in msg.keys():
            self.value = msg['value'].strip()

        # parse paramater fields
        for param, value in msg['params'].items():
            param = param.strip()

            # maintain spaces before commands
            if isinstance(value, str) and param != 'CMD':
                value = value.strip()

            self.set(param, value)
        
        # type handling
        
        if self.type == Message.INBOX_MESSAGES:
            self.messages = []
            
            for message in msg['params']['MESSAGES']:
                dt_utc = datetime.strptime(message['params']['UTC'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)

                self.messages.append({
                    'cmd' : message['params']['CMD'],
                    'freq' : message['params']['DIAL'],
                    'offset' : message['params']['OFFSET'],
                    'snr' : message['params']['SNR'],
                    'speed' : message['params']['SUBMODE'],
                    'timestamp' : dt_utc.timestamp(),
                    'utc_time_str': '{} UTC'.format(dt_utc.strftime('%X')),
                    'local_time_str' : '{}L'.format(dt_utc.astimezone().strftime('%X')),
                    'origin' : message['params']['FROM'],
                    'destination' : message['params']['TO'],
                    'path' : message['params']['PATH'],
                    'text' : message['params']['TEXT'].strip(),
                    'value' : message['value'],
                    'status' : message['type'].lower(),
                    'unread': bool(message['type'].lower() == 'unread'),
                    'stored': bool(message['type'].lower() == 'store')
                })

        elif self.type == Message.RX_CALL_ACTIVITY:
            self.call_activity = []
            for key, value in msg['params'].items():
                if key == '_ID' or value is None:
                    continue

                dt_utc = datetime.utcfromtimestamp(value['UTC'] / 1000) # milliseconds to seconds

                self.call_activity.append({
                    'origin' : key,
                    'grid' : value['GRID'].strip(),
                    'snr' : value['SNR'],
                    'timestamp' : dt_utc.timestamp(),
                    'utc_time_str' : '{} UTC'.format(dt_utc.strftime('%X')),
                    'local_time_str' : '{}L'.format(dt_utc.astimezone().strftime('%X'))
                })

        elif self.type == Message.RX_BAND_ACTIVITY:
            self.band_activity = []
            for key, value in msg['params'].items():
                try:
                    # skip if key is not a freq offset (int)
                    int(key)

                    dt_utc = datetime.utcfromtimestamp(value['UTC'] / 1000) # milliseconds to seconds

                    self.band_activity.append({
                        'freq' : value['DIAL'],
                        'offset' : value['OFFSET'],
                        'snr' : value['SNR'],
                        'timestamp' : dt_utc.timestamp(),
                        'utc_time_str' : '{} UTC'.format(dt_utc.strftime('%X')),
                        'local_time_str' : '{}L'.format(dt_utc.astimezone().strftime('%X')),
                        'text' : value['TEXT']
                    })
                except ValueError:
                    continue

        # command handling

        if self.cmd == Message.CMD_GRID and self.text is not None and Message.ERR not in self.text:
            grid = self.text.split()
            
            if len(grid) >= 4:
                self.set('grid', grid[3])
                
        elif self.cmd == Message.CMD_HEARING and self.text is not None and Message.ERR not in self.text:
            # 0 = origin, 1 = destination, 2 = command, -1 = EOM
            hearing = self.text.split()[3:-1]
            self.set('hearing', hearing)

        # relay path handling

        if self.path is not None and Message.CMD_RELAY in self.path and Message.ERR not in self.path:
            self.path = self.path.strip(Message.CMD_RELAY).split(Message.CMD_RELAY)

        # allow usage like: msg = Message().parse(rx_str)
        return self
 
    def age(self):
        '''Message age in seconds.
        
        Returns:
            float: Message age in seconds
        '''
        return time.time() - self.timestamp

    def is_directed(self):
        '''Message object is directed message.

        Used internally.

        Returns:
            bool: True if message is a directed message, False otherwise
        '''
        return bool(self.type in Message.DIRECTED_TYPES or self.cmd in Message.COMMANDS)
        
    def is_directed_to(self, station):
        '''Message object is directed to specified station.

        If *station* is a list of callsigns and/or groups then each is compared to *Message.destination*. Returns *True* if any match. This is useful for filtering incoming messages per a list of callsigns and groups associated with the local station.

        Args:
            station (str, list): Callsign(s) to compare to *destination*

        Returns:
            bool: True if message is a directed to the specified station, False otherwise
        '''
        if isinstance(station, str):
            return bool(self.is_directed() and self.destination == station.upper())

        elif isinstance(station, list):
            return any( [self.is_directed_to(str(callsign)) for callsign in station] )

    def is_relay(self):
        '''Message is relayed.

        Incoming relay message *path* attribute is a list. Outgoing relay message *destination* attribute is a list.

        Returns:
            bool: *True* if message is relayed, *False* otherwise
        '''
        if type(self.destination) == list or type(self.path) == list:
            return True

        return False

    def dump(self):
        '''Get object attributes as *str*.

        For use with *load()*.

        Returns:
            str: *dict* of attributes converted using *json.dumps*
        '''
        return json.dumps( dict(zip(self.attributes, map(self.get, self.attributes))) )

    def load(self, msg_str):
        '''Load object attributes from *str*.

        For use with *dump()*.

        Args:
            msg_str (str): *str* of attributes to convert using *json.loads*

        Returns:
            pyjs8call.Message: self, for use like `msg = Message().load(str)`
        '''
        for attribute, value in json.loads(msg_str.strip()).items():
            self.set(attribute, value)

        return self

    def encode(self):
        '''Encode incoming JS8Call compatible message value to bytes.

        Due to the limited character set of JS8Call, a unique process is used to re-encode JS8Call compatible text back to bytes. The text to be re-encoded is derived by *Message.decode()*.
        
        Custom encoding process: `JS8Call compatible text -> translate to Base64 alphabet -> encode to byte string -> decode Base64 to bytes`

        The *text* attribute is processed to support cleaning of incoming directed message text. If *text* is not set, and *value* is set, *value* is processed instead.
        
        Returns:
            bytes: Message text converted to bytes
        '''
        global JS8CALL_TO_BASE64_TRANSLATION_TABLE

        if self.get('text') is not None and len(self.get('text')) > 0:
            # use msg.text if set
            msg_value = self.text
        elif self.get('value') is not None and len(self.get('value')) > 0:
            # use msg.value if set
            msg_value = self.value
        else:
            # set and return empty bytes string
            self._bytes = b''
            return self._bytes

        try:
            # translate js8call alphabet to base46 alphabet
            base64_text = msg_value.translate(JS8CALL_TO_BASE64_TRANSLATION_TABLE)
            # encode to bytes
            base64_bytes = base64_text.encode()
            # decode base64 to bytes
            self._bytes = base64.b64decode(base64_bytes)
        except Exception as e:
            self._bytes = b''
            
        return self._bytes
    
    def decode(self, bytes_str):
        '''Decode outgoing bytes to JS8Call compatible message value.

        Due to the limited character set of JS8Call, a unique process is used to decode bytes into JS8Call compatible text. The decoded text can be re-encoded using *Message.encode()*.
        
        Custom decoding process: `bytes -> encode bytes to Base64 -> decode to string -> translate to JS8Call alphabet -> JS8Call compatible text`

        Supports usage like `Message().decode(byte_string)`.

        Args:
            bytes_str (bytes): Byte string to decode into JS8Call compatible text

        Returns:
            pyjs8call.Message: Message object with *value* attribute set to decoded text string

        Raises:
            TypeError: *bytes_str* is not type bytes
        '''
        global BASE64_TO_JS8CALL_TRANSLATION_TABLE

        if not isinstance(bytes_str, bytes):
            raise TypeError('Only type \'bytes\' can be decoded')
        
        try:
            # convert bytes to base64
            base64_bytes = base64.b64encode(bytes_str)
            # decode from bytes
            base64_text = base64_bytes.decode()
            # translate base64 alphabet to js8call alphabet
            msg_value = base64_text.translate(BASE64_TO_JS8CALL_TRANSLATION_TABLE)
            self.set('value', msg_value)
        except Exception as e:
            self.set('value', '')
            
        return self
        
    def __eq__(self, msg):
        '''Whether another message is considered equal to self.

        There are multiple cases where spots are considered equal:
        - When both incoming messages have the same timestamps (literally the same message)
        - When both incoming messages have the same origin, offset frequency, and snr (same station event reported by differnt JS8Call API messages at slightly different times) 
        - When both outgoing messages have the same timestamp, type, and value

        Args:
            msg (pyjs8call.message): Message to compare

        Returns:
            bool: *True* if the two messages are considered equal, *False* otherwise
        '''
        if not isinstance(msg, Message):
            return False

        # comparing origin, offset, and snr allows equating the same message sent more than once
        # from the js8call application (likely as different message types) at slightly different
        # times (likely milliseconds apart)
        if msg.type in self.RX_TYPES:
            return bool( self.timestamp == msg.timestamp or
                (msg.origin == self.origin and msg.offset == self.offset and msg.snr == self.snr) )

        else:
            # tx types
            return bool(msg.type == self.type and msg.value == msg.value and msg.timestamp == self.timestamp)

    def __lt__(self, msg):
        '''Whether another message is less than self.

        Timestamps are compared.

        Args:
            msg (pyjs8call.message): Message to compare

        Returns:
            bool: *True* if self.timestamp is less than the specified msg.timestamp, *False* otherwise
        '''
        return bool(self.timestamp < msg.timestamp)

    def __gt__(self, msg):
        '''Whether another message is greater than self.

        Timestamps are compared.

        Args:
            msg (pyjs8call.message): Message to compare

        Returns:
            bool: *True* if self.timestamp is greater than the specified msg.timestamp, *False* otherwise
        '''
        return bool(self.timestamp > msg.timestamp)

    def __repr__(self):
        return '<{} message {}>'.format(self.type, self.id)

