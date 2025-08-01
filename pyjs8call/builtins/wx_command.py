# MIT License
# 
# Copyright (c) 2022-2025 Simply Equipped
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

'''Custom weather forecast command handling'''

__docformat__ = 'google'


import re
import requests

from pyjs8call import CustomCommand
import us


class WeatherCommand(CustomCommand)
    '''Custom command for location-specific weather forecasts and area synopsis.

    Note that only messages directed to the local station will be handled, and only if a callsign is *not* selected in the JS8Call application (active directed chat).
    
    Example JS8Call message requesting a weather forecast for today and tomorrow, and then for the next 3 days:
    ```
    ORIGIN:DEST WX? EM19ES
    ORIGIN:DEST WX? EM19ES 3
    ```
    
    To trigger an area synopsis instead of a forecast, include text characters after the grid square instead of a number. All of the following are acceptable:
    ```
    ORIGIN:DEST WX? EM19ES A
    ORIGIN:DEST WX? EM19ES AREA
    ORIGIN:DEST WX? EM19ES DETAIL
    ORIGIN:DEST WX? EM19ES SYNOPSIS
    ```

    4- and 6- character grid squares are currently supported in *pyjs8call*. 6-character grid squares will result in a more precise weather forecast.
    '''
    command = ' WX?' # note leading space
    
    # send weather forecast for specified grid square
    def process(self, pyjs8call_client, msg):
        '''Weather command processing and response.

        Args:
            pyjs8call_client (pyjs8call.client.Client): client object for interfacing with application (ex. sending response message)
            msg (pyjs8call.message.Message): received message object containing custom command
        '''
        # ignore if a callsign is selected on the js8call ui
        if self._client.get_selected_call() is not None:
            return
        
        # only respond if message is directed to local station
        if not msg.is_directed_to(js8call.settings.get_station_callsign()):
            return
        
        grid = None # grid square like EM19 or EM19ES
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
    
            lat, lon = pyjs8call_client.grid_to_lat_lon(grid)

            if synopsis:
                forecast = self._get_area_synopsis(lat, lon)
            else:
                forecast = self._get_forecast(lat, lon, num_days)
        except Exception:
            # ignore incorrect message structure and web api request errors
            return
            
        # send message with weather forecast
        pyjs8call_client.send_directed_message(msg.origin, forecast)

    def _get_forecast(self, lat, lon, num_days):
        location = self._get_location_name(lat, lon)
        
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

        # convenience / consistency function
        def build_forecast(forecast):
            name = forecast['name']
            temp = forecast["temperature"]
            precip = forecast["probabilityOfPrecipitation"]["value"]
            conditions = self._shorten_conditions(forecast["shortForecast"])
    
            if name.lower() not in ['today', 'tonight', 'overnight']:
                # convert days like "Sunday" to "Sun"
                name_parts = name.split()
                name = name_parts[0][0:3]
                if len(name_parts) > 1:
                    name += name_parts[1]
            
            return f'{name}: {precip}%, {conditions}'
    
        # location and current conditions
        forecasts.append(f'{location}: {temp_f}F, {self._shorten_conditions(conditions)}')
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
    def _get_area_synopsis(self, lat, lon):
        location = self._get_location_name(lat, lon)
        
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
    
    def _shorten_conditions(self, forecast):
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
    
    def _get_location_name(self, lat, lon):
        params = {
            'lat': lat,
            'lon': lon,
            'format': 'json',
            'zoom': 10,
            'addressdetails': 1
        }
    
        location = requests.get('https://nominatim.openstreetmap.org/reverse', params=params, headers={'User-Agent': 'pyjs8call-wx'}).json()
        city = location['name']
        state = us.states.lookup(location['address']['state']).abbr
        return f'{city}, {state}'
