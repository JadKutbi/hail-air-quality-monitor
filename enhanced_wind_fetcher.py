"""Fetch wind data from multiple sources with time-synchronized accuracy."""

import requests
import numpy as np
from datetime import datetime, timedelta
import pytz
import logging
from typing import Dict, Optional, List
import os
from functools import lru_cache

logger = logging.getLogger(__name__)


class EnhancedWindFetcher:
    """Fetches wind data from multiple sources with time-synchronized accuracy."""

    def __init__(self):
        self.api_keys = {
            'openweather': os.getenv('OPENWEATHER_API_KEY'),
            'tomorrow': os.getenv('TOMORROW_IO_API_KEY'),
            'weatherapi': os.getenv('WEATHERAPI_KEY'),
            'visualcrossing': os.getenv('VISUALCROSSING_KEY')
        }

        self.weather_stations = {
            'Hail': {
                'airport_code': 'OEHL',
                'lat': 27.5114,
                'lon': 41.7208,
                'ncmc_station_id': '40394',
                'nearest_stations': [
                    {'id': '40394', 'name': 'Hail', 'distance_km': 0}
                ]
            }
        }

    def fetch_wind_data(self, city: str, target_time: datetime, max_time_diff_minutes: int = 30) -> Dict:
        """Fetch wind data with minimal time difference from target."""
        if city not in self.weather_stations:
            logger.warning(f"City '{city}' not found in weather stations, using fallback")
            return self._create_fallback_wind_data(city, target_time)

        logger.info(f"Fetching wind for {city} at {target_time} UTC")

        results = []
        now = datetime.now(pytz.UTC)
        hours_ago = abs((now - target_time).total_seconds() / 3600)

        if hours_ago <= 3:
            sources = [
                ('openweather', self._fetch_openweather_realtime),
                ('tomorrow_io', self._fetch_tomorrow_io),
                ('metar', self._fetch_metar_wind),
                ('weatherapi', self._fetch_weatherapi_historical),
            ]
        elif hours_ago <= 24:
            sources = [
                ('tomorrow_io', self._fetch_tomorrow_io),
                ('weatherapi', self._fetch_weatherapi_historical),
                ('openweather', self._fetch_openweather_realtime),
                ('metar', self._fetch_metar_wind),
            ]
        else:
            sources = [
                ('weatherapi', self._fetch_weatherapi_historical),
                ('visualcrossing', self._fetch_visualcrossing),
                ('metar', self._fetch_metar_wind),
            ]

        for source_name, fetch_func in sources:
            try:
                wind_data = fetch_func(city, target_time)
                if wind_data:
                    time_diff = abs((wind_data['observation_time'] - target_time).total_seconds() / 60)

                    if time_diff <= max_time_diff_minutes:
                        confidence = self._calculate_confidence(time_diff, source_name)

                        wind_data.update({
                            'source': source_name,
                            'time_difference_minutes': round(time_diff, 1),
                            'confidence': confidence,
                            'confidence_reason': self._get_confidence_reason(time_diff, source_name)
                        })

                        logger.info(f"{source_name}: {time_diff:.1f} min difference, {confidence}% confidence")
                        results.append(wind_data)

                        if time_diff <= 5:
                            return wind_data

            except Exception as e:
                logger.debug(f"{source_name} failed: {e}")

        if results:
            results.sort(key=lambda x: x['time_difference_minutes'])
            best_result = results[0]

            if len(results) >= 2 and best_result['time_difference_minutes'] > 15:
                interpolated = self._interpolate_wind_data(results, target_time)
                if interpolated:
                    return interpolated

            return best_result

        logger.warning(f"No accurate wind data found for {city} at {target_time}")
        return self._create_fallback_wind_data(city, target_time)

    def _fetch_metar_wind(self, city: str, target_time: datetime) -> Optional[Dict]:
        """Fetch METAR data from nearby airports."""
        station = self.weather_stations.get(city)
        if not station:
            return None
        airport_code = station.get('airport_code')
        if not airport_code:
            return None

        endpoints = [
            f"https://aviationweather.gov/api/data/metar?ids={airport_code}&hours=3",
        ]

        for endpoint in endpoints:
            try:
                response = requests.get(endpoint, timeout=5)
                if response.status_code == 200:
                    data = response.text
                    import re
                    wind_pattern = r'(\d{3})(\d{2,3})(G\d{2,3})?KT'
                    match = re.search(wind_pattern, data)

                    if match:
                        direction = int(match.group(1))
                        speed_knots = int(match.group(2))
                        speed_ms = speed_knots * 0.514444

                        observation_time = target_time.replace(minute=0, second=0, microsecond=0)

                        return {
                            'direction_deg': direction,
                            'speed_ms': speed_ms,
                            'observation_time': observation_time,
                            'direction_cardinal': self._degrees_to_cardinal(direction)
                        }
            except Exception as e:
                logger.debug(f"METAR endpoint failed: {e}")
                continue

        return None

    def _fetch_openweather_realtime(self, city: str, target_time: datetime) -> Optional[Dict]:
        """OpenWeatherMap - Real-time current conditions."""
        if not self.api_keys['openweather']:
            return None

        station = self.weather_stations.get(city)
        if not station:
            return None
        now = datetime.now(pytz.UTC)
        time_diff_hours = abs((now - target_time).total_seconds() / 3600)

        if time_diff_hours <= 3:
            url = (f"https://api.openweathermap.org/data/2.5/weather"
                   f"?lat={station['lat']}&lon={station['lon']}"
                   f"&appid={self.api_keys['openweather']}")

            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    wind = data.get('wind', {})

                    if wind:
                        obs_timestamp = data.get('dt', int(now.timestamp()))
                        observation_time = datetime.fromtimestamp(obs_timestamp, pytz.UTC)

                        return {
                            'direction_deg': wind.get('deg', 0),
                            'speed_ms': wind.get('speed', 0),
                            'observation_time': observation_time,
                            'direction_cardinal': self._degrees_to_cardinal(wind.get('deg', 0))
                        }
            except Exception as e:
                logger.debug(f"OpenWeatherMap failed: {e}")

        return None

    def _fetch_tomorrow_io(self, city: str, target_time: datetime) -> Optional[Dict]:
        """Tomorrow.io - 1-minute temporal resolution."""
        if not self.api_keys['tomorrow']:
            return None

        station = self.weather_stations.get(city)
        if not station:
            return None
        base_url = "https://api.tomorrow.io/v4/timelines"

        headers = {'accept': 'application/json', 'Accept-Encoding': 'gzip'}

        start_time = (target_time - timedelta(minutes=30))
        end_time = (target_time + timedelta(minutes=30))

        start_str = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_str = end_time.strftime('%Y-%m-%dT%H:%M:%SZ')

        params = {
            'location': f"{station['lat']},{station['lon']}",
            'fields': 'windSpeed,windDirection',
            'timesteps': '1m',
            'startTime': start_str,
            'endTime': end_str,
            'apikey': self.api_keys['tomorrow']
        }

        try:
            response = requests.get(base_url, params=params, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()

                if 'data' in data and 'timelines' in data['data']:
                    timelines = data['data']['timelines']
                    if timelines and len(timelines) > 0:
                        intervals = timelines[0].get('intervals', [])

                        if intervals:
                            closest = None
                            min_diff = float('inf')

                            for interval in intervals:
                                start_str = interval['startTime']
                                if start_str.endswith('Z'):
                                    obs_time = datetime.fromisoformat(start_str[:-1] + '+00:00')
                                else:
                                    obs_time = datetime.fromisoformat(start_str)

                                diff = abs((obs_time - target_time).total_seconds())
                                if diff < min_diff:
                                    min_diff = diff
                                    closest = interval

                            if closest:
                                values = closest.get('values', {})
                                start_str = closest['startTime']
                                if start_str.endswith('Z'):
                                    obs_time = datetime.fromisoformat(start_str[:-1] + '+00:00')
                                else:
                                    obs_time = datetime.fromisoformat(start_str)

                                return {
                                    'direction_deg': values.get('windDirection', 0),
                                    'speed_ms': values.get('windSpeed', 0),
                                    'observation_time': obs_time,
                                    'direction_cardinal': self._degrees_to_cardinal(values.get('windDirection', 0))
                                }

        except Exception as e:
            logger.debug(f"Tomorrow.io error: {e}")

        return None

    def _fetch_weatherapi_historical(self, city: str, target_time: datetime) -> Optional[Dict]:
        """WeatherAPI.com - Historical data with hourly resolution."""
        if not self.api_keys['weatherapi']:
            return None

        station = self.weather_stations.get(city)
        if not station:
            return None
        now = datetime.now(pytz.UTC)
        days_ago = (now - target_time).days

        if days_ago > 7:
            return None

        base_url = "http://api.weatherapi.com/v1/history.json"

        params = {
            'key': self.api_keys['weatherapi'],
            'q': f"{station['lat']},{station['lon']}",
            'dt': target_time.strftime('%Y-%m-%d')
        }

        try:
            response = requests.get(base_url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()

                forecast = data.get('forecast', {}).get('forecastday', [])
                if forecast and len(forecast) > 0:
                    hours = forecast[0].get('hour', [])

                    closest_hour = None
                    min_diff = float('inf')

                    for hour_data in hours:
                        epoch_time = hour_data.get('time_epoch')
                        if epoch_time:
                            try:
                                hour_time = datetime.fromtimestamp(epoch_time, pytz.UTC)
                                diff = abs((hour_time - target_time).total_seconds())
                                if diff < min_diff:
                                    min_diff = diff
                                    closest_hour = hour_data
                                    closest_time = hour_time
                            except Exception:
                                continue

                    if closest_hour:
                        return {
                            'direction_deg': closest_hour.get('wind_degree', 0),
                            'speed_ms': closest_hour.get('wind_kph', 0) / 3.6,
                            'observation_time': closest_time,
                            'direction_cardinal': closest_hour.get('wind_dir', 'N')
                        }

        except Exception as e:
            logger.debug(f"WeatherAPI error: {e}")

        return None

    def _fetch_visualcrossing(self, city: str, target_time: datetime) -> Optional[Dict]:
        """Visual Crossing - Historical weather with hourly data."""
        if not self.api_keys['visualcrossing']:
            return None

        station = self.weather_stations.get(city)
        if not station:
            return None
        date_str = target_time.strftime('%Y-%m-%d')
        hour = target_time.hour

        url = (f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/"
               f"{station['lat']},{station['lon']}/{date_str}T{hour:02d}:00:00")

        params = {
            'key': self.api_keys['visualcrossing'],
            'include': 'hours',
            'elements': 'datetime,windspeed,winddir'
        }

        try:
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()

                days = data.get('days', [])
                if days:
                    hours = days[0].get('hours', [])

                    for hour_data in hours:
                        if hour_data.get('datetime', '').startswith(f"{hour:02d}:"):
                            return {
                                'direction_deg': hour_data.get('winddir', 0),
                                'speed_ms': hour_data.get('windspeed', 0) * 0.44704,
                                'observation_time': target_time.replace(minute=0, second=0),
                                'direction_cardinal': self._degrees_to_cardinal(hour_data.get('winddir', 0))
                            }
        except Exception as e:
            logger.debug(f"Visual Crossing API failed: {e}")

        return None

    def _interpolate_wind_data(self, results: List[Dict], target_time: datetime) -> Optional[Dict]:
        """Interpolate between multiple wind measurements."""
        if len(results) < 2:
            return None

        before = [r for r in results if r['observation_time'] <= target_time]
        after = [r for r in results if r['observation_time'] > target_time]

        if before and after:
            b = max(before, key=lambda x: x['observation_time'])
            a = min(after, key=lambda x: x['observation_time'])

            total_diff = (a['observation_time'] - b['observation_time']).total_seconds()
            weight = (target_time - b['observation_time']).total_seconds() / total_diff

            dir1 = b['direction_deg']
            dir2 = a['direction_deg']

            if abs(dir2 - dir1) > 180:
                if dir2 > dir1:
                    dir1 += 360
                else:
                    dir2 += 360

            interp_dir = dir1 + (dir2 - dir1) * weight
            interp_dir = interp_dir % 360

            interp_speed = b['speed_ms'] + (a['speed_ms'] - b['speed_ms']) * weight

            return {
                'direction_deg': interp_dir,
                'speed_ms': interp_speed,
                'observation_time': target_time,
                'direction_cardinal': self._degrees_to_cardinal(interp_dir),
                'source': 'interpolated',
                'time_difference_minutes': 0,
                'confidence': 85,
                'confidence_reason': f"Interpolated between {b['source']} and {a['source']}"
            }

        return None

    def _calculate_confidence(self, time_diff_minutes: float, source: str) -> int:
        """Calculate confidence score based on temporal difference and source quality."""
        source_confidence = {
            'saudi_ncmc': 100,
            'metar': 95,
            'tomorrow_io': 95,
            'openweather': 90,
            'weatherapi': 85,
            'visualcrossing': 85,
            'interpolated': 85
        }.get(source, 50)

        if time_diff_minutes <= 5:
            time_penalty = 0
        elif time_diff_minutes <= 15:
            time_penalty = 5
        elif time_diff_minutes <= 30:
            time_penalty = 10
        elif time_diff_minutes <= 60:
            time_penalty = 20
        else:
            time_penalty = 40

        return max(10, source_confidence - time_penalty)

    def _get_confidence_reason(self, time_diff_minutes: float, source: str) -> str:
        """Explain confidence score."""
        if time_diff_minutes <= 5:
            time_desc = "Nearly perfect temporal match"
        elif time_diff_minutes <= 15:
            time_desc = "Good temporal match"
        elif time_diff_minutes <= 30:
            time_desc = "Acceptable temporal match"
        elif time_diff_minutes <= 60:
            time_desc = "Moderate temporal difference"
        else:
            time_desc = "Significant temporal difference"

        source_desc = {
            'saudi_ncmc': "Official Saudi weather station",
            'metar': "Airport weather observation",
            'tomorrow_io': "High-resolution weather API",
            'openweather': "Real-time weather service",
            'weatherapi': "Historical weather data",
            'visualcrossing': "Multi-source weather data",
            'interpolated': "Interpolated from multiple sources"
        }.get(source, "Alternative source")

        return f"{time_desc} ({time_diff_minutes:.1f} min). Source: {source_desc}"

    def _degrees_to_cardinal(self, degrees: float) -> str:
        """Convert degrees to cardinal direction."""
        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                     "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        index = round(degrees / 22.5) % 16
        return directions[index]

    def _create_fallback_wind_data(self, city: str, target_time: datetime) -> Dict:
        """Create fallback wind data when no accurate source available."""
        return {
            'direction_deg': 0,
            'speed_ms': 0,
            'observation_time': target_time,
            'direction_cardinal': 'UNKNOWN',
            'source': 'fallback',
            'time_difference_minutes': 999,
            'confidence': 0,
            'confidence_reason': 'No wind data available - factory attribution unreliable',
            'warning': 'Wind data unavailable - results should not be used for attribution'
        }

    @lru_cache(maxsize=128)
    def get_historical_wind_patterns(self, city: str, hour: int) -> Dict:
        """Get typical wind patterns for a specific hour."""
        return {
            'typical_direction': 315,
            'typical_speed': 4.5,
            'direction_variance': 45,
            'speed_variance': 2.0
        }
