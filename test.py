import time
import pyjs8call

def rx_message(msg):
    print('\t--- Message from ' + str(msg['from']) + ': ' + str(msg['text']))

def new_spots(spots):
    global modem
    for spot in spots:
        if spot['grid'] == '':
            grid = ' '
        else:
            grid = ' (' + str(spot['grid']) + ') '

        print('\t--- Spot: ' + str(spot['from']) + grid + '@ ' + str(spot['offset']) + ' Hz\t' + time.strftime('%x %X', time.localtime(spot['time'])))

def send_message():
    global modem
    dest = input('\n\tEnter destination callsign: ')
    msg = input('\tEnter message: ')
    modem.send_directed_message(dest, msg)
    print('\n\tSending message on next transmit cycle\n')

def show_inbox():
    global modem
    messages = modem.get_inbox_messages()
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
        exit()




modem = pyjs8call.Modem()
#modem.js8call._debug = True
modem.set_rx_callback(rx_message)
modem.spot_monitor.set_new_spot_callback(new_spots)

freq = modem.get_freq()
offset = modem.get_offset()
grid = modem.get_station_grid()
callsign = modem.get_station_callsign()
connected = modem.js8call_connected()

if connected:
    state = 'Connected'
else:
    state = 'Disconnected'

print('\nStation ' + callsign + ' (' + grid + ') - ' + state + ' ---------------------------------------------')
print('Frequency: ' + str(freq / 1000000).format('0.000') + 'MHz (' + str(offset) + 'Hz)\n')

while modem.online:
    show_menu()    










