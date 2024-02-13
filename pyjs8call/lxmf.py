import threading
import time
import os

import RNS
import LXMF


class pyjs8callApp:
    def __init__(self, client, config_path=None, identity_path=None, announce_on_start=True):
        self._client = client
        self.notification_destination_hash = None
        self.callsign_destinations = {}

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
            
        if os.path.isdir(self.identity_path):
            self.identity = RNS.Identity.from_file(self.identity_path)
        else:
            self.identity = RNS.Identity()
            self.identity.to_file(self.identity_path)

        self.router = LXMF.LXMRouter(self.identity, storagepath=self.storage_path)
        self.router.register_delivery_callback(self.lxmf_delivery_callback)
        self.destination = self.router.register_delivery_identity(self.identity, display_name='JS8Call')

        if announce_on_start:
            self.router.announce(self.destination.hash)

    def set_notification_destination_hash(destination_hash):
        if not isinstance(destination_hash, bytes):
            destination_hash = bytes.from_hex(destination_hash)

        self.notification_destination_hash = destination_hash
        RNS.Transport.request_path(self.notification_destination_hash)
        #TODO wait for known identity
        notification_identity = RNS.Identity.recall(self.notification_destination_hash)
        RNS.Identity.remember(packet_hash=None, destination_hash=self.notification_destination_hash, public_key=notification_identity.get_public_key())
    
    def lxmf_delivery_callback(self, lxm):
        callsign = self.get_callsign_by_destination_hash(lxm.get_destination())

        if callsign is None:
            #TODO improve handling for unknown callsign
            print('Callsign not known for destination {}, dropping outgoing LXMF message'.format(RNS.hexrep(source_hash, delimit=False)))
            return

        self._client.send_directed_message(callsign, lxm.content_as_string())
    
    def js8call_incoming_callback(self, msg):
        if self.notification_destination_hash is None:
            print('Notificaiton target not set, dropping incoming JS8Call message')
            return None
            
        notification_identity = RNS.Identity.recall(self.notification_destination_hash)
        notification_destination = RNS.Destination(notification_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, 'lxmf', 'delivery')

        if msg.origin in self.callsign_destinations:
            callsign_destination = self.callsign_destinations
        else:
            for destination_hash in RNS.Identity.known_destinations:
                if msg.origin == RNS.Identity.get_app_data(destination_hash):
                    callsign_destination = RNS.Identity.recall(callsign
            #callsign_identity = self.get_identity_by_callsign(msg.origin)
            callsign_identity = RNS.Identity.recall(callsign_destination.hash)

            if callsign_identity is None:
                callsign_identity = RNS.Identity()
            
        callsign_destination = RNS.Destination(callsign_identity, RNS.Destination.OUT, RNS.Destination.SINGLE, "lxmf", "delivery")
        self.callsign_destinations[msg.origin] = callsign_destination.hash
            
        lxm = LXMF.LXMessage(notification_destination, callsign_destination, msg.text)
        router.handle_outbound(lxm)

    def get_identity_by_callsign(self, callsign):
        callsign_destination_hash = None
        callsign_identity = None
        
        if callsign in self.callsign_destinations:
            callsign_destination_hash = self.callsign_destinations[callsign]

        if callsign_destination_hash is not None:
            callsign_identity = RNS.Identity.recall(callsign_destination_hash)

        if callsign_identity is None:
            callsign_identity = RNS.Identity()

    def get_callsign_by_destination_hash(self, destination_hash):
        for callsign, destination in self.callsign_destinations:
            if destination_hash == destination:
                return callsign

        return None







