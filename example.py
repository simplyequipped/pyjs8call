import time
import pyjs8call

# callback for received messages
def rx_message(msg):
    print('\t--- Message from ' + str(msg['from']) + ': ' + str(msg['text']))

# callback for all new spots
def new_spots(spots):
    for spot in spots:
        if spot['grid'] == '':
            grid = ' '
        else:
            grid = ' (' + str(spot['grid']) + ') '

        print('\t--- Spot: ' + str(spot['from']) + grid + '@ ' + str(spot['offset']) + ' Hz\t' + time.strftime('%x %X', time.localtime(spot['time'])))

# function for sending a directed message
def send_message():
    global client
    dest = input('\n\tEnter destination callsign: ')
    msg = input('\tEnter message: ')
    client.send_directed_message(dest, msg)
    print('\n\tSending message on next transmit cycle\n')

# function for showing inbox messages
def show_inbox():
    global client
    messages = client.get_inbox_messages()
    print('\n--- Inbox Messages: ' + str(len(messages)))

    if len(messages) > 0:
        print('')
        for msg in messages:
            print('\tFrom: ' + str(msg['from']) + '\t\tTo: ' + str(msg['to']) + '\t\tPath: ' + str(msg['path']))
            print('\tDate/Time (UTC): ' + str(msg['time']))
            print('\tMessage: ' + str(msg['message']))
            print('')
    else:
        print('')

# function for printing the menu and handling selections
def show_menu():
    menu =  '\n---------------  Menu  ---------------'
    menu += '\n   m)     Send message'
    menu += '\n   i)     Inbox messages'
    menu += '\n   x)     Exit'
    menu += '\n   Enter) Show menu'
    menu += '\n\nType a menu option and press enter: '

    user_input = input(menu)

    if user_input == 'm':
        send_message()
    if user_input == 'i':
        show_inbox()
    if user_input == 'x':
        global client
        client.stop()
        exit()


# initialize the client object and start the js8call application
client = pyjs8call.Client()
# set callback functions
client.set_rx_callback(rx_message)
client.spot_monitor.set_new_spot_callback(new_spots)

# read current configuration values
freq = client.get_freq()
offset = client.get_offset()
grid = client.get_station_grid()
callsign = client.get_station_callsign()
# check if connected to js8call
connected = client.js8call_connected()

# parse connected state
if connected:
    state = 'Connected'
else:
    state = 'Disconnected'

# print a summary of this station
print('\nStation ' + callsign + ' (' + grid + ') - ' + state + ' ---------------------------------------------')
print('Frequency: ' + str(freq / 1000000).format('0.000') + 'MHz (' + str(offset) + 'Hz)\n')

# show the menu until the user exits
while client.online:
    show_menu()    
