# MIT License
# 
# Copyright (c) 2022-2025 Simply Equipped
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

'''Custom JS8Call command loading and processing, and base class for custom commands.

Custom commands are to be a subclasses of the *CustomCommand* base class defined in this module, and are to be separate Python packages with a *pyjs8call.commands* entry point group pointing to the command subclass. Note that *pyjs8call* entry point commands cannot be run directly from the CLI like a typical entry point, as they are referenced and loaded internally.

Example base class import and subclass structure:
```
from pyjs8call import CustomCommand

class NewCommand(CustomCommand):
  command=' CMD' # note leading space

  def process(self, pyjs8call_client, msg):
    # command processing here
    pyjs8call_client.send_directed_message(msg.origin, value='cmd response')
```

Example setup.py entry point structure for a custom command package:
```
setup(
  ...,
  entry_points={
    'pyjs8call.commands': [
      'any_descriptive_name = package.module.import.path:CommandSubclass'
    ]
  }
)
```
Once a package with an appropriate entry point is installed, *pyjs8call* will discover the command when the application is launched and handle custom command processing automatically.
'''

__docformat__ = 'google'


import importlib.metadata


class CustomCommand:
    '''Base class for all custom JS8Call commands'''

    command = None
    '''Override with JS8Call command string, including a leading space'''

    def __init_subclass__(cls, **kwargs):
        '''Property checks on subclass initialization'''
        super().__init_subclass__(**kwargs)
        
        if cls.command is None:
            raise TypeError(cls.__name__ + '.command must be type str')
        if not cls.command.startswith(' '):
            raise ValueError(cls.__name__ + '.command missing required leading space')

    def process(self, pyjs8call_client, msg):
        '''Custom command processing logic.
        
        This function in the subclass will be registered as a callback function for the command using *pyjs8call.callbacks*.

        Args:
            pyjs8call_client (pyjs8call.client.Client): client object for interfacing with application (ex. sending response message)
            msg (pyjs8call.message.Message): received message object containing custom command
        '''
        pass
                

class Commands:
    '''Custom command registration and processing.'''
    
    def __init__(self, client):
        ''''''
        self.client = client
        self.commands = {}

    def get_command(self, command):
        if command in self.commands:
            return self.commands[command]

    def set_command(self, command, command_class, replace_existing=False):
        if command in self.commands and not replace_existing:
            raise NameError('Custom command "' + command + '" already exists')
            
        if issubclass(command_class, CustomCommand):
            self.commands[command] = command_class() # custom command subclass instance
            self.client.callback.register_command(command, self.process)

    def load(self):
        ''''''
        entry_points = importlib.metadata.entry_points(group='pyjs8call.commands')
        
        for ep in entry_points:
            try:
                command_class = ep.load()
                self.set_command(command_class.command, command_class)
            except Exception as e:
                print('Failed to load custom command: ' + e)

    def process(self, msg):
        '''Process custom command message.
        
        Args:
            msg (pyjs8call.message.Message): message object to process
        '''
        if msg.cmd in self.commands:
            # pass client object to provide access for sending a response message
            self.commands[msg.cmd].process(self.client, msg)
