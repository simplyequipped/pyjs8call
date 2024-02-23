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


import configparser

from pyjs8call import Message


class Settings:
    '''Settings function container.
    
    This class is initilized by pyjs8call.client.Client.
    '''
    
    def __init__(self, client):
        '''Initialize settings object.

        Returns:
            pyjs8call.client.Settings: Constructed setting object
        '''
        self._client = client
        self.loaded_settings = {}

    def enable_heartbeat_networking(self):
        '''Enable heartbeat networking via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        
        Note that this function disables JS8Call application heartbeat networking via the config file. To enable the pyjs8call heartbeat network messaging module see pyjs8call.hbnetwork.HeartbeatNetworking.enable_networking().
        '''
        self._client.config.set('Common', 'SubModeHB', 'true')

    def disable_heartbeat_networking(self):
        '''Disable heartbeat networking via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        
        Note that this function disables JS8Call application heartbeat networking via the config file. To disable the pyjs8call heartbeat network messaging module see pyjs8call.hbnetwork.HeartbeatNetworking.disable_networking().
        '''
        self._client.config.set('Common', 'SubModeHB', 'false')

    def heartbeat_networking_enabled(self):
        '''Whether heartbeat networking enabled in config file.
        
        Returns:
            bool: True if heartbeat networking enabled, False otherwise
        '''
        return self._client.config.get('Common', 'SubModeHB', bool)

    def get_heartbeat_interval(self):
        '''Get heartbeat networking interval.
        
        Returns:
            int: Heartbeat networking time interval in minutes
        '''
        return self._client.config.get('Common', 'HBInterval', int)
        
    def set_heartbeat_interval(self, interval):
        '''Set the heartbeat networking interval.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.

        Args:
            interval (int): New heartbeat networking time interval in minutes
        
        Returns:
            int: Current heartbeat networking time interval in minutes
        '''
        return self._client.config.set('Common', 'HBInterval', interval)
        
    def enable_heartbeat_acknowledgements(self):
        '''Enable heartbeat acknowledgements via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Common', 'SubModeHBAck', 'true')

    def disable_heartbeat_acknowledgements(self):
        '''Disable heartbeat acknowledgements via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Common', 'SubModeHBAck', 'false')

    def heartbeat_acknowledgements_enabled(self):
        '''Whether heartbeat acknowledgements enabled in config file.
        
        Returns:
            bool: True if heartbeat acknowledgements enabled, False otherwise
        '''
        return self._client.config.get('Common', 'SubModeHBAck', bool)
        
    def pause_heartbeat_during_qso(self):
        '''Pause heartbeat messages during QSO via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'HeartbeatQSOPause', 'true')

    def allow_heartbeat_during_qso(self):
        '''Allow heartbeat messages during QSO via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'HeartbeatQSOPause', 'false')

    def heartbeat_during_qso_paused(self):
        '''Whether heartbeat messages paused during QSO in config file.
        
        Returns:
            bool: True if heartbeat messages paused during QSO, False otherwise
        '''
        return self._client.config.get('Configuration', 'HeartbeatQSOPause', bool)

    def enable_multi_decode(self):
        '''Enable multi-speed decoding via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Common', 'SubModeHBMultiDecode', 'true')

    def disable_multi_decode(self):
        '''Disable multi-speed decoding via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Common', 'SubModeMultiDecode', 'false')

    def multi_decode_enabled(self):
        '''Whether multi-decode enabled in config file.
        
        Returns:
            bool: True if multi-decode enabled, False otherwise
        '''
        return self._client.config.get('Common', 'SubModeMultiDecode', bool)

    def enable_autoreply_startup(self):
        '''Enable autoreply on start-up via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'AutoreplyOnAtStartup', 'true')

    def disable_autoreply_startup(self):
        '''Disable autoreply on start-up via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'AutoreplyOnAtStartup', 'false')

    def autoreply_startup_enabled(self):
        '''Whether autoreply enabled at start-up in config file.
        
        Returns:
            bool: True if autoreply is enabled at start-up, False otherwise
        '''
        return self._client.config.get('Configuration', 'AutoreplyOnAtStartup', bool)

    def enable_autoreply_confirmation(self):
        '''Enable autoreply confirmation via config file.
        
        When running headless the autoreply confirmation dialog box will be inaccessible.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'AutoreplyConfirmation', 'true')

    def disable_autoreply_confirmation(self):
        '''Disable autoreply confirmation via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'AutoreplyConfirmation', 'false')

    def autoreply_confirmation_enabled(self):
        '''Whether autoreply confirmation enabled in config file.
        
        Returns:
            bool: True if autoreply confirmation enabled, False otherwise
        '''
        return self._client.config.get('Configuration', 'AutoreplyConfirmation', bool)

    def enable_allcall(self):
        '''Enable @ALLCALL participation via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'AvoidAllcall', 'false')

    def disable_allcall(self):
        '''Disable @ALLCALL participation via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'AvoidAllcall', 'true')

    def allcall_enabled(self):
        '''Whether @ALLCALL participation enabled in config file.
        
        Returns:
            bool: True if @ALLCALL participation enabled, False otherwise
        '''
        return not self._client.config.get('Configuration', 'AvoidAllcall', bool)

    def enable_reporting(self):
        '''Enable PSKReporter reporting via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'PSKReporter', 'true')

    def disable_reporting(self):
        '''Disable PSKReporter reporting via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'PSKReporter', 'false')

    def reporting_enabled(self):
        '''Whether PSKReporter reporting enabled in config file.
        
        Returns:
            bool: True if reporting enabled, False otherwise
        '''
        return self._client.config.get('Configuration', 'PSKReporter', bool)

    def enable_transmit(self):
        '''Enable JS8Call transmitting via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'TransmitOFF', 'false')

    def disable_transmit(self):
        '''Disable JS8Call transmitting via config file.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        '''
        self._client.config.set('Configuration', 'TransmitOFF', 'true')

    def transmit_enabled(self):
        '''Whether JS8Call transmitting enabled in config file.
        
        Returns:
            bool: True if transmitting enabled, False otherwise
        '''
        return not self._client.config.get('Configuration', 'TransmitOFF', bool)

    def get_profile(self):
        '''Get active JS8call configuration profile via config file.

        This is a convenience function. See pyjs8call.confighandler for other configuration related functions.

        Returns:
            str: Name of the active configuration profile
        '''
        return self._client.config.get_active_profile()

    def get_profile_list(self):
        '''Get list of JS8Call configuration profiles via config file.

        This is a convenience function. See pyjs8call.confighandler for other configuration related functions.

        Returns:
            list: List of configuration profile names
        '''
        return self._client.config.get_profile_list()

    def set_profile(self, profile, restore_on_exit=False):
        '''Set active JS8Call configuration profile via config file.
        
        This is a convenience function. See pyjs8call.confighandler for other configuration related functions.
        
        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.

        Args:
            profile (str): Profile name
            restore_on_exit (bool): Restore previous profile on exit, defaults to False

        Raises:
            ValueError: Specified profile name does not exist
        '''
        if profile not in self._client.config.get_profile_list():
            raise ValueError('Config profile \'' + profile + '\' does not exist')

        if restore_on_exit:
            self._client._previous_profile = self.get_profile()
            
        # set profile as active
        self._client.config.change_profile(profile)

    def get_primary_highlight_words(self):
        '''Get primary highlight words via config file.

        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        
        Returns:
            list: Words that should be highlighted on the JC8Call UI
        '''
        words = self._client.config.get('Configuration', 'PrimaryHighlightWords')

        if words == '@Invalid()':
            words = []
        elif words is not None:
            words = words.split(', ')

        return words

    def set_primary_highlight_words(self, words):
        '''Set primary highlight words via config file.

        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        
        Args:
            words (list): Words that should be highlighted on the JC8Call UI
        '''
        if len(words) == 0:
            words = '@Invalid()'
        else:
            words = ', '.join(words)

        self._client.config.set('Configuration', 'PrimaryHighlightWords', words)

    def get_secondary_highlight_words(self):
        '''Get secondary highlight words via config file.

        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        
        Returns:
            list: Words that should be highlighted on the JC8Call UI
        '''
        words = self._client.config.get('Configuration', 'SecondaryHighlightWords')

        if words == '@Invalid()':
            words = []
        elif words is not None:
            words = words.split(', ')

        return words

    def set_secondary_highlight_words(self, words):
        '''Set secondary highlight words via config file.

        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.
        
        Args:
            words (list): Words that should be highlighted on the JC8Call UI
        '''
        if len(words) == 0:
            words = '@Invalid()'
        else:
            words = ', '.join(words)

        self._client.config.set('Configuration', 'SecondaryHighlightWords', words)

    def submode_to_speed(self, submode):
        '''Map submode *int* to speed *str*.

        | Submode | Speed |
        | -------- | -------- |
        | 0 | normal |
        | 1 | fast |
        | 2 | turbo |
        | 4 | slow |
        | 8 | ultra |

        Args:
            submode (int): Submode to map to text

        Returns:
            str: Speed as text
        '''
        # map integer to text
        speeds = {4:'slow', 0:'normal', 1:'fast', 2:'turbo', 8:'ultra'}

        if submode is not None and int(submode) in speeds:
            return speeds[int(submode)]
        else:
            raise ValueError('Invalid submode \'' + str(submode) + '\'')

    def get_speed(self, update=False):
        '''Get JS8Call modem speed.

        Possible modem speeds:
        - slow
        - normal
        - fast
        - turbo
        - ultra

        Args:
            update (bool): Update speed if True or use local state if False, defaults to False

        Returns:
            str: JS8call modem speed setting
        '''
        speed = self._client.js8call.get_state('speed')

        if update or speed is None:
            msg = Message()
            msg.set('type', Message.MODE_GET_SPEED)
            self._client.js8call.send(msg)
            speed = self._client.js8call.watch('speed')

        return self.submode_to_speed(speed)

    def set_speed(self, speed):
        '''Set JS8Call modem speed via config file.

        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.

        Possible modem speeds:
        - slow
        - normal
        - fast
        - turbo
        - ultra

        Args:
            speed (str): Speed to set

        Returns:
            str: JS8Call modem speed setting

        '''
        if isinstance(speed, str):
            speeds = {'slow':4, 'normal':0, 'fast':1, 'turbo':2, 'ultra':8}
            if speed in speeds:
                speed = speeds[speed]
            else:
                raise ValueError('Invalid speed: ' + str(speed))

        return self._client.config.set('Common', 'SubMode', speed)

#        TODO this code sets speed via API, which doesn't work as of JS8Call v2.2
#        msg = Message()
#        msg.set('type', Message.MODE_SET_SPEED)
#        msg.set('params', {'SPEED': speed})
#        self._client.js8call.send(msg)
#        time.sleep(self._client._set_get_delay)
#        return self.get_speed()

    def get_freq(self, update=False):
        '''Get JS8Call dial frequency.

        Args:
            update (bool): Update if True or use local state if False, defaults to False

        Returns:
            int: Dial frequency in Hz
        '''
        freq = self._client.js8call.get_state('dial')

        if update or freq is None:
            msg = Message()
            msg.type = Message.RIG_GET_FREQ
            self._client.js8call.send(msg)
            freq = self._client.js8call.watch('dial')

        return freq

    def set_freq(self, freq):
        '''Set JS8Call dial frequency.

        Args:
            freq (int): Dial frequency in Hz

        Returns:
            int: Dial frequency in Hz
        '''
        msg = Message()
        msg.set('type', Message.RIG_SET_FREQ)
        msg.set('params', {'DIAL': freq, 'OFFSET': self._client.js8call.get_state('offset')})
        self._client.js8call.send(msg)
        time.sleep(self._client._set_get_delay)
        return self.get_freq(update = True)

    def get_band(self):
        '''Get frequency band designation.

        Returns:
            str: Band designator like \'40m\' or Client.OOB (out-of-band)
        '''
        return Client.freq_to_band(self.get_freq())

    def get_offset(self, update=False):
        '''Get JS8Call offset frequency.

        Args:
            update (bool): Update if True or use local state if False, defaults to False

        Returns:
            int: Offset frequency in Hz
        '''
        offset = self._client.js8call.get_state('offset')
        
        if update or offset is None:
            msg = Message()
            msg.type = Message.RIG_GET_FREQ
            self._client.js8call.send(msg)
            offset = self._client.js8call.watch('offset')

        return offset

    def set_offset(self, offset):
        '''Set JS8Call offset frequency.

        Args:
            offset (int): Offset frequency in Hz

        Returns:
            int: Offset frequency in Hz
        '''
        msg = Message()
        msg.set('type', Message.RIG_SET_FREQ)
        msg.set('params', {'DIAL': self._client.js8call.get_state('dial'), 'OFFSET': offset})
        self._client.js8call.send(msg)
        time.sleep(self._client._set_get_delay)
        return self.get_offset(update = True)

    def get_station_callsign(self, update=False):
        '''Get JS8Call callsign.

        Args:
            update (bool): Update if True or use local state if False, defaults to False

        Returns:
            str: JS8Call configured callsign
        '''
        callsign = self._client.js8call.get_state('callsign')

        if update or callsign is None:
            msg = Message()
            msg.type = Message.STATION_GET_CALLSIGN
            self._client.js8call.send(msg)
            callsign = self._client.js8call.watch('callsign')

        return callsign

    def set_station_callsign(self, callsign):
        '''Set JS8Call callsign.

        Callsign must be a maximum of 9 characters and contain at least one number.

        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.

        Args:
            callsign (str): Callsign to set

        Returns:
            str: JS8Call configured callsign
        '''
        callsign = callsign.upper()

        if len(callsign) <= 9 and any(char.isdigit() for char in callsign):
            return self._client.config.set('Configuration', 'MyCall', callsign)
        else:
            raise ValueError('callsign must be <= 9 characters in length and contain at least 1 number')

    def get_idle_timeout(self):
        '''Get JS8Call idle timeout.

        Returns:
            int: Idle timeout in minutes
        '''
        return self._client.config.get('Configuration', 'TxIdleWatchdog', value_type=int)

    def set_idle_timeout(self, timeout):
        '''Set JS8Call idle timeout.

        If the JS8Call idle timeout is between 1 and 5 minutes, JS8Call will force the idle timeout to 5 minutes on the next application start or exit.

        The maximum idle timeout is 1440 minutes (24 hours).

        Disable the idle timeout by setting it to 0 (zero).

        It is recommended that this function be called before calling *client.start()*. If this function is called after *client.start()* then the application will have to be restarted to utilize the new config file settings. See *client.restart()*.

        Args:
            timeout (int): Idle timeout in minutes

        Returns:
            int: Current idle timeout in minutes

        Raises:
            ValueError: Idle timeout must be between 0 and 1440 minutes
        '''
        if timeout < 0 or timeout > 1440:
            raise ValueError('Idle timeout must be between 0 and 1440 minutes')

        self._client.config.set('Configuration', 'TxIdleWatchdog', timeout)
        return self.get_idle_timeout()

    def get_distance_units_miles(self):
        '''Get JS8Call distance unit setting.
        
        Returns:
            bool: True if distance units are set to miles, False if km
        '''
        return self._client.config.get('Configuration', 'Miles', bool)
        
    def set_distance_units_miles(self, units_miles):
        '''Set JS8Call distance unit setting.
        
        Args:
            units_miles (bool): Set units to miles if True, set to km if False
            
        Returns:
            bool: True if distance units are set to miles, False if km
        '''
        self._client.config.set('Configuration', 'Miles', str(units_miles).lower())
        return self.get_distance_units_miles()
        
    def get_distance_units(self):
        '''Get JS8Call distance units.
        
        Returns:
            str: Configured distance units: 'mi' or 'km'
        '''
        if self.get_distance_units_miles():
            return 'mi'
        else:
            return 'km'
        
    def set_distance_units(self, units):
        ''' Set JS8Call distance units.
        
        Args:
            units (str): Distance units: 'mi', 'miles', 'km', or 'kilometers'
            
        Returns:
            str: Configured distance units: 'miles' or 'km'
        '''
        if units.lower() in ['mi', 'miles']:
            self.set_distance_units_miles(True)
            return self.get_distance_units()
        elif units.lower() in ['km', 'kilometers']:
            self.set_distance_units_miles(False)
            return self.get_distance_units()
        else:
            raise ValueError('Distance units must be: mi, miles, km, or kilometers')
    
    def get_station_grid(self, update=False):
        '''Get JS8Call grid square.

        Args:
            update (bool): Update if True or use local state if False, defaults to False

        Returns:
            str: JS8Call configured grid square
        '''
        grid = self._client.js8call.get_state('grid')

        if update or grid is None:
            msg = Message()
            msg.type = Message.STATION_GET_GRID
            self._client.js8call.send(msg)
            grid = self._client.js8call.watch('grid')

        return grid

    def set_station_grid(self, grid):
        '''Set JS8Call grid square.

        Args:
            grid (str): Grid square

        Returns:
            str: JS8Call configured grid square
        '''
        grid = grid.upper()
        msg = Message()
        msg.type = Message.STATION_SET_GRID
        msg.value = grid
        self._client.js8call.send(msg)
        time.sleep(self._client._set_get_delay)
        return self.get_station_grid(update = True)

    def get_station_info(self, update=False):
        '''Get JS8Call station information.

        Args:
            update (bool): Update if True or use local state if False, defaults to False

        Returns:
            str: JS8Call configured station information
        '''
        info = self._client.js8call.get_state('info')

        if update or info is None:
            msg = Message()
            msg.type = Message.STATION_GET_INFO
            self._client.js8call.send(msg)
            info = self._client.js8call.watch('info')

        return info

    def set_station_info(self, info):
        '''Set JS8Call station information.

        Args:
            info (str): Station information

        Returns:
            str: JS8Call configured station information
        '''
        msg = Message()
        msg.type = Message.STATION_SET_INFO
        msg.value = info
        self._client.js8call.send(msg)
        time.sleep(self._client._set_get_delay)
        return self.get_station_info(update = True)

    def append_pyjs8call_to_station_info(self):
        '''Append pyjs8call info to station info

        A string like ', PYJS8CALL V0.0.0' is appended to the current station info.
        Example: 'QRPLABS QDX, 40M DIPOLE 33FT, PYJS8CALL V0.2.2'

        If a string like ', PYJS8CALL' or ',PYJS8CALL' is found in the current station info, that substring (and everything after it) is dropped before appending the new pyjs8call info.

        Returns:
            str: JS8Call configured station information
        '''
        info = self.get_station_info().upper()
        
        if ', PYJS8CALL' in info:
            info = info.split(', PYJS8CALL')[0]
        elif ',PYJS8CALL' in info:
            info = info.split(',PYJS8CALL')[0]
            
        info = '{}, PYJS8CALL {}'.format(info, pyjs8call.__version__)
        return self.set_station_info(info)

    def get_bandwidth(self, speed=None):
        '''Get JS8Call signal bandwidth based on modem speed.

        Uses JS8Call configured speed if no speed is given.

        | Speed | Bandwidth |
        | -------- | -------- |
        | slow | 25 Hz |
        | normal | 50 Hz |
        | fast | 80 Hz |
        | turbo | 160 Hz |
        | ultra | 250 Hz |

        Args:
            speed (str): Speed setting, defaults to None

        Returns:
            int: Bandwidth of JS8Call signal
        '''
        if speed is None:
            speed = self.get_speed()
        elif isinstance(speed, int):
            speed = self.submode_to_speed(speed)

        bandwidths = {'slow':25, 'normal':50, 'fast':80, 'turbo':160, 'ultra':250}

        if speed in bandwidths:
            return bandwidths[speed]
        else:
            raise ValueError('Invalid speed \'' + speed + '\'')

    def get_window_duration(self, speed=None):
        '''Get JS8Call rx/tx window duration based on modem speed.

        Uses JS8Call configured speed if no speed is given.

        | Speed | Duration |
        | -------- | -------- |
        | slow | 30 seconds |
        | normal | 15 seconds |
        | fast | 10 seconds |
        | turbo | 6 seconds |
        | ultra | 4 seconds |

        Args:
            speed (str): Speed setting, defaults to None

        Returns:
            int: Duration of JS8Call rx/tx window in seconds
        '''
        if speed is None:
            speed = self.get_speed()
        elif isinstance(speed, int):
            speed = self.submode_to_speed(speed)

        duration = {'slow': 30, 'normal': 15, 'fast': 10, 'turbo': 6, 'ultra':4}
        return duration[speed]
    
