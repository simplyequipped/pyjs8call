A Python package that interfaces with the JS8Call API.

&nbsp;

### Documentation

See the official [pyjs8call documentation](https://simplyequipped.github.io/pyjs8call).

See a simple example in the *example.py* file at the top level of the repo.

&nbsp;  

### Installation

1. Install JS8Call. For example, on Raspberry Pi OS:
    
    ```
    wget http://files.js8call.com/2.2.0/js8call_2.2.0_armhf.deb
    sudo dpkg -i js8call_2.2.0_armhf.deb
    ```
    
    See the [JS8Call downloads](http://files.js8call.com/latest.html) page for OS-specific packages as well as source files. If you are compiling from source for Linux be sure to read the INSTALL file at the top level of the JS8Call repo.

2. Install pyjs8call using pip3 (or pip if python3 is the default on your system):
    
    ```
    pip3 install pyjs8call
    ```

3. Launch JS8Call to configure audio and CAT interface settings. Launching the application and exiting normally will initilize the configuration file.

&nbsp;

### Modules

Some setup (i.e. setting callback functions) is required to used certain module features. Most modules are initialized automatically by pyjs8call.client.

**Client** (pyjs8call.client)

The main JS8Call API interface. Includes many functions for reading and writting settings as well as sending various types of messages.

**JS8Call** (pyjs8call.js8call)

Manages TCP socket communication with the JS8Call application.

**Application Monitor** (pyjs8call.appmonitor)

Manages the start and stop of the JS8Call application, as well as the restarting of the application if closed. 

**Configuration Handler** (pyjs8call.confighandler)

Reads from and writes to the JS8Call.ini config file to change virtually any setting, including creating and activating configuration profiles. **Specific knowledge of configuration file options is required. Configuring options incorrectly may cause the JS8Call application to not run.**

**Spot Monitor** (pyjs8call.spotmonitor)

Monitors recent station spots. Spot data can be queried for various uses, and spot callbacks can be set for all heard stations and/or for specific stations.

**Window Monitor** (pyjs8call.windowmonitor)

Monitors the next rx/tx window transition. JS8Call API messages associated with incoming and outgoing messages are used to determine the start or end of a window, and the modem speed setting is used to determine the duration of the window. Notification of a window transition is handled via callback function.

**Offset Monitor** (pyjs8call.offsetmonitor)

Manages JS8Call offset frequency based on activity in the pass band. The offset frequency is automatically moved to an unsed portion of the pass band if a recently heard signal overlaps with the current offset. Signal bandwidth is calculated based on the modem speed of each heard signal. Only decoded signal data is available from the JS8Call API so other QRM cannot be handled.

**TX Monitor** (pyjs8call.txmonitor)

Monitors JS8Call tx text for queued outgoing messages. Notification of a message status change is handled via callback function.

**Heartbeat Monitor** (pyjs8call.hbmonitor)

Sends a heartbeat message on a time interval.

**Time Monitor** (pyjs8call.timemonitor)

Monitors a group, station, or all activity for time drift data and synchronizes local time drift. Enable automatic synchronization to the specified source on a time interval. Synchronizes to the @TIME group by default.

Time master functionality is also implemented which sends outgoing messages on a time interval that other stations can use to synchronize their time drift. Targets the @TIME group by default.

**Inbox Monitor** (pyjs8call.inboxmonitor)

Monitors the local inbox. Notification of new messages is handled via callback function.

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

# see who is hearing who in the last hour
js8call.hearing()

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
```

Using the spot monitor:
```
import pyjs8call

# callback function for all new spots
def new_spots(spots):
    for spot in spots:
        print('Spotted ' + spot.origin + ' with a ' + str(spot.snr) + 'dB SNR')
    
# callback function for watched station spots
def station_spotted(spot):
    print(spot.origin + ' spotted!')

# callback function for watched group spots
def group_spotted(spot):
    print(spot.destination + ' spotted!')
    
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
js8call.spots.add_group_watch('@AMMRON')
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

# enable local inbox monitoring and periodic remote inbox message query
js8call.inbox.enable()
```

Using the tx monitor:
```
import pyjs8call

# callback function for message status change
def tx_status(msg):
    print('Message ' + msg.id + ' status: ' + msg.status)
    
js8call = pyjs8call.Client()
# set tx monitor callback
js8call.callback.outgoing = tx_status
js8call.start()

# monitor directed message tx automatically (default)
js8call.send_directed_message('OH8STN', 'Thanks for the great content')

# monitor outgoing message manually
js8call.monitor_outgoing = False
msg = js8call.send_directed_message('KT7RUN', 'Thanks for the great content')
js8call.outgoing.monitor(msg)
```

Set config file settings:
```
import pyjs8call

js8call = pyjs8call.Client()
# set config file settings before starting
js8call.settings.enable_heartbeat_acknowledgements()
js8call.settings.enable_reporting()
js8call.settings.set_speed('normal')
js8call.start()
```

&nbsp;

### Acknowledgements

Inspired by [js8net](https://github.com/jfrancis42/js8net) by N0GQ.

[JS8Call](http://js8call.com) by KN4CRD

&nbsp;

