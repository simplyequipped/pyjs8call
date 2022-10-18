import json
import time
from datetime import datetime, timezone


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
    TX_TEXT                 = 'RX.TEXT'
    TX_FRAME                = 'TX.FRAME'
    RIG_FREQ                = 'RIG.FREQ'
    RIG_PTT                 = 'RIG.PTT'
    STATION_CALLSIGN        = 'STATION.CALLSIGN'
    STATION_GRID            = 'STATION.GRID'
    STATION_INFO            = 'STATION.INFO'
    MODE_SPEED              = 'MODE.SPEED'
    # Non-JS8Call type, used for messages assembled by pyjs8call.RxMonitor
    ASSEMBLED               = 'ASSEMBLED'
    
    RX_TYPES = [MESSAGES, INBOX_MESSAGES, RX_SPOT, RX_DIRECTED, RX_SELECTED_CALL, RX_CALL_ACTIVITY, RX_BAND_ACTIVITY, RX_ACTIVITY, RX_TEXT, TX_TEXT, TX_FRAME, RIG_FREQ, RIG_PTT, STATION_CALLSIGN, STATION_GRID, STATION_INFO, MODE_SPEED, ASSEMBLED]

    #TODO are more commands supported?
    # command types
    CMD_SNR                 = 'SNR'
    CMD_GRID                = 'GRID'
    CMD_HEARING             = 'HEARING'
    CMD_QUERY_CALL          = 'QUERY CALL'
    COMMANDS = [CMD_SNR, CMD_GRID, CMD_HEARING, CMD_QUERY_CALL]

    # constants
    EOM = '♢'
    ERR = '…'

    def __init__(self, destination=None, value=None, raw=None):
        self.raw = raw
        self.type = Message.TX_SEND_MESSAGE
        self.destination = destination
        self.value = value
        self.time = datetime.now(timezone.utc).timestamp()
        self.snr = None
        self.messages = None
        self.band_activity = None
        self.call_activity = None
        self.params = {
            'FREQ'      : None,
            'DIAL'      : None,
            'OFFSET'    : None,
            'CALL'      : None,
            'GRID'      : None,
            'SNR'       : None,
            'FROM'      : None,
            'TO'        : None,
            'UTC'       : None,
            'CMD'       : None,
            'TEXT'      : None,
            'SPEED'     : None,
            'EXTRA'     : None
        }

    def data(self):
        data = {
            'type' : self.type,
            'value' : self.value,
            'time' : self.time,
            'messages' : self.messages,
            'band_activity' : self.band_activity,
            'call_activity' : self.call_activity
        }

        for param, value in self.params.items():
            data[param.lower()] = value

        # handle CALL param for consistency
        if data['call'] != None and data['from'] == None:
            data['from'] = data['call']

        return data

    def pack(self):
        if self.value == None:
            self.value = ''
        # handle directed message value
        elif self.type == Message.TX_SEND_MESSAGE and self.destination != None:
            self.value = self.destination + ' ' + self.value

        packed = {
            'type' : self.type,
            'value' : self.value,
            'params' : {param.upper(): value for (param, value) in self.params.items() if value != None}
        }

        packed = json.dumps(packed) + '\r\n'
        return packed.encode('utf-8')
        
    def parse(self, msg_str):
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
                    'callsign' : key,
                    'grid' : value['GRID'],
                    'snr' : value['SNR'],
                    'time' : value['UTC']
                }

                self.call_activity.append(call)

        #handle band activity
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
                        'message' : value['TEXT']
                    }

                    self.band_activity.append(data)
                except:
                    continue

        else:

            # get message time or set current UTC time
            #if 'time' in msg:
            #    self.time = msg['time']
            #else:
            #    self.time = datetime.now(timezone.utc).timestamp()

            if 'value' in msg:
                self.value = msg['value'].strip()

            # parse remaining message parameters
            for param, value in msg['params'].items():
                if isinstance(value, str):
                    self.params[param.strip()] = value.strip()
                else:
                    self.params[param.strip()] = value

            #TODO review, not clear what is going on here
            if self.params['CMD'] == 'GRID':
                grid = self.params['TEXT'].split()
                if len(grid) >= 4:
                    grid = grid[3]
                
                #TODO expand error checking
                if Message.ERR in grid:
                    self.params['GRID'] = None
                else:
                    self.params['GRID'] = grid

        return self.data()
                
        
