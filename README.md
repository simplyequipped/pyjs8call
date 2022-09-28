# pyjs8call

A Python library for interfacing with the JS8Call API. See the code in js8call-interface/modem.py for more information.

### Examples

Basic usage:
```
import pyjs8call

# use default host, port
modem = pyjs8call.Modem()
# set frequency and offset
freq = modem.set_freq(7078000, 1500)
print(freq)

# get inbox messages
inbox = modem.get_inbox_messages()
print(inbox)

# send directed message
modem.send_directed_message('N0GQ', 'Thanks for your work on js8net')
```

Using the spot monitor:
```
import pyjs8call

def new_spots(spots):
  for spot in spots:
    print('Spotted ' + spot['from] + ' with a ' + str(spot['snr']) + 'dB SNR')
    
def station_spotted(spot):
  print(spot['from'] + ' spotted!')
    
modem = pyjs8call.Modem()
# set spot monitor callback
modem.spot_monitor.set_new_spot_callback(new_spots)
# set station watcher callback
modem.spot_monitor.set_watch_callback(station_spotted)
modem.spot_monitor.add_station_watch('N0GQ')
```

### Acknowledgements

Based on the excellent work found in [js8net](https://github.com/jfrancis42/js8net) by N0GQ.
