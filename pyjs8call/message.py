import json


class Message:

    # message types
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

    # constants
    EOM = '♢'
    ERR = '…'

    def __init__(destination=None, value=None):
        self.type = Message.TX_SEND_MESSAGE
        self.destination = destination
        self.value = value
        self.time = None
        self.messages = None
        self.params = {
            'FREQ'      : None,
            'DIAL'      : None,
            'OFFSET'    : None,
            'CALL'      : None,
            'CALLSIGN'  : None,
            'GRID'      : None,
            'SNR'       : None,
            'FROM'      : None,
            'TO'        : None,
            'CMD'       : None,
            'TEXT'      : None,
            'SPEED'     : None,
            'EXTRA'     : None
        }

    def pack(self):
        if self.value == None:
            self.value = ''
        elif self.type == Message.TX_SEND_MESSAGE and self.destination != None:
            self.value = self.destination + ' ' + self.value

        packed = {
            'type' : self.type,
            'value' : self.value,
            'params' : {param:value for (param, value) in self.params.items() if value != None}
        }

        packed = json.dumps(packed) + '\r\n'
        return packed.encode('utf-8')
        
    def parse(self, msg):
        self.type = msg['type']
        
        if self.type == 'MESSAGES':
            self.messages = msg['params']['MESSAGES']
            return None
            
        #TODO confirm time format
        if 'time' in msg:
            self.time = msg['time']
        if 'value' in msg:
            self.value = msg['value']
        if 'params' not in msg:
            return None
        
        for param, value in msg['params'].items():
            self.params[param.strip()] = value.strip()

        if self.params['GRID'] == '':
            self.params['GRID'] = None

        if self.params['CMD'] == 'HEARTBEAT SNR' or self.params['CMD'] == 'SNR':
            self.params['extra'] = int(self.params['extra'])
            
        #TODO review
        if self.params['CMD'] == 'GRID':
            grid = self.params['TEXT'].split()
            if len(grid) >= 4:
                grid = grid[3]
                
            if Message.ERR in grid:
                self.params['GRID'] = None
            else:
                self.params['GRID'] = grid
                
        #TODO review
        if self.params['CMD'] == 'HEARING':
            self.params['TEXT'] = self.params['TEXT'].split()[3:]

        
