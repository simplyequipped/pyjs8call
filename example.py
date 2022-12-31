import time
import pyjs8call

# callback for received directed messages (includes groups such as @HB)
def rx_message(msg):
    print('\t--- Message from ' + str(msg.origin) + ': ' + str(msg.text))

# callback for new spots
def new_spots(spots):
    for spot in spots:
        if spot.grid == '':
            grid = ' '
        else:
            grid = ' (' + spot.grid + ') '

        print('\t--- Spot: ' + spot.origin + grid + '@ ' + str(spot.offset) + ' Hz\t' + time.strftime('%x %X', spot.timestamp))

# callback for tx monitor status change
def tx_status(msg):
    print('\n\tMessage ' + msg.id + ' status: ' + msg.status)

# function to send a directed message
def send_message():
    global js8call
    destination = input('\n\tEnter destination callsign: ')
    text = input('\tEnter message: ')
    msg = js8call.send_directed_message(destination, text)
    print('\n\tSending message ' + msg.id + ' on next transmit cycle\n')

# function to show JS8Call inbox messages
def show_inbox():
    global js8call
    messages = js8call.get_inbox_messages()
    print('\n--- Inbox Messages: ' + str(len(messages)))

    if len(messages) > 0:
        print('')
        for msg in messages:
            print('\tFrom: ' + msg.origin + '\t\tTo: ' + msg.destination + '\t\tPath: ' + msg.path)
            print('\tDate/Time: ' + time.strftime('%c', msg.timestamp))
            print('\tMessage: ' + msg.text)
            print('')
    else:
        print('')

# function to set JS8Call dial frequency
def set_freq():
    global js8call
    new_freq = input('\n\tEnter new dial frequency in Hz: ')
    freq = js8call.set_freq(new_freq)
    print('\nNew dial frequency: ' + str(freq / 1000000).format('0.000') + ' MHz (' + str(offset) + ' Hz)\n')

# function for printing the menu and handling selections
def show_menu():
    menu =  '\n---------------  Menu  ---------------'
    menu += '\n   m)     Send directed message'
    menu += '\n   i)     Show inbox messages'
    menu += '\n   f)     Set new dial frequency'
    menu += '\n   x)     Exit'
    menu += '\n   Enter) Show menu'
    menu += '\n\nType a menu option and press enter: '

    user_input = input(menu)

    if user_input == 'm':
        send_message()
    if user_input == 'i':
        show_inbox()
    if user_input == 'f':
        set_freq()
    if user_input == 'x':
        global js8call
        js8call.stop()
        exit()


# initialize the client object and start the js8call application
js8call = pyjs8call.Client()
js8call.start()
# set callback functions
js8call.callback.register_incoming(rx_message)
js8call.callback.spots = new_spots
js8call.callback.outgoing = tx_status

# read current configuration values
freq = js8call.get_freq()
offset = js8call.get_offset()
grid = js8call.get_station_grid()
callsign = js8call.get_station_callsign()
# check if connected to js8call
connected = js8call.connected()

# parse connected state
if connected:
    state = 'Connected'
else:
    state = 'Disconnected'

# print a summary of this station
print('\nStation ' + callsign + ' (' + grid + ') - ' + state + ' ---------------------------------------------')
print('Frequency: ' + str(freq / 1000000).format('0.000') + ' MHz (' + str(offset) + ' Hz)\n')

# show the menu until the user exits
while js8call.online:
    show_menu()

