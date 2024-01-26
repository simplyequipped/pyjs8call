import sys
import time
import pyjs8call

# callback for received directed messages (includes groups such as @HB)
def rx_message(msg):
    print('\t--- Message from {}: {}'.format(msg.origin, msg.text))

# callback for new spots
def new_spots(spots):
    for spot in spots:
        if spot.grid in (None, ''):
            grid = ' '
        else:
            grid = ' (' + spot.grid + ') '

        print('\t--- Spot: {}{}@ {} Hz\t{}L'.format(spot.origin, grid, spot.offset, time.strftime('%x %X', time.localtime(spot.timestamp))))

# callback for tx monitor status change
def tx_status(msg):
    print('\tMessage {} status: {}'.format(msg.id, msg.status))
    
# callback for new inbox messages
def new_inbox_msg(msgs):
    for msg in msgs:
        print('\t--- New inbox message from {}'.format(msg['origin']))

# function to send a directed message
def send_message():
    global js8call
    destination = input('\n\tEnter destination callsign: ')
    text = input('\tEnter message: ')
    msg = js8call.send_directed_message(destination, text)
    print('\n\tSending message {} on next transmit cycle'.format(msg.id))
    input()

# function to show JS8Call inbox messages
def show_inbox():
    global js8call
    messages = js8call.get_inbox_messages()
    print('\n--- Inbox Messages: {}'.format(len(messages)))

    if len(messages) > 0:
        print('')
        for msg in messages:
            print('\tFrom: {}\t\tTo: {}\t\tPath: {}'.format(msg.origin, msg.destination, msg.path))
            print('\tData/Time: {}'.format(time.strftime('%c', msg.timestamp)))
            print('\tMessage: {}\n'.format(msg.text))
    else:
        print('')

# function to set JS8Call dial frequency
def set_freq():
    global js8call
    new_freq = input('\n\tEnter new dial frequency in Hz: ')
    freq = js8call.settings.set_freq(new_freq) / 1000000
    offset = js8call.settings.get_offset()
    print('\nNew dial frequency: {:.3f} MHz ({} Hz offset)'.format(freq, offset))

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

# run JS8Call headless
if '--headless' in sys.argv:
    headless = True
else:
    headless = False

# initialize the client object and start the js8call application
js8call = pyjs8call.Client()
# set callback functions
js8call.callback.register_incoming(rx_message)
js8call.callback.register_spots(new_spots)
js8call.callback.outgoing = tx_status
js8call.callback.inbox = new_inbox_msg
js8call.start(headless = headless)

# read current configuration values
freq = js8call.settings.get_freq() / 1000000
offset = js8call.settings.get_offset()
grid = js8call.settings.get_station_grid()
callsign = js8call.settings.get_station_callsign()
# check if connected to js8call
connected = js8call.connected()

# parse connected state
if connected:
    state = 'Connected'
else:
    state = 'Disconnected'

# print a summary of this station
print('\nStation {} ({}) - {}  ---------------------------------------------'.format(callsign, grid, state))
print('Frequency: {:.3f} MHz ({} Hz offset)'.format(freq, offset))

# show the menu until the user exits
while js8call.online:
    show_menu()

