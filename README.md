[![pypi version](https://img.shields.io/pypi/v/pyjs8call?color=blue&label=pypi%20version)](https://pypi.org/project/pyjs8call) &nbsp;&nbsp;&nbsp;
[![pypi downloads](https://img.shields.io/pypi/dw/pyjs8call?color=blue&label=pypi%20downloads)](https://pypi.org/project/pyjs8call) &nbsp;&nbsp;&nbsp;
[![github license](https://img.shields.io/github/license/simplyequipped/pyjs8call?color=blue)](https://github.com/simplyequipped/pyjs8call/blob/main/LICENSE)

A Python package for interfacing with the JS8Call API.

&nbsp;

### &beta;eta Software

This software is currently in a beta state. This means that the software will likely change in the future, and that there will be bugs. You can provide feedback in the [Discussions](https://github.com/simplyequipped/pyjs8call/discussions) section of the repository.

&nbsp;

### Responsibility

It is the station operator's reponsibility to ensure compliance with local laws.

&nbsp;

### Documentation

See the official [pyjs8call documentation](https://simplyequipped.github.io/pyjs8call).

See a basic example in the *example.py* file at the top level of the repo.

&nbsp;  

### Cross-Platform Support

All functionality is supported on all major platforms as of version 0.2.0. Running the JS8Call application headless is only supported on Linux operating systems due to the *xvfb* requirement. *xvfb* does not function correctly on Manjaro (at least on the PineBook Pro) even though it can be installed.

| OS&nbsp;Platform                          | Hardware&nbsp;Platform                              | Process&nbsp;Management | Headless&nbsp;Application |
| :---                                      | :---                                                | :---                    | :---                      |
| Ubuntu&nbsp;20.04&nbsp;LTS                | AMD&nbsp;Ryzen&nbsp;5 &nbsp;(Zen 3)                 | Supported               | Supported                 |
| Raspberry&nbsp;Pi&nbsp;OS&nbsp;Buster     | Raspberry&nbsp;Pi&nbsp;3B+                          | Supported               | Supported                 |
| Raspberry&nbsp;Pi&nbsp;OS&nbsp;Bullseye   | Raspberry&nbsp;Pi&nbsp;4B                           | Supported               | Supported                 |
| Manjaro&nbsp;ARM                          | Pine64&nbsp;PineBook&nbsp;Pro                       | Supported               | Not&nbsp;Supported        |
| Windows&nbsp;10                           | MS&nbsp;Surface&nbsp;Pro&nbsp;X&nbsp;(SQ2&nbsp;ARM) | Supported               | Not&nbsp;Supported        |
| Windows&nbsp;11                           | MS&nbsp;Surface&nbsp;Pro&nbsp;9&nbsp;(i5&nbsp;x86)  | Supported               | Not&nbsp;Supported        |
| MacOS&nbsp;Big&nbsp;Sur&nbsp;(11.3.1)     | Apple&nbsp;MacBook&nbsp;Pro&nbsp;2019               | Supported               | Not&nbsp;Supported        |

&nbsp;

### Installation

1. Install applications
    
    a. Install JS8Call
    
    On some platforms, such as Raspberry Pi OS, JS8Call can be installed with the package manager:
    ```
    sudo apt install js8call
    ```

    Otherwise, see the [JS8Call downloads](http://files.JS8Call.com/latest.html) page for OS-specific packages as well as source files. If you are compiling from source for Linux be sure to read the INSTALL file at the top level of the JS8Call repo.

    **NOTE:** When installing JS8Call on Windows be sure to select the option to add JS8Call to the PATH variable during the installation process. This will allow *pyjs8call* to locate the JS8Call executable.

    **NOTE:** When installing JS8Call on MacOS be sure to read the readme file included in the dmg image for information on the fix for the JS8Call shared memory error. The following directory must also be added to the PATH variable to allow *pyjs8call* to locate the JS8Call executable: `/Applications/js8call.app/Contents/MacOS`
    
    **NOTE:** When using a QRPLabs QDX tranceiver on Linux, consider masking the ModemManager service using the below commands to prevent CAT control dropouts (aka rig control errors). See [this post from QRPLabs](https://groups.io/g/QRPLabs/topic/87048220#74634) for more information.
    ```
    sudo systemctl stop ModemManager.service
    sudo systemctl mask ModemManager.service
    ```

    b. Install xvfb if running headless (not supported on Windows or MacOS)
    
    On Debian systems:
    ```
    sudo apt install xvfb
    ```

2. Install pyjs8call using pip (or pip3, if python3 is not the default on your system)
    
    ```
    pip install pyjs8call
    ```

    This will also install *psutil* for cross platform process management.

3. Launch JS8Call to configure audio and CAT interface settings as needed. Launching the application and exiting normally will also initialize the configuration file, which is required by *pyjs8call*.

&nbsp;

### Modules

Some setup (i.e. setting callback functions) is required to use certain module features. Most modules are initialized automatically by pyjs8call.client.

**Client** (pyjs8call.client)

The main JS8Call API interface. Includes functions for sending various types of messages.

**JS8Call** (pyjs8call.js8call)

Manages TCP socket communication with the JS8Call application.

**Application Monitor** (pyjs8call.appmonitor)

Manages the start and stop of the JS8Call application, as well as the restarting of the application if closed. 

**Configuration Handler** (pyjs8call.confighandler)

Reads from and writes to the JS8Call.ini config file to change virtually any setting, including creating and activating configuration profiles. **Specific knowledge of configuration file options is required. Configuring options incorrectly may cause the JS8Call application to not run.**

**Spot Monitor** (pyjs8call.spotmonitor)

Monitors recent station spots. Spot data can be queried for various uses, and spot callbacks can be set for all heard stations and/or for specific stations and groups.

**Window Monitor** (pyjs8call.windowmonitor)

Monitors the next rx/tx window transition. JS8Call API messages associated with incoming and outgoing messages are used to determine the start or end of a window, and the modem speed setting is used to determine the duration of the window. Notification of a window transition is handled via callback function.

**Offset Monitor** (pyjs8call.offsetmonitor)

Manages JS8Call offset frequency based on activity in the pass band. The offset frequency is automatically moved to an unused portion of the pass band if a recently heard signal overlaps with the current offset. Signal bandwidth is calculated based on the modem speed of each heard signal. Only decoded signal data is available from the JS8Call API so other QRM cannot be handled.

**Outgoing Monitor** (pyjs8call.outgoingmonitor)

Monitors JS8Call outgoing message text. Notification of a message status change is handled via callback function.

**Heartbeat Networking** (pyjs8call.hbnetwork)

Sends a heartbeat message in the heartbeat sub-band on a time interval. This module is useful for enabling heatbeat networking programmatically and without using the JS8Call interface (i.e. running headless).

**Time Monitor** (pyjs8call.timemonitor)

Monitors a group, station, or all activity for time drift data and synchronizes local time drift. Enable automatic synchronization to the specified source on a time interval. Synchronizes to the @TIME group by default.

Time master functionality is also implemented which sends outgoing messages on a time interval that other stations can use to synchronize their time drift. Targets the @TIME group by default.

**Inbox Monitor** (pyjs8call.inboxmonitor)

Monitors the local inbox. Notification of new messages is handled via callback function.

Automatic periodic syncing of remote messages from a specified source (@ALLCALL by default) is also supported. Be aware of your local laws regarding unattended stations when using this feature.

*NOTE: enabling syncing of remote messages will cause the local station to transmit immediately*

**Schedule Monitor** (pyjs8call.schedulemonitor)

Monitors configured schedule entries and applies the necessary setting changes at the scheduled time. Settings that can be changed on a schedule include frequency, modem speed, and configuration profile. The JS8Call application can also be restarted on a schedule.

**Propagation** (pyjs8call.propagation)

Parses stored spot data into datasets of individual or median SNR values for grid squares or callsigns. This information can be used to infer general propagation conditions between the local station and a specific station, or the local station and a specific grid square.

**Notifications** (pyjs8call.notifications)

Send an email message (including email-to-text) via a specified SMTP server when a message directed to the local station is received, or when a specific station or group is spotted.

&nbsp;

### Command Line Interface (CLI)

A command line interface is available for the *pyjs8call* module as of version 0.2.3. CLI usage:

```
USAGE: python -m pyjs8call [OPTIONS]

OPTIONS:
--rns
    Utilize IO buffers to support the RNS PipeInterface, set configuration profile
    to 'RNS', allow free text, and add group @RNS (*)
--freq
    Set radio frequency in Hz
--grid
    Set station grid square
--speed
    Set speed of JS8Call modem, defaults to 'fast'
--profile
    Set JS8Call configuration profile (**)
--callsign
    Set station callsign
--settings
    File path to pyjs8call settings file (NOT JS8CALL CONFIG FILE),
    see pyjs8call.settings.Settings.load
    for more information
--headless
    Run JS8Call headless using xvfb (only available on Linux platforms)
--heartbeat
    Enable pyjs8call heartbeat networking


(*) RNS PipeInterface must be configured and enabled in the Reticulum config file,
    see below example:

    [[Pipe Interface]]
    type = PipeInterface
    interface_enabled = True
    command = python -m pyjs8call --rns --settings ~/.config/pyjs8call_rns.ini
    respawn_delay = 5

(**) If the specified profile does not exist, it is created by copying 'Default'
```
See [RNS PipeInterface](https://markqvist.github.io/Reticulum/manual/interfaces.html#pipe-interface) for more information on configuring a RNS PipeInterface.

&nbsp;

### Examples

Basic usage:
```
import pyjs8call

# use default host, port (127.0.0.1:2442)
js8call = pyjs8call.Client()
js8call.start()

# set frequency and offset
freq = js8call.settings.set_freq(7078000)
offset = js8call.settings.set_offset(1500)
print('Frequency: ' + str(freq))
print('Offset: ' + str(offset))

# get inbox messages via JS8Call API
inbox = js8call.get_inbox_messages()
for message in inbox:
    print(message)

# send a directed message
js8call.send_directed_message('N0GQ', 'Thanks for your work on js8net')

# who is hearing who
js8call.hearing()

# who is hearing a specific station
js8call.station_heard_by('KI6NAZ')

# who a specific station is hearing
js8call.station_hearing('KT7RUN')

# get a list of spot messages from a specific station
js8call.spots.filter(origin = 'OH8STN')

# get a list of spot messages sent to a specific group
js8call.spots.filter(destination = '@AMRRON')

# get a list of spot messages within 1000 km
# (or miles, depending on JS8Call settings)
js8call.spots.filter(distance = 1000)

# get a list of spot messages in the last 15 minutes
max_age = 15 * 60 # convert minutes to seconds
js8call.spots.filter(age = max_age)

# get a list of the 10 most recent spot messages from regional stations on the 40m band
js8call.spots.filter(distance = 500, band = '40m', count = 10)
```

Run multiple JS8Call instances:
```
import pyjs8call

# Option A: use the standard network port and no rig name for the primary instance
js8call = pyjs8call.Client()
js8call.start()

# Option B: specify a network port and rig name for the primary instance
#js8call_ft857 = pyjs8call.Client(port=2443)
#js8call_ft857.start(args=['--rig-name', 'FT857'])

# specify a different network port for the secondary instance
js8call_qdx = pyjs8call.Client(port=2444)
# specify the rig name as a command line argument
js8call_qdx.start(args=['--rig-name', 'QDX'])
```
**Note:** radio interface and audio devices should be configured manually in each JS8Call instance

Using the spot monitor:
```
import pyjs8call

# callback function for all new spots
def new_spots(spots):
    for spot in spots:
        print('Spotted {} with a {}db SNR'.format(spot.origin, spot.snr))
    
# callback function for watched station spots
def station_spotted(spot):
    print('{} spotted!'.format(spot.origin))

# callback function for watched group spots
def group_spotted(spot):
    print('{} spotted!'.format(spot.destination))
    
js8call = pyjs8call.Client()
# set spot monitor callback
js8call.callback.spots = new_spots
# set station watcher callback
js8call.callback.station_spot = station_spotted
# set group watcher callback
js8call.callback.group_spot = group_spotted
js8call.start()

# watch multiple stations
js8call.spots.add_station_watch('N0GQ')
js8call.spots.add_station_watch('K6ARK')

# remove a station watcher, no hard feelings Adam :)
js8call.spots.remove_station_watch('K6ARK')

# watch a group
js8call.spots.add_group_watch('@AMRRON')
```

Using the inbox monitor:
```
import pyjs8call

# callback function for new inbox message
def new_inbox_msg(msgs):
    for msg in msgs:
        print('New inbox message from ' + msg['origin'])

js8call = pyjs8call.Client()
# set inbox monitor callback
js8call.callback.inbox = new_inbox_msg
js8call.start()

# enable local inbox monitoring
js8call.inbox.enable()

# enable local inbox monitoring and periodic remote inbox message query
# to @ALLCALL every 60 minutes
js8call.inbox.enable(query=True)

# enable local inbox monitoring and periodic remote inbox message query
# to @MYGROUP every 30 minutes
js8call.inbox.enable(query=True, destination='@MYGROUP', interval=30)
```

Using the outgoing message monitor:
```
import pyjs8call

# callback function for message status change
def tx_status(msg):
    print('Message {} status: {}'.format(msg.id, msg.status))
    
js8call = pyjs8call.Client()
# set outgoing monitor callback
js8call.callback.outgoing = tx_status
js8call.start()

# monitor directed message tx automatically (default)
js8call.send_directed_message('OH8STN', 'Thanks for the great content')

# monitor outgoing message manually
js8call.monitor_outgoing = False
msg = js8call.send_directed_message('KT7RUN', 'Thanks for the great content')
js8call.outgoing.monitor(msg)
```

Using heartbeat networking:
```
import pyjs8call

js8call = pyjs8call.Client()
# set heartbeat interval via config file
js8call.settings.set_heartbeat_interval(15)
js8call.start()

# interval based on JS8Call settings
js8call.heartbeat.enable()
```

Using the schedule monitor:
```
import pyjs8call

# callback function for schedule entry activation
def schedule_activation(schedule_entry):
    print('Activating {}'.format(repr(schedule_entry)))

js8call = pyjs8call.Client()
# set schedule activation callback
js8call.callbacks.schedule = schedule_activation
js8call.start()

# return to the current configuration later
js8call.schedule.add('14:00')
# change configuration profile and set frequency and modem speed
js8call.schedule.add('8:00', 7078000, 'normal', 'QDX')
# change frequency only
js8call.schedule.add('9:00', 7074000)
# remove schedule entry
js8call.schedule.remove('9:00')

# print formatted information for each schedule entry
for entry in js8call.schedule.get_schedule():
    print(str(entry))
```

Set config file settings:
```
import pyjs8call

js8call = pyjs8call.Client()

# set config file settings before starting
# see pyjs8call.settings for many more settings options
js8call.settings.enable_heartbeat_acknowledgements()
js8call.settings.set_heartbeat_interval(15)
js8call.settings.enable_reporting()
js8call.settings.set_speed('normal')

js8call.start()
```

Utilize grid distance and bearing:
```
import pyjs8call

js8call = pyjs8call.Client()
js8call.start()

# use built-in spot distance filter
regional_stations = [spot.origin for spot in js8call.spots.filter(distance = 500)]
for station in regional_stations:
    print('{}: {} {} at {}\N{DEGREE SIGN}'.format(station.origin, station.distance, station.distance_units, station.bearing))

# access message attributes directly
# this requires the message to contain grid square data (ex. heartbeat message)
last_heartbeat = js8call.spots.filter(destination='@HB', count=1)[-1]
distance = last_heartbeat.distance
bearing = last_heartbeat.bearing

# manually calculate distance and bearing from local station
distance, distance_units, bearing = js8call.grid_distance('FM16')

# manually calculate distance and bearing between grid squares
distance, distance_units, bearing = js8call.grid_distance('FM16fq', 'EM19ub')
```

Using propagation data:
```
from datetime import datetime
import pyjs8call

js8call = pyjs8call.Client()
js8call.start()

# allow some time to capture spots
# note: default maximum spot age is 7 days

# get SNR data for each spotted grid square in the last 30 minutes
js8call.propagation.grids_dataset()

# get median SNR data for each unique grid square spotted in the last hour
js8call.propagation.grids_median_dataset(60)

# get median SNR data for each unique origin callsign spotted from 8pm to 10pm yesterday
now = datetime.now()
start = datetime(now.year, now.month, now.day - 1, hour = 20)
end = datetime(now.year, now.month, now.day - 1, hour = 22)
js8call.propagation.origins_median_dataset(start_time = start, end_time = end)

# get the median SNR of a specific origin callsign spotted over the last 2 hours
js8call.propagation.origin_median_snr(120)
```

Implementing custom commands:
```
import pyjs8call

# custom command callback function
def news_cmd(msg):
    # do not respond in the following cases:
    if (
        js8call.settings.autoreply_confirmation_enabled() or
        not js8call.msg_is_to_me(msg) or # not directed to local station or configured group
        msg.text in (None, '') # message text is empty
    ):
        return

    # read latest news from file
    with open('latest_news.txt', 'r') as fd:
        news = fd.read()

    # respond to origin station with directed message
    js8call.send_directed_message(msg.origin, news)

js8call = pyjs8call.Client()
js8call.start()

# set custom command callback
# note the leading space in the command string
js8call.callback.register_command(' NEWS?', news_cmd)
```

Configuring email notifications:
```
import pyjs8call
js8call = pyjs8call.Client()
js8call.start()

# set SMTP server credentials
js8call.notifications.set_smtp_credentials('email.address@gmail.com', 'app_password')
# set destination email address to a Verzion mobile number
js8call.notifications.set_email_destination('2018675309@vtext.com')
# enable automatic notifications for incoming directed messages
js8call.notifications.enable()

# set stations to watch
js8call.spots.add_station_watch('KT7RUN')
# enable station spot notifications
js8call.notifications.enable_station_spots()

# set groups to watch
js8call.spots.add_group_watch('@TTP')
# enable station spot notifications
js8call.notifications.enable_group_spots()
```

&nbsp;

### Acknowledgements

Inspired by [js8net](https://github.com/jfrancis42/js8net) by N0GQ<br>
[JS8Call](http://js8call.com) by KN4CRD

&nbsp;

