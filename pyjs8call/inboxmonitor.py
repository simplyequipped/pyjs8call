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

'''Monitor inbox messages.

Set `client.callback.inbox` to receive new inbox messages as they arrive. See pyjs8call.client.Callbacks for *inbox* callback function details.
'''

__docformat__ = 'google'


import time
import threading

from pyjs8call import Message

class InboxMonitor:
    '''Monitor inbox messages.'''
    def __init__(self, client):
        '''Initialize inbox monitor object.

        Args:
            client (pyjs8call.client): Parent client object

        Returns:
            pyjs8call.hbmonitor: Constructed heartbeat object
        '''
        self._client = client
        self._enabled = False

        self.enable()

    def enable(self):
        '''Enable inbox monitoring.'''
        if self._enabled:
            return

        self._enabled = True

        thread = threading.Thread(target=self._monitor)
        thread.daemon = True
        thread.start()

    def disable(self):
        '''Disable inbox monitoring.'''
        self._enabled = False

    def process_incoming_remote_message_id(self, msg):
        '''Process incoming message with remote message ID.

        This function is used internally.

        Parses message ID and sends a query for the remote message (see *pyjs8call.client.query_message_id*).

        Handles the following cases:
        - Directed heartbeat message (ex. *ORIGIN*: *DESTINATION* HEARTBEAT SNR -11 MSG 42)

        Args:
            msg (pyjs8call.message): Incoming message object
        '''
        if msg.cmd == Message.CMD_HEARTBEAT:
            msg_id = msg.value.split(Message.CMD_MSG)[1].trim(' ' + Message.EOM)
            self._client.query_message_id(msg.origin, msg_id)

    def _callback(self, msgs):
        if self._client.callback.inbox is not None:
            thread = threading.Thread(target=self._client.callback.inbox, args=(msgs,)) 
            thread.daemon = True
            thread.start()

    def _monitor(self):
        '''Inbox monitor thread.'''
        last_inbox = []

        while self._enabled:
            inbox = self._client.get_inbox_messages()

            if inbox is not None:
                new_msgs = [msg for msg in inbox if msg not in last_inbox]
                last_inbox = inbox

                if len(new_msgs) > 0:
                    self._callback(new_msgs)

            # delay until next window transition
            default_delay = self._client.get_tx_window_duration() / 3
            delay = self._client.window_monitor.next_transition_seconds(count = 1, fallback = default_delay)
            time.sleep(delay)


