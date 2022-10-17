import pyjs8call


class RxMonitor:
    def __init__(self, client):
        self.client = client
        self.message_parts = {}
        self.msg_rx_callback = None
        
    def set_msg_rx_callback(self, callback):
        self.msg_rx_callback = callback
        
    def process_rx_msg(self, msg):
        # msg parts queued for callsign
        if msg['from'] in self.message_parts.keys():
            # last message part and new message part received on adjacent rx/tx windows
            if self.adjacent_window(self.message_parts[msg['from']][-1]['time'], msg['time']):
                self.message_parts[msg['from']].append(msg)

            # end of the message
            #TODO is msg['value'] where the message itself is stored?
            if pyjs8call.Message.EOM in msg['value']:
                compiled_msg = self.assemble_message(self.message_parts[msg['from']])
                self.message_parts[msg['from']] = []
                if self.msg_rx_callback != None:
                    self.msg_rx_callback(compiled_message)
                
        # no msg parts queued for callsign but message has EOM, must be a 1 window message
        #TODO is msg['value'] where the message itself is stored?
        elif pyjs8call.Message.EOM in msg['value']:
            if self.msg_rx_callback != None:
                self.msg_rx_callback(msg)
        # no msg parts queued for callsign and no EOM, start msg part queue
        else:
            self.message_parts[msg['from']] = []
            self.message_parts[msg['from']].append(msg)
            
    def assemble_message(self, msg_parts):
        message = ''
        for msg in msg_parts:
            #TODO is msg['value'] where the message itself is stored?
            message.append(msg['value'])
            
        msg = msg_parts[-1]
        msg['value'] = message
            
        return msg
            
    def adjacent_window(self, timestamp_a, timestamp_b):
        # ensure timestamp_a is the earlier timestamp, and timestamp_b is the later 
        timestamps = [timestamp_a, timestamp_b]
        timestamp_a = min(timestamps)
        timestamp_b = max(timestamps)
        
        window_duration = self.client.get_tx_window_duration()
        
        if timestamp_b < (timestamp_a + window_duration + 1):
            return True
        else:
            return False
        
