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

'''Send email notifications.

Email notifications can be sent using an existing SMTP server such as Gmail or Outlook. Notification can be used to send a regular email, or a text message. See the following carrier domain reference, or lookup other carrier domains.

**Note*
Gmail, Outlook, and other SMTP providers may require that the "less secure apps" setting be enabled to allow access via username and password. Allowing "less secure apps" is not available if 2-factor authentication is enabled on the account. If you do not feel confortable enabling this feature for your personal email account, consider making another email account specifically for notifications purposes.

Common North America SMS carrier domains:
XXXXXXXXXX@vtext.com (limited to 160 characters)
XXXXXXXXXX@text.att.net
XXXXXXXXXX@tmomail.net
XXXXXXXXXX@txt.bellmobility.com
XXXXXXXXXX@pcs.rogers.com

Example (default GMail SMTP server):

```
import pyjs8call

# directed message callback function
def directed_msg_notify(msg):
    # ignore standard and custom commands
    ignore_commands = js8call.Message.COMMANDS
    ignore_commands.extend(js8call.callback.commands.keys())
    # do not ignore inbox messages
    ignore_commands.remove(pyjs8call.Message.CMD_MSG')

    # send notification if the incoming message is to the local station or configured groups
    # ignore messages containing a JS8Call command
    if js8call.is_directed_to_me(msg) and msg.cmd not in ignore_commands:
        js8call.notifications.send(msg)

js8call = pyjs8call.Client()
js8call.start()

# set SMTP server credentials
js8call.notifications.set_smtp_credentials('email.address@gmail.com', 'Sup3rS3cur3Password123')
# set destination email address to Verzion mobile number
js8call.notifications.set_destination('0123456789@vtext.com')

# register callback function for incoming *RX.DIRECTED* message types (default type)
js8call.callback.register_incoming(directed_msg_notify)
```
'''

__docformat__ = 'google'


import ssl
import libsmtp

import pyjs8call


class Notifications:
    '''Send email notifiations via SMTP server.'''
    def __init__(self):
        '''Initialize notifications.

        Returns:
            pyjs8call.Notifications: Constructed notifications object
        '''
        self._smtp_server = 'smtp.gmail.com'
        self._smtp_port = 465
        self._smtp_email = None
        self.__smtp_password = None
        self._destination_email = None

    def set_smtp_credentials(self, email, password):
        '''Set SMTP server credentials.

        Note: Credentials are not written to disk and must be set each time *pyjs8call* is started. Credentials are stored in plain text internally in a variable. This variable is destroyed when the program is closed.

        Args:
            email (str): SMTP server username (email address)
            password (str): SMTP server password
        '''
        self._smtp_email = email
        self.__smtp_password = password

    def set_smtp_server(self, server, port = None):
        '''Set SMTP server domain.

        Args:
            server (str): SMTP server domain (ex. smtp.gmail.com)
            port (int): SMTP server port, defaults to 465 (SSL)
        '''
        self._smtp_server = server

        if port is not None:
            self._smtp_port = int(port)
    
    def set_destination(self, email):
        '''
        '''
        self._destination_email = email

    def send(self, message, destination_email=None, origin_email=None, subject=None):
        '''Send email notification.

        If *message* is a *pyjs8call.Message* object, *message.value* is used as the email body.

        Note: Setting *subject* to *None* (default) is convenient when the destination email is associted with a mobile number (email to text).

        Args:
            message (str or pyjs8call.Message): Message text or *pyjs8call.Message* to use as email body
            destination_email (str): Destination (aka "to") email address, defaults to address set by *set_destination()*
            origin_email (str): Origin (aka "from") email address, defaults to SMTP address set by *set_smtp_credentials()*
            subject (str): Email subject, defaults to None
        '''
        if self._smtp_email is None or self.__smtp_password is None:
            raise ValueError('SMTP credentials must be set: see set_smtp_credentials()')
            
        if self._destination_email is None and destination_email is None:
            raise ValueError('Destination email must be set: see set_destination() or send()')

        if isinstance(message, pyjs8call.Message):
            message = message.value

        if destination_email is None:
            destination = self._destination_email
        else:
            destination = destination_email

        if origin_email is None:
            origin = self._smtp_email
        else:
            origin = origin_email

        if subject is None:
            subject = ''
        else:
            subject = subject.strip() + '\n\n'

        context = ssl.create_default_context()
        
        with smtplib.SMTP_SSL(self._smtp_server, port = self._smtp_port, context = context) as server:
            server.login(self._smtp_email, self.__smtp_password)
            server.sendmail(origin, destination, subject + message)
