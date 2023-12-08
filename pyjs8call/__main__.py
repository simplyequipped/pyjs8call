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


#TODO
byte_map_latin = [
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', ' ', '.', '?', '+', '-', '`', '~', '!', '@', '#', '$', '%', '^', '&', '*', '(',
    ')', '_', '=', '[', ']', '{', '}', '|', ';', '’', ':', '”', ',', '<', '>', ')', '¡', '¿', 'À', 'Á', 'Â', 'Ã', 'Ä', 'Å', 'Æ', 'Ç',
    'È', 'É', 'Ê', 'Ë', 'Ì', 'Í', 'Î', 'Ï', 'Ð', 'Ñ', 'Ò', 'Ó', 'Ô', 'Õ', 'Ö', 'Ø', 'Ù', 'Ú', 'Û', 'Ü', 'Ý', 'Þ', '\A', '\\B','\\C', '\\D',
    '\\E', '\\F', '\\G', '\\H', '\\I', '\\J', '\\K', '\\L', '\\M', '\\N', '\\O', '\\P', '\\Q', '\\R', '\\S', '\\T', '\\U', '\\V', '\\W', '\\X', '\\Y', '\\Z',
    '\\0', '\\1', '\\2', '\\3', '\\4', '\\5', '\\6', '\\7', '\\8', '\\9', '\\ ', '\\.', '\\?', '\\+', '\\-', '\\`', '\\~', '\\!', '\\@', '\\#', '\\$', '\\%',
    '\\^', '\\&','\\*', '\\(', '\\)', '\\_', '\\=', '\\[', '\\]', '\\{', '\\}', '\\|', '\\;', '\\’', '\\:', '\\”', '\\,', '\\<', '\\>', '\\)', '\\¡', '\\¿',
    '\\À', '\\Á', '\\Â', '\\Ã', '\\Ä', '\\Å', '\\Æ', '\\Ç', '\\È', '\\É', '\\Ê', '\\Ë', '\\Ì', '\\Í', '\\Î', '\\Ï', '\\Ð', '\\Ñ', '\\Ò', '\\Ó', '\\Ô', '\\Õ',
    '\\Ö', '\\Ø', '\\Ù', '\\Ú', '\\Û', '\\Ü','\\Ý', '\\Þ', '/A', '/B', '/C', '/D', '/E', '/F', '/G', '/H', '/I', '/J', '/K', '/L', '/M', '/N',
    '/O', '/P', '/Q', '/R', '/S', '/T', '/U', '/V', '/W', '/X', '/Y', '/Z', '/0', '/1', '/2', '/3', '/4', '/5', '/6', '/7', '/8', '/9',
    '/.', '/?', '/+', '/-', '/`', '/~', '/!', '/@', '/#', '/$', '/%', '/^', '/&', '/*', '/(', '/)', '/_', '\=', '\[', '\]', '\{', '\}'
]
byte_map_latin_prefix = ['\\', '/']

byte_map_huff = [
    'N', 'S', 'H', 'R', 'D', 'L', 'C', 'U', 'M', 'W', 'F', 'G', 'Y', 'P', 'B', '.', 'V', 'K', '-', '+', '?', '!', '"', 'X', '0', 'J', '1',
    'Q', '2', 'Z', '3', '5', '4', '9', '8', '6', '7', '/', ' N', ' S', ' H', ' R', ' D', ' L', ' C', ' U', ' M', ' W', ' F', ' G', ' Y',
    ' P', ' B', ' .', ' V', ' K', ' -', ' +', ' ?', ' !', ' "', ' X', ' 0', ' J', ' 1', ' Q', ' 2', ' Z', ' 3', ' 5', ' 4', ' 9', ' 8',
    ' 6', ' 7', ' /', 'EN', 'ES', 'EH', 'ER', 'ED', 'EL', 'EC', 'EU', 'EM', 'EW', 'EF', 'EG', 'EY', 'EP', 'EB', 'E.', 'EV', 'EK', 'E-',
    'E+', 'E?', 'E!', 'E"', 'EX', 'E0', 'EJ', 'E1', 'EQ', 'E2', 'EZ', 'E3', 'E5', 'E4', 'E9', 'E8', 'E6', 'E7', 'E/', 'TN', 'TS', 'TH',
    'TR', 'TD', 'TL', 'TC', 'TU', 'TM', 'TW', 'TF', 'TG', 'TY', 'TP', 'TB', 'T.', 'TV', 'TK', 'T-', 'T+', 'T?', 'T!', 'T"', 'TX', 'T0',
    'TJ', 'T1', 'TQ', 'T2', 'TZ', 'T3', 'T5', 'T4', 'T9', 'T8', 'T6', 'T7', 'T/', 'AN', 'AS', 'AH', 'AR', 'AD', 'AL', 'AC', 'AU', 'AM',
    'AW', 'AF', 'AG', 'AY', 'AP', 'AB', 'A.', 'AV', 'AK', 'A-', 'A+', 'A?', 'A!', 'A"', 'AX', 'A0', 'AJ', 'A1', 'AQ', 'A2', 'AZ', 'A3',
    'A5', 'A4', 'A9', 'A8', 'A6', 'A7', 'A/', 'ON', 'OS', 'OH', 'OR', 'OD', 'OL', 'OC', 'OU', 'OM', 'OW', 'OF', 'OG', 'OY', 'OP', 'OB',
    'O.', 'OV', 'OK', 'O-', 'O+', 'O?', 'O!', 'O"', 'OX', 'O0', 'OJ', 'O1', 'OQ', 'O2', 'OZ', 'O3', 'O5', 'O4', 'O9', 'O8', 'O6', 'O7',
    'O/', 'IN', 'IS', 'IH', 'IR', 'ID', 'IL', 'IC', 'IU', 'IM', 'IW', 'IF', 'IG', 'IY', 'IP', 'IB', 'I.', 'IV', 'IK', 'I-', 'I+', 'I?',
    'I!', 'I"', 'IX', 'I0', 'IJ', 'I1', 'IQ'
]
byte_map_huff_prefix = [' ', 'E', 'T', 'A', 'O', 'I']

byte_map = byte_map_latin
byte_map_prefix = byte_map_latin_prefix


def map_from_bytes(data):
    text = ''

    for byte in data:
        index = int.from_bytes(byte, byteorder=sys.byteorder)
        char = byte_map[index]
        text.append(char)

    return text

def map_to_bytes(text):
    data = b''

    for i in range(len(text)):
        char = text[i]

        # handle escaped characters
        if char in byte_map_prefix:
            char += text[i + 1]
            i += 1

        index = byte_map.index(char)
        data.append( bytes([index]) )

    return data



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
    msg_text = bytes.fromhex( msg.text.lower() )
    data = bytes([HDLC.FLAG]) + HDLC.escape(msg_text) + bytes([HDLC.FLAG])

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

            js8call.send_directed_message('@RNS', data_buffer.hex())

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

    if args.callsign:
        js8call.settings.set_station_callsign(args.callsign)

    if args.speed:
        js8call.settings.set_speed(args.speed)

    if args.profile:
        if args.profile in js8call.settings.get_profile_list():
            js8call.settings.set_profile(args.profile)
        else:
            # copies 'Default' profile by default
            js8call.config.create_new_profile(args.profile)

    # set after setting profile to avoid overwrite after setting
    # allow freetext
    js8call.config.set('Configuration', 'AvoidForcedIdentify', 'true')
    # disable idle timeout
    js8call.settings.set_idle_timeout(0)

    if args.headless:
        headless = True
    else:
        headless = False

    #TODO remove debugging
    js8call.start(headless = headless, debugging = True)

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

