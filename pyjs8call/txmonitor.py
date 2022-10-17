import time
import threading

import pyjs8call


class TxMonitor:
    PENDING = 1
    ACTIVE  = 2
    SUCCESS = 3
    TIMEOUT = 4

    def __init__(self, client, text):
        self.client = client
        self.text = text
        self.state = TxMonitor.PENDING

        #TODO timeout based on text length
        next_window_end_timestamp = self.client.windowmonitor.next_window_end()

        if next_window_end_timestamp == 0:
            self.timeout = self.client.get_tx_window_size() * 2
        else:
            

    def _monitor(self):
        while self.client.online:
            tx_text = self.client.get_tx_text()
            if self.state == TxMonitor.PENDING and self.text in tx_text:
                # text found in tx text, tx in progress
                self.state = TxMonitor.ACTIVE
            elif self.state == TxMonitor.ACTIVE and self.text not in tx_text: 
                # text removed from tx text, tx complete
                self.state = TxMonitor.SUCCESS
            elif timeout:
                self.state = TxMonitor.TIMEOUT
                
        
