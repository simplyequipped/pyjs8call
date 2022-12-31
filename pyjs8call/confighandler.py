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

'''Read from and write to the JS8Call.ini config file.

This module is initialized by pyjs8call.client.

See the JS8Call.ini config file (located at ~/.config/JS8Call.ini on linux systems) for section titles and options. Pay special attention to option spelling and capitalization. Configuring options incorrectly may cause the JS8Call application not to start.

Note that JS8Call will need to be restarted to implement changes made while JS8Call is running.

Typical usage example:

    ```
    js8call.config.get_profile_list()
    js8call.config.create_new_profile('AppName')
    js8call.config.change_profile('AppName')
    js8call.config.get_active_profile()

    js8call.config.change_profile('Default')
    js8call.set('Configuration', 'AvoidAllcall', 'true')
    js8call.config.set_profile_option('AppName', 'Configuration', 'Miles', 'true')
    ```
'''

__docformat__ = 'google'


import os
import shutil
import configparser

# Note: Callsign (Configuration > MyCall) required to contain at least one number and have a max length of 9 characters

class ConfigHandler:
    '''JS8Call.ini configuration file handler.

    Attributes:
        path (str): File path to the JS8Call config file, defaults to *~/.config/JS8Call.ini*
        config (configparser.ConfigParser): Config parser object containing config file data
    '''
    def __init__(self, config_path=None):
        '''Initialize JS8Call config handler.

        Args:
            config_path (str): Alternate config file path, defaults to None

        Raises:
            FileNotFoundError: Config file not found at specified path
        '''
        if config_path == None:
            self.path = os.path.join(os.path.expanduser('~'), '.config/JS8Call.ini')
        else:
            self.path = config_path

        if not os.path.exists(self.path):
            raise FileNotFoundError('JS8Call config file not found at ' + str(self.path))

        self.config = configparser.ConfigParser(interpolation = None)
        self.config.optionxform = lambda option: option
        self.config.read(self.path)

    def write(self):
        '''Write the config parser object to file.

        A backup of the original JS8Call config file is saved as JS8Call.ini.original in the same directory as the JS8Call.ini file.
        '''
        if not os.path.exists(self.path + '.original'):
            # create a backup of the original config file before writing changes
            with open(self.path + '.original', 'w') as fd:
                self.config.write(fd, space_around_delimiters = False)

        with open(self.path, 'w') as fd:
            # write current config object to the config file
            self.config.write(fd, space_around_delimiters = False)

    def set(self, section, option, value):
        '''Set an option value in a given section.

        Value can be of the following types:
            - str
            - int
            - float
            - bool

        Note that config file boolean types are the lower case strings 'true' and 'false'.

        Args:
            section (str): Section name containing the specified option
            option (str): Option name to set value for
            value (str, int, float, bool): Option value to set

        Returns:
            str: Value of the specified option in the specified section, or None if value is a type other than those listed above

        Raises:
            RuntimeError: JS8Call onfig file does not contain a 'Configuration' section, likely because JS8Call has not be run before using pyjs8call
        '''
        try:
            self.config.set(section, option, str(value))
        except configparser.NoSectionError as e:
            if section == 'Configuration':
                raise RuntimeError('JS8Call config file section \'Configuration\' does not exist, try running and configuring the JS8Call application normally before attempting to use pyjs8call') from e
            else:
                raise e

        if isinstance(value, (str, int, float, bool)):
            return self.get(section, option, value_type=type(value))
        else:
            return None

    def get(self, section, option, value_type=str(), fallback=None):
        '''Get an option value from a given section.

        Values can be of the following types:
            - str
            - int
            - float
            - bool

        Args:
            section (str): Section name containing the specified option
            option (str): Option name to get value for
            value_type (str, int, float, bool): A variable or constructor function of the same type as the value to be returned
            fallback (any): The value to be returned if the given option is not found, defaults to None

        Returns:
            The value of the specified option in the specified section as the specified type, or the fallback value if the option is not found.
        '''
        if isinstance(value_type, str):
            return self.config.get(section, option, fallback=fallback)
        elif isinstance(value_type, int):
            return self.config.getint(section, option, fallback=fallback)
        elif isinstance(value_type, float):
            return self.config.getfloat(section, option, fallback=fallback)
        elif isinstance(value_type, bool):
            return self.config.getboolean(section, option, fallback=fallback)

    def clear_call_activity(self):
        '''Clear JS8Call call activity.

        This removes the section *CallActivity* from the config file.
        '''
        self.config.remove_section('CallActivity')

    def get_active_profile(self):
        '''Get active JS8Call configuration profile.

        Returns:
            str: Name of active configuration profile
        '''
        return self.get('MultiSettings', 'CurrentName')

    def get_profile_list(self):
        '''Get list of existing JS8Call configuration profiles.

        Returns:
            list: List of profiles in the configuration file
        '''
        profiles = []
        profiles.append(self.get_active_profile())

        for option in self.config.options('MultiSettings'):
            option_parts = option.split('\\')

            if len(option_parts) == 1:
                continue

            profile_name = option_parts[0]

            if profile_name not in profiles:
                profiles.append(profile_name)

        return profiles

    def get_profile_options(self, profile):
        '''Get all options and values for a configuration profile.

        Args:
            profile (str): The name of the configuration profile to get options and values for

        Returns:
            A dictionary of the following structure:
                dict[section][option] = value
        '''
        if profile not in self.get_profile_list():
            raise Exception('Profile ' + profile + ' does not exist')

        options = {}

        for option, value in self.config.items('MultiSettings'):
            option_parts = option.split('\\')

            if len(option_parts) == 1:
                continue

            profile_name = option_parts[0]
            profile_section = option_parts[1]

            if len(option_parts) > 3:
                profile_option = '\\'.join(option_parts[2:])
            else:
                profile_option = option_parts[2]

            if profile_name == profile:
                if profile_section not in options.keys():
                    options[profile_section] = {}

                options[profile_section][profile_option] = value

        return options

    def get_profile_option(self, profile, section, option, value_type=str(), fallback=None):
        '''Get an option value from a given section in a given profile.

        Values can be of the following types:
            - str
            - int
            - float
            - bool

        Args:
            profile (str): Profile name containing the the specified section and option
            section (str): Section name containing the specified option
            option (str): Option name to get value for
            value_type (str, int, float, bool): A variable or constructor function of the same type as the value to be returned
            fallback (any): The value to be returned if the given option is not found, defaults to None

        Returns:
            The value of the specified option in the specified section in the specified profile as the specified type, or the fallback value if the option is not found.
        '''
        if profile not in self.get_profile_list():
            raise Exception('Profile ' + profile + ' does not exist')

        option = profile + '\\' + section + '\\' + option
        section = 'MultiSettings'
        return self.get(section, option, value_type=value_type, fallback=fallback)
        
    def set_profile_option(self, profile, section, option, value):
        '''Set an option value in a given section of a given profile.

        Value can be of the following types:
            - str
            - int
            - float
            - bool

        Note that config file boolean types are the lower case strings 'true' and 'false'.

        Args:
            profile (str): Profile name containing the specified section and option
            section (str): Section name containing the specified option
            option (str): Option name to set value for
            value (str, int, float, bool): Option value to set

        Returns:
            str: Value of the specified option in the specified section of the specified profile, or None if value is a type other than those listed above
        '''
        if profile not in self.get_profile_list():
            raise Exception('Profile ' + profile + ' does not exist')

        option = profile + '\\' + section + '\\' + option
        section = 'MultiSettings'
        return self.set(section, option, value)
        
    def change_profile(self, new_profile):
        '''Change JS8Call active configuration profile.

        Args:
            new_profile (str): Name of the profile to change to

        Raises:
            Exception: Specified profile does not exist
        '''
        if new_profile not in self.get_profile_list():
            raise Exception('Profile ' + new_profile + ' does not exist')

        active_profile = self.get_active_profile()
        new_profile_options = self.get_profile_options(new_profile)

        for section in self.config.sections():
            if section == 'MultiSettings':
                continue

            for option, value in self.config.items(section):
                # save setting from currently active profile
                active_profile_option = active_profile + '\\' + section + '\\' + option
                self.config.set('MultiSettings', active_profile_option, value)

                # set new setting from newly selected profile
                new_value = self.get_profile_option(new_profile, section, option)
                self.config.set(section, option, str(new_value))
                
                # remove newly selected profile multisettings
                new_profile_option = new_profile + '\\' + section + '\\' + option
                self.config.remove_option('MultiSettings', new_profile_option)

        self.set('MultiSettings', 'CurrentName', new_profile)

    def create_new_profile(self, new_profile, copy_profile='Default'):
        '''Create new JS8Call configuration profile.

        Args:
            new_profile (str): Name of new profile to create
            copy_profile (str): Name of an existing profile to copy when creating the new profile

        Raises:
            Exception: Specified profile to be copied does not exist
        '''
        if copy_profile not in self.get_profile_list():
            raise Exception('Profile ' + copy_profile + ' cannot be copied because it does not exist')

        active_profile = self.get_active_profile()

        # if copying from the active profile
        if copy_profile == active_profile:
            for section in self.config.sections():
                if section == 'MultiSettings':
                    continue

                for option, value in self.config.items(section):
                    new_profile_option = new_profile + '\\' + section + '\\' + option
                    self.config.set('MultiSettings', new_profile_option, str(value))

        # if copying from an inactive profile
        else:
            profile_options = self.get_profile_options(copy_profile)

            for section in profile_optoins.keys():
                for option, value in profile_options.items():
                    new_profile_option = new_profile + '\\' + section + '\\' + option
                    self.config.set('MultiSettings', new_profile_option, str(value))

    def remove_profile(self, profile):
        '''Remove an existing JS8Call configuration profile.

        Args:
            profile (str): Name of existing configuration profile to remove

        Raises:
            Exception: Specified profile does not exist
        '''
        if profile not in self.get_profile_list():
            raise Exception('Profile ' + profile + ' does not exist')

        profile_options = self.get_profile_options(profile)

        for section in profile_options.keys():
            for option in profile_options[section].keys():
                profile_option = profile + '\\' + section + '\\' + option
                self.config.remove_option('MultiSettings', profile_option)

    def get_groups(self):
        '''Get list of JS8Call callsign groups.

        Returns:
            list: List of callsign groups
        '''
        groups = self.config.get('Configuration', 'MyGroups')
        groups = groups.split(',')
        # strip spaces, ensure a single @ symbol
        groups = ['@' + group.strip(' @') for group in groups if len(group.strip()) > 0]
        
        return groups

    def add_group(self, group):
        '''Add a new JS8Call callsign group.

        Args:
            group (str): Name of the callsign group to create
        '''
        # strip spaces, ensure a single @ symbol
        group = '@' + group.strip(' @')

        if group not in self.get_groups():
            groups = self.config.get('Configuration', 'MyGroups')
            # add second @ symbol to match config file formatting
            groups += ', @' + group
            self.config.set('Configuration', 'MyGroups', groups)

    def remove_group(self, group):
        '''Remove an existing JS8Call callsign group.

        Args:
            group (str): Name of the callsign group to remove
        '''
        # strip spaces, ensure a single @ symbol
        remove_group = '@' + group.strip(' @')
        groups = self.get_groups()

        if remove_group in groups:
            # add second @ symbol to match config file formatting
            groups = ['@' + group for group in groups if group != remove_group]
            groups = ', '.join(groups)
            self.config.set('Configuration', 'MyGroups', groups)

