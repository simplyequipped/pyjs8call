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

'''Main JS8Call API interface.

Includes many functions for reading/writing settings and sending various types
of messages.

Typical usage example:

    ```
    js8call = pyjs8call.Client()
    js8call.callback.register_incoming(incoming_callback_function)
    js8call.start()

    js8call.send_directed_message('KT7RUN', 'Great content thx')
    ```
'''

__docformat__ = 'google'


from pyjs8call import Message


class Callbacks:
    '''Callback functions container.
    
    This class is initilized by pyjs8call.client.Client.

    Attributes:
        incoming (dict): Incoming message callback function lists organized by message type
        outgoing (func): Outgoing message status change callback function, defaults to None
        spots (list): New spots callback funtions, defaults to empty list
        station_spot (list): Watched station spot callback functions, defaults to empty list
        group_spot (list): Watched group spot callback functions, defaults to empty list
        window (func): rx/tx window transition callback function, defaults to None
        inbox (func): New inbox message callback function, defaults to None
        schedule (func): Schedule entry activation callback function, defaults to None

    *incoming* structure: *{type: [callback, ...], ...}*
    - *type* is an incoming  message type (see pyjs8call.message for information on message types)
    - *callback* signature: *func(msg)* where *msg* is a pyjs8call.message object

    *outgoing* callback signature: *func(msg)* where *msg* is a pyjs8call.message object
    - Called by pyjs8call.txmonitor

    *spots* structure: *[callback, ...]*
    - callback signature: *func( list(msg, ...) )* where *msg* is a pyjs8call.message object
    - Called by pyjs8call.spotmonitor

    *station_spot* structure: *[callback, ...]*
    - callback signature: *func(msg)* where *msg* is a pyjs8call.message object
    - Called by pyjs8call.spotmonitor

    *group_spot* structure: *[callback, ...]*
    - callback signature: *func(msg)* where *msg* is a pyjs8call.message object
    - Called by pyjs8call.spotmonitor

    *window* callback signature: *func()*
    - Called by pyjs8call.windowmonitor

    *inbox* callback signature: *func(msgs)* where *msgs* is a list of *dict* message items
    - See *client.get_inbox_messages()* for message item *dict* key details
    - Called by pyjs8call.inboxmonitor

    *schedule* callback signature: *func(sch)* where *sch* is a pyjs8call.schedule.Schedule object
    - See *pyjs8call.schedule.Schedule* for object property details
    - Called by pyjs8call.schedulemonitor
    '''

    def __init__(self):
        '''Initialize callback object.

        Returns:
            pyjs8call.client.Callbacks: Constructed callback object
        '''
        self.outgoing = None
        self.spots = []
        self.station_spot = []
        self.group_spot = []
        self.window = None
        self.inbox = None
        self.schedule = None
        self.incoming = {
            Message.RX_DIRECTED: [],
        }
        self.commands = {}

    def register_incoming(self, callback, message_type=Message.RX_DIRECTED):
        '''Register incoming message callback function.

        Incoming message callback functions are associated with specific message types. The directed message type is assumed unless otherwise specified. See pyjs8call.message for more information on message types.

        Note that pyjs8call internal modules may register callback functions for specific message type handling. Keep this in mind if minipulating registered callback functions directly.

        Args:
            callback (func): Callback function object
            message_type (str): Associated message type, defaults to RX_DIRECTED

        *callback* function signature: *func(msg)* where *msg* is a pyjs8call.message object

        Raises:
            TypeError: An invaid message type is specified
        '''
        if message_type not in Message.RX_TYPES:
            raise TypeError('Invalid message type \'' + str(message_type) + '\', see pyjs8call.Message.RX_TYPES')

        if message_type not in self.incoming:
            self.incoming[message_type] = []

        self.incoming[message_type].append(callback)

    def remove_incoming(self, callback, message_type=None):
        '''Remove incoming message callback function.
    
        If *message_type* is None *callback* is removed from all message types.

        Args:
            callback (func): Function to remove
            message_type (str): Message type to remove function from, defaults to None
        '''
        for msg_type, callbacks in self.incoming.items():
            if message_type in (None, msg_type) and callback in callbacks:
                self.incoming[msg_type].remove(callback)

    def incoming_type(self, message_type=Message.RX_DIRECTED):
        '''Get incoming message callback functions.
        
        See pyjs8call.message for more information on message types.
        
        Args:
            message_type (str): Message type, defaults to RX_DIRECTED
        
        Returns:
            list: Callback functions associated with the specified message type
        '''
        if message_type in self.incoming:
            return self.incoming[message_type]
        else:
            return []

    def register_command(self, cmd, callback):
        '''Register command callback function.

        Note: All JS8Call commands must have a leading space. Custom command strings also require a leading space for consistent internal handling.

        Note: Custom commands are only processed for directed messages.

        Args:
            cmd (str): Command string (with leading space)
            callback (func): Callback function object

        *callback* function signature: *func(msg)* where *msg* is a pyjs8call.message object

        Raises:
            ValueError: Specified command string is an exsiting JS8Call command
            ValueError: Specified command string does not have a leading space
        '''
        if cmd in Message.COMMANDS:
            raise ValueError('\'' + cmd + '\' is an existing JS8Call command')

        if cmd[0] != ' ':
            raise ValueError('All JS8Call commands must have a leading space')

        if cmd not in self.commands:
            self.commands[cmd] = []

        self.commands[cmd].append(callback)
        
    def remove_command(self, cmd):
        '''Remove command and callback functions.

        Args:
            cmd (str): Command to remove
        '''
        if cmd in self.commands:
            del self.commands[cmd]

    def remove_command_callback(self, callback):
        '''Remove command callback function.

        Args:
            callback (func): Function to remove
        '''
        for cmd, callbacks in self.commands.items():
            if callback in callbacks:
                self.commands[cmd].remove(callback)

    def register_spots(self, callback):
        '''Register spots callback.

        Args:
            callback (func): Callback function object
            
        *callback* function signature: *func(msg)* where *msg* is a pyjs8call.message object
        '''
        if callback not in self.spots:
            self.spots.append(callback)

    def remove_spots(self, callback):
        '''Remove spots callback.

        Args:
            callback (func): Callback function object
        '''
        if callback in self.spots:
            del self.spots[callback]

    def register_station_spot(self, callback):
        '''Register station spot callback.

        Args:
            callback (func): Callback function object
            
        *callback* function signature: *func(msg)* where *msg* is a pyjs8call.message object
        '''
        if callback not in self.station_spot:
            self.station_spot.append(callback)

    def remove_station_spot(self, callback):
        '''Remove station spot callback.

        Args:
            callback (func): Callback function object
        '''
        if callback in self.station_spot:
            del self.station_spot[callback]

    def register_group_spot(self, callback):
        '''Register group spot callback.

        Args:
            callback (func): Callback function object
            
        *callback* function signature: *func(msg)* where *msg* is a pyjs8call.message object
        '''
        if callback not in self.group_spot:
            self.group_spot.append(callback)

    def remove_group_spot(self, callback):
        '''Remove group spot callback.

        Args:
            callback (func): Callback function object
        '''
        if callback in self.group_spot:
            del self.group_spot[callback]
    
