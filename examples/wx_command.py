import re
import requests
import pyjs8call
import us


# send weather forecast for specified grid square
def cmd_wx(msg):
    # only respond to messages directed to local station
    if not msg.is_directed_to(js8call.settings.get_station_callsign()):
        return
    
    grid = None # grid square like EM19ES
    num_days = 1 # number of days after today/tonight
    synopsis = False # whether to return synopsis instead of forecast
    
    try:
        msg_parts = msg.text.strip().split()
        if len(msg_parts) == 2:
            # ex. ' WX EM19ES'
            grid = msg_parts[1]
        elif len(msg_parts) == 3:
            # ex. ' WX EM19ES 3'
            grid = msg_parts[1]

            if msg_parts[2].isnumeric():
                num_days = int(msg_parts[2])
                num_days = min(num_days, 5) # 5 days max
            else:
                # any value after grid square that is not an integer will result in synopsis
                synopsis = True
        else:
            # ignore incorrect message structure
            return
    except:
        # ignore incorrect message structure
        return

    lat, lon = js8call.grid_to_lat_lon(grid)

    if synopsis:
        forecast = get_area_synopsis(lat, lon)
    else:
        forecast = get_forecast(lat, lon, num_days)
        
    # send message with weather forecast
    js8call.send_directed_message(msg.origin, forecast)

# get day/night forecasts for given coordinates
def get_forecast(lat, lon, num_days):
    location = get_location_name(lat, lon)
    
    points_data = requests.get(f'https://api.weather.gov/points/{lat},{lon}').json()
    forecast_url = points_data['properties']['forecast']
    forecast = requests.get(forecast_url).json()['properties']['periods']
    stations_url = points_data['properties']['observationStations']
    station_id = requests.get(stations_url).json()['features'][0]['properties']['stationIdentifier']
    observations_url = f'https://api.weather.gov/stations/{station_id}/observations/latest'
    observations = requests.get(observations_url).json()['properties']
    temp_c = int(round(observations['temperature']['value']))
    temp_f = round(temp_c * 9/5 + 32) if temp_c is not None else '??'
    conditions = observations['textDescription']

    forecasts = []
    day_start_index = 1

    def build_forecast(forecast):
        name = forecast['name']
        temp = forecast["temperature"]
        precip = forecast["probabilityOfPrecipitation"]["value"]
        conditions = shorten_conditions(forecast["shortForecast"])

        if name.lower() not in ['today', 'tonight', 'overnight']:
            # convert days like "Sunday" to "Sun"
            name_parts = name.split()
            name = name_parts[0][0:3]
            if len(name_parts) > 1:
                name += name_parts[1]
        
        return f'{name}: {precip}%, {conditions}'

    # location and current conditions
    forecasts.append(f'{location}: {temp_f}F, {shorten_conditions(conditions)}')
    # today, tonight, or overnight forecast
    forecasts.append(build_forecast(forecast[0]))

    # handle case where both 'today' and 'tonight' are included in forecast
    if forecast[1]['name'].lower() in ('tonight', 'overnight'):
        forecasts.append(build_forecast(forecast[1]))
        day_start_index = 2

    # days forecasts
    for i in range(day_start_index, day_start_index + (num_days * 2)):
        forecasts.append(build_forecast(forecast[i]))
    
    return '\n'.join(forecasts)

# get area weather synopsis for given coordinates
def get_area_synopsis(lat, lon):
    location = get_location_name(lat, lon)
    
    points_data = requests.get(f'https://api.weather.gov/points/{lat},{lon}').json()
    office = points_data['properties']['forecastOffice'].split('/')[-1]
    afd = requests.get(f'https://api.weather.gov/products/types/AFD/locations/{office}').json()
    latest_id = afd['@graph'][0]['@id']
    afd_text = requests.get(latest_id).json()['productText']
    
    match = re.search(r'\.SYNOPSIS\.\.\.\n(.*?)(?:\n\n|\.\w)', afd_text, re.DOTALL)
    synopsis = '\n' + ' '.join(match.group(1).split()) + '.' if match else None
    if synopsis is not None and '* ' in synopsis:
        # convert bullet points to sentences
        bullets = synopsis.split('* ')
        bullets = [bullet.strip() for bullet in bullets if len(bullet) > 1]
        synopsis = '\n' + '. '.join(bullets)

    return '\n'.join([location, synopsis])

def shorten_conditions(forecast):
    forecast = forecast.lower()

    forecast = forecast.replace('showers and thunderstorms', 't-storms')
    forecast = forecast.replace('rain and thunderstorms', 't-storms')
    forecast = forecast.replace('rain showers', 'rain')

    forecast = forecast.replace('of', '')
    forecast = forecast.replace('mostly', '')
    forecast = forecast.replace('likely', '')
    forecast = forecast.replace('slight', '')
    forecast = forecast.replace('patchy', '')
    forecast = forecast.replace('isolated', '')
    forecast = forecast.replace('scattered', '')
    forecast = forecast.replace('chance', '')

    forecast = forecast.replace('sunny', 'sun')
    forecast = forecast.replace('partly', 'part')
    forecast = forecast.replace('thunderstorms', 't-storms')
    forecast = forecast.replace('blustery', 'wind')
    forecast = forecast.replace('showers', 'rain')

    forecast = forecast.replace('  ', ' ')

    return forecast.strip()

def get_location_name(lat, lon):
    params = {
        'lat': lat,
        'lon': lon,
        'format': 'json',
        'zoom': 10,
        'addressdetails': 1
    }

    location = requests.get('https://nominatim.openstreetmap.org/reverse', params=params, headers={'User-Agent': 'pyjs8call-wx'}).json()
    city = location['name']
    state = us.states.lookup(location ['address']['state']).abbr
    return f'{city}, {state}'



# init js8call client and register wx commands
js8call = pyjs8call.Client()
js8call.callback.register_command(' WX?', cmd_wx)
js8call.start()

# simulate received weather command
#msg = pyjs8call.Message(destination='ABC123', cmd=' WX?', value=' WX? EM19ES', origin='CBA321')
#msg.set('type', pyjs8call.Message.RX_DIRECTED)
#js8call.js8call.append_to_rx_queue(msg)
#
# simulate received weather command for 3 days
#msg = pyjs8call.Message(destination='ABC123', cmd=' WX?', value=' WX? EM19ES 3', origin='CBA321')
#msg.set('type', pyjs8call.Message.RX_DIRECTED)
#js8call.js8call.append_to_rx_queue(msg)
#
# simulate received weather command for synopsis
#msg = pyjs8call.Message(destination='ABC123', cmd=' WX?', value=' WX? EM19ES DETAIL', origin='CBA321')
#msg.set('type', pyjs8call.Message.RX_DIRECTED)
#js8call.js8call.append_to_rx_queue(msg)

input('Press enter to exit')
