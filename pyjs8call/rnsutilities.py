# MIT License
# 
# Copyright (c) 2022-2024 Simply Equipped
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

'''Reticulum Network Stack (RNS) utility functions.
'''

__docformat__ = 'google'


import base64

BASE64_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
JS8CALL_BASE64_ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ,.-"?!)(=:_&$%#@*><[]{}|;^0123456789+/'
PIPE_TRANSLATION_TABLE = str.maketrans(JS8CALL_BASE64_ALPHABET, BASE64_ALPHABET)
JS8CALL_TRANSLATION_TABLE = str.maketrans(BASE64_ALPHABET, JS8CALL_BASE64_ALPHABET)

def encode(js8call_text):
    '''Encode JS8Call text to PipeInterface bytes.'''
    # translate js8call alphabet to base46 alphabet
    base64_text = js8call_text.translate(JS8CALL_TRANSLATION_TABLE)
    # convert base64 to bytes
    return base64.decode(base64_text)

def decode(pipe_bytes):
    '''Decode PipeInterface bytes to JS8Call text.'''
    # convert bytes to base64
    base64_text = base64.encode(pipe_bytes)
    # translate base64 alphabet to js8call alphabet
    return base64_text.translate(PIPE_TRANSLATION_TABLE)
