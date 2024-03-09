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


import os
import time
import shutil
import atexit
import threading
import configparser
from datetime import datetime, timezone
from math import radians, sin, cos, acos, atan2, pi

import pyjs8call
from pyjs8call import Message


class Client:
    '''JS8Call API client.
    
    **Caution**: Custom processing of messages is an advanced feature that can break internal message handling if implemented incorrectly. Use this feature only if you understand what you are doing.
    **Note**: Any delay in *process_incoming* and *process_outgoing* functions will cause delays in internal incoming and outgoing message processing loops. Custom processing should be kept to a minimum to avoid cumulative delays.
    
    Custom Incoming Message Processing:
    
    The *process_incoming* function is called after internal processing of an incoming message from the JS8Call application, but before adding the message to the incoming message queue.
    
    *process_incoming* should accept a pyjs8call.message object, and return a pyjs8call.message object. If an error occurs during processing, either:
        - set the *msg.error* string before returning the message, which will cause the message to continue processing and be added to the incoming message queue
        OR
        - return None, which will cause the message to be dropped
    
    *process_incoming* function signatures:
        `func(pyjs8call.Message) -> pyjs8call.Message`
        `func(pyjs8call.Message) -> None`

    Custom Outgoing Message Processing:
    
    The *process_outgoing* function is called just after message creation in the following functions:
        - send_message
        - send_directed_message
        - send_directed_command_message
    
    *process_outgoing* should accept a pyjs8call.message object, and return a pyjs8call.message object. If an error occurs during processing:
        - set the *msg.error* string, which will cause the message to be returned with a failed status (the message will not be sent)
    
    *process_outoing* function signature:
        `func(pyjs8call.Message) -> pyjs8call.Message`

    Attributes:
        js8call (pyjs8call.js8call): Manages JS8Call application and TCP socket communication
        spots (pyjs8call.spotmonitor): Monitors station activity and issues callbacks
        window (pyjs8call.windowmonitor): Monitors the JS8Call transmit window
        offset (pyjs8call.offsetmonitor): Manages JS8Call offset frequency
        outgoing (pyjs8call.outgoingmonitor): Monitors JS8Call outgoing message text
        drift_sync (pyjs8call.timemonitor): Monitors JS8Call time drift
        time_master (pyjs8call.timemonitor): Manages time master outgoing messages
        inbox (pyjs8call.inboxmonitor): Monitors JS8Call inbox messages
        config (pyjs8call.confighandler): Manages JS8Call configuration file
        heartbeat (pyjs8call.hbnetwork): Manages heartbeat outgoing messages
        schedule (pyjs8call.schedulemonitor): Monitors and activates schedule entries
        propagation (pyjs8call.propagation): Parse spots into propagation data
        notifications (pyjs8call.notifications): Send email notifications via SMTP server
        callback (pyjs8call.client.Callbacks): Callback function reference object
        settings (pyjs8call.client.Settings): Configuration setting function reference object
        clean_directed_text (bool): Remove JS8Call callsign structure from incoming messages, defaults to True
        monitor_outgoing (bool): Monitor outgoing message status (see pyjs8call.outgoingmonitor), defaults to True
        max_spot_age (int): Maximum age (in seconds) of spots to store before dropping old spots, defaults to 7 days
        online (bool): Whether the JS8Call application and pyjs8call interface are online
        host (str): IP address matching JS8Call *TCP Server Hostname* setting
        port (int): Port number matching JS8Call *TCP Server Port* setting
        process_incoming (func): Function to call for custom processing of incoming messages, defaults to None
        process_outgoing (func): Function to call for custom processing of outgoing messages, defaults to None
        BANDS (dict): mapping of frequency bands to minimum and maximum frequencies
        OOB (str): out-of-band designator
    '''

    BANDS = {
        '2190m':  (136000,       137000),
        '630m':   (472000,       479000),
        '560m':   (501000,       504000),
        '160m':   (1800000,      2000000),
        '80m':    (3500000,      4000000),
        '60m':    (5060000,      5450000),
        '40m':    (7000000,      7300000),
        '30m':    (10000000,     10150000),
        '20m':    (14000000,     14350000),
        '17m':    (18068000,     18168000),
        '15m':    (21000000,     21450000),
        '12m':    (24890000,     24990000),
        '10m':    (28000000,     29700000),
        '6m':     (50000000,     54000000),
        '4m':     (70000000,     71000000),
        '2m':     (144000000,    148000000),
        '1.25m':  (222000000,    225000000),
        '70cm':   (420000000,    450000000),
        '33cm':   (902000000,    928000000),
        '23cm':   (1240000000,   1300000000),
        '13cm':   (2300000000,   2450000000),
        '9cm':    (3300000000,   3500000000),
        '6cm':    (5650000000,   5925000000),
        '3cm':    (10000000000,  10500000000),
        '1.25cm': (24000000000,  24250000000),
        '6mm':    (47000000000,  47200000000),
        '4mm':    (75500000000,  81000000000),
        '2.5mm':  (119980000000, 120020000000),
        '2mm':    (142000000000, 149000000000),
        '1mm':    (241000000000, 250000000000)
    }
    
    OOB = 'OOB'
    
    @staticmethod
    def freq_to_band(freq):
        '''Get band for specified frequency.

        Args:
            freq (int): Frequency in Hz

        Returns:
            str: Band designator like \'40m\' if frequency is in a known band, otherwise *Client.OOB*
        '''
        if freq is None:
            return Client.OOB
            
        for band, freqs in Client.BANDS.items():
            if freqs[0] <= freq <= freqs[1]:
                return band

        return Client.OOB

    @staticmethod
    def band_freq_range(band):
        '''Get frequency range for specified band.

        Args:
            band (str): Band designator like \'40m\'

        Returns:
            tuple or str: (min_freq, max_freq) if band is known, otherwise *Client.OOB*
        '''
        if band is None:
            return Client.OOB
            
        band = band.lower()
        
        if band in Client.BANDS:
            return Client.BANDS[band]
        
        return Client.OOB

    def __init__(self, host='127.0.0.1', port=2442, config_path=None):
        '''Initialize JS8Call API client.

        Registers the Client.stop function with the atexit module.
        
        Configures the following settings:
        - enable autoreply at startup
        - disable autoreply confirmation
        - enable transmit

        Initializes the following for access prior to starting:
        - js8call (pyjs8call.js8call)
        - config (pyjs8call.confighandler)
        - settings (pyjs8call.client.settings)
        - callback (pyjs8call.client.callbacks)
        - notifications (pyjs8call.notifications)

        Args:
            host (str): JS8Call TCP address setting, defaults to '127.0.0.1'
            port (int): JS8Call TCP port setting, defaults to 2442
            config_path (str): Non-standard JS8Call.ini configuration file path, defaults to None

        Returns:
            pyjs8call.Client: Constructed client object

        Raises:
            RuntimeError: JS8Call application not installed
        '''
        self.host = host
        self.port = port
        self.online = False
        self.restarting = False
        self.process_incoming = None
        self.process_outgoing = None
        self.clean_directed_text = True
        self.monitor_outgoing = True
        self.max_spot_age = 7 * 24 * 60 * 60 # 7 days
        self._previous_profile = None

        self.config = None
        self.settings = None
        self.callback = None
        self.js8call = None
        self.spots = None
        self.window = None
        self.offset = None
        self.outgoing = None
        self.drift_sync = None
        self.time_master = None
        self.inbox = None
        self.heartbeat = None
        self.schedule = None
        self.propagation = None
        self.notifications = None

        # delay between setting value and getting updated value
        self._set_get_delay = 0.1 # seconds

        # ensure js8call application is installed
        if shutil.which('js8call') is None:
            raise RuntimeError('JS8Call application not installed')

        self.config = pyjs8call.ConfigHandler(config_path = config_path)
        self.settings = pyjs8call.Settings(self)
        self.callback = pyjs8call.Callbacks()
        self.js8call = pyjs8call.JS8Call(self, self.host, self.port)
        self.notifications = pyjs8call.Notifications(self)

        if 'pyjs8callCleanDirectedTest' in self.config.config['Configuration'] and self.config.get('Configuration', 'pyjs8callCleanDirectedText') is not None:
        config_clean_directed_text = self.config.get('Configuration', 'pyjs8callCleanDirectedText', bool)
        if config_clean_directed_text is not None:
            self.clean_directed_text = config_clean_directed_text

        config_monitor_outgoing = self.config.get('Configuration', 'pyjs8callMonitorOutgoing', bool, fallback=self.monitor_outgoing)
        if config_monitor_outgoing is not None:
            self.monitor_outgoing = config_monitor_outgoing

        config_max_spot_age = self.config.get('Configuration', 'pyjs8callMaxSpotAge', int, fallback=self.max_spot_age)
        if config_max_spot_age is not None:
            self.max_spot_age = config_max_spot_age

        # stop application and client at exit
        atexit.register(self.stop)

    def start(self, headless=False, args=None, debugging=False, logging=False):
        '''Start and connect to the the JS8Call application.

        Initializes module objects:
        - Spot monitor (see pyjs8call.spotmonitor)
        - Window monitor (see pyjs8call.windowmonitor)
        - Offset monitor (see pyjs8call.offsetmonitor)
        - Outgoing monitor (see pyjs8call.outgoingmonitor)
        - Time drift monitor (see pyjs8call.timemonitor)
        - Time master (see pyjs8call.timemonitor)
        - Heartbeat networking (see pyjs8call.hbnetwork)
        - Inbox monitor (see pyjs8call.inboxmonitor)
        - Schedule monitor (see pyjs8call.schedulemonitor)
        - Propagation (see pyjs8call.propagation)

        Enables modules:
        - window
        - spots
        - offset
        - outgoing
        - schedule

        Adds the @TIME group to JS8Call via the config file to enable drift monitor features.

        If logging is enabled the log file will be stored in the current user's *HOME* directory.

        if *args* contains the rig name switch (-r or --rig-name) the rig name is used to instantiate the rig specific config file before launching. Changes to the config object prior to calling *start* are saved to the rig specifc file only, and are not written to the main config file.

        Args:
            headless (bool): Run JS8Call headless via xvfb (Linux only)
            args (list): Command line arguments (see appmonitor.start()), defaults to None
            debugging (bool): Print message data to the console, defaults to False
            logging (bool): Print message data to ~/pyjs8call.log, defaults to False

        Raises:
            RuntimeError: JS8Call config file section does not exist (likely because JS8Call has not been run and configured after installation)
        '''
        if args is None:
            args = []
        else:
            rig_name = None

            # try to find the rig name switch, and then the following rig name
            try:
                rig_name = args[args.index('-r') + 1]
            except ValueError:
                pass

            try:
                rig_name = args[args.index('--rig-name') + 1]
            except ValueError:
                pass

            if rig_name is not None:
                self.config.load_rig_config(rig_name)

        try:
            # enable JS8Call TCP connection
            self.config.set('Configuration', 'TCPEnabled', 'true')
            self.config.set('Configuration', 'TCPServer', self.host)
            self.config.set('Configuration', 'TCPServerPort', str(self.port))
            self.config.set('Configuration', 'AcceptTCPRequests', 'true')
            # support pyjs8call.timemonitor features
            self.config.add_group('@TIME')
            self.config.write()
        except RuntimeError as e:
            raise RuntimeError('Try launching JS8Call, configuring audio and CAT interfaces as needed, '
                               'and then exiting the application normally. When the application '
                               'exits normally the first time it will initialize the config file.') from e

        self.js8call.start(headless = headless, args = args)
        self.online = True

        if debugging:
            self.js8call.enable_debugging()

        if logging:
            self.js8call.enable_logging()

        rx_thread = threading.Thread(target=self._rx)
        rx_thread.daemon = True
        rx_thread.start()
        time.sleep(1)

        self.window = pyjs8call.WindowMonitor(self)
        self.spots = pyjs8call.SpotMonitor(self)
        self.offset = pyjs8call.OffsetMonitor(self)
        self.outgoing = pyjs8call.OutgoingMonitor(self)
        self.drift_sync = pyjs8call.DriftMonitor(self)
        self.time_master = pyjs8call.TimeMaster(self)
        self.heartbeat = pyjs8call.HeartbeatNetworking(self)
        self.inbox = pyjs8call.InboxMonitor(self)
        self.schedule = pyjs8call.ScheduleMonitor(self)
        self.propagation = pyjs8call.Propagation(self)
        
        self.window.enable()
        self.spots.enable()
        self.offset.enable()
        self.outgoing.enable()
        self.schedule.enable()

        # if settings loaded, apply post start settings
        if self.settings.loaded_settings is not None:
            self.settings.apply_loaded_settings(post_start = True)
    
    def exit_tasks(self):
        '''Perform application exit tasks.

        This function is called automatically as needed.
        '''
        self.config.set('Configuration', 'pyjs8callCleanDirectedText', self.clean_directed_text)
        self.config.set('Configuration', 'pyjs8callMonitorOutgoing', self.monitor_outgoing)
        self.config.set('Configuration', 'pyjs8callMaxSpotAge', self.max_spot_age)

        # restore previous config profile
        if self._previous_profile is not None and self._previous_profile in self.settings.get_profile_list():
            self.settings.set_profile(self._previous_profile)
            
        self.config.write()

    def stop(self):
        '''Stop client, modules, and JS8Call application.

        Write to the configuration file, stop all threads, close the TCP socket, and kill the JS8Call application.
        '''
        self.online = False
        self.exit_tasks()
        
        try:
            return self.js8call.stop()
        except Exception:
            pass

    def restart(self):
        '''Stop and restart the JS8Call application and the associated TCP socket.

        Settings, local state, and spots are preserved.
        '''
        self.restarting = True

        # pause module loops to prevent errors
        modules = [
            self.outgoing,
            self.offset,
            self.inbox,
            self.heartbeat,
            self.drift_sync,
            self.time_master,
            self.spots,
            self.schedule
        ]

        paused_modules = []
        
        for module in modules:
            if module.enabled() and not module.paused():
                module.pause()
                paused_modules.append(module)

        # write any pending config file changes, convience
        self.config.write()
        # reeset window monitoring
        self.window.reset()
        # save settings
        headless = self.js8call.app.headless
        args = self.js8call.app.args
        settings = self.js8call.restart_settings()

        # stop
        self.stop()

        # start
        self.js8call = pyjs8call.JS8Call(self, self.host, self.port)
        # restore settings
        self.js8call.reinitialize(settings)
        self.js8call.start(headless = headless, args = args)
        self.online = True

        rx_thread = threading.Thread(target=self._rx)
        rx_thread.daemon = True
        rx_thread.start()
        time.sleep(0.5)

        # resume paused module loops
        for module in paused_modules:
            module.resume()

        self.restarting = False

    def restart_when_inactive(self, age=0):
        '''Restart the JS8Call application once there is no outgoing activity.
        
        This function is non-blocking due to the use of *threading.Thread* internally.
        
        See *pyjs8call.js8call.activity()* for more details.
        
        Args:
            age (int): Maximum age in seconds of outgoing activity to consider active, defaults to 0
        '''
        thread = threading.Thread(target=self._restart_when_inactive, args=(age,))
        thread.daemon = True
        thread.start()
        
    def _restart_when_inactive(self, age):
        '''Thread function to restart once there is no outgoing activity.'''
        self.js8call.block_until_inactive(age = age)
        self.restart()
        
    def set_profile_on_exit(self, profile):
        '''
        '''
        if profile not in self.config.get_profile_list():
            raise ValueError('Config profile \'' + profile + ' \' does not exist')

        self._previous_profile = profile

    def activity(self, age=0):
        '''Whether there is outgoing activity.

        This is a convenience function that calls *pyjs8call.js8call.activity()*.
        
        Args:
            age (int): Maximum age of outgoing activity to consider active, defaults to 0 (disabled)

        Returns:
            bool: True if text in the tx text field, queued outgoing messages, or recent activity, False otherwise
        '''
        return self.js8call.activity(age)

    def _rx(self):
        '''Rx thread function.'''
        while self.online:
            msg = self.js8call.get_next_message()

            if msg is not None:
                # incoming type callback
                for callback in self.callback.incoming_type(msg.type):
                    thread = threading.Thread(target=callback, args=[msg])
                    thread.daemon = True
                    thread.start()

                # custom command callback
                if msg.cmd is not None and msg.cmd in self.callback.commands:
                    for callback in self.callback.commands[msg.cmd]:
                        thread = threading.Thread(target=callback, args=[msg])
                        thread.daemon = True
                        thread.start()

            time.sleep(0.1)

    def connected(self):
        '''Get the state of the connection to the JS8Call application.

        Returns:
            bool: State of connection to JS8Call application
        '''
        return self.js8call.connected

    def identities(self, hb = False):
        '''Get identities associated with local stations.
        
        Args:
            hb (bool): Whether to include the @HB group in identity list, defaults to False
        Returns:
            list: Configured callsign and custom groups
        '''
        ids = self.config.get_groups()
        
        if hb and '@HB' not in ids:
            ids.append('@HB')
            
        ids.append(self.settings.get_station_callsign())
        return ids
    
    def msg_is_to_me(self, msg):
        '''Determine if specified message is addressed to local station.
        
        Utilizes *msg.is_directed_to()* and *client.identities()* internally.
        
        Args:
            msg (pyjs8call.message): Message object to evaluate
            
        Returns:
            bool: True if *msg* is addressed to the local station, False otherwise
        '''
        
        return msg.is_directed_to(self.identities())
    
    def clean_rx_message_text(self, msg):
        '''Clean incoming message text.

        Remove origin callsign, destination callsign or group (including relays), whitespace, and end-of-message characters. This leaves only the message text.
        
        The *pyjs8call.message.text* attribute stores the cleaned text while the *pyjs8call.message.value* attribute is unchanged.

        Custom commands are also parsed out of message text. If a custom command is found, *pyjs8call.message.cmd* is set in the returned message.

        Args:
            message (pyjs8call.message): Message object to clean

        Returns:
            pyjs8call.message: Cleaned message object
        '''
        if msg is None:
            return msg
        # nothing to clean
        elif msg.value in (None, ''):
            return msg
        # already cleaned
        elif msg.value != msg.text:
            return msg

        message = msg.value

        # remove origin callsign
        # avoid other semicolons in message text
        message = ':'.join(message.split(':')[1:]).strip()

        # handle no spaces between relay path and message text
        # avoid other relay character in message text
        last_relay_index = message.rfind(Message.CMD_RELAY, 0, message.find(' '))

        if last_relay_index > 0:
            # remove relay path
            message = message[last_relay_index + 1:]
        else:
            # remove destination callsign or group
            message = ' '.join(message.split(' ')[1:])

        # parse out custom commands
        space_after_cmd = message.find(' ', 1)
        cmd = message[0:space_after_cmd]

        if msg.cmd in (None, '', ' ') and cmd in self.callback.commands:
            msg.set('cmd', cmd)

        # strip spaces and end-of-message symbol
        message = message.strip(' ' + Message.EOM)

        msg.set('text', message)
        return msg
    
    def send_message(self, message):
        '''Send a raw JS8Call message.
        
        Message format: *MESSAGE*
        
        *process_outgoing* is called just after message object creation, if set. If *msg.error* is set after custom processing, the message object is returned with a failed status and without being sent.

        The constructed message object is passed to pyjs8call.outgoingmonitor internally if *monitor_outgoing* is True (default).

        Args:
            message (str): Message text to send

        Returns:
            pyjs8call.message: Constructed message object
        '''
        # msg.type = Message.TX_SEND_MESSAGE by default
        msg = Message(value = message, origin = self.settings.get_station_callsign())
        
        # custom processing of outgoing messages
        if self.process_outgoing is not None:
            msg = self.process_outgoing(msg)

            if msg.error is not None:
                msg.set('status', Message.STATUS_FAILED)
                return msg

        if self.monitor_outgoing:
            self.outgoing.monitor(msg)

        self.js8call.send(msg)
        return msg

    def send_directed_bytes_message(self, destination, message):
        '''Send bytes via JS8Call message.
        
        Message format: *MESSAGE*
        
        *process_outgoing* is called just after message object creation, if set. If *msg.error* is set after custom processing, the message object is returned with a failed status and without being sent.

        The constructed message object is passed to pyjs8call.outgoingmonitor internally if *monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the message to
            message (bytes): Bytes to decode and send as JS8Call text

        Returns:
            pyjs8call.message: Constructed message object
        '''
        # msg.type = Message.TX_SEND_MESSAGE by default
        msg = Message(destination = destination, origin = self.settings.get_station_callsign())
        # decode message bytes to js8call supported characters
        msg.decode(message)
        
        # custom processing of outgoing messages
        if self.process_outgoing is not None:
            msg = self.process_outgoing(msg)

            if msg.error is not None:
                msg.set('status', Message.STATUS_FAILED)
                return msg

        if self.monitor_outgoing:
            self.outgoing.monitor(msg)

        self.js8call.send(msg)
        return msg

    def send_directed_command_message(self, destination, command, message=None):
        '''Send a directed JS8Call command message.

        Message format: *DESTINATION**COMMAND* *MESSAGE*

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.
        
        *process_outgoing* is called just after message object creation, if set. If *msg.error* is set after custom processing, the message object is returned with a failed status and without being sent.

        The constructed message object is passed to pyjs8call.outgoingmonitor internally if *monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the message to
            command (str): Command to include in message (see *pyjs8call.message* static commands)
            message (str): Message text to send, defaults to None
        '''
        # msg.type = Message.TX_SEND_MESSAGE by default
        msg = Message(destination, command, message, self.settings.get_station_callsign())
        
        # custom processing of outgoing messages
        if self.process_outgoing is not None:
            msg = self.process_outgoing(msg)

            if msg.error is not None:
                msg.set('status', Message.STATUS_FAILED)
                return msg

        if self.monitor_outgoing:
            self.outgoing.monitor(msg)
            
        self.js8call.send(msg)
        return msg
    
    def send_directed_message(self, destination, message):
        '''Send a directed JS8Call message.
        
        Message format: *DESTINATION* *MESSAGE*

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.
        
        *process_outgoing* is called just after message object creation, if set. If *msg.error* is set after custom processing, the message object is returned with a failed status and without being sent.

        The constructed message object is passed to pyjs8call.outgoingmonitor internally if *monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the message to
            message (str): Message text to send

        Returns:
            pyjs8call.message: Constructed message object
        '''
        # msg.type = Message.TX_SEND_MESSAGE by default
        msg = Message(destination, value = message, origin = self.settings.get_station_callsign())
        
        # custom processing of outgoing messages
        if self.process_outgoing is not None:
            msg = self.process_outgoing(msg)

            if msg.error is not None:
                msg.set('status', Message.STATUS_FAILED)
                return msg

        if self.monitor_outgoing:
            self.outgoing.monitor(msg)

        self.js8call.send(msg)
        return msg

    def send_heartbeat(self, grid=None):
        '''Send a JS8Call heartbeat message.

        Note that JS8Call will only transmit API messages at the selected offset. Heartbeat messages can still be sent, but will not be in the heartbeat sub-band.

        Message format: @HB HEARTBEAT *GRID*

        If no grid square is given the configured JS8Call grid square is used.

        The constructed message object is passed to pyjs8call.outgoingmonitor internally if *monitor_outgoing* is True (default).

        Args:
            grid (str): Grid square (truncated to 4 characters), defaults to None

        Returns:
            pyjs8call.message: Constructed messsage object
        '''
        if grid is None:
            grid = self.settings.get_station_grid()

        if grid is None:
            grid = ''

        if len(grid) > 4:
            grid = grid[:4]

        return self.send_directed_command_message('@HB', Message.CMD_HEARTBEAT, grid)

    def send_aprs_grid(self, grid=None):
        '''Send a JS8Call message with APRS grid square.
        
        Message format: @APRSIS GRID *GRID*

        If no grid square is given the configured JS8Call grid square is used.

        The constructed message object is passed to pyjs8call.outgoingmonitor internally if *monitor_outgoing* is True (default).

        Args:
            grid (str): Grid square (trucated to 4 characters), defaults to None

        Returns:
            pyjs8call.message: Constructed messsage object

        Raises:
            ValueError: Grid square not specified and JS8Call grid square not set
        '''
        if grid is None:
            grid = self.settings.get_station_grid()
        if grid in (None, ''):
            raise ValueError('Grid square cannot be None when sending an APRS grid message')
        if len(grid) > 4:
            grid = grid[:4]

        return self.send_directed_command_message('@APRSIS', Message.CMD_GRID, grid)

    def send_aprs_sms(self, phone, message):
        '''Send a JS8Call APRS message via a SMS gateway.
        
        Message format: @APRSIS CMD :SMSGATE&nbsp;&nbsp;&nbsp;:@1234567890 *MESSAGE*

        The constructed message object is passed to pyjs8call.outgoingmonitor internally if *monitor_outgoing* is True (default).

        Args:
            phone (str): Phone number to send SMS message to
            message (str): Message to be sent via SMS message

        Returns:
            pyjs8call.message: Constructed message object
        '''
        phone = str(phone).replace('-', '').replace('.', '').replace('(', '').replace(')', '')
        message = ':SMSGATE   :@' + phone + ' ' + message
        return self.send_directed_command_message('@APRSIS', Message.CMD_CMD, message)
    
    def send_aprs_email(self, email, message):
        '''Send a JS8Call APRS message via an e-mail gateway.
        
        Message format: @APRSIS CMD :EMAIL-2&nbsp;&nbsp;&nbsp;:EMAIL@DOMAIN.COM *MESSAGE*

        The constructed message object is passed to pyjs8call.outgoingmonitor internally if *monitor_outgoing* is True (default).

        Args:
            email (str): Email address to send message to
            message (str): Message to be sent via email

        Returns:
            pyjs8call.message: Constructed message object
        '''
        message = ':EMAIL-2   :' + email + ' ' + message
        return self.send_directed_command_message('@APRSIS', Message.CMD_CMD, message)
    
    def send_aprs_pota_spot(self, park, freq, mode, message, callsign=None):
        '''Send JS8Call APRS POTA spot message.
        
        Message format: @APRSIS CMD :POTAGW&nbsp;&nbsp;&nbsp;:*CALLSIGN* *PARK* *FREQ* *MODE* *MESSAGE*

        JS8Call configured callsign is used if no callsign is given.

        The constructed message object is passed to pyjs8call.outgoingmonitor internally if *monitor_outgoing* is True (default).

        Args:
            park (str): Name of park being activated
            freq (int): Frequency (in kHz) being used for park activation
            mode (str): Radio operating mode used for park activation
            message (str): Message to be sent with POTA spot
            callsign (str): Callsign of operator activating the park, defaults to None

        Returns:
            pyjs8call.message: Constructed message object
        '''
        if callsign is None:
            callsign = self.settings.get_station_callsign()

        message = ':POTAGW   :' + callsign + ' ' + park + ' ' + str(freq) + ' ' + mode + ' ' + message
        return self.send_directed_command_message('@APRSIS', Message.CMD_CMD, message)
    
    def get_inbox_messages(self, unread=True):
        '''Get JS8Call inbox messages.

        Args:
            unread (bool): Get unread messages only if True, all messages if False

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
            list: List of inbox messages
        '''
        msg = Message()
        msg.type = Message.INBOX_GET_MESSAGES
        self.js8call.send(msg)
        messages = self.js8call.watch('inbox')

        if messages is not None and len(messages) > 0 and unread:
            messages = [msg for msg in messages if msg['unread']]
            
        return messages

    def send_inbox_message(self, destination, message):
        '''Send JS8Call inbox message.

        Message format: *DESTINATION* MSG *MESSAGE*

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.outgoingmonitor internally if *monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the message to
            message (str): Message text to send

        Returns:
            pyjs8call.message: Constructed message object
        '''
        return self.send_directed_command_message(destination, Message.CMD_MSG, message)

    def store_remote_inbox_message(self, remote, destination, message):
        '''Send JS8Call inbox message to be forwarded.

        Message format: *REMOTE* MSG TO:*DESTINATION* *MESSAGE*

        If *remote* is a list of callsigns they will be joined in the specified order and sent as a relay.
        
        The constructed message object is passed to pyjs8call.outgoingmonitor internally if *monitor_outgoing* is True (default).

        Args:
            remote (str, list): Callsign of intermediate station storing the message
            destination (str): Callsign of message recipient
            message (str): Message text to send

        Returns:
            pyjs8call.message: Constructed message object
        '''
        message = destination + ' ' + message
        return self.send_directed_command_message(remote, Message.CMD_MSG_TO, message)

    def store_local_inbox_message(self, destination, message):
        '''Store local JS8Call inbox message for future retrieval.

        Args:
            destination (str): Callsign to direct inbox message to
            message (str): Message text to send

        Returns:
            pyjs8call.message: Constructed message object
        '''
        msg = Message()
        msg.set('type', Message.INBOX_STORE_MESSAGE)
        msg.set('params', {'CALLSIGN': destination, 'TEXT': message})
        self.js8call.send(msg)
        time.sleep(self._set_get_delay)
        return self.get_inbox_messages()

    def query_call(self, callsign, destination='@ALLCALL'):
        '''Send JS8Call callsign query.
        
        Message format: *DESTINATION* QUERY CALL *CALLSIGN*?

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.outgoingmonitor internally if *monitor_outgoing* is True (default).

        Args:
            callsign (str): Callsign to query for
            destination (str, list): Callsign(s) to direct the query to, defaults to @ALLCALL

        Returns:
            pyjs8call.message: Constructed message object
        '''
        message = callsign + Message.CMD_Q
        return self.send_directed_command_message(destination, Message.CMD_QUERY_CALL, message)

    def query_messages(self, destination='@ALLCALL'):
        '''Send JS8Call stored message query.
        
        Message format: *DESTINATION* QUERY MSGS

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.outgoingmonitor internally if *monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the query to, defaults to '@ALLCALL'

        Returns:
            pyjs8call.message: Constructed message object
        '''
        return self.send_directed_command_message(destination, Message.CMD_QUERY_MSGS)

    def query_message_id(self, destination, msg_id):
        '''Send JS8Call stored message ID query.
        
        Message format: *DESTINATION* QUERY MSG *ID*

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.outgoingmonitor internally if *monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the query to
            msg_id (str): Message ID to query for

        Returns:
            pyjs8call.message: Constructed message object
        '''
        return self.send_directed_command_message(destination, Message.CMD_QUERY, 'MSG {}'.format(msg_id))

    def query_hearing(self, destination):
        '''Send JS8Call hearing query.
        
        Message format: *DESTINATION* HEARING?

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.outgoingmonitor internally if *monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the query to

        Returns:
            pyjs8call.message: Constructed message object
        '''
        return self.send_directed_command_message(destination, Message.CMD_HEARING_Q)

    def query_snr(self, destination):
        '''Send JS8Call SNR query.
        
        Message format: *DESTINATION* SNR?

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.outgoingmonitor internally if *monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the query to

        Returns:
            pyjs8call.message: Constructed message object
        '''
        return self.send_directed_command_message(destination, Message.CMD_SNR_Q)

    def query_grid(self, destination):
        '''Send JS8Call grid query.
        
        Message format: *DESTINATION* GRID?

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.outgoingmonitor internally if *monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the query to

        Returns:
            pyjs8call.message: Constructed message object
        '''
        return self.send_directed_command_message(destination, Message.CMD_GRID_Q)

    def query_info(self, destination):
        '''Send JS8Call info query.
        
        Message format: *DESTINATION* INFO?

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.

        The constructed message object is passed to pyjs8call.outgoingmonitor internally if *monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the query to

        Returns:
            pyjs8call.message: Constructed message object
        '''
        return self.send_directed_command_message(destination, Message.CMD_INFO_Q)

    def query_status(self, destination):
        '''Send JS8Call status query.
        
        Message format: *DESTINATION* STATUS?

        If *destination* is a list of callsigns they will be joined in the specified order and sent as a relay.
        
        The constructed message object is passed to pyjs8call.outgoingmonitor internally if *monitor_outgoing* is True (default).

        Args:
            destination (str, list): Callsign(s) to direct the query to

        Returns:
            pyjs8call.message: Constructed message object
        '''
        return self.send_directed_command_message(destination, Message.CMD_STATUS_Q)

    def get_call_activity(self, age=None):
        '''Get JS8Call call activity.

        To get or set JS8Call callsign activity aging from the configuration file:
        `client.config.get('Configuration', 'CallsignAging', int)`
        `client.config.set('Configuration', 'CallsignAging', 120) # 120 minutes`

        See *client.get_distance()* for more information on the value and format of *distance*.

        Each call activity item is a dictionary with the following keys:

        | Key | Value Type |
        | -------- | -------- |
        | origin | str |
        | grid | str |
        | snr | int |
        | time (UTC) | int |
        | timestamp (local) | int |
        | local_time_str | str |
        | speed | str |
        | hearing | list |
        | heard_by | list |
        | distance | tuple |

        Args:
            age (int): Maximum activity age in minutes, defaults to JS8Call callsign activity aging

        Returns:
            list: Call activity items, sorted decending by *time* (recent first)

            If grid is not set, distance is *(None, None, None)*.
        '''
        if age is None:
            age = self.config.get('Configuration', 'CallsignAging', int)

        age *= 60 # minutes to seconds

        msg = Message()
        msg.type = Message.RX_GET_CALL_ACTIVITY
        self.js8call.send(msg)
        call_activity = self.js8call.watch('call_activity')

        hearing = self.hearing(age)
        heard_by = self.heard_by(age , hearing)
        now = time.time()

        for i in call_activity.copy():
            activity = call_activity.pop(0)
            activity['origin'] = activity['origin'].strip()
            activity['grid'] = activity['grid'].strip()

            # remove aged activity
            if age != 0 and (now - activity['timestamp']) > age:
                continue

            if activity['origin'] in hearing:
                activity['hearing'] = hearing[activity['origin']]
            else:
                activity['hearing'] = []

            if activity['origin'] in heard_by:
                activity['heard_by'] = heard_by[activity['origin']]
            else:
                activity['heard_by'] = []

            if activity['grid'] not in (None, ''):
                activity['distance'] = self.grid_distance(activity['grid'])
            else:
                activity['distance'] = (None, None, None)

            spot = self.spots.filter(origin = activity['origin'], age = age, count = 1)
            if len(spot) and isinstance(spot[0].get('speed'), int):
                activity['speed'] = self.settings.submode_to_speed(spot[0].get('speed'))
            else:
                activity['speed'] = ''

            call_activity.append(activity)

        call_activity.sort(key = lambda activity: activity['timestamp'], reverse = True)
        return call_activity

    def get_band_activity(self, age=None):
        '''Get JS8Call band activity.

        To get or set JS8Call callsign activity aging from the configuration file:
        `client.config.get('Configuration', 'ActivityAging', int)`
        `client.config.set('Configuration', 'ActivityAging', 5) # 5 minutes`

        Each band activity item is a dictionary with the following keys:

        | Key | Value Type |
        | -------- | -------- |
        | freq (Hz) | int |
        | offset (Hz) | int |
        | snr | int |
        | time (UTC) | int |
        | timestamp (local) | int |
        | local_time_str | str |
        | text | str |

        Args:
            age (int): Maximum activity age in minutes, defaults to JS8Call band activity aging

        Returns:
            list: Band activity items, sorted ascending by offset
        '''
        if age is None:
            age = self.config.get('Configuration', 'ActivityAging', int)

            if age == 0:
                age = None

        if age is not None:
            age *= 60 # minutes to seconds

        msg = Message()
        msg.type = Message.RX_GET_BAND_ACTIVITY
        self.js8call.send(msg)
        band_activity = self.js8call.watch('band_activity')

        now = time.time()

        if age is not None:
            # remove aged activity
            for i in band_activity.copy():
                activity = band_activity.pop(0)

                if (now - activity['timestamp']) > age:
                    continue

                band_activity.append(activity)

        band_activity.sort(key=lambda activity: activity['offset'])
        return band_activity

    def get_selected_call(self):
        '''Get JS8Call selected callsign.

        Returns:
            str: Callsign selected on the JS8Call user interface
            None: No callsign selected
        '''
        msg = Message()
        msg.type = Message.RX_GET_SELECTED_CALL
        self.js8call.send(msg)
        selected_call = self.js8call.watch('selected_call')

        if selected_call == '':
            selected_call = None

        return selected_call

    def get_rx_text(self):
        '''Get JS8Call rx text.

        Returns:
            str: Text from the JS8Call rx text field
        '''
        msg = Message()
        msg.type = Message.RX_GET_TEXT
        self.js8call.send(msg)
        rx_text = self.js8call.watch('rx_text')
        return rx_text
        
    def get_tx_text(self, update=False):
        '''Get JS8Call tx text.

        Args:
            update (bool): Update tx text if True or use local state if False, defaults to False
            
        Returns:
            str: Text from the JS8Call tx text field
        '''
        if not update:
            return self.js8call.get_state('tx_text')
            
        msg = Message()
        msg.set('type', Message.TX_GET_TEXT)
        self.js8call.send(msg)
        tx_text = self.js8call.watch('tx_text')
        return tx_text

    def set_tx_text(self, text):
        '''Set JS8Call tx text.

        Args:
            text (str): Text to set

        Returns:
            str: Text from the JS8Call tx text field
        '''
        msg = Message()
        msg.set('type', Message.TX_SET_TEXT)
        msg.set('value', text)
        time.sleep(self._set_get_delay)
        return self.get_tx_text()

    def raise_window(self):
        '''Raise the JS8Call application window.'''
        msg = Message()
        msg.type = Message.WINDOW_RAISE
        self.js8call.send(msg)

    def get_rx_messages(self, own=True):
        '''Get list of messages from the JS8Call rx text field.

        Each message is a dictionary object with the following keys:
        - time
        - offset
        - origin
        - destination
        - text

        Dictionary keys *origin* and *destination* may be *None*.

        Args:
            own (bool): Include outgoing messages listed in the rx text field, defaults to True

        Returns:
            list: Messages from the rx text field
        '''
        # rx message structure:
        # hh:mm:ss - (offset) - text
        #   [0]        [1]      [2]
        #    ^ index when split on '-'

        rx_text = self.get_rx_text()
        callsign = self.settings.get_station_callsign()
        msgs = rx_text.split('\n\n')
        msgs = [msg.strip(' ' + Message.EOM) for msg in msgs if len(msg.strip()) > 0]

        rx_messages = []
        for msg in msgs:
            # check for first dash and opening offset parenthesis to avoid processing malformed text 
            # this string avoids finding negative SNR values in message text
            if ' - (' not in msg:
                continue

            parts = msg.split('-')
            # handle dash/hyphen/negative in message text
            if len(parts) > 3:
                parts[2] = '-'.join(parts[2:])
                parts = parts[:3]

            data = {}

            data['time'] = parts[0].strip()
            data['offset'] = int(parts[1].strip(' \n()'))
            data['text'] = parts[2].strip()
            data['origin'] = None
            data['destination'] = None

            if ':' in data['text']:
                # directed message structure
                #   origin: destination[ command] text
                #   note: directed message without command has double space after destination
                #
                # free text with only origin falls through with no further processing

                directed_parts = data['text'].split(':')
                data['origin'] = directed_parts[0].strip()
                data['text'] = directed_parts[1].strip()
                first_space = data['text'].find(' ')

                # double space
                if '  ' in data['text']:
                    # directed message without command
                    directed_parts = data['text'].split('  ')
                    data['destination'] = directed_parts[0].strip()
                    data['text'] = directed_parts[1].strip()

                elif first_space > 0:
                    # directed message with command
                    destination = data['text'][:first_space].strip()
                    # do not strip whitespace here, this removes leading space in command string
                    text = data['text'][first_space:]

                    # look for command at begining of text to confirm destination/text split is correct
                    commands = Message.COMMANDS.copy()
                    commands.remove(Message.CMD_FREETEXT)
                    commands.remove(Message.CMD_FREETEXT_2)

                    for cmd in commands:
                        if text.find(cmd) == 0:
                            data['destination'] = destination
                            data['text'] = text

            if not own and data['origin'] == callsign:
                continue

            rx_messages.append(data)

        return rx_messages
    
    def hearing(self, age=None):
        '''Which stations other stations are hearing.

        Args:
            age (int): Maximum message age in minutes, defaults to JS8Call callsign activity aging

        Returns:
            dict: Example format `{'station': ['station', ...], ...}`
        '''
        if age is None:
            age = self.config.get('Configuration', 'CallsignAging', int)

        age *= 60 # minutes to seconds
            
        callsign = self.settings.get_station_callsign()
        hearing = {}
        
        for spot in self.spots.filter(age = age):
            # only process msgs with directed commands
            if spot.cmd is None:
                continue

            # stations we are hearing
            if callsign not in hearing:
                hearing[callsign] = [spot.origin]
            elif spot.origin not in hearing[callsign]:
                hearing[callsign].append(spot.origin)
                
            if spot.cmd == Message.CMD_HEARING and spot.hearing is not None:
                if spot.origin not in hearing:
                    hearing[spot.origin] = spot.hearing
                else:
                    spot_hearing = [station for station in spot.hearing if station not in hearing[spot.origin]]
                    hearing[spot.origin].extend(spot_hearing)
            
            if spot.cmd in Message.AUTOREPLY_COMMANDS:
                if spot.origin not in hearing:
                    hearing[spot.origin] = []

                if isinstance(spot.path, list):
                    # handle relay path
                    relay_path = Message.CMD_RELAY.join(spot.path)

                    if relay_path not in hearing[spot.origin]:
                        hearing[spot.origin].append(relay_path)

                elif spot.destination != '@ALLCALL' and spot.destination not in hearing[spot.origin]:
                    hearing[spot.origin].append(spot.destination)

        return hearing

    def station_hearing(self, station=None, age=None):
        '''Which stations the specified station is hearing.
        
        See *client.hearing()* for more information.

        Args:
            station (str): Station callsign to get hearing data for, defaults to local station callsign
            age (int): Maximum message age in minutes, defaults to JS8Call callsign activity aging

        Returns:
            list: Station callsigns the specified station is hearing
        '''
        hearing = self.hearing(age)

        if station is None:
            station = self.settings.get_station_callsign()

        if station in hearing:
            return hearing[station]
        else:
            return []
    
    def heard_by(self, age=None, hearing=None):
        '''Which stations are hearing other station.

        *client.heard_by()* is the inverse of *client.hearing()*.

        If calling both *client.hearing()* and *client.heard_by*, it is more efficient to pass the result of *client.hearing()* to *client.heard_by()*. Otherwise, *client.heard_by()* will call *client.hearing()* again internally.

        Args:
            age (int): Maximum message age in minutes, defaults to JS8Call callsign activity aging
            hearing (dict): Result of *client.hearing()*, defaults to result of *client.hearing()*

        Returns:
            dict: Example format `{'station': ['station', ...], ...}`
        '''
        if age is None:
            age = self.config.get('Configuration', 'CallsignAging', int)
        
        age *= 60
        heard_by = {}

        if hearing is None:
            hearing = self.hearing(age)

        for key, value in hearing.items():
            for callsign in value:
                if callsign not in heard_by:
                    heard_by[callsign] = [key]
                elif key not in heard_by[callsign]:
                    heard_by[callsign].append(key)

        return heard_by

    def station_heard_by(self, station=None, age=None, hearing=None):
        '''Which stations are hearing the specified station.

        See *client.heard_by()* for more information.
        
        Args:
            station (str): Station callsign to get heard by data for, defaults to local station callsign
            age (int): Maximum message age in minutes, defaults to JS8Call callsign activity aging
            hearing (dict): Result of *client.hearing()*, defaults to result of *client.hearing()*

        Returns:
            list: Station callsigns heard by the specified station
        '''
        heard_by = self.heard_by(age, hearing)

        if station is None:
            station = self.settings.get_station_callsign()

        if station in heard_by:
            return heard_by[station]
        else:
            return []

#    def discover_path(self, destination, age=60):
#        '''
#        '''
#        age *= 60
#        callsign = self.settings.get_station_callsign()
#        heard_by = self.heard_by(age = age)
#
#        if destination in heard_by:
#            if callsign in heard_by[destination]:
#                return destination
#
#            else:
#                '>'.join()
            
        
    def grid_distance(self, grid_a, grid_b=None):
        '''Calculate great circle distance and bearing between grid squares.

        If *grid_b* is *None*, the JS8Call grid square is used.

        Bearing is calculated from *grid_b* to *grid_a*.

        *grid* must be a 4 or 6 character Maidenhead grid square (ex. EM19 or EM19es). If *grid* is longer than 6 characters it will be truncated to 6 characters.

        Reference: https://www.movable-type.co.uk/scripts/latlong.html

        Args:
            grid_a (str): First grid square
            grid_b (str): Second grid square, defaults to JS8Call grid square

        Returns:
            tuple (int, str, int): Distance, distance units, and bearing in degrees (ex. (1194, 'mi', 312)).
            
            Distance units match JS8Call distance units, see *client.settings.get_distance_units()*.

        Raises:
            ValueError: *grid_b* is *None* and JS8Call grid square is not set
        '''
        earth_radius_km = 6371
        earth_radius_mi = 3958.756

        if grid_b is None:
            grid_b = self.settings.get_station_grid()

        if grid_b in (None, ''):
            raise ValueError('Second grid square required, JS8Call grid square not set.')

        lat_a, lon_a = self.grid_to_lat_lon(grid_a)
        lat_b, lon_b = self.grid_to_lat_lon(grid_b)
        # convert degrees to radians
        lat_a, lon_a, lat_b, lon_b = map(radians, [lat_a, lon_a, lat_b, lon_b])

        # calculate great circle distance
        gcd = acos(sin(lat_a) * sin(lat_b) + cos(lat_a) * cos(lat_b) * cos(lon_b - lon_a))
        
        if self.settings.get_distance_units_miles():
            distance = int(round(earth_radius_mi * gcd, 0))
            units = 'mi'
        else:
            distance = int(round(earth_radius_km * gcd, 0))
            units = 'km'

        # calculate bearing
        y = sin(lon_a - lon_b) * cos(lat_a)
        x = cos(lat_b) * sin(lat_a) - sin(lat_b) * cos(lat_a) * cos(lon_a - lon_b)
        angle = atan2(y, x)
        bearing = (angle * 180 / pi + 360) % 360
        bearing = int(round(bearing, 0))

        return (distance, units, bearing)

    def grid_to_lat_lon(self, grid):
        '''Convert grid square to latitude/longitude.

        *grid* must be a 4 or 6 character Maidenhead grid square (ex. EM19 or EM19es). If *grid* is longer than 6 characters it will be truncated to 6 characters.

        Latitude and longitude are rounded to 3 decimal places.

        Reference: http://www.w8bh.net/grid_squares.pdf

        Args:
            grid (str): Grid square to convert to latitude/longitude

        Returns:
            tuple (float, float): Latitude/longitude pair (ex. (39.750, -97.667))

        Raises:
            ValueError: Invalid grid square format
        '''
        if len(grid) > 6:
            grid = grid[:6]

        if len(grid) not in (4, 6):
            raise ValueError('Grid must contain 4 or 6 characters (ex. EM19 or EM19es)')

        grid = grid.upper()

        field_map = ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R']
        sub_square_map = ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X']
        field_lon_deg = 20
        field_lat_deg = 10
        square_lon_deg = 2
        square_lat_deg = 1
        sub_square_lon_deg = 1/12
        sub_square_lat_deg = 1/24

        grid_lon = [grid[i] for i in range(0, len(grid), 2)]
        grid_lat = [grid[i] for i in range(1, len(grid), 2)]

        try:
            lon = field_map.index(grid_lon[0]) * field_lon_deg
            lon += int(grid_lon[1]) * square_lon_deg

            if len(grid_lon) == 3:
                lon += sub_square_map.index(grid_lon[2]) * sub_square_lon_deg

            lon -= 180
            lon = round(lon, 3)

            lat = field_map.index(grid_lat[0]) * field_lat_deg
            lat += int(grid_lat[1]) * square_lat_deg

            if len(grid_lat) == 3:
                lat += sub_square_map.index(grid_lat[2]) * sub_square_lat_deg

            lat -= 90
            lat = round(lat, 3)

        except ValueError as e:
            raise ValueError('Invalid grid square format. Field and sub-square must be letters A-R '
                             '(case insensitive), and square must be numbers 0-9 (ex. EM19es).') from e

        return (lat, lon)

