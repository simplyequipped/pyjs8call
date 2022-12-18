import json
import time
from datetime import datetime, timezone
import secrets


class Message:

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
        self.id = secrets.token_urlsafe(16)
        self.type = Message.TX_SEND_MESSAGE
        self.destination = destination
        self.value = value
        self.time = datetime.now(timezone.utc).timestamp()
        self.timestamp = time.time()
        self.params = {}
        self.attributes = ['id', 'type', 'to', 'value', 'time', 'params']
        self.packed = None
        self.status = Message.STATUS_CREATED
        
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
        if self.destination != None:
            self.destination = self.destination.upper()
        if self.value != None:
            self.value = self.value.upper()
            self.text = self.value

    def set(self, attribute, value):
        attribute = attribute.lower()
        setattr(self, attribute, value)

        if attribute not in self.attributes:
            self.attributes.append(attribute)

        # set 'from' = 'call' for consistency
        if attribute == 'call' and value != None and self.get('from') == None:
            self.set('from', value)

        # Message.from cannot be called directly, use origin instead
        if attribute == 'from':
            self.set('origin', value)

    def get(self, attribute):
        return getattr(self, attribute, None)

    def dict(self, exclude=[]):
        data = {}
        for attribute in self.attributes:
            # skip attribues excluded or already in dict
            if attribute in exclude or attribute in data.keys():
                continue

            value = self.get(attribute)

            # handle special cases
            if attribute == 'value':
                # replace None with empty string, 'value' is always included
                if value == None:
                    value = ''
                # build directed message
                elif self.type == Message.TX_SEND_MESSAGE and self.destination != None:
                    value = self.destination + ' ' + value

            # add to dict if value is set
            if value != None:
                data[attribute] = value

        return data

    def pack(self, exclude=[]):
        #TODO make sure 'text' is not used!

        # exclude attributes from packed data
        exclude.extend(['id', 'destination', 'time', 'from', 'origin', 'text'])
        data = self.dict(exclude = exclude)
        # convert dict to json string
        packed = json.dumps(data) + '\r\n'
        # return bytes
        return packed.encode('utf-8')

    # call using try/catch to handle parse errors during rx processing
    def parse(self, msg_str):
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
                    'from' : self.messages[i]['FROM'],
                    'to' : self.messages[i]['TO'],
                    'path' : self.messages[i]['PATH'],
                    'message' : self.messages[i]['TEXT']
                }

        # handle call activity
        elif self.type == Message.RX_CALL_ACTIVITY:
            self.call_activity = []
            for key, value in msg['params'].items():
                if key == '_ID' or value == None:
                    continue

                call = {
                    'from' : key,
                    'grid' : value['GRID'],
                    'snr' : value['SNR'],
                    'time' : value['UTC']
                }

                self.call_activity.append(call)

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
                except:
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
            if self.cmd == 'GRID' and self.text != None:
                grid = self.text.split()
                if len(grid) >= 4:
                    grid = grid[3]
                
                if Message.ERR in grid:
                    self.set('grid', None)
                else:
                    self.set('grid', grid)

        # allow usage like: msg = Message().parse(rx_str)
        return self
 
