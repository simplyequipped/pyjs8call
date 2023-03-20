import os
import time
import shutil
import subprocess

import psutil

import pyjs8call

NAME = 'Cross Platform Start/Stop'

def run(external_start_delay = 5):
    if psutil.WINDOWS:
        print('\tWindows platform detected')
    elif psutil.MACOS:
        print('\tMacOS platform detected')
    elif psutil.LINUX:
        print('\tLinux platform detected')
    elif psutil.POSIX:
        print('\tPOSIX platform detected')
    else:
        raise AssertionError('Platform not detected')

    print('\t')

    print('\tInitializing pyjs8call client...')
    # pyjs8call.ConfigHandler init raises FileNotFoundError if config file not found
    js8call = pyjs8call.Client()
    print('\tpyjs8call client initialized')
    assert os.path.exists(js8call.config.path), 'Incorrect JS8Call.ini config file path'
    print('\tJS8Call.ini config file found: ' + str(js8call.config.path))
    print('')

    print('\tStarting JS8Call application internally...')
    run_internal(js8call)
    print('')

    print('\tStarting JS8Call application internally and headless...')
    run_internal_headless(js8call)
    print('')

    print('\tStarting JS8Call application externally...')
    run_external(js8call, external_start_delay)
    print('')

    print('\tStarting JS8Call application externally and headless...')
    run_external_headless(js8call, external_start_delay)

    del js8call
    return True

def run_internal(js8call):
    js8call.start()
    assert js8call.js8call.app.is_running(), 'JS8Call application failed to start'
    print('\tJS8Call application started')
    print('\tpyjs8call log file location: ' + str(js8call.js8call._log_path))

    js8call.stop()
    assert not js8call.js8call.app.is_running(), 'JS8Call application failed to stop'
    print('\tJS8Call application stopped')

def run_internal_headless(js8call):
    try:
        js8call.start(headless = True)
    except RuntimeError as e:
        if psutil.WINDOWS:
            print('\txvfb not supported on Windows, skipping test')
            return
        if psutil.MACOS:
            print('\txvfb not supported on MacOS, skipping test')
            return
        else:
            raise e

    assert js8call.js8call.app.is_running(), 'JS8Call application failed to start'
    print('\tJS8Call application started')
    print('\tpyjs8call log file location: ' + str(js8call.js8call._log_path))

    js8call.stop()
    assert not js8call.js8call.app.is_running(), 'JS8Call application failed to stop'
    print('\tJS8Call application stopped')

def run_external(js8call, external_start_delay):
    js8call_exec_path = shutil.which('js8call')
    psutil.Popen([js8call_exec_path], stderr = subprocess.DEVNULL)
    time.sleep(external_start_delay)

    js8call.start()
    assert js8call.js8call.app.is_running(), 'JS8Call application failed to start'
    print('\tJS8Call application started')
    print('\tpyjs8call log file location: ' + str(js8call.js8call._log_path))

    js8call.stop()
    assert not js8call.js8call.app.is_running(), 'JS8Call application failed to stop'
    print('\tJS8Call application stopped')

def run_external_headless(js8call, external_start_delay):
    if psutil.WINDOWS:
        print('\txvfb not supported on Windows, skipping test')
        return
    if psutil.MACOS:
        print('\txvfb not supported on MacOS, skipping test')
        return

    xvfb_exec_path = shutil.which('xvfb-run')
    js8call_exec_path = shutil.which('js8call')
    psutil.Popen([xvfb_exec_path, '-a', js8call_exec_path], stderr = subprocess.DEVNULL)
    time.sleep(external_start_delay)

    js8call.start(headless = True)
    assert js8call.js8call.app.is_running(), 'JS8Call application failed to start'
    print('\tJS8Call application started')
    print('\tpyjs8call log file location: ' + str(js8call.js8call._log_path))

    js8call.stop()
    assert not js8call.js8call.app.is_running(), 'JS8Call application failed to stop'
    print('\tJS8Call application stopped')

