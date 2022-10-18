import pyjs8call


class MessageAssembler:
    def __init__(self, client):
        self.client = client
        self.message_parts = {}
        
    def process_rx_msg(self, msg):
        # msg parts queued for callsign
        if msg['from'] in self.message_parts.keys():
            # last message part and new message part received on adjacent rx/tx windows
            if self.adjacent_window(self.message_parts[msg['from']][-1]['time'], msg['time']):
                self.message_parts[msg['from']].append(msg)
            
            # must have missed EOM, clear the part queue and start over
            else:
                self.message_parts[msg['from']] = []
                self.message_parts[msg['from']].append(msg)

            # handle end of message
            if pyjs8call.Message.EOM in msg['value']:
                assembled_msg = self.assemble_message(self.message_parts[msg['from']])
                del self.message_parts[msg['from']]
                self.client.js8call.append_to_rx_queue(assembled_msg)
                
        # no msg parts queued for callsign but message has EOM, must be a single window message
        elif pyjs8call.Message.EOM in msg['value']:
            assembled_msg = self.assemble_message(msg)
            self.client.js8call.append_to_rx_queue(assembled_msg)
            
        # no msg parts queued for callsign and no EOM, start msg part queue
        else:
            self.message_parts[msg['from']] = []
            self.message_parts[msg['from']].append(msg)
            
    def assemble_message(self, msg_parts):
        # if list of msg parts given
        if isinstance(msg_parts, list):
            message = ''
            
            for msg in msg_parts:
                message.append(msg['value'])
            
            # modify last msg part to create assembled msg
            msg = msg_parts[-1]
            msg['value'] = message
            
        # if single msg part given
        else:
            msg = msg_parts
            
        msg['type'] = pyjs8call.Message.ASSEMBLED
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
        
