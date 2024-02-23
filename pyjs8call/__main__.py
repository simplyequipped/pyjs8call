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

'''stdin/stdout pipe interface for pyjs8call.

Developed for use with the [RNS PipeInterface](https://markqvist.github.io/Reticulum/manual/interfaces.html#pipe-interface), but may have other CLI uses as well.

Try `python -m pyjs8call --help` for command line switch options.
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
            # EOL reached, pipe closed
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
    help_epilog =  'If *profile* does not exist, it is created by copying the \'Default\' profile.\n\n'
    help_epilog += 'See pyjs8call docs for more information: https://simplyequipped.github.io/pyjs8call\n'

    program = 'python -m pyjs8call'

    parser = argparse.ArgumentParser(prog=program, description='RNS PipeInterface for pyjs8call package', epilog = help_epilog)
    parser.add_argument('--speed', help='Speed of JS8Call modem, defaults to \'normal\'', default='normal')
    parser.add_argument('--freq', help='Radio frequency in Hz', type=int)
    parser.add_argument('--callsign', help='Station callsign')
    parser.add_argument('--grid', help='Station grid square')
    parser.add_argument('--profile', help='JS8Call configuration profile, defaults to \'RNS\'', default='RNS')
    parser.add_argument('--headless', help='Run JS8Call headless (only available on Linux platforms)', action='store_true')
    parser.add_argument('--heartbeat', help='Enable pyjs8call heartbeat networking', action='store_true')
    args = parser.parse_args()

    js8call = pyjs8call.Client()

    if args.profile:
        if args.profile in js8call.settings.get_profile_list():
            js8call.settings.set_profile(args.profile)
        else:
            # copies 'Default' profile by default
            js8call.config.create_new_profile(args.profile)

    # set config after setting profile to avoid overwriting settings
    if args.callsign:
        js8call.settings.set_station_callsign(args.callsign)

    if args.speed:
        js8call.settings.set_speed(args.speed)

    # allow freetext
    js8call.config.set('Configuration', 'AvoidForcedIdentify', 'true')
    #
    js8call.config.add_group('@RNS')
    # disable idle timeout
    js8call.settings.set_idle_timeout(0)

    js8call.start(headless = args.headless)

    if args.freq:
        js8call.settings.set_freq(args.freq)

    if args.grid:
        js8call.settings.set_station_grid(args.grid)

    if args.heartbeat:
        js8call.heartbeat.enable()

    js8call.callback.register_incoming(_rns_write_stdout)

    thread = threading.Thread(target=_rns_read_stdin)
    thread.daemon = True
    thread.start()

    # modem is stopped when EOF reached on stdin pipe
    while js8call.connected():
        try:
            time.sleep(0.25)
        except KeyboardInterrupt:
            print()
            break


