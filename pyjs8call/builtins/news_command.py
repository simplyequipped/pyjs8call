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

'''Custom news content command handling'''

__docformat__ = 'google'


import os
import configparser

from pyjs8call import CustomCommand


class NewsCommand(CustomCommand):
    '''Custom command for sharing news content.

    Note that only messages directed to the local station will be handled, and only if a callsign is *not* selected in the JS8Call application (active directed chat).
    
    Example JS8Call message requesting news:
    ```
    ORIGIN:DEST NEWS?
    ```

    The news file path can be configured in the settings file under the *misc* section:
    ```
    [misc]
    news_path=/path/to/news.txt
    ```
    
    Alternatively, set the PYJS8CALL_NEWS_PATH environment variable. If neither is configured, the default path of ~/.pyjs8call/news.txt will be used.
    '''
    command = ' NEWS?'
    
    def process(self, pyjs8call_client, msg):
        '''News command processing and response.

        Args:
            pyjs8call_client (pyjs8call.client.Client): client object for interfacing with application (ex. sending response message)
            msg (pyjs8call.message.Message): received message object containing custom command
        '''
        # ignore if a callsign is selected on the js8call ui
        if pyjs8call_client.get_selected_call() is not None:
            return
        
        # only respond if message is directed to local station
        if not msg.is_directed_to(pyjs8call_client.settings.get_station_callsign()):
            return
        
        try:
            # get news file path
            news_path = None
            
            # try loading from pyjs8call config file
            if pyjs8call_client.settings.loaded_settings:
                try:
                    news_path = pyjs8call_client.settings.loaded_settings.get('misc', 'news_path')
                except (configparser.NoSectionError, configparser.NoOptionError):
                    pass
            
            # if not loaded from config file, try loading from env variable
            if not news_path:
                news_path = os.getenv('PYJS8CALL_NEWS_PATH')
            
            # if no path set, use default
            if not news_path:
                news_path = os.path.expanduser('~/.pyjs8call/news.txt')
            
            # ignore if news content file not found
            if not os.path.exists(news_path):
                return
            
            with open(news_path, 'r', encoding='utf-8') as f:
                news_content = f.read().strip()
            
            if news_content:
                pyjs8call_client.send_directed_message(msg.origin, news_content)

        except Exception:
            # ignore file read errors
            return

