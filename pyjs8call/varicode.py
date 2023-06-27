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

'''
'''

__docformat__ = 'google'


#TODO
# - add regular expressions to parse message parts
# - handle missing MYCALL from message text
# - handle logic for determining frame types
# - determine frame count for given msg


re_callsign = '(?<callsign>[@]?[A-Z0-9/]+)'
re_optional_cmd = '(?<cmd>\\s?(?:AGN[?]|QSL[?]|HW CPY[?]|MSG TO[:]|SNR[?]|INFO[?]|GRID[?]|STATUS[?]|QUERY MSGS[?]|HEARING[?]|(?:(?:STATUS|HEARING|QUERY CALL|QUERY MSGS|QUERY|CMD|MSG|NACK|ACK|73|YES|NO|HEARTBEAT SNR|SNR|QSL|RR|SK|FB|INFO|GRID|DIT DIT)(?=[ ]|$))|[?> ]))?'
re_optional_grid = '(?<grid>\\s?[A-R]{2}[0-9]{2})?'
re_optional_extended_grid = '^(?<grid>\\s?(?:[A-R]{2}[0-9]{2}(?:[A-X]{2}(?:[0-9]{2})?)*))?'
re_optional_num = '(?<num>(?<=SNR)\\s?[-+]?(?:3[01]|[0-2]?[0-9]))?'

re_directed = '^' + re_callsign + re_optional_cmd + re_optional_num
re_heartbeat = '(^\s*(?<callsign>[@](?:ALLCALL|HB)\s+)?(?<type>CQ CQ CQ|CQ DX|CQ QRP|CQ CONTEST|CQ FIELD|CQ FD|CQ CQ|CQ|HB|HEARTBEAT(?!\s+SNR))(?:\s(?<grid>[A-R]{2}[0-9]{2}))?\b)'
re_compound = '^\\s*[`]' + re_callsign + '(?<extra>' + re_optional_grid + re_optional_cmd + re_optional_num + ')'


huff_table = {
   # char code           weight
    ' ': '01',          # 1.0
    'E': '100',         # 0.5
    'T': '1101',        # 0.333333333333
    'A': '0011',        # 0.25
    'O': '11111',       # 0.2
    'I': '11100',       # 0.166666666667
    'N': '10111',       # 0.142857142857
    'S': '10100',       # 0.125
    'H': '00011',       # 0.111111111111
    'R': '00000',       # 0.1
    'D': '111011',      # 0.0909090909091
    'L': '110011',      # 0.0833333333333
    'C': '110001',      # 0.0769230769231
    'U': '101101',      # 0.0714285714286
    'M': '101011',      # 0.0666666666667
    'W': '001011',      # 0.0625
    'F': '001001',      # 0.0588235294118
    'G': '000101',      # 0.0555555555556
    'Y': '000011',      # 0.0526315789474
    'P': '1111011',     # 0.05
    'B': '1111001',     # 0.047619047619
    '.': '1110100',     # 0.0434782608696
    'V': '1100101',     # 0.0416666666667
    'K': '1100100',     # 0.04
    '-': '1100001',     # 0.0384615384615
    '+': '1100000',     # 0.037037037037
    '?': '1011001',     # 0.0344827586207
    '!': '1011000',     # 0.0333333333333
    '"': '1010101',     # 0.0322580645161
    'X': '1010100',     # 0.03125
    '0': '0010101',     # 0.030303030303
    'J': '0010100',     # 0.0294117647059
    '1': '0010001',     # 0.0285714285714
    'Q': '0010000',     # 0.0277777777778
    '2': '0001001',     # 0.027027027027
    'Z': '0001000',     # 0.0263157894737
    '3': '0000101',     # 0.025641025641
    '5': '0000100',     # 0.025
    '4': '11110101',    # 0.0243902439024
    '9': '11110100',    # 0.0238095238095
    '8': '11110001',    # 0.0232558139535
    '6': '11110000',    # 0.0227272727273
    '7': '11101011',    # 0.0222222222222
    '/': '11101010'     # 0.0217391304348
}

def char_to_bits(char):
    global huff_table

    if char in huff_table:
        return huff_table[char]
    else:
        return ''

def huff_encode(text):
    bits = ''
    for char in text:
        bits += char_to_bits(char)








