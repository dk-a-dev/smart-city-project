"""
Air Quality Monitor Agent
Fetches and analyzes real-time air quality data from WAQI API
"""

import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json

class AirQualityMonitorAgent:
    """
    Monitors air quality in real-time and detects pollution hotspots.
    Uses WAQI (World Air Quality Index) API for data collection.
    """
    
    def __init__(self, waqi_api_key: str, city_name: str = "bengaluru"):
        """
        Initialize air quality monitor
        
        Args:
            waqi_api_key: API key from https://waqi.info/api/
            city_name: City to monitor (default: bengaluru)
        """
        self.api_key = waqi_api_key
        self.city_name = city_name
        self.base_url = "https://api.waqi.info"
        self.pollution_history = {}  # Store historical data for hotspot detection
        self.hotspots = []  # Detected pollution hotspots
        
    def fetch_current_aqi(self, location: Tuple[float, float] = None) -> Dict:
        """
        Fetch current AQI data for location
        
        Args:
            location: (latitude, longitude) tuple. If None, use city name
            
        Returns:
            Dictionary with AQI data:
            {
                'aqi': 113,
                'pm25': 45.5,
                'pm10': 78.2,
                'o3': 12,
                'no2': 25,
                'so2': 8,
                'co': 450,
                'timestamp': '2025-11-06T16:10:00Z',
                'station': 'Shivapura_Peenya'
            }
        """
        try:
            if location:
                # Geo-coordinates based query
                lat, lon = location
                endpoint = f"{self.base_url}/feed/geo:{lat};{lon}/"
            else:
                # City-based query
                endpoint = f"{self.base_url}/feed/{self.city_name}/"
            
            params = {'token': self.api_key}
            response = requests.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data['status'] != 'ok':
                print(f"API Error: {data.get('data', 'Unknown error')}")
                return None
            
            result = data['data']
            
            # Extract pollutant data
            aqi_data = {
                'aqi': result.get('aqi', 0),
                'pm25': result.get('iaqi', {}).get('pm25', {}).get('v'),
                'pm10': result.get('iaqi', {}).get('pm10', {}).get('v'),
                'o3': result.get('iaqi', {}).get('o3', {}).get('v'),
                'no2': result.get('iaqi', {}).get('no2', {}).get('v'),
                'so2': result.get('iaqi', {}).get('so2', {}).get('v'),
                'co': result.get('iaqi', {}).get('co', {}).get('v'),
                'timestamp': datetime.now().isoformat(),
                'station': result.get('city', {}).get('name', 'Unknown'),
                'coordinates': (
                    result.get('city', {}).get('geo', [0, 0])[0],
                    result.get('city', {}).get('geo', [0, 0])[1]
                )
            }
            
            return aqi_data
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching AQI data: {e}")
            return None
    
    def classify_aqi_level(self, aqi: int) -> str:
        """
        Classify AQI into health risk categories
        
        Args:
            aqi: AQI value
            
        Returns:
            Category: 'Good', 'Satisfactory', 'Moderately Polluted', 
                     'Poor', 'Very Poor', 'Severe'
        """
        if aqi <= 50:
            return 'Good'
        elif aqi <= 100:
            return 'Satisfactory'
        elif aqi <= 150:
            return 'Moderately Polluted'
        elif aqi <= 200:
            return 'Poor'
        elif aqi <= 300:
            return 'Very Poor'
        else:
            return 'Severe'
    
    def detect_hotspots(self, threshold: int = 150, 
                       history_window_hours: int = 24) -> List[Dict]:
        """
        Detect pollution hotspots based on historical data
        
        Uses proactive approach: if location consistently exceeds threshold
        over history, it's marked as hotspot
        
        Args:
            threshold: AQI threshold for hotspot (default 150 = Moderately Polluted)
            history_window_hours: How far back to check (default 24 hours)
            
        Returns:
            List of hotspots with location, avg AQI, and pattern
        """
        hotspots = []
        
        current_time = datetime.now()
        window_start = current_time - timedelta(hours=history_window_hours)
        
        for station, history in self.pollution_history.items():
            # Filter history within window
            recent_data = [
                d for d in history 
                if datetime.fromisoformat(d['timestamp']) > window_start
            ]
            
            if len(recent_data) < 3:  # Need at least 3 data points
                continue
            
            # Calculate statistics
            aqi_values = [d['aqi'] for d in recent_data]
            avg_aqi = np.mean(aqi_values)
            std_aqi = np.std(aqi_values)
            max_aqi = np.max(aqi_values)
            exceeds_threshold = sum(1 for aqi in aqi_values if aqi > threshold)
            exceed_percentage = (exceeds_threshold / len(aqi_values)) * 100
            
            # Classify as hotspot if consistently high
            if avg_aqi > threshold or exceed_percentage > 40:
                hotspot = {
                    'station': station,
                    'coordinates': recent_data[-1].get('coordinates'),
                    'avg_aqi': round(avg_aqi, 1),
                    'max_aqi': max_aqi,
                    'std_aqi': round(std_aqi, 1),
                    'exceed_percentage': round(exceed_percentage, 1),
                    'type': 'proactive' if avg_aqi > threshold else 'reactive',
                    'primary_pollutant': self._identify_primary_pollutant(recent_data[-1])
                }
                hotspots.append(hotspot)
        
        self.hotspots = hotspots
        return hotspots
    
    def _identify_primary_pollutant(self, aqi_data: Dict) -> str:
        """Identify which pollutant is causing the most pollution"""
        pollutants = {
            'PM2.5': aqi_data.get('pm25', 0) or 0,
            'PM10': aqi_data.get('pm10', 0) or 0,
            'NO2': aqi_data.get('no2', 0) or 0,
            'O3': aqi_data.get('o3', 0) or 0,
            'CO': aqi_data.get('co', 0) or 0,
            'SO2': aqi_data.get('so2', 0) or 0,
        }
        return max(pollutants, key=pollutants.get)
    
    def get_pollution_dispersion_model(self, source_location: Tuple[float, float],
                                      wind_speed: float = 5.0,
                                      wind_direction: float = 0.0) -> Dict:
        """
        Simple pollution dispersion model (Gaussian plume model)
        In production, use RLINE model
        
        Args:
            source_location: (lat, lon) of pollution source
            wind_speed: Wind speed in m/s
            wind_direction: Wind direction in degrees (0=North, 90=East, etc)
            
        Returns:
            Dispersion pattern with affected radius and concentration gradient
        """
        if wind_speed < 0.5:
            # Calm conditions - uniform dispersion
            shape = 'circular'
            major_axis = 2.0  # km
            minor_axis = 2.0
        else:
            # Windy conditions - elliptical dispersion
            shape = 'elliptical'
            major_axis = min(10.0, 2.0 + (wind_speed * 0.5))  # Extends with wind
            minor_axis = 1.0 + (wind_speed * 0.2)
        
        dispersion = {
            'source': source_location,
            'shape': shape,
            'major_axis_km': major_axis,
            'minor_axis_km': minor_axis,
            'wind_direction_deg': wind_direction,
            'wind_speed_ms': wind_speed,
            'concentration_gradient': 'exponential',
            'affected_area_km2': (major_axis * minor_axis * np.pi) / 4
        }
        
        return dispersion
    
    def update_history(self, aqi_data: Dict, max_history_points: int = 1000):
        """
        Update pollution history for hotspot detection
        
        Args:
            aqi_data: Current AQI reading
            max_history_points: Keep last N readings per station
        """
        if aqi_data is None:
            return
        
        station = aqi_data.get('station', 'Unknown')
        
        if station not in self.pollution_history:
            self.pollution_history[station] = []
        
        self.pollution_history[station].append(aqi_data)
        
        # Keep only recent history
        if len(self.pollution_history[station]) > max_history_points:
            self.pollution_history[station] = self.pollution_history[station][-max_history_points:]
    
    def get_health_recommendations(self, aqi: int, 
                                   sensitive_groups: bool = False) -> Dict:
        """
        Get health recommendations based on AQI
        
        Args:
            aqi: Current AQI value
            sensitive_groups: Include recommendations for sensitive groups
            
        Returns:
            Health guidance and recommendations
        """
        level = self.classify_aqi_level(aqi)
        
        recommendations = {
            'Good': {
                'general': 'Air quality is good. Enjoy outdoor activities.',
                'sensitive': 'No restrictions. Outdoor activities are safe.',
                'driving_caution': False,
                'work_from_home': False,
                'mask_recommended': False
            },
            'Satisfactory': {
                'general': 'Air quality is satisfactory. Most can enjoy outdoor activities.',
                'sensitive': 'Sensitive individuals should limit prolonged outdoor activities.',
                'driving_caution': False,
                'work_from_home': False,
                'mask_recommended': False
            },
            'Moderately Polluted': {
                'general': 'Avoid outdoor activities. Use masks if going outside.',
                'sensitive': 'Stay indoors. Avoid outdoor activities.',
                'driving_caution': True,
                'work_from_home': False,
                'mask_recommended': True
            },
            'Poor': {
                'general': 'Limit outdoor activities. Use N95 masks.',
                'sensitive': 'Stay indoors. Avoid all outdoor activities.',
                'driving_caution': True,
                'work_from_home': True,
                'mask_recommended': True
            },
            'Very Poor': {
                'general': 'Avoid all outdoor activities. Stay indoors with air purifier.',
                'sensitive': 'Stay indoors with windows closed.',
                'driving_caution': True,
                'work_from_home': True,
                'mask_recommended': True
            },
            'Severe': {
                'general': 'Emergency! Stay indoors. Minimize movement.',
                'sensitive': 'Emergency situation. Seek medical guidance.',
                'driving_caution': True,
                'work_from_home': True,
                'mask_recommended': True
            }
        }
        
        return {
            'aqi_level': level,
            'recommendations': recommendations.get(level, {}),
            'affected_groups': ['Children', 'Elderly', 'People with respiratory diseases'] if sensitive_groups else [],
            'affected_activities': ['Outdoor sports', 'Construction', 'Heavy exercise'] if aqi > 150 else []
        }
    
    def get_summary(self) -> Dict:
        """Get current air quality summary"""
        return {
            'current_hotspots': len(self.hotspots),
            'hotspots': self.hotspots[:5],  # Top 5
            'total_stations_monitored': len(self.pollution_history),
            'timestamp': datetime.now().isoformat()
        }


# Example usage
if __name__ == "__main__":
    # Initialize agent
    agent = AirQualityMonitorAgent(
        waqi_api_key="6156a307c458ded2cade119f90a3435b2e341200",
        city_name="bengaluru"
    )
    
    # Fetch current data
    aqi = agent.fetch_current_aqi()
    if aqi:
        print("\n=== Current Air Quality ===")
        print(f"AQI: {aqi['aqi']} ({agent.classify_aqi_level(aqi['aqi'])})")
        print(f"PM2.5: {aqi['pm25']} μg/m³")
        print(f"PM10: {aqi['pm10']} μg/m³")
        print(f"Station: {aqi['station']}")
        
        # Health recommendations
        health = agent.get_health_recommendations(aqi['aqi'], sensitive_groups=True)
        print("\n=== Health Recommendations ===")
        print(health['recommendations']['general'])
        print(health['recommendations']['sensitive'])
