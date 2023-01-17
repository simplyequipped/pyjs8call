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

'''Monitor band activity.'''

__docformat__ = 'google'


import time
import threading

from pyjs8call import Message


#TODO does offset move a couple Hz over rx cycles, or is it stable?

class ActivityMonitor:
    '''Monitor band activity.
    
    Attributes:
        max_activity_length (int): Maximum number of characters maintained per offset, defaults to 1024
        stale_age (int): Age of stale activity in minutes, defaults to 5
    '''
    def __init__(self, client):
        '''Initialize activity monitor object.

        Args:
            client (pyjs8call.client): Parent client object

        Returns:
            pyjs8call.activitymonitor: Constructed activity monitor object
        '''
        self._client = client
        self._enabled = False
        self._activity = {}
        self._messages = {}
        self._activity_lock = threading.Lock()
        self.max_activity_length = 1024
        self.max_age = 5 # minutes

    def enable(self):
        '''Enable activity monitoring.
        '''
        if self._enabled:
            return

        self._enabled = True
        self._client.callback.register_incoming(self.process_new_activity, message_type = Message.RX_ACTIVITY)

        thread = threading.Thread(target=self._monitor)
        thread.daemon = True
        thread.start()

    def disable(self):
        '''Disable activity monitoring.'''
        self._enabled = False
        self._client.callback.remove_incoming(self.process_new_activity)

    def process_new_activity(self, msg):
        '''Process new band activity.
        
        Args:
            msg (pyjs8call.message): Received message object
        '''
        with self._activity_lock:
            if msg.offset in self._activity:
                self._activity[msg.offset]['activity'] += msg.value
                self._activity[msg.offset]['updated'] = time.time()
            else:
                self._activity[msg.offset] = {'activity': msg.value, 'updated': time.time()}
                
            if len(self._activity[msg.offset]['activity']) > self.max_activity_length:
                # maintain max activity length
                start = len(self._activity[msg.offset]['activity']) - self.max_activity_length
                self._activity[msg.offset]['activity'] = self._activity[msg.offset]['activity'][start:]
    
    def _callback(self, activity):
        '''New activity callback function handling.
        
        Args:
            activity (dict): New activity information from monitoring thread
        
        Calls the *pyjs8call.client.callback.activity* callback function using *threading.Thread*.
        '''
        if self._client.callback.activity is not None:
            thread = threading.Thread(target = self._client.callback.activity, args=(activity,))
            thread.daemon = True
            thread.start()
        
    def _monitor(self):
        '''Activity monitor thread.'''
        last_activity = self._activity.copy()
            
        while self._enabled:
            default_delay = self._client.get_tx_window_duration() / 2
            delay = self._client.window_monitor.next_transition_seconds(count = 1, fallback = default_delay)
            time.sleep(delay)
            
            with self._activity_lock:
                if self._activity == last_activity:
                    continue
                
                for offset, activity in self._activity.items():
                    activity = activity['activity']
                    
                    if offset not in last_activity:
                        new_activity = activity
                    elif activity != last_activity[offset]:
                        new_activity = activity[len(last_activity[offset]['activity']):]
                    else:
                        new_activity = False
                        
                    if new_activity:
                        self._callback({'offset': offset, 'all': activity, 'new': new_activity})
                    elif self._activity[offset]['updated'] + (self.max_age * 60) < time.time():
                        # cull old activity
                        del self._activity[offset]
            
                last_activity = self._activity.copy()
