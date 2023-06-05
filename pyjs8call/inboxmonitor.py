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

**CAUTION: Enabling inbox monitoring will cause your radio to transmit almost immediately. Consider cabling and antenna connections prior to enabling inbox monitoring.**

Set `client.callback.inbox` to receive new inbox messages as they arrive. See pyjs8call.client.Callbacks for *inbox* callback function details.
'''

__docformat__ = 'google'


import os
import time
import json
import sqlite3
import threading

from pyjs8call import Message

class InboxMonitor:
    '''Monitor local and remote inbox messages.
    
    Note that inbox functions in this class access the JS8Call sqlite3 inbox database directly.
    
    The JS8Call sqlite3 inbox database has the following schema:
    
    ```
    CREATE TABLE inbox_v1 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        blob TEXT
    );
    ```
    '''

    def __init__(self, client):
        '''Initialize inbox monitor object.

        Args:
            client (pyjs8call.client): Parent client object

        Returns:
            pyjs8call.hbmonitor: Constructed heartbeat object
        '''
        self._client = client
        self._enabled = False
        self._paused = False
        self._rx_queue = []
        self._rx_queue_lock = threading.Lock()

    def enabled(self):
        '''Get enabled status.

        Returns:
            bool: True if enabled, False if disabled
        '''
        return self._enabled

    def paused(self):
        '''Get paused status.

        Returns
            bool: True if paused, False if running
        '''
        return self._paused

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

    def pause(self):
        '''Pause inbox monitoring.'''
        self._paused = True

    def resume(self):
        '''Resume inbox monitoring.'''
        self._paused = False

    def message(self, msg_id):
        '''Get specified inbox message.
        
        An inbox message is a *dict* with the following keys:
        
        | Key | Value Type |
        | -------- | -------- |
        | cmd | *str* |
        | freq | *int* | 
        | offset | *int* | 
        | snr | *int* |
        | speed | *int* |
        | time | *str* |
        | origin | *str* |
        | destination | *str* |
        | path | *str* |
        | text | *str* |
        | type | *str* |
        | value | *str* |
        | status | *str* |
        | unread | *bool* |
        | stored | *bool* |
        
        Args:
            msg_id (int): ID of message to retrieve

        Returns:
            dict: Message information
            None: Message with the specified ID does not exist
        '''
        db_path = self._client.config.get('Configuration', 'AzElDir')
        db_file = os.path.join(db_path, 'inbox.db3')
        conn = sqlite3.connect(db_file)
        msg = conn.cursor().execute('SELECT * FROM inbox_v1 WHERE id = ?;', (str(msg_id),)).fetchone()
        conn.close()

        if msg is None:
            return None

        msg_id, blob = msg
        blob = json.loads(blob)
        msg = {
            'id': int(msg_id),
            'cmd' : blob['params']['CMD'],
            'freq' : blob['params']['DIAL'],
            'offset' : blob['params']['OFFSET'],
            'snr' : blob['params']['SNR'],
            'speed' : blob['params']['SUBMODE'],
            'time' : blob['params']['UTC'],
            'origin' : blob['params']['FROM'],
            'destination' : blob['params']['TO'],
            'path' : blob['params']['PATH'],
            'text' : blob['params']['TEXT'].strip(),
            'value' : blob['value'],
            'status' : blob['type'].lower(),
            'unread': bool(blob['type'].lower() == 'unread'),
            'stored': bool(blob['type'].lower() == 'store')
        }

        return msg

    def messages(self):
        '''Get all inbox messages.
            
        Each inbox message is a *dict* with the following keys:
        
        | Key | Value Type |
        | -------- | -------- |
        | cmd | *str* |
        | freq | *int* | 
        | offset | *int* | 
        | snr | *int* |
        | speed | *int* |
        | time | *str* |
        | origin | *str* |
        | destination | *str* |
        | path | *str* |
        | text | *str* |
        | type | *str* |
        | value | *str* |
        | status | *str* |
        | unread | *bool* |
        | stored | *bool* |
        
        Returns:
            list: Inbox messages
        '''
        db_path = self._client.config.get('Configuration', 'AzElDir')
        db_file = os.path.join(db_path, 'inbox.db3')
        conn = sqlite3.connect(db_file)
        inbox = conn.cursor().execute('SELECT * FROM inbox_v1;').fetchall()
        conn.close()

        if len(inbox) == 0:
            return []

        msgs = []
        for msg_id, blob in inbox:
            blob = json.loads(blob)
            msgs.append({
                'id': int(msg_id),
                'cmd' : blob['params']['CMD'],
                'freq' : blob['params']['DIAL'],
                'offset' : blob['params']['OFFSET'],
                'snr' : blob['params']['SNR'],
                'speed' : blob['params']['SUBMODE'],
                'time' : blob['params']['UTC'],
                'origin' : blob['params']['FROM'],
                'destination' : blob['params']['TO'],
                'path' : blob['params']['PATH'],
                'text' : blob['params']['TEXT'].strip(),
                'value' : blob['value'],
                'status' : blob['type'].lower(),
                'unread': bool(blob['type'].lower() == 'unread'),
                'stored': bool(blob['type'].lower() == 'store')
            })

        return msgs

    def unread(self):
        '''Get unread messages addressed to local station.

        Returns:
            list: Unread messages
        '''
        return [msg for msg in self.messages() if msg['unread']]

    def stored(self):
        '''Get stored messages addressed to remote stations.

        Returns:
            list: Unread messages
        '''
        return [msg for msg in self.messages() if msg['stored']]

    def unread_count(self):
        '''Get count of unread messages addressed to local station.

        Returns:
            int: Number of unread messages in the local inbox
        '''
        return len(self.unread())

    def stored_count(self):
        '''Get count of stored messages addressed to remote stations.

        Returns:
            int: Number of stored messages in the local inbox
        '''
        return len(self.stored())

    def mark_read(self, msg_id):
        '''Mark specified inbox message as read.
        
        Args:
            msg_id (int): ID of message to mark as read
        '''
        db_path = self._client.config.get('Configuration', 'AzElDir')
        db_file = os.path.join(db_path, 'inbox.db3')
        conn = sqlite3.connect(db_file)
        conn.cursor().execute('UPDATE inbox_v1 SET blob = json_set(blob, "$.type", "READ") WHERE id = ?;', (str(msg_id),))
        conn.commit()
        conn.close()

    def mark_unread(self, msg_id):
        '''Mark specified inbox message as unread.
        
        Args:
            msg_id (int): ID of message to mark as unread
        '''
        db_path = self._client.config.get('Configuration', 'AzElDir')
        db_file = os.path.join(db_path, 'inbox.db3')
        conn = sqlite3.connect(db_file)
        conn.cursor().execute('UPDATE inbox_v1 SET blob = json_set(blob, "$.type", "UNREAD") WHERE id = ?;', (str(msg_id),))
        conn.commit()
        conn.close()

    def mark_all_read(self):
        '''Mark all inbox messages addressed to local station as read.
        
        Messages stored for other stations are not changed.
        '''
        db_path = self._client.config.get('Configuration', 'AzElDir')
        db_file = os.path.join(db_path, 'inbox.db3')
        conn = sqlite3.connect(db_file)
        conn.cursor().execute('UPDATE inbox_v1 SET blob = json_set(blob, "$.type", "READ") WHERE json_extract(blob, "$.type") != "STORE";')
        conn.commit()
        conn.close()
                
    def clear(self, unread=False):
        '''Remove inbox messages addressed to local station.
        
        Messages stored for other stations are not removed. See *clear_all()* to remove all inbox messages.
        
        Args:
            unread (bool): Remove unread messages if True, only remove read messages if False, defaults to False
        '''
        db_path = self._client.config.get('Configuration', 'AzElDir')
        db_file = os.path.join(db_path, 'inbox.db3')
        conn = sqlite3.connect(db_file)
                
        if unread:
            conn.cursor().execute('DELETE FROM inbox_v1 WHERE json_extract(blob, "$.type") != "STORE";')
        else:
            conn.cursor().execute('DELETE FROM inbox_v1 WHERE json_extract(blob, "$.type") = "READ" AND json_extract(blob, "$.type") != "STORE";')
                
        conn.commit()
        conn.close()

    def clear_all(self):
        '''Remove all inbox messages.
        
        Removes all messages including those stored for other stations. See *clear()* to only remove messages addressed to the local station.
        '''
        db_path = self._client.config.get('Configuration', 'AzElDir')
        db_file = os.path.join(db_path, 'inbox.db3')
        conn = sqlite3.connect(db_file)
        conn.cursor().execute('DELETE FROM inbox_v1;')
        conn.commit()
        conn.close()
        
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
        if msg.destination != self._client.settings.get_station_callsign():
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
            # delay until next window transition
            self._client.window.sleep_until_next_transition(within = 0.5)
            
            if self._paused:
                continue
            
            window_duration = self._client.settings.get_window_duration()
            response_delay = window_duration * 30

            if len(self._rx_queue) > 0:
                rx_processing = True
                msg = self._rx_queue.pop(0)

                if msg.get('msg_id') is None and (last_tx_timestamp + response_delay) < time.time():
                    # process next msg response
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
                # ensure no last second state change before transmitting
                if not self._paused and self._enabled:
                    self._client.query_messages(destination)
                    last_query_timestamp = time.time()

            # check local inbox for new unread msgs
            inbox = self.unread()

            if inbox is not None:
                new_msgs = [msg for msg in inbox if msg not in last_inbox]
                last_inbox = inbox

                if len(new_msgs) > 0:
                    self._callback(new_msgs)
