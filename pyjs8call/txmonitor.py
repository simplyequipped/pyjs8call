import time
import threading

import pyjs8call


class TxMonitor:
    def __init__(self, client):
        self.client = client
        self.msg_queue = []
        self.msg_queue_lock = threading.Lock()
        self.msg_queue_size_limit = 25
        self.tx_complete_callback = None

        monitor_thread = threading.Thread(target=self._monitor)
        monitor_thread.setDaemon(True)
        monitor_thread.start()

    def set_tx_complete_callback(self, callback):
        self.tx_complete_callback = callback

    def monitor(self, msg):
        msg.status = pyjs8call.Message.STATUS_QUEUED

        self.msg_queue_lock.acquire()
        self.msg_queue.append(msg)
        self.msg_queue_lock.release()

    def _monitor(self):
        while self.client.online:
            time.sleep(1)
            tx_text = self.client.get_tx_text()

            if tx_text == None:
                continue

            tx_text.strip(' ' + pyjs8call.Message.EOM)

            self.msg_queue_lock.acquire()

            # cull msg queue
            while len(self.msg_queue) > self.msg_queue_size_limit:
                self.msg_queue.pop(0)

            # process msg queue
            for i in range(len(self.msg_queue)):
                msg = self.msg_queue.pop(0)

                # msg text was added to js8call tx field, sending
                if msg.value in tx_text and msg.status == pyjs8call.Message.STATUS_QUEUED:
                    msg.status = pyjs8call.Message.STATUS_SENDING
                        
                # msg text was removed from js8call tx field, sent
                elif msg.value not in tx_text and msg.status == pyjs8call.Message.STATUS_SENDING:
                    msg.status = pyjs8call.Message.STATUS_SENT

                    if self.tx_complete_callback != None:
                        self.tx_complete_callback(msg)

                if msg.status != pyjs8call.Message.STATUS_SENT:
                    self.msg_queue.append(msg)
                        
            self.msg_queue_lock.release()
                        
