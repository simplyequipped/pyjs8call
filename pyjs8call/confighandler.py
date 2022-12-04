import os
import configparser

import pyjs8call

#TODO JS8Call requires callsign to contain at least one number, and max length is 9 characters

class ConfigHandler:
    def __init__(self, config_path=None):
        if config_path == None:
            self.path = os.path.join(os.path.expanduser('~'), '.config/JS8Call.ini')
        else:
            self.path = config_path

        if not os.path.exists(self.path):
            raise FileNotFoundError('JS8Call config file not found at ' + str(self.path))

        self.config = configparser.ConfigParser(interpolation = None)
        self.config.optionxform = lambda option: option
        self.config.read(self.path)

    def write(self, file_path=None):
        if file_path == None:
            file_path = self.path

        with open(file_path, 'w') as fd:
            self.config.write(fd, space_around_delimiters = False)

    def set(self, section, option, value):
        self.config.set(section, option, str(value))
        if isinstance(value, (str, int, float, bool)):
            return self.get(section, option, value_type=type(value))
        else:
            return None

    def get(self, section, option, value_type=str(), fallback=None):
        if isinstance(value_type, str):
            return self.config.get(section, option, fallback=fallback)
        elif isinstance(value_type, int):
            return self.config.getint(section, option, fallback=fallback)
        elif isinstance(value_type, float):
            return self.config.getfloat(section, option, fallback=fallback)
        elif isinstance(value_type, bool):
            return self.config.getboolean(section, option, fallback=fallback)

    def clear_call_activity(self):
        self.config.remove_section('CallActivity')

    def get_active_profile(self):
        return self.get('MultiSettings', 'CurrentName')

    def get_profile_list(self):
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
        if profile not in self.get_profile_list():
            raise Exception('Profile ' + profile + ' does not exist')

        option = profile + '\\' + section + '\\' + option
        section = 'MultiSettings'
        return self.get(section, option, value_type=value_type, fallback=fallback)
        
    def set_profile_option(self, profile, section, option, value):
        if profile not in self.get_profile_list():
            raise Exception('Profile ' + profile + ' does not exist')

        option = profile + '\\' + section + '\\' + option
        section = 'MultiSettings'
        return self.set(section, option, value)
        
    def change_profile(self, new_profile):
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
        if copy_profile not in self.get_profile_list():
            #TODO more specific exception
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
        if profile not in self.get_profile_list():
            raise Exception('Profile ' + profile + ' does not exist')

        profile_options = self.get_profile_options(profile)

        for section in profile_options.keys():
            for option in profile_options[section].keys():
                profile_option = profile + '\\' + section + '\\' + option
                self.config.remove_option('MultiSettings', profile_option)

    def get_groups(self):
        groups = self.config.get('Configuration', 'MyGroups')
        groups = groups.split(',')
        # strip spaces, ensure a single @ symbol
        groups = ['@' + group.strip(' @') for group in groups if len(group.strip()) > 0]
        
        return groups

    def add_group(self, group):
        # strip spaces, ensure a single @ symbol
        group = '@' + group.strip(' @')

        if group not in self.get_groups():
            groups = self.config.get('Configuration', 'MyGroups')
            # add second @ symbol to match config file formatting
            groups += ', @' + group
            self.config.set('Configuration', 'MyGroups', groups)

    def remove_group(self, group):
        # strip spaces, ensure a single @ symbol
        remove_group = '@' + group.strip(' @')
        groups = self.get_groups()

        if remove_group in groups:
            # add second @ symbol to match config file formatting
            groups = ['@' + group for group in groups if group != remove_group]
            groups = ', '.join(groups)
            self.config.set('Configuration', 'MyGroups', groups)

