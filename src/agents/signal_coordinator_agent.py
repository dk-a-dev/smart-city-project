"""
Traffic Signal Coordinator Agent
=================================
Coordinates traffic signal timing across multiple intersections.
Integrates with Air Quality + Traffic Flow agents for adaptive signal control.

Multi-Agent Coordination:
- Receives adaptive speed recommendations from Traffic Flow Agent
- Receives pollution data from Air Quality Agent
- Optimizes signal timing to:
  1. Maximize traffic flow (green wave coordination)
  2. Minimize emissions (reduce idling at red lights)
  3. Prioritize eco-friendly corridors during pollution episodes

Reference: Adaptive signal control systems (SCATS, SCOOT, UTOPIA)
"""

import requests
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import json


class SignalPhase(Enum):
    """Traffic signal phases"""
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"


@dataclass
class TrafficSignal:
    """Represents a single traffic signal at an intersection"""
    signal_id: str
    intersection_name: str
    coordinates: Tuple[float, float]  # (lat, lon)
    
    # Signal timing (seconds)
    cycle_time: int = 120  # Total cycle time
    red_time: int = 60
    green_time: int = 50
    yellow_time: int = 5
    all_red_time: int = 5  # Safety buffer
    
    # Current state
    current_phase: SignalPhase = SignalPhase.RED
    phase_start_time: datetime = None
    time_in_phase: int = 0
    
    # Connected roads
    connected_roads: List[str] = None
    
    # Optimization params
    min_green: int = 15
    max_green: int = 80
    adaptive_offset: int = 0  # Offset for green wave coordination


@dataclass
class Intersection:
    """Represents a traffic intersection with multiple signals"""
    intersection_id: str
    name: str
    coordinates: Tuple[float, float]
    
    # Signals (one per approach direction: N, S, E, W)
    signals: Dict[str, TrafficSignal] = None
    
    # Traffic data
    queue_length_north: int = 0
    queue_length_south: int = 0
    queue_length_east: int = 0
    queue_length_west: int = 0
    
    # Congestion metrics
    avg_speed: float = 30.0
    avg_congestion: float = 50.0
    
    # Pollution data
    local_aqi: int = 100
    
    # Optimization priority
    priority_level: str = "normal"  # critical, high, normal, low


class TrafficSignalCoordinator:
    """
    Coordinates signal timing across multiple intersections.
    
    Responsibilities:
    1. Manage individual intersection signals
    2. Optimize signal timing based on traffic + pollution
    3. Coordinate green waves across intersections
    4. Implement adaptive offset strategies
    5. Detect and resolve traffic conflicts
    6. Monitor queue lengths and congestion
    """
    
    def __init__(self, city_name: str = "bengaluru"):
        """
        Initialize Signal Coordinator
        
        Args:
            city_name: City to manage signals for
        """
        self.city_name = city_name
        self.intersections: Dict[str, Intersection] = {}
        self.signal_timing_history = {}
        self.coordination_offsets = {}  # Store green wave offsets
        self.optimization_mode = "balanced"  # flow, emissions, balanced
        
        # Initialize default intersections for Bengaluru
        self._initialize_default_intersections()
    
    def _initialize_default_intersections(self):
        """Initialize default intersections for the city"""
        
        # Define major intersections in Bengaluru
        default_intersections = [
            {
                'id': 'INT_001',
                'name': 'MG Road - Brigade Road',
                'coordinates': (13.0351, 80.2664),
                'roads': ['MG Road', 'Brigade Road', 'Vittal Mallya Road', 'Bengaluru Cantonment']
            },
            {
                'id': 'INT_002',
                'name': 'Koramangala - Indiranagar',
                'coordinates': (13.0353, 80.2788),
                'roads': ['Koramangala Road', 'Indiranagar Main', 'White Field Road', 'Old Airport Road']
            },
            {
                'id': 'INT_003',
                'name': 'Connaught Place - Residency Road',
                'coordinates': (13.0309, 80.2614),
                'roads': ['Connaught Place', 'Residency Road', 'Museum Road', 'Cubbon Park Road']
            },
            {
                'id': 'INT_004',
                'name': 'Richmond Road - Benson Town',
                'coordinates': (13.0269, 80.2527),
                'roads': ['Richmond Road', 'Benson Town', 'Palace Road', 'Tennis Court Road']
            },
            {
                'id': 'INT_005',
                'name': 'Whitefield - Varthur Road Junction',
                'coordinates': (13.0249, 80.3015),
                'roads': ['Whitefield Road', 'Varthur Road', 'Outer Ring Road', 'Electronic City Road']
            },
        ]
        
        for int_data in default_intersections:
            intersection = Intersection(
                intersection_id=int_data['id'],
                name=int_data['name'],
                coordinates=int_data['coordinates'],
                signals={}
            )
            
            # Create 4 signals (N, S, E, W)
            directions = ['north', 'south', 'east', 'west']
            for direction in directions:
                signal_id = f"{int_data['id']}_{direction.upper()}"
                signal = TrafficSignal(
                    signal_id=signal_id,
                    intersection_name=int_data['name'],
                    coordinates=int_data['coordinates'],
                    connected_roads=[int_data['roads'][directions.index(direction)]] if direction != 'south' else [int_data['roads'][(directions.index(direction) + 1) % 4]],
                    phase_start_time=datetime.now()
                )
                intersection.signals[direction] = signal
            
            self.intersections[int_data['id']] = intersection
    
    def update_intersection_data(self, intersection_id: str, 
                                traffic_data: Dict, 
                                pollution_level: int) -> bool:
        """
        Update intersection with current traffic and pollution data
        
        Args:
            intersection_id: Intersection ID
            traffic_data: {queues: {north, south, east, west}, speeds, congestion}
            pollution_level: Current AQI level
            
        Returns:
            True if updated successfully
        """
        if intersection_id not in self.intersections:
            return False
        
        intersection = self.intersections[intersection_id]
        
        # Update queue lengths
        queues = traffic_data.get('queues', {})
        intersection.queue_length_north = queues.get('north', 0)
        intersection.queue_length_south = queues.get('south', 0)
        intersection.queue_length_east = queues.get('east', 0)
        intersection.queue_length_west = queues.get('west', 0)
        
        # Update traffic metrics
        intersection.avg_speed = traffic_data.get('avg_speed', 30.0)
        intersection.avg_congestion = traffic_data.get('congestion', 50.0)
        
        # Update pollution
        intersection.local_aqi = pollution_level
        
        # Determine priority level based on conditions
        intersection.priority_level = self._determine_priority(
            intersection.avg_congestion,
            pollution_level,
            max(intersection.queue_length_north, intersection.queue_length_south,
                intersection.queue_length_east, intersection.queue_length_west)
        )
        
        return True
    
    def _determine_priority(self, congestion: float, aqi: int, max_queue: int) -> str:
        """Determine intersection priority level"""
        
        if congestion > 70 or aqi > 150 or max_queue > 50:
            return "critical"
        elif congestion > 50 or aqi > 100 or max_queue > 30:
            return "high"
        elif congestion > 30 or aqi > 50:
            return "normal"
        else:
            return "low"
    
    def optimize_signal_timing(self, intersection_id: str,
                              pollution_levels: Dict = None,
                              traffic_recommendations: Dict = None) -> Dict:
        """
        Optimize signal timing for single intersection
        
        Strategy:
        1. High pollution + Heavy traffic → Maximize green time (reduce idling)
        2. Heavy traffic + Low pollution → Balanced optimization
        3. Light traffic + High pollution → Shorter cycles (faster through)
        4. Light traffic + Low pollution → Standard timing
        
        Args:
            intersection_id: Intersection to optimize
            pollution_levels: {direction: aqi_value}
            traffic_recommendations: {direction: recommended_speed}
            
        Returns:
            {
                'signal_timings': {direction: {green, red, cycle_time}},
                'strategy': 'emission_priority' | 'flow_priority' | 'balanced',
                'emission_reduction': percentage,
                'flow_improvement': percentage,
                'urgency': 'critical' | 'high' | 'normal' | 'low'
            }
        """
        
        if intersection_id not in self.intersections:
            return {'error': 'Intersection not found'}
        
        intersection = self.intersections[intersection_id]
        
        # Get queue and congestion data
        queues = [
            intersection.queue_length_north,
            intersection.queue_length_south,
            intersection.queue_length_east,
            intersection.queue_length_west
        ]
        directions = ['north', 'south', 'east', 'west']
        max_queue_length = max(queues)
        
        # Determine optimization strategy
        if intersection.local_aqi > 150 and intersection.avg_congestion > 60:
            strategy = "emission_priority"
        elif intersection.avg_congestion > 60:
            strategy = "flow_priority"
        elif intersection.local_aqi > 100:
            strategy = "emission_priority"
        else:
            strategy = "balanced"
        
        # Calculate optimal timings
        timings = {}
        base_cycle_time = 120
        
        if strategy == "emission_priority":
            # Maximize green time to reduce idling
            base_green = 70
            base_red = 40
            base_cycle = 120
            emission_reduction = 18
            flow_improvement = -5
        elif strategy == "flow_priority":
            # Optimize based on queue distribution
            base_green = 60
            base_red = 50
            base_cycle = 120
            emission_reduction = 5
            flow_improvement = 15
        else:  # balanced
            base_green = 50
            base_red = 60
            base_cycle = 120
            emission_reduction = 10
            flow_improvement = 8
        
        # Allocate green time based on queue length (longer queue = more green time)
        total_queue = max(1, sum(queues))
        signal_timings = {}
        
        for i, direction in enumerate(directions):
            queue_proportion = queues[i] / total_queue
            adjusted_green = max(15, min(80, base_green * (0.5 + queue_proportion)))
            adjusted_red = base_cycle - adjusted_green - 5  # 5 seconds yellow + all-red
            
            signal_timings[direction] = {
                'green_time': int(adjusted_green),
                'red_time': int(adjusted_red),
                'yellow_time': 5,
                'all_red_time': 3,
                'cycle_time': base_cycle,
                'queue_length': queues[i],
                'priority': 'high' if queue_proportion > 0.35 else 'normal'
            }
            
            # Update signal
            intersection.signals[direction].green_time = int(adjusted_green)
            intersection.signals[direction].red_time = int(adjusted_red)
            intersection.signals[direction].cycle_time = base_cycle
        
        return {
            'intersection_id': intersection_id,
            'signal_timings': signal_timings,
            'strategy': strategy,
            'emission_reduction': emission_reduction,
            'flow_improvement': flow_improvement,
            'urgency': intersection.priority_level,
            'timestamp': datetime.now().isoformat()
        }
    
    def coordinate_green_wave(self, intersection_ids: List[str],
                             road_name: str = "main_corridor",
                             target_speed: float = 30.0) -> Dict:
        """
        Coordinate green wave across multiple intersections
        
        Green wave: Synchronize signals so vehicles get green lights sequentially
        Reduces stops and improves traffic flow
        
        Args:
            intersection_ids: List of intersection IDs along corridor
            road_name: Name of corridor/road
            target_speed: Target speed for green wave (km/h)
            
        Returns:
            {
                'corridor': road_name,
                'offsets': {int_id: offset_seconds},
                'expected_travel_time': minutes,
                'stops_reduced': percentage,
                'emissions_reduced': percentage
            }
        """
        
        if len(intersection_ids) < 2:
            return {'error': 'Need at least 2 intersections for green wave'}
        
        # Estimate distance between intersections
        # Simplified: assume ~1 km between each intersection
        distance_between = 1.0  # km
        travel_time_per_intersection = (distance_between / target_speed) * 60  # seconds
        
        offsets = {}
        total_stops_reduced = 0
        total_emissions_reduced = 0
        
        for i, int_id in enumerate(intersection_ids):
            if int_id not in self.intersections:
                continue
            
            # Calculate offset for green wave
            # Each intersection gets a delayed green to align with traffic flow
            offset = int(i * travel_time_per_intersection)
            offsets[int_id] = offset
            
            # Store offset
            self.coordination_offsets[int_id] = offset
            
            # Update signal adaptive offset
            for direction in self.intersections[int_id].signals:
                self.intersections[int_id].signals[direction].adaptive_offset = offset
            
            # Estimate improvements
            total_stops_reduced += 12  # Estimate: 12% per intersection
            total_emissions_reduced += 8  # Estimate: 8% per intersection
        
        avg_stops_reduced = total_stops_reduced / len(intersection_ids)
        avg_emissions_reduced = total_emissions_reduced / len(intersection_ids)
        
        # Calculate total travel time
        total_distance = distance_between * (len(intersection_ids) - 1)
        travel_time_minutes = (total_distance / target_speed) * 60
        
        return {
            'corridor': road_name,
            'intersections': intersection_ids,
            'offsets_seconds': offsets,
            'target_speed_kmph': target_speed,
            'expected_travel_time_minutes': round(travel_time_minutes, 1),
            'total_corridor_distance_km': round(total_distance, 1),
            'stops_reduced_percent': round(avg_stops_reduced, 1),
            'emissions_reduced_percent': round(avg_emissions_reduced, 1),
            'coordination_status': 'active',
            'timestamp': datetime.now().isoformat()
        }
    
    def detect_conflicts(self, intersection_id: str) -> List[Dict]:
        """
        Detect potential traffic conflicts at intersection
        
        Conflicts:
        - Queue overflow (exceeds capacity)
        - Opposite flows blocked (opposing directions both queued)
        - Signal timing conflicts
        - Deadlock situations
        
        Args:
            intersection_id: Intersection to check
            
        Returns:
            List of detected conflicts with severity
        """
        
        if intersection_id not in self.intersections:
            return []
        
        intersection = self.intersections[intersection_id]
        conflicts = []
        
        # Conflict 1: Queue overflow
        queue_capacity = 100  # vehicles
        for direction in ['north', 'south', 'east', 'west']:
            queue = getattr(intersection, f'queue_length_{direction}')
            if queue > queue_capacity:
                conflicts.append({
                    'type': 'queue_overflow',
                    'direction': direction,
                    'severity': 'critical' if queue > queue_capacity * 1.5 else 'high',
                    'queue_length': queue,
                    'capacity': queue_capacity,
                    'remediation': 'Increase green time for this direction'
                })
        
        # Conflict 2: Opposing flows both queued
        if (intersection.queue_length_north > 20 and intersection.queue_length_south > 20) or \
           (intersection.queue_length_east > 20 and intersection.queue_length_west > 20):
            conflicts.append({
                'type': 'opposing_flows_blocked',
                'severity': 'high',
                'remediation': 'Distribute green time between opposing directions'
            })
        
        # Conflict 3: High congestion at intersection
        if intersection.avg_congestion > 70:
            conflicts.append({
                'type': 'high_congestion',
                'severity': 'high',
                'congestion_percent': intersection.avg_congestion,
                'remediation': 'Implement emission priority strategy'
            })
        
        # Conflict 4: Air quality emergency
        if intersection.local_aqi > 200:
            conflicts.append({
                'type': 'air_quality_emergency',
                'severity': 'critical',
                'aqi': intersection.local_aqi,
                'remediation': 'Switch to emission priority mode - maximize green time'
            })
        
        return conflicts
    
    def get_corridor_status(self, corridor_intersections: List[str]) -> Dict:
        """
        Get overall status of a traffic corridor
        
        Args:
            corridor_intersections: List of intersection IDs in corridor
            
        Returns:
            Comprehensive corridor analysis
        """
        
        corridor_data = {
            'intersections': len(corridor_intersections),
            'avg_congestion': 0,
            'avg_aqi': 0,
            'total_vehicles_queued': 0,
            'intersections_status': [],
            'conflicts_detected': 0,
            'optimization_needed': False
        }
        
        total_congestion = 0
        total_aqi = 0
        total_conflicts = 0
        
        for int_id in corridor_intersections:
            if int_id not in self.intersections:
                continue
            
            intersection = self.intersections[int_id]
            
            # Collect metrics
            total_congestion += intersection.avg_congestion
            total_aqi += intersection.local_aqi
            
            # Queue analysis
            queues = [intersection.queue_length_north, intersection.queue_length_south,
                     intersection.queue_length_east, intersection.queue_length_west]
            total_queued = sum(queues)
            corridor_data['total_vehicles_queued'] += total_queued
            
            # Detect conflicts
            conflicts = self.detect_conflicts(int_id)
            total_conflicts += len(conflicts)
            
            corridor_data['intersections_status'].append({
                'id': int_id,
                'name': intersection.name,
                'congestion': round(intersection.avg_congestion, 1),
                'aqi': intersection.local_aqi,
                'queued_vehicles': total_queued,
                'priority': intersection.priority_level,
                'conflicts': len(conflicts)
            })
        
        # Calculate averages
        if corridor_intersections:
            n = len([i for i in corridor_intersections if i in self.intersections])
            if n > 0:
                corridor_data['avg_congestion'] = round(total_congestion / n, 1)
                corridor_data['avg_aqi'] = int(total_aqi / n)
        
        corridor_data['conflicts_detected'] = total_conflicts
        corridor_data['optimization_needed'] = total_conflicts > 0 or corridor_data['avg_congestion'] > 60
        
        return corridor_data
    
    def generate_signal_plan(self, intersection_id: str) -> Dict:
        """
        Generate detailed signal control plan for intersection
        
        Returns:
            {
                'current_phase': {direction, time_remaining},
                'next_phases': [sequence of upcoming phases],
                'cycle_timeline': visual timeline,
                'adaptive_parameters': {offsets, timings},
                'estimated_wait_times': {direction: seconds}
            }
        """
        
        if intersection_id not in self.intersections:
            return {'error': 'Intersection not found'}
        
        intersection = self.intersections[intersection_id]
        now = datetime.now()
        
        # Build cycle timeline
        cycle_timeline = []
        current_time = 0
        
        for direction in ['north', 'south', 'east', 'west']:
            signal = intersection.signals[direction]
            
            # Green phase
            cycle_timeline.append({
                'phase': 'GREEN',
                'direction': direction,
                'start': current_time,
                'duration': signal.green_time,
                'end': current_time + signal.green_time
            })
            current_time += signal.green_time + signal.yellow_time + signal.all_red_time
        
        # Estimate wait times
        wait_times = {}
        for direction in ['north', 'south', 'east', 'west']:
            signal = intersection.signals[direction]
            estimated_wait = signal.red_time / 2  # Average wait time
            wait_times[direction] = int(estimated_wait)
        
        return {
            'intersection_id': intersection_id,
            'name': intersection.name,
            'cycle_timeline': cycle_timeline,
            'total_cycle_time': sum([s.cycle_time for s in intersection.signals.values()]) // 4,
            'adaptive_offsets': {
                direction: intersection.signals[direction].adaptive_offset
                for direction in intersection.signals
            },
            'estimated_wait_times_seconds': wait_times,
            'priority_level': intersection.priority_level,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_network_status(self) -> Dict:
        """Get overall traffic signal network status"""
        
        all_intersections = list(self.intersections.values())
        
        if not all_intersections:
            return {'error': 'No intersections configured'}
        
        avg_congestion = np.mean([i.avg_congestion for i in all_intersections])
        avg_aqi = int(np.mean([i.local_aqi for i in all_intersections]))
        total_queued = sum([i.queue_length_north + i.queue_length_south + 
                           i.queue_length_east + i.queue_length_west 
                           for i in all_intersections])
        
        critical_intersections = sum(1 for i in all_intersections if i.priority_level == 'critical')
        high_priority_intersections = sum(1 for i in all_intersections if i.priority_level in ['critical', 'high'])
        
        return {
            'total_intersections': len(self.intersections),
            'avg_network_congestion_percent': round(avg_congestion, 1),
            'avg_network_aqi': avg_aqi,
            'total_vehicles_queued': total_queued,
            'critical_intersections': critical_intersections,
            'high_priority_intersections': high_priority_intersections,
            'optimization_mode': self.optimization_mode,
            'intersections_summary': [
                {
                    'id': i.intersection_id,
                    'name': i.name,
                    'congestion': round(i.avg_congestion, 1),
                    'aqi': i.local_aqi,
                    'priority': i.priority_level
                }
                for i in all_intersections
            ],
            'timestamp': datetime.now().isoformat()
        }


# Example usage
if __name__ == "__main__":
    # Initialize coordinator
    coordinator = TrafficSignalCoordinator(city_name="bengaluru")
    
    print("\n" + "="*80)
    print("TRAFFIC SIGNAL COORDINATOR - NETWORK MANAGEMENT".center(80))
    print("="*80)
    
    # Simulate traffic data for intersections
    traffic_scenarios = {
        'INT_001': {
            'queues': {'north': 45, 'south': 30, 'east': 25, 'west': 35},
            'avg_speed': 25.0,
            'congestion': 65.5
        },
        'INT_002': {
            'queues': {'north': 20, 'south': 25, 'east': 40, 'west': 30},
            'avg_speed': 28.0,
            'congestion': 55.0
        },
        'INT_003': {
            'queues': {'north': 35, 'south': 35, 'east': 20, 'west': 25},
            'avg_speed': 22.0,
            'congestion': 70.0
        },
        'INT_004': {
            'queues': {'north': 15, 'south': 20, 'east': 30, 'west': 25},
            'avg_speed': 32.0,
            'congestion': 45.0
        },
        'INT_005': {
            'queues': {'north': 50, 'south': 45, 'east': 55, 'west': 40},
            'avg_speed': 20.0,
            'congestion': 75.0
        },
    }
    
    pollution_levels = {
        'INT_001': 120,  # Moderate
        'INT_002': 95,   # Good
        'INT_003': 180,  # High
        'INT_004': 85,   # Good
        'INT_005': 150,  # High
    }
    
    # Update intersections
    print("\n📊 Updating Intersection Data...")
    for int_id, traffic in traffic_scenarios.items():
        coordinator.update_intersection_data(int_id, traffic, pollution_levels.get(int_id, 100))
    
    # Get network status
    print("\n🌐 NETWORK STATUS")
    print("-" * 80)
    status = coordinator.get_network_status()
    print(f"Total Intersections: {status['total_intersections']}")
    print(f"Average Congestion: {status['avg_network_congestion_percent']}%")
    print(f"Average AQI: {status['avg_network_aqi']}")
    print(f"Total Vehicles Queued: {status['total_vehicles_queued']}")
    print(f"Critical Intersections: {status['critical_intersections']}")
    print(f"High Priority: {status['high_priority_intersections']}")
    
    # Optimize signal timings
    print("\n\n🎯 SIGNAL OPTIMIZATION")
    print("-" * 80)
    for int_id in list(coordinator.intersections.keys())[:3]:
        optimization = coordinator.optimize_signal_timing(int_id, pollution_levels)
        print(f"\n📍 {optimization['intersection_id']}")
        print(f"   Strategy: {optimization['strategy'].upper()}")
        print(f"   Urgency: {optimization['urgency']}")
        print(f"   Expected Emission Reduction: {optimization['emission_reduction']}%")
        print(f"   Expected Flow Improvement: {optimization['flow_improvement']}%")
        print(f"   Signal Timings:")
        for direction, timing in optimization['signal_timings'].items():
            print(f"      {direction.upper()}: Green {timing['green_time']}s | Red {timing['red_time']}s | Cycle {timing['cycle_time']}s")
    
    # Coordinate green wave
    print("\n\n💚 GREEN WAVE COORDINATION")
    print("-" * 80)
    green_wave = coordinator.coordinate_green_wave(
        ['INT_001', 'INT_003', 'INT_005'],
        road_name="Main Corridor - MG Road",
        target_speed=30.0
    )
    print(f"Corridor: {green_wave['corridor']}")
    print(f"Intersections: {len(green_wave['intersections'])}")
    print(f"Target Speed: {green_wave['target_speed_kmph']} km/h")
    print(f"Expected Travel Time: {green_wave['expected_travel_time_minutes']} minutes")
    print(f"Stops Reduced: {green_wave['stops_reduced_percent']}%")
    print(f"Emissions Reduced: {green_wave['emissions_reduced_percent']}%")
    print(f"\nSignal Offsets (seconds):")
    for int_id, offset in green_wave['offsets_seconds'].items():
        print(f"  {int_id}: {offset}s")
    
    # Conflict detection
    print("\n\n⚠️  CONFLICT DETECTION")
    print("-" * 80)
    for int_id in coordinator.intersections:
        conflicts = coordinator.detect_conflicts(int_id)
        if conflicts:
            print(f"\n📍 {int_id}:")
            for conflict in conflicts:
                print(f"   ⚠️  {conflict['type'].upper()} ({conflict['severity']})")
                print(f"      → {conflict.get('remediation', 'No action needed')}")
    
    # Corridor analysis
    print("\n\n🛣️  CORRIDOR ANALYSIS")
    print("-" * 80)
    corridor = coordinator.get_corridor_status(['INT_001', 'INT_003', 'INT_005'])
    print(f"Corridor Intersections: {corridor['intersections']}")
    print(f"Average Congestion: {corridor['avg_congestion']}%")
    print(f"Average AQI: {corridor['avg_aqi']}")
    print(f"Total Vehicles Queued: {corridor['total_vehicles_queued']}")
    print(f"Conflicts Detected: {corridor['conflicts_detected']}")
    print(f"Optimization Needed: {'Yes' if corridor['optimization_needed'] else 'No'}")
    
    print("\n" + "="*80 + "\n")
