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

Email notifications can be sent using an existing SMTP server such as GMail or Outlook. Notification can be used to send a regular email, or a text message. See the following carrier domain reference, or search online for a list of SMS carrier domains if yours is not listed below.

Common North America SMS carrier domains:
XXXXXXXXXX@vtext.com (limited to 160 characters)
XXXXXXXXXX@text.att.net
XXXXXXXXXX@tmomail.net
XXXXXXXXXX@txt.bellmobility.com
XXXXXXXXXX@pcs.rogers.com

The current best practice for services like GMail is to use app passwords in place of your account password. App passwords are passwords that are specific to a single 3rd party application. This makes it easier to control access to your account. Typically you have to enable two-factor authentication on your account before you can use app passwords. You can enable two-factor authentication on a Google account by visiting [https://myaccount.google.com/security](https://myaccount.google.com/security). You can configure an app password for use with pyjs8call by visiting [https://myaccount.google.com/u/0/apppasswords](https://myaccount.google.com/u/0/apppasswords). Once the app password is generated, copy and paste it into your script in place of your password when calling *set_smtp_credentials()*.

The default SSL context is used to establish a secure connection to the SMTP server.

Example (default GMail SMTP server):

```
import pyjs8call
js8call = pyjs8call.Client()
js8call.start()

# set SMTP server credentials
js8call.notifications.set_smtp_credentials('email.address@gmail.com', 'app_password')
# set destination email address to a Verzion mobile number
js8call.notifications.set_email_destination('2018675309@vtext.com')
# enable automatic email notifications
js8call.notifications.enable()
```
'''

__docformat__ = 'google'


import ssl
import email
import smtplib
import socket

import pyjs8call


class Notifications:
    '''Send email notifiations via SMTP server.
    
    Attributes:
        incoming_enabled (bool): Process incoming directed messages if True, ignore otherwise, defaults to True
        spots_enabled (bool): Process spots if True, ignore otherwise, defaults to False
        station_spots_enabled (bool): Process watched station spot if True, ignore otherwise, defaults to False
        group_spots_enabled (bool): Process watched group spot if True, ignore otherwise, defaults to False
        notify_on_incoming_if_callsign_selected (bool): Process incoming messages while a callsign is selected on the UI if True, ignore otherwise, defaults to False
        commands (list): Commands matching incoming *Message.cmd* to notify for, defaults to MSG and freetext

    See pyjs8call.Message for more information on message commands.
    '''
    def __init__(self, client):
        '''Initialize notifications.

        Returns:
            pyjs8call.Notifications: Constructed notifications object
        '''
        self._client = client
        self._enabled = False
        self._smtp_server = 'smtp.gmail.com'
        self._smtp_port = 465
        self._smtp_email = None
        self.__smtp_password = None
        self._email_destination = None
        self._email_subject = None

        self.incoming_enabled = True
        self.spots_enabled = False
        self.station_spots_enabled = False
        self.group_spots_enabled = False
        self.notify_on_incoming_if_callsign_selected = False

        self.commands = [pyjs8call.Message.CMD_MSG, pyjs8call.Message.CMD_FREETEXT]

    def enabled(self):
        '''Get enabled status.

        Returns:
            bool: True if enabled, False if disabled
        '''
        return self._enabled

    def enable(self):
        '''Enable automatic email notifications.

        Incoming directed messages directed to the local station or configured groups will be emailed to the configured destination email (see *set_email_destination()*). Messages with a command are ignored unless the command is in *pyjs8call.notifications.commands*.
        '''
        if self._enabled:
            return

        self._enabled = True
        self._client.callback.register_incoming(self.process_incoming)
        self._client.callback.register_spots(self.process_spots)
        self._client.callback.register_station_spot(self.process_station_spots)
        self._client.callback.register_group_spot(self.process_group_spots)

    def disable(self):
        '''Disable automatic email notifiations.'''
        self._enabled = False
        self._client.callback.remove_incoming(self.process_incoming)
        self._client.callback.remove_spots(self.process_spots)
        self._client.callback.remove_station_spot(self.process_station_spots)
        self._client.callback.remove_group_spot(self.process_group_spots)

    def process_incoming(self, msg):
        '''Process incoming directed messages.

        This function is used internally.
        '''
        if not self.incoming_enabled:
            return

        if self._client.get_selected_call() is not None and self.notify_on_incoming_if_callsign_selected == False:
            # do not send notification for incoming message if a callsign is selected on the UI
            return
            
        if self._client.msg_is_to_me(msg) and (msg.cmd in (None, '') or msg.cmd in self.commands):
            self.send(msg)

    def process_spots(self, spots):
        '''Process spots.

        This function is used internally.
        '''
        if not self.spots_enabled:
            return

        spots = [spot.origin for spot in spots]
        text = 'Spotted {}'.format( ', '.join(spots) )
        self.send(text)

    def process_station_spots(self, spot):
        '''Process watched station spots.

        This function is used internally.
        '''
        if not self.station_spots_enabled:
            return

        text = 'Spotted watched station {}'.format(spot.origin)
        self.send(text)

    def process_group_spots(self, spot):
        '''Process watched group spots.

        This function is used internally.
        '''
        if not self.group_spots_enabled:
            return

        text = 'Spotted watched group {}'.format(spot.destination)
        self.send(text)

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
    
    def set_email_destination(self, email):
        '''Set destination email address.

        Args:
            email (str): Destination (aka "to") email address
        '''
        self._email_destination = email

    def set_email_subject(self, subject):
        '''Set email subject.

        Args:
            subject (str): Email subject text
        '''
        self._email_subject = subject

    def send(self, message, destination_email=None, origin_email=None, subject=None):
        '''Send email notification.

        If *message* is a *pyjs8call.Message* object, *message.value* is used as the email body.

        Note: Setting *subject* to *None* (default) is convenient when the destination email is associted with a mobile number (email to text).

        Args:
            message (str or pyjs8call.Message): Message text or *pyjs8call.Message* to use as email body
            destination_email (str): Destination (aka "to") email address, defaults to address set by *set_email_destination()*
            origin_email (str): Origin (aka "from") email address, defaults to SMTP address set by *set_smtp_credentials()*
            subject (str): Email subject, defaults to None

        Raises:
            OSError: Unable to connect to SMTP server
        '''
        if self._smtp_email is None or self.__smtp_password is None:
            raise ValueError('SMTP credentials must be set: see set_smtp_credentials()')
            
        if self._email_destination is None and destination_email is None:
            raise ValueError('Destination email must be set: see set_email_destination() or send()')

        if isinstance(message, pyjs8call.Message):
            message = '{}: {}'.format(message.origin, message.text)
            # remove end-of-message character
            message = message.replace(pyjs8call.Message.EOM, '')
            # replace error character
            message = message.replace(pyjs8call.Message.ERR, '...')

        if destination_email is None:
            destination_email = self._email_destination

        if origin_email is None:
            origin_email = self._smtp_email

        if subject is None:
            if self._email_subject is not None:
                subject = self._email_subject
            else:
                subject = ''

        # contruct email object
        msg = email.message.EmailMessage()
        msg.set_content(message)
        msg['Subject'] = subject
        msg['From'] = origin_email
        msg['To'] = destination_email

        context = ssl.create_default_context()
        
        try:
            with smtplib.SMTP_SSL(self._smtp_server, port = self._smtp_port, context = context) as server:
                server.login(self._smtp_email, self.__smtp_password)
                server.send_message(msg)

        except (socket.herror, socket.gaierror, socket.timeout):
            raise OSError('Unable to connect to SMTP server, check network connection')
        except (smtplib.SMTPAuthenticationError):
            raise OSError('Unable to connect to SMTP server, bad credentials')


