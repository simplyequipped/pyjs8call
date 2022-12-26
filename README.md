A Python package that interfaces with the JS8Call API.

&nbsp;  

### Modules

The following modules are loaded and enabled by default. Some setup (i.e. setting callback functions) is required to used certain features.

**Client** (pyjs8call.client)

The main interface to the JS8Call application. Includes many functions for reading and writting settings as well as sending various types of messages.

**Application Monitor** (pyjs8call.appmonitor)

Manage the startup of the JS8Call application (if needed), as well as the restarting of the application if closed. 

**JS8Call Configuration Handler** (pyjs8call.confighandler)

Read from and write to the JS8Call.ini config file to change virtually any setting, including creating and activating configuration profiles. Specific knowledge of the configuration file options is required. Configuring options incorrectly may cause the JS8Call application not to start.

**Station Spot Monitor** (pyjs8call.spotmonitor)

Store heard station data. Spot data can be queried for various uses, and spot callbacks can be set for all heard stations or for specific stations.

**TX Window Monitor** (pyjs8call.windowmonitor)

Monitor tx frames to calculate the beginning and end of the transmit window.

**Offset Monitor** (pyjs8call.offsetmonitor)

Monitor recent activity and automatically move the offset frequency to an unsed portion of the pass band if a heard signal overlaps with the current offset. Signal bandwidth is calculated based on the speed of each heard signal. Only decoded signal data is available from JS8Call, so other QRM cannot be handled.

**TX Monitor** (pyjs8call.txmonitor)

Monitor the JS8Call transmit text box for given messages. Notification of a completed message transmission is handled via callback function.

&nbsp;  

### Examples

Basic usage:
```
import pyjs8call

# use default host, port (127.0.0.1:2442)
js8call = pyjs8call.Client()
js8call.start()

# set frequency and offset
freq = js8call.set_freq(7078000)
offset = js8call.set_offset(1500)
print('Frequency: ' + str(freq))
print('Offset: ' + str(offset))

# get inbox messages
inbox = js8call.get_inbox_messages()
for message in inbox:
    print(message)

# send a directed message
js8call.send_directed_message('N0GQ', 'Thanks for your work on js8net')
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
    
js8call = pyjs8call.Client()
js8call.start()

# set spot monitor callback
js8call.spot_monitor.set_new_spot_callback(new_spots)
# set station watcher callback
js8call.spot_monitor.set_watch_callback(station_spotted)

# watch multiple stations
js8call.spot_monitor.add_station_watch('N0GQ')
js8call.spot_monitor.add_station_watch('K6ARK')

# remove a station watcher, no hard feelings Adam :)
js8call.spot_monitor.remove_station_watch('K6ARK')
```

Using the tx monitor:
```
import pyjs8call

# callback function for complete tx
def tx_status(msg):
    print('Message ' + msg.id + ' status: ' + msg.status)
    
js8call = pyjs8call.Client()
js8call.start()

# set tx monitor callback
js8call.tx_monitor.set_tx_status_change_callback(tx_status)

# monitor directed message tx automatically (default)
js8call.send_directed_message('OH8STN', 'Thanks for the great content')

# monitor message tx manually
js8call.monitor_directed_tx = False
msg = js8call.send_directed_message('KT1RUN', 'Thanks for the great content')
js8call.tx_monitor.monitor(msg)
```

&nbsp;

### Acknowledgements

Inspired by [js8net](https://github.com/jfrancis42/js8net) by N0GQ.

[JS8Call](http://js8call.com) by KN4CRD

