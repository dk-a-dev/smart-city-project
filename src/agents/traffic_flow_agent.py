"""
Traffic Flow Agent - Real-time Traffic Monitoring and Adaptive Control
=======================================================================
Fetches live traffic data from TomTom API and detects congestion patterns.
Integrates with air quality data to make speed limits adaptive based on pollution.
Reference: Göttlich et al. (2025) - Speed limits in traffic emission models using multi-objective optimization
"""

import requests
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from enum import Enum


class TrafficLevel(Enum):
    """Traffic congestion levels"""
    FREE_FLOW = "free_flow"          # <20% congestion
    LIGHT = "light"                  # 20-40% congestion
    MODERATE = "moderate"            # 40-60% congestion
    HEAVY = "heavy"                  # 60-80% congestion
    SEVERE = "severe"                # >80% congestion


class TrafficFlowAgent:
    """
    Real-time traffic flow monitoring agent.
    
    Responsibilities:
    1. Fetch current traffic speed/congestion from TomTom
    2. Detect traffic congestion hotspots
    3. Classify traffic levels (Free → Severe)
    4. Track traffic patterns (history-based analysis)
    5. Recommend adaptive speed limits based on traffic + pollution
    6. Estimate vehicle emissions based on traffic flow
    
    Integration with Air Quality Agent:
    - Heavy traffic + High pollution → Reduce speed limits → Lower emissions
    - Free flow + Low pollution → Allow higher speeds → Maintain efficiency
    - Moderate traffic + Moderate pollution → Balanced speeds
    
    Multi-objective optimization approach:
    Maximize: Traffic flow (vehicles/time)
    Minimize: Emissions (pollution from congestion + idling + high speeds)
    """
    
    def __init__(self, tomtom_api_key: str, city_name: str = "bengaluru"):
        """
        Initialize Traffic Flow Agent
        
        Args:
            tomtom_api_key: TomTom API key for traffic data
            city_name: City to monitor (e.g., "bengaluru")
        """
        self.tomtom_api_key = tomtom_api_key
        self.city_name = city_name.lower()
        self.base_url = "https://api.tomtom.com/traffic/services/5"
        
        # City center coordinates (Bengaluru example)
        self.city_coords = {
            "bengaluru": (13.0827, 80.2707),  # (lat, lon)
            "delhi": (28.6139, 77.2090),
            "mumbai": (19.0760, 72.8777),
        }
        
        # Traffic history: {road_id: [(timestamp, speed, congestion, flow), ...]}
        self.traffic_history = {}
        self.max_history = 1000
        
        # Historical speed baselines (free-flow speeds in km/h)
        self.baseline_speeds = {}
        
        # Congestion hotspots tracking
        self.hotspots = []
        
        # Incident tracking (accidents, roadworks)
        self.incidents = []
        
        # Speed limit recommendations based on pollution-traffic tradeoff
        self.adaptive_speed_limits = {}
    
    def fetch_traffic_flow(self, bbox: Optional[Tuple[float, float, float, float]] = None,
                          location: Optional[str] = None) -> Dict:
        """
        Fetch current traffic flow data from TomTom API
        
        Args:
            bbox: Bounding box (minLat, minLon, maxLat, maxLon) for region
            location: City name or specific location
            
        Returns:
            {
                'timestamp': '2025-11-06T16:30:00Z',
                'roads': [
                    {
                        'id': 'road_001',
                        'name': 'MG Road',
                        'current_speed': 25,  # km/h
                        'free_flow_speed': 60,  # km/h
                        'congestion': 58.3,  # 0-100%
                        'flow_rate': 450,  # vehicles/hour/lane
                        'functional_class': 'arterial',
                        'road_use': 'normal'
                    },
                    ...
                ],
                'status': 'success'
            }
        """
        try:
            if location is None:
                location = self.city_name
            
            # Get city coordinates
            if bbox is None:
                lat, lon = self.city_coords.get(location.lower(), (13.0827, 80.2707))
                # Create 2km x 2km bbox around city center
                lat_offset = 0.02  # ~2km
                lon_offset = 0.02
                bbox = (lat - lat_offset, lon - lon_offset, lat + lat_offset, lon + lon_offset)
            
            min_lat, min_lon, max_lat, max_lon = bbox
            
            # TomTom Flow Segment Data endpoint
            # Returns: current speed, congestion level, travel time
            url = f"{self.base_url}/flowSegmentData/absolute/10/json"
            
            params = {
                'key': self.tomtom_api_key,
                'bbox': f"{min_lon},{min_lat},{max_lon},{max_lat}",
                'zoom': 10
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                return {
                    'status': 'error',
                    'message': f"TomTom API error: {response.status_code}",
                    'roads': []
                }
            
            data = response.json()
            
            # Parse flow data
            roads = []
            if 'flowSegmentData' in data:
                for segment in data['flowSegmentData']:
                    road_info = {
                        'id': segment.get('segmentId', 'unknown'),
                        'name': segment.get('roadName', 'Unknown Road'),
                        'current_speed': segment.get('currentSpeed', 0),  # km/h
                        'free_flow_speed': segment.get('freeFlowSpeed', 60),  # km/h
                        'congestion': segment.get('currentTravelTime', 0) / segment.get('freeFlowTravelTime', 1) * 100 if segment.get('freeFlowTravelTime') else 0,
                        'flow_rate': segment.get('flowRate', 0),  # vehicles/hour
                        'confidence': segment.get('confidence', 0.8),
                        'functional_class': segment.get('functionalClass', 'unknown'),
                        'road_use': segment.get('roadUse', 'normal'),
                        'coordinates': (
                            segment['startPoint'].get('latitude', 0),
                            segment['startPoint'].get('longitude', 0)
                        ) if 'startPoint' in segment else (0, 0)
                    }
                    roads.append(road_info)
            
            return {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'roads': roads,
                'bbox': bbox,
                'status': 'success'
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'status': 'error',
                'message': f"Request failed: {str(e)}",
                'roads': []
            }
    
    def classify_traffic_level(self, congestion_percent: float) -> TrafficLevel:
        """
        Classify traffic congestion level
        
        Args:
            congestion_percent: Congestion level 0-100%
            
        Returns:
            TrafficLevel enum value
        """
        if congestion_percent < 20:
            return TrafficLevel.FREE_FLOW
        elif congestion_percent < 40:
            return TrafficLevel.LIGHT
        elif congestion_percent < 60:
            return TrafficLevel.MODERATE
        elif congestion_percent < 80:
            return TrafficLevel.HEAVY
        else:
            return TrafficLevel.SEVERE
    
    def detect_congestion_hotspots(self, traffic_data: Dict, 
                                  threshold_congestion: float = 50.0,
                                  history_window_hours: int = 1) -> List[Dict]:
        """
        Detect traffic congestion hotspots using current + historical data
        
        Approach:
        1. Real-time: Roads with congestion > threshold
        2. Historical: Roads with consistent high congestion in past hours
        3. Emerging: Roads showing rapid congestion increase
        
        Args:
            traffic_data: Current traffic data from fetch_traffic_flow()
            threshold_congestion: Congestion % threshold to flag as hotspot
            history_window_hours: Hours to look back for patterns
            
        Returns:
            [{
                'road_id': 'road_001',
                'road_name': 'MG Road',
                'current_congestion': 75.5,
                'avg_congestion': 72.3,
                'exceed_percentage': 85.2,  # % of time congested
                'primary_issue': 'heavy_traffic',  # or 'accident', 'roadwork'
                'severity': 'severe',  # from TrafficLevel
                'estimated_delay_minutes': 15,
                'affected_vehicles': 450,
                'coordinates': (lat, lon)
            }]
        """
        hotspots = []
        current_time = datetime.utcnow()
        
        for road in traffic_data['roads']:
            road_id = road['id']
            congestion = road['congestion']
            
            # REAL-TIME DETECTION: Current congestion above threshold
            if congestion >= threshold_congestion:
                # Calculate historical statistics
                if road_id in self.traffic_history:
                    history = self.traffic_history[road_id]
                    
                    # Filter history within window
                    cutoff_time = current_time - timedelta(hours=history_window_hours)
                    recent_history = [
                        h for h in history 
                        if datetime.fromisoformat(h[0].replace('Z', '+00:00')) > cutoff_time
                    ]
                    
                    if recent_history:
                        avg_congestion = np.mean([h[2] for h in recent_history])
                        max_congestion = np.max([h[2] for h in recent_history])
                        exceed_count = len([h for h in recent_history if h[2] >= threshold_congestion])
                        exceed_percentage = (exceed_count / len(recent_history)) * 100
                    else:
                        avg_congestion = congestion
                        exceed_percentage = 100
                else:
                    avg_congestion = congestion
                    exceed_percentage = 100
                
                # Estimate delay and affected vehicles
                free_flow_time = 60  # Assume 60 min baseline
                current_time_estimate = free_flow_time * (congestion / 100)
                delay_minutes = max(0, current_time_estimate - free_flow_time)
                
                # Estimate vehicles affected (rough: traffic flow * delay)
                affected_vehicles = int(road['flow_rate'] * (delay_minutes / 60))
                
                # Determine primary issue
                if road['road_use'] == 'roadwork':
                    primary_issue = 'roadwork'
                elif any(inc['road_id'] == road_id for inc in self.incidents):
                    primary_issue = 'accident'
                else:
                    primary_issue = 'heavy_traffic'
                
                hotspot = {
                    'road_id': road_id,
                    'road_name': road['name'],
                    'current_congestion': round(congestion, 1),
                    'avg_congestion': round(avg_congestion, 1),
                    'exceed_percentage': round(exceed_percentage, 1),
                    'primary_issue': primary_issue,
                    'severity': self.classify_traffic_level(congestion).value,
                    'estimated_delay_minutes': round(delay_minutes, 1),
                    'affected_vehicles': affected_vehicles,
                    'coordinates': road['coordinates'],
                    'confidence': road['confidence']
                }
                hotspots.append(hotspot)
        
        self.hotspots = hotspots
        return hotspots
    
    def get_incidents(self, bbox: Optional[Tuple[float, float, float, float]] = None) -> Dict:
        """
        Fetch traffic incidents (accidents, roadworks, etc.)
        
        Args:
            bbox: Bounding box for incident search
            
        Returns:
            {
                'incidents': [
                    {
                        'id': 'incident_001',
                        'type': 'accident',  # or 'roadwork', 'congestion'
                        'severity': 'high',  # low/medium/high
                        'description': 'Major accident on MG Road',
                        'location': 'MG Road, Bengaluru',
                        'coordinates': (13.0, 80.2),
                        'start_time': '2025-11-06T15:30:00Z',
                        'estimated_end_time': '2025-11-06T17:30:00Z',
                        'delay_minutes': 20,
                        'affected_roads': ['road_001', 'road_002']
                    }
                ],
                'status': 'success'
            }
        """
        try:
            if bbox is None:
                lat, lon = self.city_coords.get(self.city_name, (13.0827, 80.2707))
                lat_offset = 0.02
                lon_offset = 0.02
                bbox = (lat - lat_offset, lon - lon_offset, lat + lat_offset, lon + lon_offset)
            
            min_lat, min_lon, max_lat, max_lon = bbox
            
            # TomTom Incident Details endpoint
            url = f"{self.base_url}/incidentDetails/json"
            
            params = {
                'key': self.tomtom_api_key,
                'bbox': f"{min_lon},{min_lat},{max_lon},{max_lat}",
                'details': 'true'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                return {
                    'status': 'error',
                    'incidents': []
                }
            
            data = response.json()
            incidents = []
            
            if 'incidents' in data:
                for incident in data['incidents']:
                    inc_obj = {
                        'id': incident.get('id', 'unknown'),
                        'type': incident.get('type', 'unknown').lower(),
                        'severity': incident.get('severity', 'medium').lower(),
                        'description': incident.get('description', ''),
                        'location': incident.get('address', {}).get('freeformAddress', 'Unknown'),
                        'coordinates': (
                            incident.get('coordinate', {}).get('latitude', 0),
                            incident.get('coordinate', {}).get('longitude', 0)
                        ),
                        'delay_minutes': incident.get('delay', 0) // 60
                    }
                    incidents.append(inc_obj)
            
            self.incidents = incidents
            return {
                'incidents': incidents,
                'status': 'success'
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'status': 'error',
                'message': str(e),
                'incidents': []
            }
    
    def update_history(self, traffic_data: Dict):
        """
        Update traffic history for pattern analysis
        
        Args:
            traffic_data: Current traffic data from fetch_traffic_flow()
        """
        for road in traffic_data['roads']:
            road_id = road['id']
            
            # Create history entry: (timestamp, speed, congestion, flow_rate)
            entry = (
                traffic_data['timestamp'],
                road['current_speed'],
                road['congestion'],
                road['flow_rate']
            )
            
            if road_id not in self.traffic_history:
                self.traffic_history[road_id] = []
            
            self.traffic_history[road_id].append(entry)
            
            # Maintain max history size
            if len(self.traffic_history[road_id]) > self.max_history:
                self.traffic_history[road_id].pop(0)
    
    def estimate_emissions(self, road_id: str, current_speed: float, 
                          congestion: float, flow_rate: float) -> Dict:
        """
        Estimate vehicle emissions based on traffic flow characteristics
        
        Emission model (simplified from Göttlich et al. 2025):
        ξ(s,t) = Q(ρ,V_max) + θ·ρ
        
        Where:
        - Q(ρ,V_max) = flux (traffic flow) - depends on speed
        - θ·ρ = congestion impact - idling engines
        
        High speed → Lower emissions (optimized speed)
        Very low speed → Higher emissions (congestion, idling)
        Moderate speed → Balanced emissions
        
        Args:
            road_id: Road identifier
            current_speed: Current average speed (km/h)
            congestion: Congestion level (0-100%)
            flow_rate: Vehicles per hour
            
        Returns:
            {
                'road_id': road_id,
                'total_emissions_grams': 125.5,  # CO2 equivalent estimate
                'co2_grams': 85.2,
                'pm25_grams': 2.3,
                'nox_grams': 8.1,
                'emissions_per_vehicle': 0.278,  # grams per vehicle
                'efficiency_score': 0.65,  # 0-1, higher is better (lower emissions)
                'optimization_potential': 'high'  # low/medium/high
            }
        """
        # Baseline emissions (grams CO2/vehicle at 60 km/h free flow)
        baseline_co2_per_vehicle = 0.15  # kg CO2/km
        baseline_pm25_per_vehicle = 0.002  # grams PM2.5/km
        baseline_nox_per_vehicle = 0.010  # grams NOx/km
        
        # Speed dependency: Optimum ~55-60 km/h
        # Emissions increase at low speeds (idling) and very high speeds (inefficiency)
        optimal_speed = 55
        speed_factor = 1.0
        
        if current_speed < 10:
            # Heavy congestion/idling
            speed_factor = 3.0
        elif current_speed < 25:
            # Moderate congestion
            speed_factor = 2.0
        elif current_speed < optimal_speed:
            # Below optimal but not congested
            speed_factor = 1.2
        elif current_speed < 80:
            # Optimal range
            speed_factor = 1.0
        else:
            # High speed (highway efficiency worse at very high speeds)
            speed_factor = 1.3
        
        # Congestion factor (idling engines multiply emissions)
        congestion_factor = 1.0 + (congestion / 100.0) * 2.0  # Up to 3x at 100% congestion
        
        # Total vehicles on segment (assume 10 minute travel time)
        vehicles_on_segment = flow_rate / 6
        
        # Calculate emissions
        co2_grams = baseline_co2_per_vehicle * speed_factor * congestion_factor * vehicles_on_segment * 1000
        pm25_grams = baseline_pm25_per_vehicle * speed_factor * congestion_factor * vehicles_on_segment
        nox_grams = baseline_nox_per_vehicle * speed_factor * congestion_factor * vehicles_on_segment
        total_emissions = co2_grams + pm25_grams * 100 + nox_grams * 10  # Weighted
        
        # Efficiency score (0-1, higher = better = lower emissions)
        max_emissions = baseline_co2_per_vehicle * 3.0 * 3.0 * vehicles_on_segment * 1000
        efficiency_score = max(0, min(1, 1 - (total_emissions / max_emissions)))
        
        # Optimization potential
        if current_speed < 20 or current_speed > 90:
            optimization_potential = 'high'  # Can improve by speed adjustment
        elif congestion > 60:
            optimization_potential = 'high'
        elif efficiency_score < 0.5:
            optimization_potential = 'medium'
        else:
            optimization_potential = 'low'
        
        return {
            'road_id': road_id,
            'total_emissions_grams': round(total_emissions, 1),
            'co2_grams': round(co2_grams, 1),
            'pm25_grams': round(pm25_grams, 3),
            'nox_grams': round(nox_grams, 1),
            'emissions_per_vehicle': round(total_emissions / max(1, vehicles_on_segment), 3),
            'efficiency_score': round(efficiency_score, 2),
            'optimization_potential': optimization_potential
        }
    
    def recommend_adaptive_speed_limits(self, traffic_data: Dict, 
                                       pollution_levels: Dict,
                                       current_aqi: Optional[int] = None) -> Dict:
        """
        Recommend adaptive speed limits based on traffic + pollution
        
        Multi-objective optimization approach:
        - Minimize: Emissions + Congestion
        - Maximize: Traffic flow
        
        Strategy:
        1. High traffic + High pollution → Lower limits (reduce emissions, congestion)
        2. High traffic + Low pollution → Maintain speeds (efficiency > emissions)
        3. Low traffic + High pollution → Lower limits (prioritize air quality)
        4. Low traffic + Low pollution → Higher limits (maximize flow)
        
        Args:
            traffic_data: Current traffic data
            pollution_levels: {road_id: aqi_value, ...} from air quality agent
            current_aqi: Current city AQI (overall)
            
        Returns:
            {
                'recommendations': [
                    {
                        'road_id': 'road_001',
                        'road_name': 'MG Road',
                        'current_limit': 60,  # km/h
                        'recommended_limit': 45,  # km/h (reduced)
                        'change_percentage': -25,
                        'rationale': 'High congestion + High pollution',
                        'expected_emission_reduction': 22.5,  # %
                        'expected_flow_impact': -8.2,  # % (minor)
                        'confidence': 0.92
                    }
                ],
                'overall_strategy': 'Reduce speeds across network',
                'aqi_based_urgency': 'high'  # low/medium/high
            }
        """
        recommendations = []
        total_emission_reduction_potential = 0
        
        for road in traffic_data['roads']:
            road_id = road['id']
            current_speed = road['current_speed']
            free_flow_speed = road['free_flow_speed']
            congestion = road['congestion']
            
            # Get pollution level for this road (if available)
            pollution = pollution_levels.get(road_id, current_aqi or 100)
            
            # Classify pollution impact
            if pollution > 200:
                pollution_urgency = 'severe'
            elif pollution > 150:
                pollution_urgency = 'high'
            elif pollution > 100:
                pollution_urgency = 'moderate'
            else:
                pollution_urgency = 'low'
            
            # Classify traffic impact
            traffic_level = self.classify_traffic_level(congestion)
            
            # MULTI-OBJECTIVE OPTIMIZATION LOGIC
            # Based on Göttlich et al. (2025) framework
            
            recommended_speed = free_flow_speed  # Start with free-flow
            rationale = ""
            emission_reduction = 0
            
            # Case 1: Heavy traffic + High pollution → Reduce speeds significantly
            if (congestion > 60 and pollution > 150):
                recommended_speed = max(20, free_flow_speed * 0.60)  # 60% of free-flow
                rationale = "High congestion + High pollution: Reduce emissions & ease congestion"
                emission_reduction = 25
            
            # Case 2: Heavy traffic + Low pollution → Moderate reduction
            elif (congestion > 60 and pollution <= 100):
                recommended_speed = max(25, free_flow_speed * 0.75)  # 75% of free-flow
                rationale = "High congestion: Moderate speed reduction to ease traffic"
                emission_reduction = 12
            
            # Case 3: Moderate traffic + High pollution → Lower speeds
            elif (30 < congestion <= 60 and pollution > 150):
                recommended_speed = max(30, free_flow_speed * 0.80)  # 80% of free-flow
                rationale = "Moderate traffic + High pollution: Reduce speeds for air quality"
                emission_reduction = 15
            
            # Case 4: Light traffic + High pollution → Lower speeds (air quality priority)
            elif (congestion <= 30 and pollution > 150):
                recommended_speed = max(35, free_flow_speed * 0.85)  # 85% of free-flow
                rationale = "Light traffic but high pollution: Reduce speeds to improve air quality"
                emission_reduction = 10
            
            # Case 5: Light traffic + Low pollution → Allow higher speeds
            elif (congestion <= 20 and pollution <= 100):
                recommended_speed = free_flow_speed  # No change
                rationale = "Light traffic & low pollution: Maintain optimal speeds"
                emission_reduction = 0
            
            # Case 6: Moderate traffic + Low pollution → Balanced
            else:
                recommended_speed = free_flow_speed * 0.90  # 90% of free-flow
                rationale = "Balanced conditions: Slight speed moderation"
                emission_reduction = 5
            
            # Calculate impact metrics
            speed_change_pct = ((recommended_speed - current_speed) / current_speed * 100) if current_speed > 0 else 0
            
            # Flow impact estimation (lower speeds generally reduce throughput by ~5-10%)
            flow_impact = -min(abs(speed_change_pct) * 0.15, 15) if speed_change_pct < 0 else 0
            
            recommendation = {
                'road_id': road_id,
                'road_name': road['name'],
                'current_limit': round(current_speed, 1),
                'recommended_limit': round(recommended_speed, 1),
                'change_percentage': round(speed_change_pct, 1),
                'rationale': rationale,
                'expected_emission_reduction': round(emission_reduction, 1),
                'expected_flow_impact': round(flow_impact, 1),
                'traffic_level': traffic_level.value,
                'pollution_level': pollution_urgency,
                'confidence': round(0.85 + (0.15 * road['confidence']), 2)
            }
            
            recommendations.append(recommendation)
            total_emission_reduction_potential += emission_reduction
        
        # Overall strategy based on network-wide conditions
        avg_congestion = np.mean([r['congestion'] for r in traffic_data['roads']])
        avg_pollution = np.mean(list(pollution_levels.values())) if pollution_levels else (current_aqi or 100)
        
        if avg_congestion > 60 or avg_pollution > 150:
            overall_strategy = "Reduce speeds across network to minimize emissions and ease congestion"
            aqi_based_urgency = "high"
        elif avg_congestion > 40 or avg_pollution > 100:
            overall_strategy = "Moderate speed reduction for balanced traffic flow and air quality"
            aqi_based_urgency = "medium"
        else:
            overall_strategy = "Maintain optimal speeds for efficiency and air quality"
            aqi_based_urgency = "low"
        
        return {
            'recommendations': recommendations,
            'overall_strategy': overall_strategy,
            'aqi_based_urgency': aqi_based_urgency,
            'total_emission_reduction_potential': round(total_emission_reduction_potential, 1),
            'timestamp': traffic_data['timestamp']
        }
    
    def get_traffic_summary(self, traffic_data: Dict) -> Dict:
        """
        Get summary statistics of current traffic conditions
        
        Returns:
            {
                'total_roads': 42,
                'free_flow_roads': 18,
                'light_traffic_roads': 12,
                'moderate_traffic_roads': 8,
                'heavy_traffic_roads': 3,
                'severe_traffic_roads': 1,
                'avg_congestion': 35.2,
                'total_vehicles_flowing': 4250,
                'estimated_total_emissions_grams': 1250.5,
                'network_efficiency_score': 0.72
            }
        """
        if not traffic_data['roads']:
            return {}
        
        roads = traffic_data['roads']
        
        # Count by traffic level
        level_counts = {level.value: 0 for level in TrafficLevel}
        total_congestion = 0
        total_vehicles = 0
        total_emissions = 0
        
        for road in roads:
            congestion = road['congestion']
            level = self.classify_traffic_level(congestion)
            level_counts[level.value] += 1
            total_congestion += congestion
            total_vehicles += road['flow_rate']
            
            # Estimate emissions for this road
            emissions = self.estimate_emissions(
                road['id'], road['current_speed'], congestion, road['flow_rate']
            )
            total_emissions += emissions['total_emissions_grams']
        
        avg_congestion = total_congestion / len(roads) if roads else 0
        network_efficiency = max(0, min(1, 1 - (avg_congestion / 100.0)))
        
        return {
            'timestamp': traffic_data['timestamp'],
            'total_roads': len(roads),
            'free_flow_roads': level_counts['free_flow'],
            'light_traffic_roads': level_counts['light'],
            'moderate_traffic_roads': level_counts['moderate'],
            'heavy_traffic_roads': level_counts['heavy'],
            'severe_traffic_roads': level_counts['severe'],
            'avg_congestion': round(avg_congestion, 1),
            'total_vehicles_flowing': int(total_vehicles),
            'estimated_total_emissions_grams': round(total_emissions, 1),
            'network_efficiency_score': round(network_efficiency, 2)
        }


# Example usage
if __name__ == "__main__":
    # Initialize agent
    agent = TrafficFlowAgent(
        tomtom_api_key="AjUGQBYYQkgDFM6UGLRWQbNtzU9raICL",
        city_name="bengaluru"
    )
    
    # Fetch current traffic
    print("\n" + "="*70)
    print("TRAFFIC FLOW AGENT - LIVE TRAFFIC MONITORING")
    print("="*70)
    
    traffic = agent.fetch_traffic_flow()
    print(f"\nStatus: {traffic['status']}")
    print(f"Timestamp: {traffic['timestamp']}")
    print(f"Total roads monitored: {len(traffic['roads'])}")
    
    if traffic['roads']:
        # Show first 3 roads
        print("\nSample Traffic Data (first 3 roads):")
        for road in traffic['roads'][:3]:
            print(f"\n  Road: {road['name']}")
            print(f"    Current Speed: {road['current_speed']} km/h")
            print(f"    Free Flow Speed: {road['free_flow_speed']} km/h")
            print(f"    Congestion: {road['congestion']:.1f}%")
            print(f"    Flow Rate: {road['flow_rate']} vehicles/hour")
        
        # Update history
        agent.update_history(traffic)
        
        # Detect hotspots
        hotspots = agent.detect_congestion_hotspots(traffic)
        print(f"\n\nCongestion Hotspots Detected: {len(hotspots)}")
        for hotspot in hotspots[:3]:
            print(f"\n  {hotspot['road_name']}")
            print(f"    Severity: {hotspot['severity']}")
            print(f"    Current Congestion: {hotspot['current_congestion']}%")
            print(f"    Estimated Delay: {hotspot['estimated_delay_minutes']} min")
        
        # Get traffic incidents
        incidents = agent.get_incidents()
        print(f"\n\nTraffic Incidents: {len(incidents['incidents'])}")
        
        # Network summary
        summary = agent.get_traffic_summary(traffic)
        print(f"\n\nNETWORK SUMMARY")
        print(f"  Average Congestion: {summary.get('avg_congestion', 0):.1f}%")
        print(f"  Total Vehicles: {summary.get('total_vehicles_flowing', 0)}")
        print(f"  Network Efficiency: {summary.get('network_efficiency_score', 0):.2f}")
        print(f"  Total Emissions (est.): {summary.get('estimated_total_emissions_grams', 0):.1f}g CO2")
        
        # Recommend adaptive speed limits
        pollution_data = {road['id']: 120 for road in traffic['roads']}  # Example pollution levels
        recommendations = agent.recommend_adaptive_speed_limits(traffic, pollution_data, current_aqi=120)
        
        print(f"\n\nADAPTIVE SPEED LIMIT RECOMMENDATIONS")
        print(f"Strategy: {recommendations['overall_strategy']}")
        print(f"Urgency: {recommendations['aqi_based_urgency']}")
        print(f"Potential Emission Reduction: {recommendations['total_emission_reduction_potential']}%")
        
        print(f"\nRecommendations (first 3):")
        for rec in recommendations['recommendations'][:3]:
            if rec['change_percentage'] != 0:
                change_dir = "↓" if rec['change_percentage'] < 0 else "↑"
                print(f"\n  {rec['road_name']}")
                print(f"    {rec['current_limit']} → {rec['recommended_limit']} km/h {change_dir}")
                print(f"    {rec['rationale']}")
                print(f"    Emission Reduction: {rec['expected_emission_reduction']}%")
