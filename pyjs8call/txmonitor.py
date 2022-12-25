import time
import threading

import pyjs8call
from pyjs8call import Message


class TxMonitor:
    def __init__(self, client):
        self._client = client
        self._msg_queue = []
        self._msg_queue_lock = threading.Lock()
        # initialize msg max age to 30 tx cycles in fast mode (10 sec cycles)
        self._msg_max_age = 10 * 30 # 5 minutes
        self.status_change_callback = None
        #self.tx_complete_callback = None
        #self.tx_failed_callback = None

        monitor_thread = threading.Thread(target=self._monitor)
        monitor_thread.setDaemon(True)
        monitor_thread.start()

    def set_status_change_callback(self, callback):
        self.status_change_callback = callback

    #def set_tx_complete_callback(self, callback):
    #    self.tx_complete_callback = callback

    #def set_tx_failed_callback(self, callback):
    #    self.tx_failed_callback = callback

    def monitor(self, msg):
        msg.status = Message.STATUS_QUEUED

        self._msg_queue_lock.acquire()
        self._msg_queue.append(msg)
        self._msg_queue_lock.release()

    def _monitor(self):
        while self._client.online:
            time.sleep(1)
            tx_text = self._client.get_tx_text()

            # no text in tx field, nothing to process
            if tx_text == None:
                continue

            # when a msg is the tx text, drop the first callsign and strip spaces and end-of-message
            # original format: 'callsign: callsign  message'
            if ':' in tx_text:
                tx_text = tx_text.split(':')[1].strip(' ' + Message.EOM)
            
            # update msg max age based on speed setting (30 tx cycles)
            #    3 min in turbo mode (6 sec cycles)
            #    5 min in fast mode (10 sec cycles)
            #    7.5 min in normal mode (15 sec cycles)
            #    15 min in slow mode (30 sec cycles)
            tx_window = self._client.get_tx_window_duration()
            self._msg_max_age = tx_window * 30
            
            self._msg_queue_lock.acquire()

            # process msg queue
            for i in range(len(self._msg_queue)):
                msg = self._msg_queue.pop(0)
                msg_value = msg.destination + '  ' + msg.value.strip()
                drop = False

                if msg_value == tx_text and msg.status == Message.STATUS_QUEUED:
                    # msg text was added to js8call tx field, sending
                    msg.status = Message.STATUS_SENDING

                    if self.status_change_callback != None:
                        self.status_change_callback(msg)
                        
                elif msg_value != tx_text and msg.status == Message.STATUS_SENDING:
                    # msg text was removed from js8call tx field, sent
                    msg.status = Message.STATUS_SENT

                    if self.status_change_callback != None:
                        self.status_change_callback(msg)
                        
                    drop = True
                       
                elif time.time() > msg.timestamp + self._msg_max_age:
                    # msg sending failed
                    msg.status = Message.STATUS_FAILED

                    if self.status_change_callback != None:
                        self.status_change_callback(msg)
                        
                    drop = True

                if not drop:
                    self._msg_queue.append(msg)
                        
            self._msg_queue_lock.release()
           
