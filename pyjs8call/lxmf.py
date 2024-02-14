import os
import time

import RNS
import LXMF

import pyjs8call


class pyjs8callLXMF:
    CONTROL_HELP_TEXT = '''JS8Call Control Help:
    settings.get_freq
    settings.set_freq 7078000
    new KT7RUN
    '''
    def __init__(self, client, config_path=None, identity_path=None):
        self._client = client
        self.notification_destination_hash = None
        self.display_name_format = '{} (JS8Call)'

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
            self.handle_js8call_control_message(lxm)
            return

        callsign = self.get_callsign_by_destination_hash(lxm.destination.hash)

        if callsign is None:
            #TODO improve handling for unknown callsign
            print('Callsign not known for destination {}, dropping outgoing LXMF message'.format(lxm.destination.hash.hex()))
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

    def handle_js8call_control_message(self, lxm):
        command = lxm.content_as_string().strip().lower()
        command_value = None
        response_content = None
        response_destination = self.destination
        notification_destination = self.get_notification_destination()
        #TODO get list of client.settings functions and arg requirements via introspection?
        #client_settings = [method for method in dir(obj) if callable(getattr(obj, method)) and not method.startswith("__")]


        # separate command and value
        if ' ' in command:
            command_parts = command.split()
            command = command_parts[0]
            command_value = command_parts[1]
        
        if command in ['help', 'setting', 'settings', 'control', 'example', 'examples']:
            response_content = pyjs8callLXMF.CONTROL_HELP_TEXT
        elif command == 'new':
            value = value.upper()

            if self.callsign_destination_exists(value):
                response_content = 'Destination exists for {}, conversation bumped'.format(value)
                callsign_response_content = 'JS8Call Control: bumping conversation'
            else:
                response_content = 'Destination created for {}, conversation initialized'.format(value)
                callsign_response_content = 'JS8Call Control: initializing conversation'
            
            callsign_destination = self.get_destination_by_callsign(value.upper())
            callsign_destination.announce()
            lxm = LXMF.LXMessage(notification_destination, callsign_destination, callsign_response_content)
            self.router.handle_outbound(lxm)
        else:
            # split on .
            # if command in client.settings and value is not None:
            pass
            
        if response_content is not None:
            lxm = LXMF.LXMessage(notification_destination, self.destination, response_content)
            self.router.handle_outbound(lxm)

        #TODO
        print('Control message: {}'.format(control))
        
