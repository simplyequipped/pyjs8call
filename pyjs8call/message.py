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
from datetime import datetime, timezone
import secrets


class Message:
    '''Message object for incoming and outgoing messages.

    Static outgoing types:
    - RX_GET_TEXT
    - RX_GET_CALL_ACTIVITY
    - RX_GET_BAND_ACTIVITY
    - RX_GET_SELECTED_CALL
    - TX_SEND_MESSAGE
    - TX_GET_TEXT
    - TX_SET_TEXT
    - MODE_GET_SPEED
    - MODE_SET_SPEED
    - STATION_GET_INFO
    - STATION_SET_INFO
    - STATION_GET_GRID
    - STATION_SET_GRID
    - STATION_GET_CALLSIGN
    - INBOX_GET_MESSAGES
    - INBOX_STORE_MESSAGE
    - RIG_GET_FREQ
    - RIG_SET_FREQ
    - WINDOW_RAISE

    Static incoming types:
    - MESSAGES
    - INBOX_MESSAGES
    - RX_SPOT
    - RX_DIRECTED
    - RX_SELECTED_CALL
    - RX_CALL_ACTIVITY
    - RX_BAND_ACTIVITY
    - RX_ACTIVITY
    - RX_TEXT
    - TX_TEXT
    - TX_FRAME
    - RIG_FREQ
    - RIG_PTT
    - STATION_CALLSIGN
    - STATION_GRID
    - STATION_INFO
    - STATION_STATUS
    - MODE_SPEED

    Static message types:
    - TX_TYPES (outgoing types)
    - RX_TYPES (incoming types)
    - TYPES (outgoing and incoming types)

    Static commands:
    - CMD_SNR
    - CMD_GRID
    - CMD_HEARING
    - CMD_QUERY_CALL

    Static statuses:
    - STATUS_CREATED
    - STATUS_QUEUED
    - STATUS_SENDING
    - STATUS_SENT
    - STATUS_FAILED
    - STATUS_RECEIVED
    - STATUS_ERROR

    Static constants:
    - ERR
    - EOM

    &nbsp;

    Most attributes with a default value of None are included so messages can be handled internally without worrying about the nuances of JS8Call API message attributes, which vary greatly.

    Attributes:
        id (str): Random url-safe text string, 16 bytes in length
        type (str): Message type (see static types), defaults to TX_SEND_MESSAGE
        destination (str): Destination callsign
        value (str): Message contents
        time (str): UTC timestamp (see datetime.now(timezone.utc).timestamp)
        timestamp (str): Local timestamp (see time.time)
        params (dict): Message parameters used by certain JS8Call API messages
        attributes (list): Attributes for internal use (see *Message.set*)
        status (str): Message status (see static statuses), defaults to STATUS_CREATED
        raw (str): Raw message string passed to *Message.parse*, defaults to None
        freq (str): Dial frequency plus offset frequency in Hz, defaults to None
        dial (str): Dial frequency in Hz, defaults to None
        offset (str): Passband offset frequency in Hz, defaults to None
        call (str): Callsign, used by certain JS8Call API messages, defaults to None
        grid (str): Grid square, default to None
        snr (str): Signal-to-noise ratio, defaults to None
        from (str): Origin callsign, defaults to None
        origin (str): Origin callsign, defaults to None
        utc (str): UTC timestamp, defaults to None
        cmd (str): JS8Call command (see static commands), defaults to None
        text (str): Used by certain JS8Call API messages, defaults to None
        speed (str): JS8Call modem speed of received signal
        extra (str): Used by certain JS8Call API messages, defaults to None
        messages (list): Inbox messages, defaults to None
        band_activity (list): JS8Call band activity items, defaults to None
        call_activity (list): JS8Call call activity items, defaults to None

    *text* is also used to store 'cleaned' incoming message text, see *pyjs8call.client.Client.clean_rx_message_text*.
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
    STATION_GET_INFO        = 'STATION.SET_INFO'
    STATION_SET_INFO        = 'STATION.GET_INFO'
    STATION_GET_GRID        = 'STATION.GET_GRID'
    STATION_SET_GRID        = 'STATION.SET_GRID'
    STATION_GET_CALLSIGN    = 'STATION.GET_CALLSIGN'
    INBOX_GET_MESSAGES      = 'INBOX.GET_MESSAGES'
    INBOX_STORE_MESSAGE     = 'INBOX.STORE_MESSAGE'
    RIG_GET_FREQ            = 'RIG.GET_FREQ'
    RIG_SET_FREQ            = 'RIG.SET_FREQ'
    WINDOW_RAISE            = 'WINDOW.RAISE'

    TX_TYPES = [RX_GET_TEXT, RX_GET_CALL_ACTIVITY, RX_GET_BAND_ACTIVITY, RX_GET_SELECTED_CALL, TX_SEND_MESSAGE, TX_GET_TEXT, TX_SET_TEXT, MODE_GET_SPEED, MODE_SET_SPEED, STATION_GET_INFO, STATION_SET_INFO, STATION_GET_GRID, STATION_SET_GRID, STATION_GET_CALLSIGN, INBOX_GET_MESSAGES, INBOX_STORE_MESSAGE, RIG_GET_FREQ, RIG_SET_FREQ, WINDOW_RAISE]
    
    # incoming message types
    MESSAGES                = 'MESSAGES'
    INBOX_MESSAGES          = 'INBOX.MESSAGES'
    RX_SPOT                 = 'RX.SPOT'
    RX_DIRECTED             = 'RX.DIRECTED'
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
    
    RX_TYPES = [MESSAGES, INBOX_MESSAGES, RX_SPOT, RX_DIRECTED, RX_SELECTED_CALL, RX_CALL_ACTIVITY, RX_BAND_ACTIVITY, RX_ACTIVITY, RX_TEXT, TX_TEXT, TX_FRAME, RIG_FREQ, RIG_PTT, STATION_CALLSIGN, STATION_GRID, STATION_INFO, MODE_SPEED]

    TYPES = TX_TYPES + RX_TYPES

    #TODO are more commands supported?
    # command types
    CMD_SNR                 = 'SNR'
    CMD_GRID                = 'GRID'
    CMD_HEARING             = 'HEARING'
    CMD_QUERY_CALL          = 'QUERY CALL'
    COMMANDS = [CMD_SNR, CMD_GRID, CMD_HEARING, CMD_QUERY_CALL]

    # status types
    STATUS_CREATED          = 'created'
    STATUS_QUEUED           = 'queued'
    STATUS_SENDING          = 'sending'
    STATUS_SENT             = 'sent'
    STATUS_FAILED           = 'failed'
    STATUS_RECEIVED         = 'received'
    STATUS_ERROR            = 'error'
    STATUSES = [STATUS_CREATED, STATUS_QUEUED, STATUS_SENDING, STATUS_SENT, STATUS_FAILED, STATUS_RECEIVED, STATUS_ERROR]

    # constants
    EOM = '♢'   # end of message, end of transmission
    ERR = '…'   # error

    def __init__(self, destination=None, value=None):
        '''Initialize message.

        Args:
            destination (bool): Callsign to send the message to, defaults to None
            value (str): Message text to send, defaults to None

        Returns:
            pyjs8call.message: Constructed message object
        '''
        self.id = secrets.token_urlsafe(16)
        self.type = Message.TX_SEND_MESSAGE
        self.destination = destination
        self.value = value
        self.time = datetime.now(timezone.utc).timestamp()
        self.timestamp = time.time()
        self.params = {}
        self.attributes = ['id', 'type', 'destination', 'value', 'time', 'params']
        self.status = Message.STATUS_CREATED
        self.raw = None
        
        # initialize common msg fields
        attrs = [
            'freq',
            'dial',
            'offset',
            'call',
            'grid',
            'snr',
            'from',
            'origin',
            'utc',
            'cmd',
            'text',
            'speed',
            'extra',
            'messages',
            'band_activity',
            'call_activity'
        ]

        for attr in attrs:
            self.set(attr, None)

        # uppercase values in tx msg
        if self.destination is not None:
            self.destination = self.destination.upper()
        if self.value is not None:
            self.value = self.value.upper()
            self.text = self.value

    def set(self, attribute, value):
        '''Set message attribute value.

        Uses *setattr* internally to add attributes to the message object. Added attributes are tracked in the *attributes* attribute. Attributes are converted to lowercase for consistency.

        Special attribute handling for consistency:
        - *call*: also sets *from* to the same value if *call* is not None and *from* is None
        - *from*: also sets *origin* to the same value

        Note that attempting to access Message.from results in an error.

        Args:
            attribute (str): Name of attribute to set
            value (str): Value of attribute to set
        '''
        attribute = attribute.lower()
        setattr(self, attribute, value)

        if attribute not in self.attributes:
            self.attributes.append(attribute)

        # set 'from' = 'call' for consistency
        if attribute == 'call' and value is not None and self.get('from') is None:
            self.set('from', value)

        # Message.from cannot be called directly, use origin instead
        if attribute == 'from':
            self.set('origin', value)

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
        - If set and Message.type is TX_SEND_MESSAGE and Message.destination is not None (i.e. directed message), set to Message.destination and Message.value joined with a space.

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
                # replace None with empty string, 'value' is always included
                if value is None:
                    value = ''
                # build directed message
                elif self.type == Message.TX_SEND_MESSAGE and self.destination is not None:
                    value = self.destination + ' ' + value

            # add to dict if value is set
            if value is not None:
                data[attribute] = value

        return data

    def pack(self, exclude=None):
        '''Pack message for transmission over TCP socket.

        The following attributes are excluded by default:
        - id
        - destination
        - time
        - from
        - origin
        - text

        Args:
            exclude (list): Attribute names to exclude, defaults to None
            
        Returns:
            UTF-8 encoded byte string. A dictionary representation of the message attributes is converted to a string using *json.dumps* before encoding.
        '''
        if exclude is None:
            exclude = [] 

        #TODO make sure 'text' is not used since it is excluded by default
        exclude.extend(['id', 'destination', 'time', 'from', 'origin', 'text'])

        data = self.dict(exclude = exclude)
        # convert dict to json string
        packed = json.dumps(data) + '\r\n'
        # return bytes
        return packed.encode('utf-8')

    def parse(self, msg_str):
        '''Load message string into message object.

        *Message.parse* should be called inside a try/except block to catch parsing errors.

        Args:
            msg_str (str): Received message string to parse and load

        Returns:
            pyjs8call.message: self
        '''
        self.raw = msg_str
        msg = json.loads(msg_str)

        self.type = msg['type'].strip()
        
        # handle inbox messages
        if self.type == Message.MESSAGES:
            self.messages = [m['params'] for m in msg['params']['MESSAGES']]
            
            for i in range(len(self.messages)):
                self.messages[i] = {
                    'id' : self.messages[i]['_ID'],
                    'time' : self.messages[i]['UTC'],
                    'origin' : self.messages[i]['FROM'],
                    'destination' : self.messages[i]['TO'],
                    'path' : self.messages[i]['PATH'],
                    'text' : self.messages[i]['TEXT']
                }

        # handle call activity
        elif self.type == Message.RX_CALL_ACTIVITY:
            self.call_activity = []
            for key, value in msg['params'].items():
                if key == '_ID' or value is None:
                    continue

                call = {
                    'origin' : key,
                    'grid' : value['GRID'],
                    'snr' : value['SNR'],
                    'time' : value['UTC']
                }

                self.call_activity.append(call)

        #TODO improve handling, remove try/except
        # handle band activity
        elif self.type == Message.RX_BAND_ACTIVITY:
            self.band_activity = []
            for key, value in msg['params'].items():
                try:
                    # skip if key is not a freq offset (int)
                    int(key)

                    data = {
                        'freq' : value['DIAL'],
                        'offset' : value['OFFSET'],
                        'snr' : value['SNR'],
                        'time' : value['UTC'],
                        'text' : value['TEXT']
                    }

                    self.band_activity.append(data)
                except ValueError:
                    continue

        else:
            if 'value' in msg.keys():
                self.value = msg['value'].strip()

            # parse remaining msg fields
            for param, value in msg['params'].items():
                param = param.strip()
                if isinstance(value, str):
                    value = value.strip()

                self.set(param, value)

            #TODO copied from js8net, test
            if self.cmd == 'GRID' and self.text is not None:
                grid = self.text.split()
                if len(grid) >= 4:
                    grid = grid[3]
                
                if Message.ERR in grid:
                    self.set('grid', None)
                else:
                    self.set('grid', grid)

        # allow usage like: msg = Message().parse(rx_str)
        return self
 
    def age(self):
        '''Message age in seconds.
        
        Returns:
            float: Message age in seconds
        '''
        return time.time() - self.timestamp

    def __eq__(self, msg):
        '''Whether another message is considered equal to self.

        There are two cases where spots are considered equal:
        - When both messages have the same timestamps (literally the same message)
        - When both messages have the same origin, offset frequency, and snr (same station event reported by differnt JS8Call API messages at slightly differnt times) 

        Args:
            msg (pyjs8call.message): Message to compare

        Returns:
            bool: Whether the two messages are considered equal
        '''
        if not isinstance(msg, Message):
            return False

        # comparing origin, offset, and snr allows equating the same message sent more than once
        # from the js8call application (likely as different message types) at slightly different
        # times (likely milliseconds apart)
        return bool( self.timestamp == msg.timestamp or
            (msg.origin == self.origin and msg.offset == self.offset and msg.snr == self.snr) )

    def __lt__(self, msg):
        '''Whether another message is less than self.

        Timestamps are compared.

        Args:
            msg (pyjs8call.message): Message to compare

        Returns:
            bool: Whether self.timestamp is less than the specified msg.timestamp
        '''
        return bool(self.timestamp < msg.timestamp)

    def __gt__(self, msg):
        '''Whether another message is greater than self.

        Timestamps are compared.

        Args:
            msg (pyjs8call.message): Message to compare

        Returns:
            bool: Whether self.timestamp is greater than the specified msg.timestamp
        '''
        return bool(self.timestamp > msg.timestamp)

