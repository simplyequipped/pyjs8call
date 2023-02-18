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
import signal
import shutil

import psutil


class AppMonitor:
    '''JS8Call application monitor.

    Attributes:
        headless (bool): Whether JS8Call is running headless using xvfb (see *start()*)
        restart (bool): Whether to restart the JS8Call application if it stops, defaults to True
    '''

    def __init__(self, parent):
        '''Initialize JS8Call application monitor.

        Args:
            parent (pyjs8call.js8call): The parent js8call object

        Returns:
            pyjs8call.appmonitor.AppMonitor: Constructed application monitor object
        '''
        self._parent = parent
        self._xvfb_proc = None
        self._js8call_proc = None
        self.headless = False
        self.restart = True

    def start(self, headless=False):
        ''' Start JS8Call application.

        Args:
            headless (bool): Run JS8Call headless using xvfb (Linux only, requires xvfb to be installed), defaults to False

        Raises:
            RuntimeError: JS8Call is not installed
            RuntimeError: Cannot run headless on Windows, xvfb-run is not supported
            RuntimeError: Application run headless on Linux and xvfb is not installed
            RuntimeError: JS8Call application failed to start
        '''
        js8call_exec_path = shutil.which('js8call')

        if js8call_exec_path is None:
            raise RuntimeError('JS8Call application not installed')

        if headless:
            if psutil.WINDOWS:
                raise RuntimeError('Cannot run headless on Windows, xvfb-run is not supported')
            elif shutil.which('xvfb-run') is None:
                raise RuntimeError('Cannot run headless since xvfb-run is not installed, on Debian systems try: sudo apt install xvfb')
            
            self._find_running_xvfb_process()

            if self._xvfb_proc is None:
                self._xvfb_proc = psutil.Popen(['xvfb-run', '-a', js8call_exec_path], stderr=signal.DEVNULL)

                for child in self._xvfb_proc:
                    if child.name().lower() = 'js8call'
                        self._js8call_proc = child


        
        else:
        # get process if application already running
        if self.is_running():
            self._process = [proc for proc in psutil.process_iter(['name']) if proc.info['name'].lower() == 'js8call'][-1]  
        # start process if application not running
        else:
            self._process = psutil.Popen(cmd, stderr=signal.DEVNULL)

        # wait for connection to application via socket
        timeout = time.time() + 60

        while True:
            # don't call parent.connect() if already connected
            if self._parent.connected:
                break

            try:
                # this will error if unable to connect to the application
                self._parent.connect()
                # no errors, must be connected
                break
            except ConnectionRefusedError:
                pass

            if time.time() > timeout:
                break

            time.sleep(0.1)

        if self.is_running():
            thread = threading.Thread(target=self._monitor)
            thread.daemon = True
            thread.start()
        else:
            raise RuntimeError('JS8Call application failed to start')

        self.headless = headless


    def _find_running_xvfb_process(self):
        '''Find running xvfb process and child JS8Call process.'''
        xvfb_proc = [proc for proc in psutil.process_iter(['name']) if proc.info['name'].lower() == 'xvfb-run']

        # check xvfb child processes for js8call process
        for proc in xvfb_proc:
            for child in proc.children:
                if child.name().lower() == 'js8call':
                    # js8call found
                    self._xvfb_proc = proc
                    self._js8call_proc = child
                    return

    def _find_running_js8call_process(self):
        '''Find running JS8Call process.'''
        js8call_proc = [proc for proc in psutil.process_iter(['name']) if proc.info['name'].lower() == 'js8call']

        if len(js8call_proc) > 0:
            self._js8call_proc = js8call_proc[-1]

    def is_running(self):
        '''Whether the JS8Call application is running.

        Returns:
            bool: True if the application is running, False otherwise
        '''
        if self._process is None:
            return False

        return self._process.is_running()

    def stop(self):
        '''Stop the JS8Call application.

        On Unix systems SIGTERM is sent to the process first. If the processs is still running SIGKILL is sent.

        On Windows systems only SIGKILL is sent.
        '''
        if not self.is_running():
            return

        self._process.terminate()

        try:
            self._process.wait(timeout = 2)
        except psutil.TimeoutExpired:
            self._process.kill()

    def _monitor(self):
        '''Application monitoring thread.'''
        while self._parent.online:
            if not self.is_running() and self.restart:
                # restart the whole system and reconnect
                self._parent._client.restart()

            time.sleep(2)

