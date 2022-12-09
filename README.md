# pyjs8call

A Python package that interfaces with the JS8Call API to control the application. See the below examples, the code in example.py, and the code in pyjs8call/client.py for more information until additonal documentation is available.

The following modules are loaded and enabled by default. Some setup (i.e. setting callback functions) is required to used certain features.


**Application Monitor**

Manage the startup of the JS8Call application (if needed), as well as the restarting of the application if closed. 

**JS8Call Configuration Handler**

Read from and write to the JS8Call.ini config file to change virtually any setting, including creating and activating configuration profiles. Specific knowledge of the configuration file options is required. Configuring options incorrectly may cause the JS8Call application not to start.

**Station Spot Monitor**

Store heard station data. Spot data can be queried for various uses, and spot callbacks can be set for all heard stations or for specific stations.

**TX Window Monitor**

Monitor tx frames to calculate the beginning and end of the transmit window.

**Offset Monitor**

Monitor recent activity and automatically move the offset frequency to an unsed portion of the pass band if a heard signal overlaps with the current offset. Signal bandwidth is calculated based on the speed of each heard signal. Only decoded signal data is available from JS8Call, so other QRM cannot be handled.

**TX Monitor**

Monitor the JS8Call transmit text box for given messages. Notification of a completed message transmission is handled via callback function.

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
        print('Spotted ' + spot['from] + ' with a ' + str(spot['snr']) + 'dB SNR')
    
# callback function for watched station spots
def station_spotted(spot):
    print(spot['from'] + ' spotted!')
    
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

# callback function for complete transmissions
def tx_complete(msg):
    print('Message ' + msg.id + ' to ' + msg.destination + ' sent')
    
# callback function for failed transmissions
def tx_failed(msg):
    print('Message ' + msg.id + ' to ' + msg.destination + ' failed')
    
js8call = pyjs8call.Client()
js8call.start()

# set tx monitor callbacks
js8call.tx_monitor.set_tx_complete_callback(tx_complete)
js8call.tx_monitor.set_tx_failed_callback(tx_failed)

# monitor message tx manually
msg = js8call.send_directed_message('KT1RUN', 'Thanks for the great content')
js8call.tx_monitor.monitor(msg)

# monitor tx for directed messages automatically
js8call.monitor_directed_tx = True
js8call.send_directed_message('OH8STN', 'Thanks for the great content')
```

### Acknowledgements

Inspired by [js8net](https://github.com/jfrancis42/js8net) by N0GQ.

