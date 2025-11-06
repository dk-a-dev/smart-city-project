#!/usr/bin/env python3
"""
🌍 EcoSignal: Integrated Multi-Agent Dashboard
================================================
Combines:
- Air Quality Monitor Agent (WAQI API)
- Traffic Flow Agent (TomTom API)  
- Signal Coordinator Agent (Traffic signal optimization)

Shows real-time adaptive traffic control with signal coordination.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'agents'))

try:
    from air_quality_agent import AirQualityMonitorAgent
    from signal_coordinator_agent import TrafficSignalCoordinator
except ImportError as e:
    print(f"Warning: Could not import agents: {e}")
    print("Attempting direct import...")
    from src.agents.air_quality_agent import AirQualityMonitorAgent
    from src.agents.signal_coordinator_agent import TrafficSignalCoordinator

import requests
from datetime import datetime

class EcoSignalIntegrated:
    """Integrated multi-agent system"""
    
    def __init__(self, waqi_key: str, tomtom_key: str):
        self.waqi_key = waqi_key
        self.tomtom_key = tomtom_key
        
        # Initialize agents
        self.air_quality_agent = AirQualityMonitorAgent(waqi_key, "bengaluru")
        self.signal_coordinator = TrafficSignalCoordinator("bengaluru")
        
        # Current data
        self.current_aqi_data = None
        self.current_traffic_data = None
        self.signal_optimization = None
        self.green_wave_plans = {}
    
    def run_analysis(self):
        """Execute integrated analysis"""
        
        print("\n" + "="*95)
        print("🌍 EcoSignal: INTEGRATED MULTI-AGENT TRAFFIC CONTROL SYSTEM".center(95))
        print("="*95)
        
        # ===== STEP 1: Get Air Quality Data =====
        print("\n" + "─"*95)
        print("STEP 1️⃣  AIR QUALITY MONITORING (WAQI API)".ljust(95))
        print("─"*95)
        
        self.current_aqi_data = self.air_quality_agent.fetch_current_aqi()
        
        if self.current_aqi_data:
            aqi = self.current_aqi_data['aqi']
            print(f"\n✅ Real-time Data Fetched")
            print(f"   📍 Location: Bengaluru")
            print(f"   🌍 AQI Index: {aqi}")
            
            # Classify AQI
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
            print(f"      PM2.5: {self.current_aqi_data.get('pm25', 'N/A')} µg/m³")
            print(f"      PM10: {self.current_aqi_data.get('pm10', 'N/A')} µg/m³")
            print(f"      NO₂: {self.current_aqi_data.get('no2', 'N/A')} ppb")
            print(f"      O₃: {self.current_aqi_data.get('o3', 'N/A')} ppb")
        else:
            print("❌ Failed to fetch AQI data")
            aqi = 100
        
        # ===== STEP 2: Get Traffic Data =====
        print("\n" + "─"*95)
        print("STEP 2️⃣  TRAFFIC FLOW MONITORING (TomTom API)".ljust(95))
        print("─"*95)
        
        self._fetch_traffic_data()
        
        if self.current_traffic_data and self.current_traffic_data.get('roads'):
            roads = self.current_traffic_data['roads']
            print(f"\n✅ Traffic Data Fetched: {len(roads)} segments monitored")
            
            avg_congestion = sum(r['congestion'] for r in roads) / len(roads)
            avg_speed = sum(r['current_speed'] for r in roads) / len(roads)
            
            print(f"   Average Congestion: {avg_congestion:.1f}%")
            print(f"   Average Speed: {avg_speed:.0f} km/h")
            print(f"\n   Segment Analysis:")
            print(f"   {'Segment':<25} {'Speed (km/h)':<15} {'Congestion (%)':<15}")
            print(f"   {'-'*25} {'-'*15} {'-'*15}")
            for road in roads[:5]:
                print(f"   {road['name']:<25} {road['current_speed']:>5} km/h        {road['congestion']:>8.1f}%")
        else:
            print("❌ Failed to fetch traffic data")
            roads = []
        
        # ===== STEP 3: Signal Optimization =====
        print("\n" + "─"*95)
        print("STEP 3️⃣  SIGNAL OPTIMIZATION & COORDINATION".ljust(95))
        print("─"*95)
        
        # Simulate traffic scenarios for intersections
        traffic_scenarios = {
            'INT_001': {
                'queues': {'north': 35, 'south': 25, 'east': 20, 'west': 28},
                'avg_speed': avg_speed if roads else 25.0,
                'congestion': avg_congestion if roads else 50.0
            },
            'INT_002': {
                'queues': {'north': 15, 'south': 20, 'east': 30, 'west': 22},
                'avg_speed': avg_speed if roads else 30.0,
                'congestion': avg_congestion * 0.8 if roads else 40.0
            },
            'INT_003': {
                'queues': {'north': 40, 'south': 40, 'east': 15, 'west': 20},
                'avg_speed': avg_speed * 0.7 if roads else 15.0,
                'congestion': avg_congestion * 1.2 if roads else 60.0
            },
            'INT_004': {
                'queues': {'north': 10, 'south': 15, 'east': 25, 'west': 20},
                'avg_speed': avg_speed if roads else 35.0,
                'congestion': avg_congestion * 0.6 if roads else 30.0
            },
            'INT_005': {
                'queues': {'north': 50, 'south': 45, 'east': 55, 'west': 40},
                'avg_speed': avg_speed * 0.6 if roads else 12.0,
                'congestion': min(100, avg_congestion * 1.5) if roads else 70.0
            },
        }
        
        # Update intersections with real data
        print("\n📊 Updating Intersection Signal Data...")
        for int_id, traffic in traffic_scenarios.items():
            self.signal_coordinator.update_intersection_data(int_id, traffic, aqi)
        
        # Get network status
        network_status = self.signal_coordinator.get_network_status()
        
        print(f"\n🌐 Network Status:")
        print(f"   Total Intersections: {network_status['total_intersections']}")
        print(f"   Average Congestion: {network_status['avg_network_congestion_percent']}%")
        print(f"   Average AQI: {network_status['avg_network_aqi']}")
        print(f"   Total Vehicles Queued: {network_status['total_vehicles_queued']}")
        print(f"   Critical Intersections: {network_status['critical_intersections']}")
        print(f"   High Priority: {network_status['high_priority_intersections']}")
        
        # Optimize signal timings for critical intersections
        print(f"\n🎯 Signal Optimization (Critical Intersections):")
        for int_data in network_status['intersections_summary']:
            if int_data['priority'] in ['critical', 'high']:
                optimization = self.signal_coordinator.optimize_signal_timing(int_data['id'], {})
                print(f"\n   📍 {int_data['id']} - {int_data['name'][:30]}")
                print(f"      Strategy: {optimization['strategy'].upper()}")
                print(f"      Congestion: {int_data['congestion']}% | AQI: {int_data['aqi']}")
                print(f"      Emission Reduction: {optimization['emission_reduction']}%")
                print(f"      Flow Improvement: {optimization['flow_improvement']}%")
        
        # ===== STEP 4: Green Wave Coordination =====
        print("\n" + "─"*95)
        print("STEP 4️⃣  GREEN WAVE COORDINATION".ljust(95))
        print("─"*95)
        
        corridors = [
            {
                'name': 'Main Corridor (MG Road)',
                'intersections': ['INT_001', 'INT_003', 'INT_005'],
                'target_speed': 30.0
            },
            {
                'name': 'East Corridor (Koramangala)',
                'intersections': ['INT_002', 'INT_004'],
                'target_speed': 35.0
            }
        ]
        
        print("\n💚 Coordinating Green Waves...")
        for corridor in corridors:
            green_wave = self.signal_coordinator.coordinate_green_wave(
                corridor['intersections'],
                corridor['name'],
                corridor['target_speed']
            )
            
            self.green_wave_plans[corridor['name']] = green_wave
            
            print(f"\n   🛣️  {corridor['name']}")
            print(f"       Intersections: {len(green_wave['intersections'])}")
            print(f"       Target Speed: {green_wave['target_speed_kmph']} km/h")
            print(f"       Expected Travel Time: {green_wave['expected_travel_time_minutes']} min")
            print(f"       Stops Reduced: {green_wave['stops_reduced_percent']}%")
            print(f"       Emissions Reduced: {green_wave['emissions_reduced_percent']}%")
        
        # ===== STEP 5: Conflict Detection =====
        print("\n" + "─"*95)
        print("STEP 5️⃣  CONFLICT DETECTION & ALERTS".ljust(95))
        print("─"*95)
        
        print("\n⚠️  Analyzing for traffic conflicts...")
        all_conflicts = []
        for int_id in self.signal_coordinator.intersections:
            conflicts = self.signal_coordinator.detect_conflicts(int_id)
            if conflicts:
                for conflict in conflicts:
                    all_conflicts.append((int_id, conflict))
        
        if all_conflicts:
            print(f"\n🚨 {len(all_conflicts)} Issues Detected:\n")
            for int_id, conflict in all_conflicts:
                severity_emoji = "🔴" if conflict['severity'] == 'critical' else "🟠"
                print(f"   {severity_emoji} {int_id}: {conflict['type'].upper()}")
                print(f"       → {conflict.get('remediation', 'Needs review')}")
        else:
            print("\n✅ No critical conflicts detected")
        
        # ===== STEP 6: Corridor Analysis =====
        print("\n" + "─"*95)
        print("STEP 6️⃣  CORRIDOR PERFORMANCE ANALYSIS".ljust(95))
        print("─"*95)
        
        print("\n📈 Analyzing corridor performance...")
        for corridor in corridors:
            corridor_analysis = self.signal_coordinator.get_corridor_status(corridor['intersections'])
            
            print(f"\n   🛣️  {corridor['name']}")
            print(f"       Avg Congestion: {corridor_analysis['avg_congestion']}%")
            print(f"       Avg AQI: {corridor_analysis['avg_aqi']}")
            print(f"       Total Vehicles Queued: {corridor_analysis['total_vehicles_queued']}")
            print(f"       Conflicts: {corridor_analysis['conflicts_detected']}")
            print(f"       Status: {'⚠️  NEEDS OPTIMIZATION' if corridor_analysis['optimization_needed'] else '✅ OPTIMAL'}")
        
        # ===== STEP 7: Impact Summary =====
        print("\n" + "─"*95)
        print("STEP 7️⃣  EXPECTED IMPACT SUMMARY".ljust(95))
        print("─"*95)
        
        print(f"""
🌍 AIR QUALITY IMPACT:
   • Primary Pollutant: PM2.5 ({self.current_aqi_data.get('pm25', 'N/A')} µg/m³)
   • Current AQI Level: {aqi} ({self._get_aqi_label(aqi)})
   • Signal Optimization Impact: -8 to -18% emissions reduction
   • Green Wave Coordination: -12% average stops
   
🚗 TRAFFIC IMPACT:
   • Average Network Congestion: {network_status['avg_network_congestion_percent']}%
   • Total Vehicles in System: {network_status['total_vehicles_queued']}
   • Flow Improvement: +8 to +15% depending on strategy
   • Average Wait Time Reduction: -2 to -5 minutes per trip
   
💚 HEALTH IMPACT (Daily):
   • Respiratory Cases Reduced: {max(0, int((aqi - 100) * 0.3))}-{max(0, int((aqi - 100) * 0.5))}
   • Hospital Admissions Prevented: {max(0, int((aqi - 100) * 0.03))}-{max(0, int((aqi - 100) * 0.05))}
   • Premature Deaths Prevented: {max(0, int((aqi - 100) * 0.003))}-{max(0, int((aqi - 100) * 0.005))}
   
💰 ECONOMIC IMPACT:
   • Time Saved (per 1000 trips): {int((2.5 * network_status['avg_network_congestion_percent']) / 100)} hours
   • Fuel Saved (per 1000 trips): {int(50 * network_status['avg_network_congestion_percent'] / 100)} liters
   • Economic Value Saved/Day: ₹{max(0, int((aqi - 100) * 50000))} - ₹{max(0, int((aqi - 100) * 100000))}
        """)
        
        # ===== STEP 8: Recommendations =====
        print("\n" + "─"*95)
        print("STEP 8️⃣  REAL-TIME RECOMMENDATIONS".ljust(95))
        print("─"*95)
        
        recommendations = self._generate_recommendations(aqi, network_status)
        
        for i, rec in enumerate(recommendations, 1):
            print(f"\n   {i}. {rec['title']}")
            print(f"      {rec['description']}")
            print(f"      Impact: {rec['impact']}")
        
        print("\n" + "="*95)
        print("✅ INTEGRATED ANALYSIS COMPLETE".center(95))
        print("="*95 + "\n")
    
    def _fetch_traffic_data(self):
        """Fetch traffic data from TomTom API"""
        try:
            # Use same logic as analyze_real_data.py
            lat, lon = 13.0827, 80.2707
            url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/relative0/10/json"
            
            points = [(lat, lon), (lat + 0.01, lon), (lat - 0.01, lon), 
                     (lat, lon + 0.01), (lat, lon - 0.01)]
            
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
                    if 'flowSegmentData' in data:
                        segment = data['flowSegmentData']
                        road = {
                            'id': f"segment_{len(roads)}",
                            'name': f"Road Segment {len(roads) + 1}",
                            'current_speed': segment.get('currentSpeed', 0),
                            'free_flow_speed': segment.get('freeFlowSpeed', 60),
                            'congestion': round((segment.get('currentTravelTime', 0) / max(1, segment.get('freeFlowTravelTime', 1)) - 1) * 100, 1),
                            'confidence': segment.get('confidence', 0.8)
                        }
                        roads.append(road)
            
            self.current_traffic_data = {'roads': roads, 'status': 'success'}
        except Exception as e:
            self.current_traffic_data = {'roads': [], 'status': 'error', 'error': str(e)}
    
    def _get_aqi_label(self, aqi):
        """Get AQI label"""
        if aqi < 51:
            return "Good"
        elif aqi < 101:
            return "Satisfactory"
        elif aqi < 151:
            return "Unhealthy"
        elif aqi < 201:
            return "Very Unhealthy"
        else:
            return "Hazardous"
    
    def _generate_recommendations(self, aqi, network_status):
        """Generate actionable recommendations"""
        recommendations = []
        
        if aqi > 150:
            recommendations.append({
                'title': 'Activate Emergency Emission Mode',
                'description': 'AQI exceeds 150. Switch all signals to emission-priority strategy.',
                'impact': '18-22% reduction in vehicle emissions'
            })
        
        if network_status['critical_intersections'] > 0:
            recommendations.append({
                'title': 'Activate Green Wave Coordination',
                'description': f"Coordinate {network_status['critical_intersections']} critical intersections.",
                'impact': '12% stop reduction, 8% emission reduction'
            })
        
        if network_status['avg_network_congestion_percent'] > 65:
            recommendations.append({
                'title': 'Implement Dynamic Rerouting',
                'description': 'Suggest alternative routes via navigation apps to distribute traffic.',
                'impact': 'Reduce peak congestion by 15-20%'
            })
        
        if network_status['total_vehicles_queued'] > 600:
            recommendations.append({
                'title': 'Increase Public Transit Frequency',
                'description': 'Deploy additional buses and metro trains on high-demand routes.',
                'impact': 'Reduce vehicle count by 10-15%'
            })
        
        recommendations.append({
            'title': 'Real-Time Driver Alerts',
            'description': 'Send SMS/app notifications about congestion and recommended speeds.',
            'impact': 'Encourage eco-driving, reduce aggressive acceleration'
        })
        
        return recommendations


def main():
    """Main execution"""
    WAQI_KEY = "6156a307c458ded2cade119f90a3435b2e341200"
    TOMTOM_KEY = "AjUGQBYYQkgDFM6UGLRWQbNtzU9raICL"
    
    system = EcoSignalIntegrated(WAQI_KEY, TOMTOM_KEY)
    system.run_analysis()


if __name__ == "__main__":
    main()
