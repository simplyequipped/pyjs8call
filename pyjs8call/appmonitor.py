import os
import time
import subprocess
import threading

import pyjs8call


class AppMonitor:
    def __init__(self, owner):
        self._exec_path = None
        self._process = None
        self.headless = False
        self.running = False
        self.restart = True
        self._owner = owner
        self._monitor_thread = None

        try:
            self._exec_path = subprocess.check_output(['which', 'js8call']).decode('utf-8').strip()
        except subprocess.CalledProcessError:
            raise ProcessLookupError('JS8Call application not installed, on Debian systems try: sudo apt install js8call')

    #TODO headless mode does not work, xvfb does not work by itself either
    def start(self, headless=False):
        cmd = [self._exec_path]

        if headless:
            try:
                subprocess.check_output(['which', 'xvfb-run'])
            except subprocess.CalledProcessError:
                raise ProcessLookupError('Cannot run headless since xvfb-run (virtual x server) not installed, on Debian systems try: sudo apt install xvfb')

            self.headless = True
            cmd.insert(0, 'xvfb-run')
            cmd.insert(1, '-a')

        if not self.is_running():
            devnull = open(os.devnull, 'w')
            self._process = subprocess.Popen(cmd, stderr=devnull)

        # wait for connection to application via socket
        timeout = time.time() + 15
        while True:
            try:
                # this will error if unable to connect to the application
                self._owner._connect()
                # no errors, must be connected
                self.running = True
                break
            except ConnectionRefusedError:
                pass

            if time.time() > timeout:
                break

            time.sleep(0.1)

        # start the application monitoring thread
        if self.running and self._monitor_thread == None:
            self._monitor_thread = threading.Thread(target=self._monitor)
            self._monitor_thread.setDaemon(True)
            self._monitor_thread.start()

        elif not self.running:
            raise RuntimeError('JS8Call application failed to start')

    def is_running(self):
        # handle process started externally
        if self._process == None:
            try:
                # errors due to non-zero return code if no running instances
                subprocess.check_output(['pgrep', 'js8call'])
                # if no error then the process is running
                running = True
            except subprocess.CalledProcessError:
                running = False

        # handle process started by self
        else:
            if self._process.poll() == None:
                running = True
            else:
                running = False

        self.running = running
        return running

    def stop(self):
        if self._process == None:
            return None

        code = None
        self._process.terminate()

        try:
            code = self._process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass

        if code == None:
            code = self._process.kill()

        return code

    def _monitor(self):
        while self._owner.online:
            if not self.is_running() and self.restart:
                # close the current socket
                self._owner._socket.close()
                # restart the whole system and reconnect
                self._owner._client.restart()
            time.sleep(2)

