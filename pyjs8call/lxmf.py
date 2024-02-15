import os
import time
import inspect

import RNS
import LXMF

import pyjs8call


#TODO
# - add enable/disable/enabled/pause/resume functions for restart handling
# - add lxmf module to client, handle in client.restart
# - use callsign grid square for telemetry?

class pyjs8callLXMF:
    CONTROL_HELP_TEXT = '''JS8Call Control Examples:
    get freq
    set freq: 7078000
    get station grid
    set station grid: EM19
    new KT7RUN
    restart js8call
    '''
    def __init__(self, client, config_path=None, identity_path=None):
        self._client = client
        self.notification_destination_hash = None
        self.display_name_format = '{} (JS8Call)'
        self.control_command_separator = ':'

        # get dict of client.settings methods and positional arguments
        #TODO handle client.settings methods that require list args, handle str or list in method?
        self.settings = {}
        for method in dir(self._client.settings):
            method_obj = getattr(self._client.settings, method)
            if callable(method_obj) and not method.startswith('__'):
                # get list of method positional arguments (excuding keyword arguments)
                positional_args = [arg for arg, params in inspect.signature(method_obj).parameters.items() if params.kind == inspect.Parameter.POSITIONAL_ONLY]
                # get positional argument count, or None if count is zero
                args = len(positional_args) if len(positional_args) > 0 else None
                self.settings[method_] = args

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

        self.router = LXMF.LXMRouter(self.identity, storagepath=self.storage_path)
        self.router.register_delivery_callback(self.lxmf_delivery_callback)
        self.destination = self.router.register_delivery_identity(self.identity, display_name='JS8Call Control')
        self.router.announce(self.destination.hash)

    def set_notification_destination_hash(self, destination_hash):
        if not isinstance(destination_hash, bytes):
            destination_hash = bytes.fromhex(destination_hash)

        self.notification_destination_hash = destination_hash
        RNS.Transport.request_path(self.notification_destination_hash)
        notification_destination = self.get_notification_destination()

        lxm = LXMF.LXMessage(notification_destination, self.destination, 'JS8Call online\nTry sending \'settings\'')
        self.router.handle_outbound(lxm)
    
    def lxmf_delivery_callback(self, lxm):
        if lxm.destination.hash == self.destination.hash:
            self.handle_control_message(lxm)
            return

        callsign = self.get_callsign_by_destination_hash(lxm.destination.hash)

        if callsign is None:
            # respond to source destination
            # may be someone else on the network responding to an announce
            response_content = 'JS8Call Control: Callsign not associated with this conversation'.format(lxm.destination.hash.hex())
            lxm = LXMF.LXMessage(lxm.source, self.destination, response_content)
            self.router.handle_outbound(lxm)
            return

        #TODO test code
        print('JS8Call -> {}: {}'.format(callsign, lxm.content_as_string()))
        #self._client.send_directed_message(callsign, lxm.content_as_string())
    
    def js8call_incoming_callback(self, msg):
        if self.notification_destination_hash is None:
            print('Notificaiton target not set, dropping incoming JS8Call message')
            return None
            
        notification_destination = self.get_notification_destination()
        callsign_destination = self.get_destination_by_callsign(msg.origin)
            
        lxm = LXMF.LXMessage(notification_destination, callsign_destination, msg.text)
        self.router.handle_outbound(lxm)

    def get_notification_destination(self):
        notification_identity = RNS.Identity.recall(self.notification_destination_hash)
        return RNS.Destination(notification_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, 'lxmf', 'delivery')

    def callsign_destination_exists(self, callsign):
        for destination_hash, destination in self.router.delivery_destinations.items():
            if destination.display_name == callsign:
                return True

        return False        
    
    def get_destination_by_callsign(self, callsign):
        # check router delivery destinations
        for destination_hash, destination in self.router.delivery_destinations.items():
            if destination.display_name == callsign:
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
            return self.router.delivery_destinations[destination_hash].display_name

        # no router delivery destination, try identity known destinations
        # None if destination not known
        return RNS.Identity.recall_app_data(destination_hash)

    # control messages must follow this format:
    #    getter methods (w/o args): method name
    #    setter methods (w/ args) : method name: arg
    # client.settings method names can use spaces or underscores
    def handle_control_message(self, lxm):
        original_command = lxm.content_as_string().strip().lower()
        command = original_command
        command_value = None
        response_content = None

        try:
            if self.control_command_separator in command:
                # separate command and value
                command_parts = command.split(self.control_command_separator)
                # handle command with spaces or underscores
                original_command = command_parts[0].strip()
                command = original_command.replace(' ', '_')
                command_value = command_parts[1].strip()
            
            if command in ['help', 'setting', 'settings', 'control', 'example', 'examples']:
                response_content = pyjs8callLXMF.CONTROL_HELP_TEXT
            elif command == 'new':
                callsign = command_value.upper()
    
                if self.callsign_destination_exists(callsign):
                    response_content = 'Destination exists for {}, conversation bumped'.format(callsign)
                    callsign_response_content = 'JS8Call Control: bumping conversation'
                else:
                    response_content = 'Destination created for {}, conversation initialized'.format(callsign)
                    callsign_response_content = 'JS8Call Control: initializing conversation'
                
                callsign_destination = self.get_destination_by_callsign(callsign)
                callsign_destination.announce()
                lxm = LXMF.LXMessage(notification_destination, callsign_destination, callsign_response_content)
                self.router.handle_outbound(lxm)
            elif command == 'restart js8call':
                notification_destination = self.get_notification_destination()
                
                response_content = 'JS8Call will restart when there is no outgoing activity, please wait...'
                lxm = LXMF.LXMessage(notification_destination, self.destination, response_content)
                self.router.handle_outbound(lxm)

                # restart after 3 seconds of inactivity
                self._client.restart_when_inactive(age=3)
                
                while not self._client.restarting:
                    time.sleep(0.1)
                
                response_content = 'JS8Call restarting, this may take several seconds...'
                lxm = LXMF.LXMessage(notification_destination, self.destination, response_content)
                self.router.handle_outbound(lxm)
                
                while self._client.restarting:
                    time.sleep(0.1)
                
                response_content = 'JS8Call successfully restarted'
                lxm = LXMF.LXMessage(notification_destination, self.destination, response_content)
                self.router.handle_outbound(lxm)
            else:
                method = command
                args = command_value
                setting = None
        
                if args is not None:
                    args = args.split()
                            
                if method in self.settings:
                    if self.settings[method] is not None and args is None:
                        # setter method, missing args
                        raise Exception('Missing expected setting value, try \'{}: VALUE\''.format(original_command))
                    elif self.settings[method] is not None and len(args.split()) != self.settings[method]:
                        # setter method, incorrect number of args
                        raise Exception('{} setting values given, {} required, check pyjs8call documentation'.format(len(args.split()), self.settings[method]))
                    elif self.settings[method] is not None:
                        # setter method, correct number of args
                        try:
                            setting = getattr(self._client.settings, method)(*args)
                        except Exception:
                            raise Exception('Failed to process setting')
                    elif self.settings[method] is None and args is not None:
                        # getter method, with args
                        raise Exception('Unexpected setting value, try \'{}\''.format(original_command))
                    else:
                        # getter method, without args
                        try:
                            setting = getattr(self._client.settings, method)()
                        except Exception:
                            raise Exception('Failed to process setting')
                else:
                    raise Exception('Invalid setting'.format(original_command))

                if setting is not None:
                    # setting request executed, return result
                    response_content = '{}: {}'.format(original_command, setting)
                
        except Exception as e:
            response_content = 'Error: {}'.format(e)
            
        if response_content is not None:
            notification_destination = self.get_notification_destination()
            lxm = LXMF.LXMessage(notification_destination, self.destination, response_content)
            self.router.handle_outbound(lxm)

        #TODO
        print('Control message: {}'.format(original_command))
            
        
