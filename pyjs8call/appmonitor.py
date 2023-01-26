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

'''Manage start and stop of the JS8Call application.

This module is initialized by pyjs8call.client via pyjs8call.js8call.

To run JS8Call headless on Linux xvfb must be installed. On Debian systems try:
`sudo apt install xvfb`
'''

__docformat__ = 'google'


import time
import threading
import subprocess


class AppMonitor:
    '''JS8Call application monitor.

    Attributes:
        headless (bool): Run JS8Call headless using xvfb (linux only, requies xvfb to be installed), defaults to False
        running (bool): Whether the JS8Call application is running
        restart (bool): Whether to restart the JS8Call application if it stops, defaults to True
    '''

    def __init__(self, owner, client):
        '''Initialize JS8Call application monitor.

        Args:
            owner (pyjs8call.js8call): The parent js8call object
            client (pyjs8call.client): The parent client object

        Returns:
            pyjs8call.appmonitor.AppMonitor: Constructed application monitor object

        Raises:
            ProcessLookupError: JS8Call is not installed
            ProcessLookupError: Application run headless and xvfb is not installed
            RuntimeError: JS8Call application failed to start
        '''
        self._exec_path = None
        self._process = None
        self.headless = False
        self.running = False
        self.restart = True
        self._owner = owner
        self._client = client
        self._thread = None

        try:
            self._exec_path = subprocess.check_output(['which', 'js8call']).decode('utf-8').strip()
        except subprocess.CalledProcessError as e:
            raise ProcessLookupError('JS8Call application not installed') from e

    def start(self, headless=False):
        cmd = [self._exec_path]

        if headless:
            try:
                subprocess.check_output(['which', 'xvfb-run'])
            except subprocess.CalledProcessError as e:
                raise ProcessLookupError('Cannot run headless since xvfb-run is not installed, on Debian systems try: sudo apt install xvfb') from e

            self.headless = True
            cmd.insert(0, 'xvfb-run')
            cmd.insert(1, '-a')

        if not self.is_running():
            self._process = subprocess.Popen(cmd, stderr=subprocess.DEVNULL)

        # wait for connection to application via socket
        timeout = time.time() + 60
        while True:
            try:
                # this will error if unable to connect to the application
                self._owner.connect()
                # no errors, must be connected
                self.running = True
                break
            except ConnectionRefusedError:
                pass

            if time.time() > timeout:
                break

            time.sleep(0.1)

        # start the application monitoring thread
        if self.running and self._thread is None:
            self._thread = threading.Thread(target=self._monitor)
            self._thread.daemon = True
            self._thread.start()

        elif not self.running:
            raise RuntimeError('JS8Call application failed to start')

    def is_running(self):
        '''Whether the JS8Call application is running.

        If JS8Call was started before pyjs8call then *pgrep js8call* is used.

        If JS8Call was started by pyjs8call (via subprocess) then *subprocess.poll()* is used.

        Returns:
            bool: True if the application is running, False otherwise
        '''
        # handle process started externally
        if self._process is None:
            try:
                # errors due to non-zero return code if no running instances
                subprocess.check_output(['pgrep', 'js8call'])
                # if no error then the process is running
                running = True
            except subprocess.CalledProcessError:
                running = False

        # handle process started by self
        else:
            # returns None when running
            code = self._process.poll()

            if code is None:
                running = True
            else:
                running = False

        self.running = running
        return running

    def stop(self):
        '''Stop the JS8Call application.

        If JS8Call was started before pyjs8call it cannot be stopped by pyjs8call.

        If JS8Call was started by pyjs8call the following steps are taken in order:
            - *subprocess.terminate()* followed by *subprocess.wait(timeout = 2)*
            - *subprocess.kill()*
            - *pgrep js8call* followed by *killall -9 js8call* if running

        Returns:
            The return code of the terminated/killed subprocess or None if no return code was given.
        '''
        if self._process is None:
            return None

        code = None
        self._process.terminate()

        try:
            code = self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass

        if code is None:
            self._process.kill()

        try:
            # errors due to non-zero return code if no running instances
            subprocess.check_output(['pgrep', 'js8call'], stderr = subprocess.DEVNULL)
            # if no error then the process is running, force kill process
            subprocess.run(['killall', '-9', 'js8call'], check = True, stderr = subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            pass

        return code

    def _monitor(self):
        '''Application monitoring thread.'''
        while self._owner.online:
            if not self.is_running() and self.restart:
                # restart the whole system and reconnect
                self._client.restart()
            time.sleep(2)

