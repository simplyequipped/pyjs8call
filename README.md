# pyjs8call

A Python package for interfacing with the JS8Call API. The package includes a spot monitor which utilizes callback functions to receive new spot information and/or to watch for a specific stations callsign, as well as an application monitor that will start the JS8Call application automatically if needed. See the below examples, the code in example.py, and the code in pyjs8call/modem.py for more information.

The following modules are loaded and enabled by default. Some setup (ex. setting callback functions) is required to used certain features.


**Application Monitor**

Manage the startup of the JS8Call application (if needed), as well as the restarting of the application if it is closed. 

**JS8Call Configuration Handler**

Read from and write to the JS8Call.ini config file to change virtually any setting, including creating and activating conf8guration profiles. Specific knowledge of the configuration file options is required. Setting options incorrectly can cause JS8Call to fail to start.

**Station Spot Monitor**

Store heard station data. Spot data can be queried for various uses, and spot callbacks can be set for all heard stations or for specific stations.

**TX Window Monitor**

Monitor tx frames to calculate the beginning and end of the transmit window.

**Offset Monitor**

Monitor recent activity and automatically move the offset frequency to an unsed portion of the pass band if a heard signal overlaps with the current offset. Signal bandwidth is calculated based on the speed of each heard signal. Only decoded signal data is available from JS8Call, so other QRM cannot be handled.

**TX Monitor**

Monitor the JS8Call transmit text box for provided messaged. Notification of a completed message transmission is handled by callback function.

### Examples

Basic usage:
```
import pyjs8call

# use default host, port (127.0.0.1:2442)
client = pyjs8call.Client()

# set frequency and offset
freq = client.set_freq(7078000)
offset = client.set_offset(1500)
print('Frequency: ' + str(freq))
print('Offset: ' + str(offset))

# get inbox messages
inbox = client.get_inbox_messages()
for message in inbox:
  print(message)

# send a directed message
client.send_directed_message('N0GQ', 'Thanks for your work on js8net')
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
    
client = pyjs8call.Client()

# set spot monitor callback
client.spot_monitor.set_new_spot_callback(new_spots)
# set station watcher callback
client.spot_monitor.set_watch_callback(station_spotted)

# watch multiple stations
client.spot_monitor.add_station_watch('N0GQ')
client.spot_monitor.add_station_watch('K6ARK')

# remove a station watcher, no hard feelings Adam :)
client.spot_monitor.remove_station_watch('K6ARK')
```

### Acknowledgements

Inspired by [js8net](https://github.com/jfrancis42/js8net) by N0GQ.
