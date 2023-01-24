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

'''Monitor local and remote inbox messages.

Set `client.callback.inbox` to receive new inbox messages as they arrive. See pyjs8call.client.Callbacks for *inbox* callback function details.
'''

__docformat__ = 'google'


import time
import threading

from pyjs8call import Message

class InboxMonitor:
    '''Monitor local and remote inbox messages.'''

    def __init__(self, client):
        '''Initialize inbox monitor object.

        Args:
            client (pyjs8call.client): Parent client object

        Returns:
            pyjs8call.hbmonitor: Constructed heartbeat object
        '''
        self._client = client
        self._enabled = False
        self._rx_queue = []
        self._rx_queue_lock = threading.Lock()

    def enable(self, query=True, destination='@ALLCALL', interval=60):
        '''Enable inbox monitoring.

        If *query* is True a message query will be sent to *destination* every *interval* minutes. Incoming directed messages are responded to whether *query* is True or not. See *process_incoming()* for more information on incoming directed message handling.

        Args:
            query (bool): Transmit message queries periodically if True, defaults to True
            destination (str): Outgoing message query destination, defaults to '@ALLCALL'
            interval (int): Minutes between message queries, defaults to 60
        '''
        if self._enabled:
            return

        self._enabled = True
        self._client.callback.register_incoming(self.process_incoming, message_type = Message.RX_DIRECTED)

        thread = threading.Thread(target=self._monitor, args=(query, destination, interval))
        thread.daemon = True
        thread.start()

    def disable(self):
        '''Disable inbox monitoring.'''
        self._enabled = False
        self._client.callback.remove_incoming(self.process_incoming)

    def process_incoming(self, msg):
        '''Process incoming directed messages.

        This function is used internally.

        Parses message ID and sends a query for the remote message (see *pyjs8call.client.query_message_id()*).

        Handles the following cases:
        - Directed heartbeat message (ex. *ORIGIN*: *DESTINATION* HEARTBEAT SNR -11 MSG ID 42)
        - Message query response (ex. *ORIGIN*: *DESTINATION* YES MSG ID 42)

        Args:
            msg (pyjs8call.message): Incoming message object
        '''
        if msg.destination != self._client.get_station_callsign():
            return

        if msg.cmd in (Message.CMD_HEARTBEAT_SNR, Message.CMD_YES) and Message.CMD_MSG in msg.value:
            self._rx_queue.append(msg)

    def _get_msg_id(self, msg):
        '''Parse out inbox message ID'''
        if msg.cmd in (Message.CMD_HEARTBEAT_SNR, Message.CMD_YES) and Message.CMD_MSG in msg.value:
            return msg.value.split('ID')[1].strip(' ' + Message.EOM)

    def _callback(self, msgs):
        if self._client.callback.inbox is not None:
            thread = threading.Thread(target=self._client.callback.inbox, args=(msgs,)) 
            thread.daemon = True
            thread.start()

    def _monitor(self, query, destination, query_interval):
        '''Inbox monitor thread.'''
        last_inbox = []
        last_query_timestamp = 0
        query_interval *= 60

        rx_processing = False
        last_tx_timestamp = 0

        while self._enabled:
            window_duration = self._client.get_tx_window_duration()
            response_delay = window_duration * 30

            if len(self._rx_queue) > 0:
                rx_processing = True
                msg = self._rx_queue.pop(0)

                if msg.get('msg_id') is None and (last_tx_timestamp + response_delay) < time.time():
                    # process next msg response
                    #TODO
                    print(self._get_msg_id(msg))
                    msg.set('msg_id', self._get_msg_id(msg))
                    self._client.query_message_id(msg.origin, msg.msg_id)
                    # reset age
                    msg.set('timestamp', time.time())
                    self._rx_queue.insert(0, msg)

                elif msg.get('msg_id') is not None and msg.age() > response_delay:
                    # cull old msg
                    rx_processing = False
                else:
                    # wait for response
                    self._rx_queue.insert(0, msg)

            elif not rx_processing and query and (last_query_timestamp + query_interval) < time.time():
                self._client.query_messages(destination)
                last_query_timestamp = time.time()

            # check local inbox for new msgs
            inbox = self._client.get_inbox_messages()

            if inbox is not None:
                new_msgs = [msg for msg in inbox if msg not in last_inbox]
                last_inbox = inbox

                if len(new_msgs) > 0:
                    self._callback(new_msgs)

            # delay until next window transition
            default_delay = window_duration / 3
            delay = self._client.window_monitor.next_transition_seconds(count = 1, fallback = default_delay)
            time.sleep(delay)


