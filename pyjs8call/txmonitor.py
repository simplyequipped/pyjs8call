import time
import threading

import pyjs8call

#TODO revise to be standalone monitor threat
#TODO - store last X tx'd messages
#TODO - monitor tx_text via thread
#TODO - watch for given text, callback
#TODO - check if given text has been sent


class TxMonitor:
    def __init__(self, client, msg, callback):
        self.client = client
        self.monitor_text = []
        self.tx_complete_callback = None

        monitor_thread = threading.Thread(target=self._monitor)
        monitor_thread.setDaemon(True)
        monitor_thread.start()

    def set_tx_complete_callback(self, callback):
        self.tx_complete_callback = callback

    def monitor(self, text):
        new_text = {'text': text, 'tx': False}
        self.monitor_text.apoend(new_text)

    def _monitor(self):
        while self.client.online:
            tx_text = self.client.get_tx_text()

            for text, tx in self.monitor_text:
                if 
        time.sleep(1)
