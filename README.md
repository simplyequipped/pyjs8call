# pyjs8call

A Python package for interfacing with the JS8Call API. The package includes a spot monitor which utilizes callback functions to receive new spot information and/or to watch for a specific stations callsign, as well as an application monitor that will start the JS8Call application automatically if needed. See the below examples, the code in example.py, and the code in pyjs8call/modem.py for more information.

### Examples

Basic usage:
```
import pyjs8call

# use default host, port (127.0.0.1:2442)
modem = pyjs8call.Modem()

# set frequency and offset
freq = modem.set_freq(7078000)
offset = modem.set_offset(1500)
print('Frequency: ' + str(freq))
print('Offset: ' + str(offset))

# get inbox messages
inbox = modem.get_inbox_messages()
for message in inbox:
  print(message)

# send a directed message
modem.send_directed_message('N0GQ', 'Thanks for your work on js8net')
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
    
modem = pyjs8call.Modem()

# set spot monitor callback
modem.spot_monitor.set_new_spot_callback(new_spots)
# set station watcher callback
modem.spot_monitor.set_watch_callback(station_spotted)

# watch multiple stations
modem.spot_monitor.add_station_watch('N0GQ')
modem.spot_monitor.add_station_watch('K6ARK')

# remove a station watcher, no hard feelings Adam :)
modem.spot_monitor.remove_station_watch('K6ARK')
```

### Acknowledgements

Based on the excellent work found in [js8net](https://github.com/jfrancis42/js8net) by N0GQ.
