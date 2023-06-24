# MIT License
# 
# Copyright (c) 2022-2023 Simply Equipped
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

'''Monitor JS8Call outgoing message text.

Directed messages are monitored by default (see pyjs8call.client.Client.monitor_outgoing).

Set `client.callback.outgoing` to receive outgoing message status updates. See pyjs8call.client.Callbacks for *outgoing* callback function details.
'''

__docformat__ = 'google'


import time
import threading

from pyjs8call import Message


class OutgoingMonitor:
    '''Monitor JS8Call outgoing message text.
    
    Monitored messages can have the the following status:
    - STATUS_QUEUED
    - STATUS_SENDING
    - STATUS_SENT
    - STATUS_FAILED

    A message changes to STATUS_QUEUED when monitoring begins.

    A message changes to STATUS_SENDING when the destination and value are seen in the JS8Call tx text field and the status of the message is STATUS_QUEUED.

    A message changes to STATUS_SENT when the destination and value are no longer seen in the JS8Call tx text field and the status of the message is STATUS_SENDING.

    A message changes to STATUS_FAILED when the message is not sent within 600 tx cycles. Therefore the maximum age of a monitored message depends on the JS8Call modem speed setting:
    - 6 minutes in turbo mode which has 6 second tx cycles
    - 10 minutes in fast mode which has 10 second tx cycles
    - 15 minutes in normal mode which has 15 second cycles
    - 30 minutes in slow mode which has 30 second tx cycles

    A message is dropped from the monitoring queue once the status is set to STATUS_SENT or STATUS_FAILED.
    '''

    def __init__(self, client):
        '''Initialize outgoing message monitor.

        Args:
            client (pyjs8call.client): Parent client object

        Returns:
            pyjs8call.outgoingmonitor: Constructed outgoing message monitor object
        '''
        self._client = client
        self._enabled = False
        self._paused = False
        self._msg_queue = []
        self._msg_queue_lock = threading.Lock()
        # initialize msg max age to 10 minutes
        self._msg_max_age = 10 * 60 # 10 minutes

    def enabled(self):
        '''Get enabled status.

        Returns:
            bool: True if enabled, False if disabled
        '''
        return self._enabled

    def paused(self):
        '''Get paused status.

        Returns:
            bool: True if paused, False if running
        '''
        return self._paused

    def enable(self):
        '''Enable outgoing message monitoring.'''
        if self._enabled:
            return

        self._enabled = True

        thread = threading.Thread(target=self._monitor)
        thread.daemon = True
        thread.start()

    def disable(self):
        '''Disable outgoing message monitoring.
        
        **Caution**: Internal processes rely on the transmit text field state updates performed by this module.
        '''
        self._enabled = False

    def pause(self):
        '''Pause outgoing message monitoring.'''
        self._paused = True

    def resume(self):
        '''Resume outgoing message monitoring.'''
        self._paused = False

    def _callback(self, msg):
        '''Handle callback for monitored message status change.

        Calls the *pyjs8call.client.callback.outgoing* callback function.

        Args:
            msg (pyjs8call.message): Monitored message with changed status
        '''
        if self._client.callback.outgoing is not None:
            thread = threading.Thread(target=self._client.callback.outgoing, args=(msg,))
            thread.daemon = True
            thread.start()

    def monitor(self, msg):
        '''Monitor a new message.

        The message status is set to STATUS_QUEUED (see pyjs8call.message) when monitoring begins.

        Args:
            msg (pyjs8call.message): Message to look for in the JS8Call tx text field
        '''
        msg.status = Message.STATUS_QUEUED

        with self._msg_queue_lock:
            self._msg_queue.append(msg)
            
    def _monitor(self):
        '''Tx monitor thread.'''
        while self._enabled:
            time.sleep(0.5)

            if self._paused:
                continue

            # other modules rely on tx text updates from JS8Call
            tx_text = self._client.get_tx_text()

            if tx_text is None:
                tx_text = ''

            # drop the first callsign and strip spaces and end-of-message
            # original format: 'callsign: callsign  message'
            if ':' in tx_text:
                tx_text = tx_text.split(':')[1].strip(' ' + Message.EOM)
            
            # update msg max age based on speed setting (60 tx cycles)
            self._msg_max_age = self._client.settings.get_window_duration() * 60
            
            with self._msg_queue_lock:
                self._process_queue(tx_text)

    def _process_queue(self, tx_text):
        '''Compare queued message to tx text.'''
        tx_text_wo_checksum = ' '.join(tx_text.split()[:-1])

        for i in range(len(self._msg_queue)):
            msg = self._msg_queue.pop(0)

            if msg.packed_dict is None:
                msg.pack()

            msg_value = msg.packed_dict['value'].strip()

            if (
                ( (msg.cmd in Message.CHECKSUM_COMMANDS and msg_value == tx_text_wo_checksum) or msg_value == tx_text ) and
                msg.status == Message.STATUS_QUEUED
            ):
                # msg text was added to js8call tx field, sending
                msg.set('status', Message.STATUS_SENDING)
                self._callback(msg)
            elif msg_value != tx_text_wo_checksum and msg_value != tx_text and msg.status == Message.STATUS_SENDING:
                # msg text was removed from js8call tx field, sent
                msg.set('status', Message.STATUS_SENT)
                self._callback(msg)
                # msg dropped from queue
                return None
            elif time.time() > msg.timestamp + self._msg_max_age:
                # msg too old, sending failed
                msg.set('status', Message.STATUS_FAILED)
                msg.error = 'failed to send'
                self._callback(msg)
                # msg dropped from queue
                return None

            self._msg_queue.append(msg)
                        
