import time
import threading

import pyjs8call

#TODO revise to be standalone monitor threat
#TODO - store last X tx'd messages
#TODO - monitor tx_text via thread
#TODO - watch for given text, callback
#TODO - check if given text has been sent


class TxMonitor:
    PENDING  = 1
    ACTIVE   = 2
    FINISHED = 3

    def __init__(self, client, msg, callback):
        self.client = client
        self.msg = msg
        self.state = TxMonitor.PENDING
        self.callback = callback

        monitor_thread = threading.Thread(target=self._monitor)
        monitor_thread.setDaemon(True)
        monitor_thread.start()

    def _monitor(self):
        while self.client.online:
            tx_text = self.client.get_tx_text()
            if self.state == TxMonitor.PENDING and self.msg['value'] in tx_text:
                # text found in tx text, tx in progress
                self.state = TxMonitor.ACTIVE
            elif self.state == TxMonitor.ACTIVE and self.msg['value'] not in tx_text: 
                # text removed from tx text, tx complete
                self.state = TxMonitor.FINISHED
                self.callback(self.msg)
                
        time.sleep(1)
