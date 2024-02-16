import os
import time
import inspect

import RNS
import LXMF

import pyjs8call


#TODO
# - add lxmf module to client (after client.settings)
# - add network activity conversation
# - add control command for callsign activity
# - handle client.settings methods that require list args, handle str or list in method
# - test propagation node
# - should propagation be on by default?
# - use callsign grid square data for telemetry?



class Node:
    '''Send notifications and control pyjs8call via LXMF.

    LXMF is a messaging format and delivery protocal built in top of the Reticulum. Reticulum is a cryptography-based networking stack for building both local and wide-area networks, with self-configuring multi-hop routing (aka auto mesh networking). See the links below for more information on these underlying systems.

    Sideband is a desktop and mobile app utilizing LXMF, allowing it to interface with other LXMF devices and nodes. Integrating an LXMF node into pyjs8call allows the user to utilize an application like Sideband to receive notifications when an incoming JS8Call message is received, as well as respond to those messages, and even issue control messages to the JS8Call application.

    **JS8Call Callsigns**
    A Reticulum Identity and Destination object are created for each callsign that an incoming message is received from, which allows messages from that callsign to be passed to the LXMF device (i.e. Sideband mobile app). Once this unique destination is created on the LXMF node, two way communication can take place. However, an unknown destination cannot initiate a new outgoing conversation directly. Instead, a control command can be sent to initiate a new conversation to a specific callsign, which will create the assocaited Identity and Destination objects. See below for more information on control commands.

    **JS8Call Control Commands**
    In additon to each conversation with a JS8Call callsign, a conversation is created to handle control commands. Control commands allow the user to change JS8Call settings and initialize new outgoing conversations from their device (i.e. Sideband mobile app). When the pyjs8call LXMF node is enabled, a conversation titled *JS8Call Control* will appear. This conversation will be used for control commands with the pyjs8call system.

    Control commands are mapped to a function in *pyjs8call.client.settings* with the same name. Control commands can be called with underscores just like the *pyjs8call.client.settings* function names, or spaces can be used instead for a more natural experience.
    
    Example control commands:
    
    ```
    | client.settings Function | Control Command         | Usage                                  |
    | ------------------------ | ----------------------- | -------------------------------------- |
    | get_freq()               | get freq                | Get current JS8Call frequency in Hz    |
    | set_freq(7078000)        | set freq: 7078000       | Set JS8Call frequency to 7.078 MHz     |
    | get_station_grid()       | get station grid        | Get current station grid square        |
    | set_station_grid(EM19)   | set station grid: EM19  | Set station grid square to EM19        |
    ```

    There are additional control commands that not directly related to *pyjs8call.client.settings* functions.

    ```
    | Control Command         | Usage                                  |
    | ----------------------- | -------------------------------------- |
    | new KT7RUN              | Initiate a conversation with KT7RUN    |
    | restart js8call         | Restart JS8Call                        |
    ```
    
    **Enabling LXMF**
    There are two options for enabling the LXMF node for JS8Call messaging and control:
    
    __Option A__
    Call the command `python -m pyjs8call --lxmf [ADDRESS]` from the command line, where [ADDRESS] is the LXMF address of the device to receive messages from JS8Call. This will launch JS8Call and enable the LXMF node.

    __Option B__
    Import pyjs8call in a script or program, enable the LXMF node, and set the LXMF address of the device to receive messages from JS8Call. Example:
    ```
    import pyjs8call
    
    js8call = pyjs8call.Client()
    js8call.start()

    js8call.lxmf.enable([ADDRESS])
    ```
    Be sure to replace [ADDRESS] with the LXMF address of the device to receive messages from JS8Call.

    See the [Sideband GitHub releases page](https://github.com/markqvist/Sideband/releases) for the latest Android APK and Python wheel.
    See the [Reticulum website](https://reticulum.network/) for more information.
    See the [LXMF GitHub repo](https://github.com/markqvist/LXMF) for an overview. LXMF documentation will be expanded in the future.
    '''
    def __init__(self, client, config_path=None, identity_path=None):
        '''Initialize LXMF node.

        Args:
            client (pyjs8call.client): Parent client object
            config_path (str): Absolute path to configuration directory, defaults to `~/.pyjs8call`
            identity_path (str): Absolute path to LXMRouter identity, defaults to `[config_path]/storage/identity`
        
        Returns:
            pyjs8call.Node: Constructed node object
        '''
        self._client = client
        self._enabled = False
        self.notification_address = None
        '''LXMF notification address, see set_notification_address()'''
        self.display_name_format = '{} (JS8Call)'
        '''Format string used to set the Sideband conversation display name assocaited with a callsign destination'''
        self.control_command_separator = ':'
        '''String used to separate control commands from their values, defaults to the colon character (ex. `set freq: 7078000`)'''
        self.router = None
        '''LXMF.LXMRouter object'''
        self.destination = None
        '''JS8Call Control RNS destination'''
        self.identity = None
        '''LXMF.LXMRouter and JS8Call Control RNS identity'''

        # get dict of client.settings methods and positional argument count
        self.settings = [method for method in dir(self._client.settings) if callable(getattr(self._client.settings, method)) and not method.startswith('__')]
        '''List of function names from *pyjs8call.client.settings*.'''

        if config_path is not None:
            self.config_path = config_path
        else:
            self.config_path = os.path.join(os.path.expanduser('~'), '.pyjs8call')
            
        self.storage_path = os.path.join(self.config_path, 'storage')
        
        if identity_path is not None:
            self.identity_path = identity_path
        else:
            self.identity_path = os.path.join(self.storage_path, 'identity')
            
        self.directory_path = os.path.join(self.storage_path, 'directory')
            
        if not os.path.isdir(self.config_path):
            os.makedirs(self.config_path)
        if not os.path.isdir(self.storage_path):
            os.makedirs(self.storage_path)
        if not os.path.isdir(self.directory_path):
            os.makedirs(self.directory_path)
            
        if os.path.exists(self.identity_path):
            self.identity = RNS.Identity.from_file(self.identity_path)
        else:
            self.identity = RNS.Identity()
            self.identity.to_file(self.identity_path)

        self.incoming_enabled = True
        self.spots_enabled = False
        self.station_spots_enabled = False
        self.group_spots_enabled = False
        self.notify_if_callsign_selected = False

        self.incoming_commands = [pyjs8call.Message.CMD_MSG, pyjs8call.Message.CMD_FREETEXT]

    def enabled(self):
        '''Get enabled status.

        Returns:
            bool: True if enabled, False if disabled
        '''
        return self._enabled

    def enable(self, notification_address=None, enable_propagation=False):
        '''Enable LXMF notifications.

        Note: *notification_address* is an optional argument, but the notification address must be set to recieve notifications. See *set_notification_address()*.

        Args:
            notification_address (str, bytes, or None): LXMF address to send JS8Call related messages to, defaults to None
            enable_propagation (bool): Whether to enable the local LXMF propagation node, defaults to False

        Incoming directed messages directed to the local station or configured groups will be sent to the notification address. Messages with a command are ignored unless the command is in *pyjs8call.lxmf.incoming_commands*.
        '''
        if self._enabled:
            return

        if RNS.Reticulum.get_instance() is None:
            RNS.Reticulum()

        # handle re-enable
        if self.router is None:
            self.router = LXMF.LXMRouter(self.identity, storagepath=self.storage_path)
            self.destination = self.router.register_delivery_identity(self.identity, display_name='JS8Call Control')
            
        self.router.register_delivery_callback(self.lxmf_delivery)
        self.router.announce(self.destination.hash)
        #TODO using own propagation node as outbound propagation node
        self.router.set_outbound_propagation_node(self.router.propagation_destination.hash)

        if enable_propagation:
            # enabling propagation announces propagation node
            self.router.enable_propagation()

        if notification_address is not None:
            self.set_notification_address(notification_address)


        self._client.callback.register_incoming(self.process_incoming)
        self._client.callback.register_spots(self.process_spots)
        self._client.callback.register_station_spot(self.process_station_spots)
        self._client.callback.register_group_spot(self.process_group_spots)
        self._enabled = True

    def disable(self):
        '''Disable LXMF notifications.'''
        self._enabled = False
        
        self.router.disable_propagation()
        self.router.register_delivery_callback(None)
        
        self._client.callback.remove_incoming(self.process_incoming)
        self._client.callback.remove_spots(self.process_spots)
        self._client.callback.remove_station_spot(self.process_station_spots)
        self._client.callback.remove_group_spot(self.process_group_spots)

    def process_incoming(self, msg):
        '''Process incoming directed messages.

        This function is used internally.
        '''
        if not self._enabled or not self.incoming_enabled:
            return

        if self._client.get_selected_call() is not None and self.notify_if_callsign_selected == False:
            # do not send notification if a callsign is selected on the UI
            return
            
        if self._client.msg_is_to_me(msg) and (msg.cmd in (None, '') or msg.cmd in self.incoming_commands):
            if self.notification_address is None:
                print('Notification address not set, dropping incoming JS8Call message')
                return None
                
            # remove end-of-message and error character
            content = msg.text.replace(pyjs8call.Message.EOM, '').replace(pyjs8call.Message.ERR, '...')
            # get callsign destination, creating new identity as required
            callsign_destination = self.get_destination_by_callsign(msg.origin)
            self.send_notification(content, callsign_destination)

    def process_spots(self, spots):
        '''Process spots.

        This function is used internally.
        '''
        if not self.spots_enabled:
            return

        spots = [spot.origin for spot in spots]
        spots_destination = self.get_destination_by_callsign('Spots')
        self.send_notification('Spotted {}'.format(', '.join(spots)), spots_destination)

    def process_station_spots(self, spot):
        '''Process watched station spots.

        This function is used internally.
        '''
        if not self.station_spots_enabled:
            return

        spots_destination = self.get_destination_by_callsign('Spots')
        self.send_notification('Spotted watched station {}'.format(spot.origin), spots_destination)

    def process_group_spots(self, spot):
        '''Process watched group spots.

        This function is used internally.
        '''
        if not self.group_spots_enabled:
            return

        spots_destination = self.get_destination_by_callsign('Spots')
        self.send_notification('Spotted watched group {}'.format(spot.destination), spots_destination)

    def set_notification_address(self, address):
        if not isinstance(address, bytes):
            address = bytes.fromhex(address)

        self.notification_address = address
        RNS.Transport.request_path(self.notification_address)
        self.send_notification('JS8Call online\nTry sending \'settings\'')
    
    def lxmf_delivery(self, lxm):
        if not self._enabled:
            return
            
        if lxm.destination.hash == self.destination.hash:
            self.process_control_message(lxm)
            return

        #TODO queue lxmf messages while restarting?
        if self._client.restarting:
            return
            
        callsign = self.get_callsign_by_destination_hash(lxm.destination.hash)

        if callsign is None:
            # unknown destination target
            #TODO are there other cases to handle here?
            print('Dropping LXMF message with unknown destination {} from {}'.format(lxm.destination.hash.hex(), lxm.source.hash.hex()))
            return

        self._client.send_directed_message(callsign, lxm.content_as_string())

    def send_notification(self, content, source=None):
        if source is None:
            source = self.destination
            
        notification_destination = self.get_notification_destination()
        lxm = LXMF.LXMessage(notification_destination, source, content)
        self.router.handle_outbound(lxm)

    def get_notification_destination(self):
        notification_identity = RNS.Identity.recall(self.notification_address)
        return RNS.Destination(notification_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, 'lxmf', 'delivery')

    def callsign_destination_exists(self, callsign):
        for destination_hash, destination in self.router.delivery_destinations.items():
            if self.get_callsign_by_display_name(destination.display_name) == callsign:
                return True

        if callsign in os.listdir(self.directory_path):
            return True

        return False        
    
    def get_destination_by_callsign(self, callsign):
        # check router delivery destinations
        for destination_hash, destination in self.router.delivery_destinations.items():
            if self.get_callsign_by_display_name(destination.display_name) == callsign:
                return destination

        # no router delivery destination, try stored callsign identities
        if callsign in os.listdir(self.directory_path):
            callsign_identity = RNS.Identity.from_file(os.path.join(self.directory_path, callsign))

        # callsign destination not known, create new identity
        if callsign_identity is None:
            callsign_identity = RNS.Identity()

        # create new callsign destination
        display_name = self.display_name_format.format(callsign)
        callsign_destination = self.router.register_delivery_identity(callsign_identity, display_name=display_name)
        self.router.announce(callsign_destination.hash)
        
        # remember new callsign identity
        if callsign not in os.listdir(self.directory_path):
            callsign_identity.to_file(os.path.join(self.directory_path, callsign))
        
        return callsign_destination

    def get_callsign_by_destination_hash(self, destination_hash):
        # check router delivery destinations
        if destination_hash in self.router.delivery_destinations:
            display_name = self.router.delivery_destinations[destination_hash].display_name
            return self.get_callsign_by_display_name(display_name)

        # no router delivery destination, try identity known destinations
        # None if destination not known
        display_name = RNS.Identity.recall_app_data(destination_hash)
        return self.get_callsign_by_display_name(display_name)

    def get_callsign_by_display_name(self, display_name):
        for pattern in self.display_name_format.split('{}'):
            display_name = display_name.strip(pattern)

        return display_name.strip()
            

    # control messages must follow this format:
    #    getter methods (w/o args): method name
    #    setter methods (w/ args) : method name: arg
    # client.settings method names can use spaces or underscores
    def process_control_message(self, lxm):
        original_command = lxm.content_as_string().strip().lower()
        command = original_command
        command_value = None
        response_content = None

        try:
            if self.control_command_separator in original_command:
                # separate command and value
                command_parts = original_command.split(self.control_command_separator)
                # handle command with spaces or underscores
                original_command = command_parts[0].strip()
                command = original_command
                command_value = self.control_command_separator.join(command_parts[1:])

            if command in ['help', 'setting', 'settings', 'control', 'example', 'examples']:
                # handle help request
                response_content = 'JS8Call Control Examples:'
                response_content += '\n  get freq'
                response_content += '\n  set freq: 7078000'
                response_content += '\n  get station grid'
                response_content += '\n  set station grid: EM19'
                response_content += '\n  new KT7RUN'
                response_content += '\n  restart js8call'

            elif command.startswith('new') and len(command.split()) == 2:
                # handle new conversation request
                callsign = command.split()[1].strip().upper()
    
                if self.callsign_destination_exists(callsign):
                    response_content = 'Conversation bumped for {}'.format(callsign)
                    callsign_response_content = 'JS8Call Control: bumping conversation'
                else:
                    response_content = 'Conversation created for {}'.format(callsign)
                    callsign_response_content = 'JS8Call Control: created conversation'
                
                callsign_destination = self.get_destination_by_callsign(callsign)
                callsign_destination.announce()
                self.send_notification(callsign_response_content, callsign_destination)
                time.sleep(1)

            elif command == 'restart js8call':
                # restart after 3 seconds of inactivity
                self._client.restart_when_inactive(age=3)
                self.send_notification('JS8Call restarting, this may take several seconds...')
                
                while not self._client.restarting:
                    time.sleep(0.1)
                
                while self._client.restarting:
                    time.sleep(0.1)
                
                self.send_notification('JS8Call successfully restarted')

            else:
                # handle setting request
                method = original_command.replace(' ', '_')
                args = command_value
        
                if args is not None:
                    args = args.split()
                            
                if method in self.settings:
                    if args is None:
                        # getter method, without args
                        try:
                            setting = getattr(self._client.settings, method)()
                            response_content = '{}: {}'.format(original_command, setting)
                        except Exception:
                            raise Exception('Failed to process setting')
                    else:
                        # setter method, with args
                        try:
                            setting = getattr(self._client.settings, method)(*args)
                            response_content = '{}: {}'.format(original_command, setting)
                        except Exception:
                            raise Exception('Failed to process setting')
                else:
                    raise Exception('Invalid setting')
                
        except Exception as e:
            response_content = 'Error: {}'.format(e)
            
        if response_content is not None:
            self.send_notification(response_content)
        
