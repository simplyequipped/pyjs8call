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
'''

__docformat__ = 'google'


import time
import threading
import shutil
import subprocess

import psutil


class AppMonitor:
    '''JS8Call application monitor.

    If the JS8Call application is closed and *restart* is *False*, pyjs8call will exit. If *restart* is *True* pyjs8call will continue to run and JS8Call will be restarted.



    Attributes:
        headless (bool): Whether JS8Call is running headless using xvfb (see *start()*)
        args (list): Sequence of command line arguments to be passed to JS8Call, defaults to empty list
        restart (bool): Whether to restart the JS8Call application if it stops, defaults to False
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
        self.args = []
        self.restart = False

    def start(self, headless=False, args=None):
        ''' Start JS8Call application.

        See the subprocess.Popen *args* parameter documentation for information on how to break command line arguments into a sequence. The *js8call* command does not need to be included, only additional arguments. For example, passing `['--rig-name', 'FT857']` as the *args* parameter results in `js8call --rig-name FT857` being called to start the JS8Call application. Note that *args* only applies if JS8Call is started by pyjs8call.

        Args:
            headless (bool): Run JS8Call headless using xvfb (Linux only, requires xvfb to be installed), defaults to False
            args (list): Sequence of command line arguments to be passed to JS8Call, defaults to None

        Raises:
            RuntimeError: JS8Call is not installed
            RuntimeError: Cannot run headless on Windows, xvfb is not supported
            RuntimeError: Attempting to run application headless and xvfb not installed
            RuntimeError: JS8Call application failed to start
        '''
        if self.is_running():
            return

        if args is None:
            self.args = []
        else:
            self.args = args

        if headless:
            self._start_xvfb()
        else:
            self._start_js8call()

        time.sleep(1)

    def start_time(self):
        '''Get JS8Call process creation timestamp.

        Returns:
            float: Timestamp of JS8Call process creation, or 0 (zero) if process is None
        '''
        if self._js8call_proc is None:
            return 0

        return self._js8call_proc.create_time()

    def run_time(self):
        '''Get JS8Call process run time.

        Returns:
            float: JS8Call process run time in seconds
        '''
        start_time = self.start_time()

        if start_time == 0:
            return 0
        else:
            return time.time() - start_time

    def is_running(self):
        '''Whether the JS8Call application is running.

        Returns:
            bool: True if the JS8Call application is running, False otherwise
        '''
        try:
            if self._js8call_proc is None:
                return False
            elif self._js8call_proc.status() == psutil.STATUS_ZOMBIE:
                return False

            return self._js8call_proc.is_running()

        except psutil.NoSuchProcess:
            return False

    def stop(self):
        '''Stop the JS8Call application.

        On Unix systems SIGTERM is sent to the process first. If the processs is still running SIGKILL is sent.

        On Windows systems only SIGKILL is sent.
        '''
        if not self.is_running():
            return

        self._js8call_proc.terminate()

        try:
            self._js8call_proc.wait(timeout = 2)
        except psutil.TimeoutExpired:
            self._js8call_proc.kill()

        # remove zombie process when running headless
        if self._xvfb_proc is not None:
            try:
                self._xvfb_proc.wait(timeout = 2)
            except psutil.TimeoutExpired:
                pass

    def _start_xvfb(self):
        '''Start JS8Call application headless via xvfb.
        
        Raises:
            RuntimeError: Cannot run headless on Windows, xvfb is not supported
            RuntimeError: Attempting to run application headless and xvfb not installed
            RuntimeError: JS8Call application not installed
            RuntimeError: JS8Call application failed to start
        '''
        xvfb_exec_path = shutil.which('xvfb-run')
        js8call_exec_path = shutil.which('js8call')

        if psutil.WINDOWS:
            raise RuntimeError('Cannot run headless on Windows, xvfb is not supported')
        if xvfb_exec_path is None:
            raise RuntimeError('Cannot run headless without xvfb installed, on Debian systems try: sudo apt install xvfb')
        if js8call_exec_path is None:
            raise RuntimeError('JS8Call application not installed')

        if self.args == []:
            # check if js8call already running via xvfb
            self._find_running_xvfb_process()

        # proc not set if not already running
        if self._xvfb_proc is None:
            exec_path = [xvfb_exec_path, '-a', js8call_exec_path]
            exec_path.extend(self.args)

            self._xvfb_proc = psutil.Popen(exec_path, stderr = subprocess.DEVNULL)
        
        # wait until socket connected or timeout
        if self._socket_connected():
            # find js8call child process under xvfb
            for child in self._xvfb_proc.children():
                if child.name().lower() == 'js8call':
                    self._js8call_proc = child

            # start js8call monitoring thread
            thread = threading.Thread(target=self._monitor)
            thread.daemon = True
            thread.start()
        else:
            raise RuntimeError('JS8Call application failed to start')
            
        self.headless = True

    def _start_js8call(self):
        '''Start JS8Call application.
        
        Raises:
            RuntimeError: JS8Call application not installed
            RuntimeError: JS8Call application failed to start
        '''
        js8call_exec_path = shutil.which('js8call')

        if js8call_exec_path is None:
            raise RuntimeError('JS8Call application not installed')

        if self.args == []:
            # check if js8call already running
            self._find_running_js8call_process()

        # proc not set if not already running
        if self._js8call_proc is None:
            exec_path = [js8call_exec_path]
            exec_path.extend(self.args)

            self._js8call_proc = psutil.Popen(exec_path, stderr = subprocess.DEVNULL)

        # wait until socket connected or timeout
        if self._socket_connected():
            # start js8call monitoring thread
            thread = threading.Thread(target=self._monitor)
            thread.daemon = True
            thread.start()
        else:
            raise RuntimeError('JS8Call application failed to start')

    def _socket_connected(self, timeout=120):
        '''Wait for JS8Call socket connection after starting application.
        
        Args:
            timeout (int): Number of seconds to wait for connection, defaults to 120
            
        Returns:
            bool: True if socket connected, False otherwise
        '''
        if self._parent.connected:
            return True

        timeout += time.time()

        while True:
            try:
                # connection refused error if unable to connect
                self._parent.connect()
                # no errors, socket connected
                return True
            except ConnectionRefusedError:
                pass

            if time.time() > timeout:
                break

            time.sleep(0.1)

        return False

    def _find_running_xvfb_process(self):
        '''Find running xvfb process and child JS8Call process.'''
        xvfb_procs = [proc for proc in psutil.process_iter(['name']) if proc.info['name'].lower() == 'xvfb-run']

        # check xvfb child processes for js8call process
        for proc in xvfb_procs:
            if proc.status() == psutil.STATUS_ZOMBIE:
                continue
                
            for child in proc.children():
                if child.name().lower() == 'js8call':
                    # js8call found
                    self._xvfb_proc = proc
                    self._js8call_proc = child
                    return

    def _find_running_js8call_process(self):
        '''Find running JS8Call process.'''
        js8call_procs = [proc for proc in psutil.process_iter(['name']) if proc.info['name'].lower() == 'js8call']
        
        for proc in js8call_procs:
            if proc.status() == psutil.STATUS_ZOMBIE:
                continue
                
            self._js8call_proc = proc
            return

    def _monitor(self):
        '''Application monitoring thread.'''
        while self._parent.online:
            if not self.is_running() and not self._parent._client.restarting:
                if self.restart:
                    # restart the whole system and reconnect
                    self._parent._client.restart()
                
                else:
                    psutil.Process().terminate()

            time.sleep(1)
