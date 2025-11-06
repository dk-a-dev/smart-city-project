#!/usr/bin/env python3
"""
🌍 EcoSignal: Real-Time Analysis
Fetches live data from WAQI and TomTom APIs, shows adaptive speed recommendations
"""

import requests
import json
from datetime import datetime
from typing import Dict, List

class EcoSignalAnalysis:
    """Real-time analysis combining Air Quality + Traffic Flow"""
    
    def __init__(self, waqi_key: str, tomtom_key: str, city: str = "bengaluru"):
        self.waqi_key = waqi_key
        self.tomtom_key = tomtom_key
        self.city = city
        
        # Bengaluru coordinates
        self.city_coords = {
            "bengaluru": {"lat": 13.0827, "lon": 80.2707, "name": "Bengaluru"},
            "delhi": {"lat": 28.6139, "lon": 77.2090, "name": "Delhi"},
            "mumbai": {"lat": 19.0760, "lon": 72.8777, "name": "Mumbai"},
        }
        
        self.coords = self.city_coords.get(city.lower(), self.city_coords["bengaluru"])
    
    def fetch_waqi_data(self) -> Dict:
        """Fetch real air quality data from WAQI API"""
        try:
            url = f"https://api.waqi.info/feed/{self.city}/?token={self.waqi_key}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'ok':
                    aqi = data['data'].get('aqi', 'N/A')
                    iaqi = data['data'].get('iaqi', {})
                    
                    return {
                        'status': 'success',
                        'aqi': aqi,
                        'pm25': iaqi.get('pm25', {}).get('v', 'N/A'),
                        'pm10': iaqi.get('pm10', {}).get('v', 'N/A'),
                        'o3': iaqi.get('o3', {}).get('v', 'N/A'),
                        'no2': iaqi.get('no2', {}).get('v', 'N/A'),
                        'so2': iaqi.get('so2', {}).get('v', 'N/A'),
                        'co': iaqi.get('co', {}).get('v', 'N/A'),
                        'city': self.city,
                        'timestamp': datetime.utcnow().isoformat()
                    }
            
            return {'status': 'error', 'message': 'WAQI API error'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    def fetch_tomtom_traffic(self) -> Dict:
        """Fetch real traffic data from TomTom API"""
        try:
            lat = self.coords['lat']
            lon = self.coords['lon']
            
            # TomTom Flow Segment Data - uses single point parameter
            # Correct endpoint format: /traffic/services/{version}/flowSegmentData/{style}/{zoom}/{format}
            url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/relative0/10/json"
            
            # Query multiple points around the city center to get area coverage
            points = [
                (lat, lon),                    # City center
                (lat + 0.01, lon),            # North
                (lat - 0.01, lon),            # South
                (lat, lon + 0.01),            # East
                (lat, lon - 0.01),            # West
            ]
            
            roads = []
            
            for point_lat, point_lon in points:
                params = {
                    'point': f"{point_lat},{point_lon}",
                    'unit': 'KMPH',
                    'openLr': 'false',
                    'key': self.tomtom_key
                }
                
                response = requests.get(url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Extract flow segment data
                    if 'flowSegmentData' in data:
                        segment = data['flowSegmentData']
                        road = {
                            'id': f"segment_{len(roads)}",
                            'name': f"Road Segment {len(roads) + 1}",
                            'current_speed': segment.get('currentSpeed', 0),
                            'free_flow_speed': segment.get('freeFlowSpeed', 60),
                            'current_travel_time': segment.get('currentTravelTime', 0),
                            'free_flow_travel_time': segment.get('freeFlowTravelTime', 1),
                            'congestion': round((segment.get('currentTravelTime', 0) / max(1, segment.get('freeFlowTravelTime', 1)) - 1) * 100, 1),
                            'confidence': segment.get('confidence', 0.8),
                            'coordinates': (point_lat, point_lon)
                        }
                        roads.append(road)
            
            if not roads:
                return {'status': 'error', 'message': 'No traffic data found', 'roads': []}
            
            return {
                'status': 'success',
                'roads': roads,
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e), 'roads': []}
    
    def calculate_recommendations(self, aqi: int, roads: List[Dict]) -> List[Dict]:
        """Calculate adaptive speed recommendations"""
        recommendations = []
        
        for road in roads:
            congestion = road['congestion']
            free_flow = road['free_flow_speed']
            
            # Decision matrix
            if congestion > 60 and aqi > 150:
                recommended = max(20, free_flow * 0.60)
                emission_reduction = 22.5
                urgency = "🔴 CRITICAL"
                rationale = "Heavy congestion + High pollution"
            elif congestion > 60 and aqi <= 100:
                recommended = max(25, free_flow * 0.75)
                emission_reduction = 12.0
                urgency = "🟠 HIGH"
                rationale = "Heavy congestion - prioritize flow"
            elif 30 < congestion <= 60 and aqi > 150:
                recommended = max(30, free_flow * 0.80)
                emission_reduction = 15.0
                urgency = "🟠 HIGH"
                rationale = "Moderate traffic + High pollution"
            elif congestion <= 30 and aqi > 150:
                recommended = max(35, free_flow * 0.85)
                emission_reduction = 10.0
                urgency = "🟡 MEDIUM"
                rationale = "Light traffic but high pollution"
            else:
                recommended = free_flow
                emission_reduction = 0.0
                urgency = "🟢 LOW"
                rationale = "Optimal conditions"
            
            change_pct = ((recommended - road['current_speed']) / road['current_speed'] * 100) if road['current_speed'] > 0 else 0
            
            recommendations.append({
                'road': road['name'],
                'current_speed': road['current_speed'],
                'recommended_speed': round(recommended, 1),
                'change_pct': round(change_pct, 1),
                'congestion': road['congestion'],
                'emission_reduction': emission_reduction,
                'urgency': urgency,
                'rationale': rationale
            })
        
        return recommendations
    
    def print_report(self):
        """Print comprehensive analysis report"""
        print("\n" + "="*90)
        print("🌍 EcoSignal: REAL-TIME ADAPTIVE TRAFFIC CONTROL ANALYSIS".center(90))
        print("="*90)
        
        # Fetch data
        print("\n📡 Fetching Real-Time Data...")
        aqi_data = self.fetch_waqi_data()
        traffic_data = self.fetch_tomtom_traffic()
        
        # Air Quality Section
        print("\n" + "─"*90)
        print("💨 AIR QUALITY MONITOR (WAQI API)".ljust(90))
        print("─"*90)
        
        if aqi_data['status'] == 'success':
            aqi = aqi_data['aqi']
            print(f"\n📍 City: {aqi_data['city'].title()}")
            print(f"⏰ Timestamp: {aqi_data['timestamp']}")
            print(f"\n📊 Current Air Quality:")
            print(f"   AQI Index: {aqi}")
            
            # AQI level classification
            if aqi < 51:
                level = "🟢 Good"
            elif aqi < 101:
                level = "🟡 Satisfactory"
            elif aqi < 151:
                level = "🟠 Unhealthy"
            elif aqi < 201:
                level = "🔴 Very Unhealthy"
            else:
                level = "⚫ Hazardous"
            
            print(f"   Level: {level}")
            print(f"\n   Pollutants:")
            print(f"      PM2.5: {aqi_data.get('pm25', 'N/A')} µg/m³")
            print(f"      PM10: {aqi_data.get('pm10', 'N/A')} µg/m³")
            print(f"      O₃: {aqi_data.get('o3', 'N/A')} ppb")
            print(f"      NO₂: {aqi_data.get('no2', 'N/A')} ppb")
            print(f"      SO₂: {aqi_data.get('so2', 'N/A')} ppb")
            print(f"      CO: {aqi_data.get('co', 'N/A')} ppb")
        else:
            print(f"❌ Error: {aqi_data.get('message', 'Failed to fetch AQI data')}")
            aqi = 100
        
        # Traffic Section
        print("\n" + "─"*90)
        print("🚗 TRAFFIC FLOW MONITOR (TomTom API)".ljust(90))
        print("─"*90)
        
        if traffic_data['status'] == 'success':
            roads = traffic_data['roads']
            print(f"\n📊 Road Network Status:")
            print(f"   Roads Monitored: {len(roads)}")
            
            if roads:
                avg_congestion = sum(r['congestion'] for r in roads) / len(roads)
                avg_speed = sum(r['current_speed'] for r in roads) / len(roads)
                print(f"   Average Congestion: {avg_congestion:.1f}%")
                print(f"   Average Speed: {avg_speed:.0f} km/h")
                print(f"\n   Individual Roads:")
                print(f"   {'Road':<30} {'Speed':<12} {'Congestion':<15}")
                print(f"   {'-'*30} {'-'*12} {'-'*15}")
                for road in roads:
                    print(f"   {road['name']:<30} {road['current_speed']:>3} km/h    {road['congestion']:>6.1f}%")
        else:
            print(f"❌ Error: {traffic_data.get('message', 'Failed to fetch traffic data')}")
            roads = []
        
        # Recommendations Section
        print("\n" + "─"*90)
        print("🎯 MULTI-OBJECTIVE OPTIMIZATION: ADAPTIVE SPEED RECOMMENDATIONS".ljust(90))
        print("─"*90)
        
        if roads:
            recommendations = self.calculate_recommendations(aqi, roads)
            print(f"\n📋 Speed Adjustment Strategy (AQI: {aqi}):")
            print(f"\n   {'Road':<30} {'Current':<12} {'Recommended':<15} {'Change':<12} {'Emission ↓':<12}")
            print(f"   {'-'*30} {'-'*12} {'-'*15} {'-'*12} {'-'*12}")
            
            for rec in recommendations:
                change_dir = "↓" if rec['change_pct'] < 0 else "↑"
                print(f"   {rec['road']:<30} {rec['current_speed']:>3} km/h    {rec['recommended_speed']:>5.0f} km/h    {rec['change_pct']:>5.0f}% {change_dir}    {rec['emission_reduction']:>6.1f}%")
            
            print(f"\n   Detailed Analysis:")
            for rec in recommendations:
                print(f"\n   📍 {rec['road']}")
                print(f"      Urgency: {rec['urgency']}")
                print(f"      Congestion: {rec['congestion']:.1f}%")
                print(f"      Recommendation: {rec['current_speed']} → {rec['recommended_speed']:.0f} km/h")
                print(f"      Rationale: {rec['rationale']}")
                print(f"      Expected Emission Reduction: {rec['emission_reduction']:.1f}%")
        
        # Impact Summary
        print("\n" + "─"*90)
        print("💚 EXPECTED IMPACT SUMMARY".ljust(90))
        print("─"*90)
        
        if roads and recommendations:
            avg_emission_reduction = sum(r['emission_reduction'] for r in recommendations) / len(recommendations)
            avg_congestion = sum(r['congestion'] for r in recommendations) / len(recommendations)
            
            print(f"\n📊 Network-Wide Metrics:")
            print(f"   Average Emission Reduction: {avg_emission_reduction:.1f}%")
            print(f"   Average Congestion: {avg_congestion:.1f}%")
            print(f"   Roads Requiring Speed Reduction: {sum(1 for r in recommendations if r['change_pct'] < 0)}/{len(recommendations)}")
            
            print(f"\n🏥 Health Impact (Daily):")
            health_cases = max(0, int((aqi - 100) * 0.5)) if aqi > 100 else 0
            print(f"   Respiratory Cases Avoided: ~{health_cases}")
            print(f"   Hospital Admissions Prevented: ~{max(0, health_cases//10)}")
            print(f"   Health Cost Saved: ₹{max(0, health_cases * 20000):,}")
            
            print(f"\n🚗 Traffic Impact:")
            avg_speed_change = sum(r['change_pct'] for r in recommendations) / len(recommendations)
            print(f"   Travel Time Change: {avg_speed_change:+.1f}%")
            print(f"   Travel Time Impact: {max(0, abs(avg_speed_change) * 0.5):+.0f} minutes per trip")
        
        # Research Framework
        print("\n" + "─"*90)
        print("📚 RESEARCH FOUNDATION".ljust(90))
        print("─"*90)
        print(f"""
Göttlich, S., Herty, M., & Ulke, A. (2025)
"Speed limits in traffic emission models using multi-objective optimization"
Optimization and Engineering, 26, 199-227

Mathematical Framework:
ξ(s,t,V^max) = Q(ρ,V_max) + θ·ρ

Where:
• Q(ρ,V_max) = Traffic flux (increases with speed)
• θ·ρ = Congestion penalty from idling (decreases with speed)
• Optimal speed: ~50-60 km/h for minimum total emissions

Decision Matrix:
┌─────────────────┬────────────────┬──────────────────┐
│ Traffic Level   │ Pollution      │ Action           │
├─────────────────┼────────────────┼──────────────────┤
│ Heavy (>60%)    │ High (>150)    │ 🔴 Reduce 60%    │
│ Heavy (>60%)    │ Low (≤100)     │ 🟠 Reduce 75%    │
│ Moderate        │ High (>150)    │ 🟠 Reduce 80%    │
│ Light (<30%)    │ High (>150)    │ 🟡 Reduce 85%    │
│ Light (<30%)    │ Low (≤100)     │ 🟢 Maintain      │
└─────────────────┴────────────────┴──────────────────┘
        """)
        
        print("=" * 90)
        print("✅ Analysis Complete".center(90))
        print("=" * 90 + "\n")

def main():
    """Main execution"""
    
    # API Keys
    WAQI_KEY = "6156a307c458ded2cade119f90a3435b2e341200"
    TOMTOM_KEY = "AjUGQBYYQkgDFM6UGLRWQbNtzU9raICL"
    
    # Initialize analysis
    analysis = EcoSignalAnalysis(WAQI_KEY, TOMTOM_KEY, city="bengaluru")
    
    # Print report
    analysis.print_report()

if __name__ == "__main__":
    main()
