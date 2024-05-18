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

__docformat__ = 'google'

'''pyjs8call command line inteface (CLI) and RNS pipe interface.

See [RNS PipeInterface](https://markqvist.github.io/Reticulum/manual/interfaces.html#pipe-interface) for more information on configuring a RNS PipeInterface.

Try `python -m pyjs8call --help` for command line switch options.

Order of precedence for settings:
    1. Command line switch settings
    2. Settings loaded from specified ini file (--settings)
    3. Configuration profile
'''

import sys
import time
import argparse
import threading

import pyjs8call


# see Reticulum
MTU = 500


class HDLC:
    # RNS PipeInterface packetizes data using simplified HDLC framing, similar to PPP
    FLAG = 0x7E
    ESC = 0x7D
    ESC_MASK = 0x20

    @staticmethod
    def escape(data):
        data = data.replace(bytes([HDLC.ESC]), bytes([HDLC.ESC, HDLC.ESC^HDLC.ESC_MASK]))
        data = data.replace(bytes([HDLC.FLAG]), bytes([HDLC.ESC, HDLC.FLAG^HDLC.ESC_MASK]))
        return data


def _rns_write_stdout(msg):
    # drop messages without destination set to @RNS group
    if not msg.is_directed_to('@RNS'):
        return

    data = bytes([HDLC.FLAG]) + HDLC.escape(msg.encode()) + bytes([HDLC.FLAG])

    try:
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
    except BrokenPipeError:
        return

def _rns_read_stdin():
    global js8call
    global MTU
    in_frame = False
    escape = False
    data_buffer = b''

    while js8call.connected():
        try:
            byte = sys.stdin.buffer.read(1)
        except:
            js8call.stop()
            return

        if len(byte) == 0:
            # EOF reached, pipe closed
            js8call.stop()
            break

        byte = ord(byte)

        if in_frame and byte == HDLC.FLAG:
            in_frame = False

            js8call.send_directed_bytes_message('@RNS', data_buffer)

        elif byte == HDLC.FLAG:
            in_frame = True
            data_buffer = b''

        elif in_frame and len(data_buffer) < MTU:
            if byte == HDLC.ESC:
                escape = True
            else:
                if escape:
                    if byte == HDLC.FLAG ^ HDLC.ESC_MASK:
                        byte = HDLC.FLAG
                    if byte == HDLC.ESC ^ HDLC.ESC_MASK:
                        byte = HDLC.ESC
                    escape = False
                data_buffer += bytes([byte])


if __name__ == '__main__':
    help_epilog =  'RNS PipeInterface must be configured and enabled in the Reticulum config file. '
    help_epilog += 'If specified profile does not exist, it is created by copying the \'Default\' profile. '
    help_epilog += 'See pyjs8call docs for more information: https://simplyequipped.github.io/pyjs8call'

    program = 'python -m pyjs8call'
    parser = argparse.ArgumentParser(prog=program, description='pyjs8call CLI and RNS interface', epilog = help_epilog)
    parser.add_argument('--rns', help='Enable RNS PipeInterface (sets config profile \'RNS\')', action='store_true')
    parser.add_argument('--freq', help='Set radio frequency in Hz', type=int)
    parser.add_argument('--grid', help='Set station grid square')
    parser.add_argument('--speed', help='Set speed of JS8Call modem, defaults to \'fast\'', default='fast')
    parser.add_argument('--profile', help='Set JS8Call configuration profile')
    parser.add_argument('--callsign', help='Set station callsign')
    parser.add_argument('--settings', help='File path to pyjs8call settings file (NOT JS8CALL CONFIG FILE)')
    parser.add_argument('--headless', help='Run JS8Call headless (only available on Linux platforms)', action='store_true')
    parser.add_argument('--heartbeat', help='Enable pyjs8call heartbeat networking', action='store_true')
    args = parser.parse_args()

    js8call = pyjs8call.Client()

    if args.rns:
        # set config profile, creating the profile if it does not exist
        js8call.settings.set_profile('RNS', restore_on_exit=True, create=True)
    elif args.profile:
        # set config profile, creating the profile if it does not exist
        js8call.settings.set_profile(args.profile, create=True)
    
    if args.settings: js8call.settings.load(args.settings)
    # set config settings after setting profile and loading settings to avoid overwriting
    if args.callsign: js8call.settings.set_station_callsign(args.callsign)
    if args.speed: js8call.settings.set_speed(args.speed)

    if args.rns:
        # allow freetext
        js8call.config.set('Configuration', 'AvoidForcedIdentify', 'true')
        # add @RNS group to station groups
        js8call.settings.add_group('@RNS')
        # disable idle timeout
        js8call.settings.set_idle_timeout(0)

    # start js8call, headless if specified
    js8call.start(headless = args.headless)

    time.sleep(1)
    if args.freq: js8call.settings.set_freq(args.freq)
    if args.grid: js8call.settings.set_station_grid(args.grid)
    if args.heartbeat: js8call.heartbeat.enable()

    if args.rns:
        # registered for incoming type RX.DIRECTED by default
        js8call.callback.register_incoming(_rns_write_stdout)
    
        thread = threading.Thread(target=_rns_read_stdin)
        thread.daemon = True
        thread.start()
    else:
        print('pyjs8call modem started, press Ctrl-C to stop the modem...')

    # modem is stopped when EOF reached on RNS stdin pipe
    while js8call.connected():
        try:
            time.sleep(0.25)
        except KeyboardInterrupt:
            js8call.stop()
            print('pyjs8call modem stopped')
            break
    
