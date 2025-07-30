import re
import requests
import pyjs8call
import us


# send short-form weather forecast based on given grid square
def cmd_wx(msg):
    try:
        cmd, grid = msg.text.strip().split()
    except ValueError:
        # no grid square given
        return

    lat, lon = js8call.grid_to_lat_lon(grid)
    location = get_location_name(lat, lon)

    points_data = requests.get(f'https://api.weather.gov/points/{lat},{lon}').json()
    forecast_url = points_data['properties']['forecast']
    stations_url = points_data['properties']['observationStations']

    station_id = requests.get(stations_url).json()['features'][0]['properties']['stationIdentifier']
    observations_url = f'https://api.weather.gov/stations/{station_id}/observations/latest'
    observations = requests.get(observations_url).json()['properties']

    temp_c = int(round(observations['temperature']['value']))
    temp_f = round(temp_c * 9/5 + 32) if temp_c is not None else '??'
    conditions = observations['textDescription']

    forecast = requests.get(forecast_url).json()['properties']['periods']
    today = None
    tonight = None
    tomorrow = None
    tomorrow_night = None

    if forecast[0]['name'].lower() == 'today':
        today = forecast[0]
    elif forecast[0]['name'].lower() in ('tonight', 'overnight'):
        tonight = forecast[0]

    if forecast[1]['name'].lower() in ('tonight', 'overnight'):
        tonight = forecast[1]

    if today is None:
        tomorrow = forecast[1]
        tomorrow_night = forecast[2]
    else:
        tomorrow = forecast[2]
        tomorrow_night = forecast[3]
    
    wx_now = f'{location}: {temp_f}F, {shorten_conditions(conditions)}'
    wx_today = f'Today: {today["temperature"]}F, {today["probabilityOfPrecipitation"]["value"]}%, {shorten_conditions(today["shortForecast"])}' if today is not None else None
    wx_tonight = f'Tonight: {tonight["temperature"]}F, {tonight["probabilityOfPrecipitation"]["value"]}%, {shorten_conditions(tonight["shortForecast"])}' if tonight is not None else None
    wx_tomorrow = f'{tomorrow["name"][0:3]}: {tomorrow["temperature"]}F, {tomorrow["probabilityOfPrecipitation"]["value"]}%, {shorten_conditions(tomorrow["shortForecast"])}'
    wx_tomorrow_night = f'{tomorrow["name"][0:3]} Night: {tomorrow_night["temperature"]}F, {tomorrow_night["probabilityOfPrecipitation"]["value"]}%, {shorten_conditions(tomorrow_night["shortForecast"])}'

    lines = [wx_now, wx_today, wx_tonight, wx_tomorrow, wx_tomorrow_night]
    lines = [line for line in lines if line is not None]
    wx = '\n'.join(lines)

    # send message with weather forecast
    js8call.send_directed_message(msg.origin, wx)

# send long-form weather forecast based on given grid square
def cmd_wxl(msg):
    try:
        cmd, grid = msg.text.strip().split()
    except ValueError:
        # no grid square given
        return

    lat, lon = js8call.grid_to_lat_lon(grid)
    location = get_location_name(lat, lon)

    points_data = requests.get(f'https://api.weather.gov/points/{lat},{lon}').json()
    forecast_url = points_data['properties']['forecast']
    forecast = requests.get(forecast_url).json()['properties']['periods']
    today = None
    tonight = None
    tomorrow = None
    tomorrow_night = None
    
    if forecast[0]['name'].lower() == 'today':
        today = forecast[0]
    elif forecast[0]['name'].lower() in ('tonight', 'overnight'):
        tonight = forecast[0]

    if forecast[1]['name'].lower() in ('tonight', 'overnight'):
        tonight = forecast[1]

    if today is None:
        tomorrow = forecast[1]
        tomorrow_night = forecast[2]
    else:
        tomorrow = forecast[2]
        tomorrow_night = forecast[3]
    
    wx_today = f'Today: {today["detailedForecast"]}' if today is not None else None
    wx_tonight = f'Tonight: {tonight["detailedForecast"]}' if tonight is not None else None
    wx_tomorrow = f'{tomorrow["name"][0:3]}: {tomorrow["detailedForecast"]}'
    wx_tomorrow_night = f'{tomorrow["name"][0:3]} Night: {tomorrow_night["detailedForecast"]}'

    lines = [location, wx_today, wx_tonight, wx_tomorrow, wx_tomorrow_night]
    lines = [line for line in lines if line is not None]
    wxl = '\n'.join(lines)

    # send message with weather forecast
    js8call.send_directed_message(msg.origin, wxl)

# send weather synopsis based on given grid square
def cmd_wxs(msg):
    try:
        cmd, grid = msg.text.strip().split()
    except ValueError:
        # no grid square given
        return

    lat, lon = js8call.grid_to_lat_lon(grid)
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

    # send message with weather forecast
    js8call.send_directed_message(msg.origin, synopsis)

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
js8call.callback.register_command(' WX', cmd_wx)
js8call.callback.register_command(' WXL', cmd_wxl)
js8call.callback.register_command(' WXS', cmd_wxs)
js8call.start()

# simulate received requests for each weather command
#msg = pyjs8call.Message(destination='ABC123', cmd=' WX', value=' WX EM19ES', origin='CBA321')
#msg.set('type', pyjs8call.Message.RX_DIRECTED)
#js8call.js8call.append_to_rx_queue(msg)
#
#msg = pyjs8call.Message(destination='ABC123', cmd=' WXL', value=' WXL EM19ES', origin='CBA321')
#msg.set('type', pyjs8call.Message.RX_DIRECTED)
#js8call.js8call.append_to_rx_queue(msg)
#
#msg = pyjs8call.Message(destination='ABC123', cmd=' WXS', value=' WXS EM19ES', origin='CBA321')
#msg.set('type', pyjs8call.Message.RX_DIRECTED)
#js8call.js8call.append_to_rx_queue(msg)

input('Press enter to exit')
