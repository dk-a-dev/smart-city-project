#!/usr/bin/env python3
"""🌍 EcoSignal: Interactive Streamlit Dashboard"""

import streamlit as st
import sys
import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import requests

# Add agents to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'agents'))

try:
    from air_quality_agent import AirQualityMonitorAgent
    from signal_coordinator_agent import TrafficSignalCoordinator
except ImportError:
    st.error("Could not import agents")
    st.stop()

# PAGE CONFIG
st.set_page_config(page_title="🌍 EcoSignal", page_icon="🚗", layout="wide")

st.markdown("# 🌍 EcoSignal: Adaptive Traffic Control System")
st.markdown("### Real-Time Multi-Agent Traffic & Air Quality Management")

# API KEYS
waqi_key = "6156a307c458ded2cade119f90a3435b2e341200"
tomtom_key = "AjUGQBYYQkgDFM6UGLRWQbNtzU9raICL"

# LOCATION COORDINATES
LOCATIONS = {
    "Bengaluru (MG Road)": {"lat": 13.0827, "lon": 80.2707, "city": "bengaluru"},
    "Bengaluru (Indiranagar)": {"lat": 13.0357, "lon": 80.2635, "city": "bengaluru"},
    "Bengaluru (Whitefield)": {"lat": 12.9698, "lon": 77.7499, "city": "bengaluru"},
    "Delhi (Connaught Place)": {"lat": 28.6315, "lon": 77.1895, "city": "delhi"},
    "Mumbai (Bandra)": {"lat": 19.0596, "lon": 72.8295, "city": "mumbai"},
}

CAR_TYPES = {
    "Sedan": {"fuel_efficiency": 15, "engine_size": 1.6, "emissions_factor": 120},
    "SUV": {"fuel_efficiency": 12, "engine_size": 2.0, "emissions_factor": 150},
    "Hatchback": {"fuel_efficiency": 18, "engine_size": 1.2, "emissions_factor": 100},
    "Electric": {"fuel_efficiency": 0, "engine_size": 0, "emissions_factor": 0},
    "Hybrid": {"fuel_efficiency": 22, "engine_size": 1.8, "emissions_factor": 60},
}

# SIDEBAR CONFIGURATION
st.sidebar.markdown("## ⚙️ User Preferences")
st.sidebar.markdown("---")

# SIDEBAR - USER INPUT
st.sidebar.markdown("### 🗺️ Trip Configuration")
location = st.sidebar.selectbox("📍 Select Location", list(LOCATIONS.keys()), help="Choose your driving location")
car_type = st.sidebar.selectbox("🚗 Select Car Type", list(CAR_TYPES.keys()), help="What type of vehicle are you driving?")
trip_distance = st.sidebar.slider("📏 Trip Distance (km)", 1, 100, 10, help="How far are you traveling?")
current_speed = st.sidebar.slider("⚡ Your Current Speed (km/h)", 0, 100, 30, help="What's your current driving speed?")
num_passengers = st.sidebar.slider("👥 Number of Passengers", 1, 6, 1, help="How many people in the car?")

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Advanced Options")
route_preference = st.sidebar.selectbox("🛣️ Route Preference", ["Fastest", "Eco-Friendly", "Balanced"], help="Optimize route for time or emissions")
departure_time = st.sidebar.selectbox("⏰ Departure Time", ["Now", "Peak Hours", "Off-Peak"], help="When are you leaving?")
enable_alerts = st.sidebar.checkbox("🔔 Enable Alerts", value=True, help="Get real-time alerts while driving")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🎯 Trip Metrics")

# GET SELECTED LOCATION DATA
loc_data = LOCATIONS[location]
lat, lon = loc_data['lat'], loc_data['lon']
city = loc_data['city']
car_data = CAR_TYPES[car_type]

# CACHE FUNCTIONS
@st.cache_data(ttl=60)
def get_aqi_data(city_name):
    try:
        agent = AirQualityMonitorAgent(waqi_key, city_name)
        return agent.fetch_current_aqi()
    except Exception as e:
        st.warning(f"Could not fetch AQI: {e}")
        return None

@st.cache_data(ttl=60)
def get_traffic_data(latitude, longitude):
    try:
        url = "https://api.tomtom.com/traffic/services/4/flowSegmentData/relative0/10/json"
        roads = []
        for dlat, dlon in [(0, 0), (0.01, 0), (-0.01, 0), (0, 0.01), (0, -0.01)]:
            try:
                params = {'point': f"{latitude+dlat},{longitude+dlon}", 'unit': 'KMPH', 'key': tomtom_key}
                r = requests.get(url, params=params, timeout=10)
                if r.status_code == 200 and 'flowSegmentData' in r.json():
                    s = r.json()['flowSegmentData']
                    roads.append({
                        'name': f'Segment {len(roads)+1}',
                        'speed': s.get('currentSpeed', 0),
                        'ff_speed': s.get('freeFlowSpeed', 60),
                        'congestion': round((s.get('currentTravelTime', 0) / max(1, s.get('freeFlowTravelTime', 1)) - 1) * 100, 1)
                    })
            except:
                pass
        return roads if roads else []
    except Exception as e:
        st.warning(f"Could not fetch traffic: {e}")
        return []

# CALCULATE EMISSIONS
def calculate_emissions(speed, congestion, car_type_data, distance):
    """Calculate estimated emissions for trip"""
    base_emissions = car_type_data['emissions_factor']
    
    # Adjust based on speed (optimal around 50 km/h)
    if speed < 20:
        speed_factor = 1.4
    elif speed < 40:
        speed_factor = 1.1
    elif speed > 80:
        speed_factor = 1.3
    else:
        speed_factor = 1.0
    
    # Adjust based on congestion
    congestion_factor = 1 + (congestion / 100) * 0.5
    
    total_emissions = (base_emissions * speed_factor * congestion_factor * distance) / 100
    return total_emissions

# CALCULATE FUEL COST
def calculate_fuel_cost(speed, distance, car_type_data, fuel_price_per_liter=90):
    """Calculate fuel cost for trip"""
    base_efficiency = car_type_data['fuel_efficiency']
    
    # Adjust efficiency based on speed
    if speed < 20:
        efficiency = base_efficiency * 0.6
    elif speed < 40:
        efficiency = base_efficiency * 0.8
    else:
        efficiency = base_efficiency
    
    liters_needed = distance / efficiency if efficiency > 0 else 0
    cost = liters_needed * fuel_price_per_liter
    return cost, liters_needed

# FETCH DATA
aqi_data = get_aqi_data(city)
traffic_data = get_traffic_data(lat, lon)

# DISPLAY RECOMMENDATIONS IN SIDEBAR
if traffic_data and aqi_data:
    avg_cong = np.mean([r['congestion'] for r in traffic_data])
    avg_speed_traffic = np.mean([r['speed'] for r in traffic_data])
    emissions = calculate_emissions(current_speed, avg_cong, car_data, trip_distance)
    fuel_cost, fuel_liters = calculate_fuel_cost(current_speed, trip_distance, car_data)
    
    st.sidebar.metric("💨 Est. Emissions", f"{emissions:.2f} kg CO₂")
    st.sidebar.metric("⛽ Est. Fuel Cost", f"₹{fuel_cost:.2f}")
    st.sidebar.metric("🌍 AQI Level", aqi_data['aqi'])
    st.sidebar.metric("🚗 Avg Traffic Speed", f"{avg_speed_traffic:.0f} km/h")

# MAIN TABS
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📊 Overview", "💨 Air Quality", "🚗 Traffic", "🚦 Signals", "💡 Recommendations", "📈 Advanced Analytics"])

# TAB 1: OVERVIEW
with tab1:
    st.markdown(f"## 🗺️ {location}")
    st.markdown(f"**Your Vehicle**: {car_type} | **Trip**: {trip_distance} km | **Passengers**: {num_passengers} | **Route**: {route_preference} | **Departure**: {departure_time}")
    
    if aqi_data and traffic_data:
        aqi = aqi_data['aqi']
        avg_cong = np.mean([r['congestion'] for r in traffic_data])
        avg_speed_traffic = np.mean([r['speed'] for r in traffic_data])
        emissions = calculate_emissions(current_speed, avg_cong, car_data, trip_distance)
        fuel_cost, fuel_liters = calculate_fuel_cost(current_speed, trip_distance, car_data)
        
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        with col1:
            st.metric("🌍 AQI", aqi, "Satisfactory" if aqi < 100 else ("Unhealthy" if aqi > 150 else "Moderate"))
        
        with col2:
            st.metric("🚗 Congestion", f"{avg_cong:.1f}%", delta=f"{avg_cong - 50:.0f}%")
        
        with col3:
            st.metric("⚡ Avg Speed", f"{avg_speed_traffic:.0f} km/h")
        
        with col4:
            st.metric("💨 Your CO₂", f"{emissions:.2f} kg", delta=f"+{emissions*0.2:.2f}" if emissions > 5 else "✅ Low")
        
        with col5:
            st.metric("⛽ Fuel Cost", f"₹{fuel_cost:.2f}", f"({fuel_liters:.2f}L)")
        
        with col6:
            carbon_offset = emissions * 0.7 if route_preference == "Eco-Friendly" else emissions
            st.metric("🌱 Eco Score", f"{int(100 - (emissions/10)*100)}%", "↑ +20%" if emissions < 5 else "→ Neutral")
        
        st.markdown("---")
        
        # QUICK STATS
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            est_time = trip_distance / (avg_speed_traffic if avg_speed_traffic > 0 else 30) * 60
            st.markdown(f"**Est. Duration**: {est_time:.0f} min")
        
        with col2:
            cost_per_km = fuel_cost / trip_distance
            st.markdown(f"**Cost/km**: ₹{cost_per_km:.2f}")
        
        with col3:
            emission_per_passenger = emissions / num_passengers
            st.markdown(f"**CO₂/Passenger**: {emission_per_passenger:.2f} kg")
        
        with col4:
            speed_efficiency = "🟢 Good" if current_speed < 60 else ("🟠 Moderate" if current_speed < 80 else "🔴 Poor")
            st.markdown(f"**Speed Efficiency**: {speed_efficiency}")
        
        st.markdown("---")
        
        # DYNAMIC RECOMMENDATION BANNER
        if aqi > 150 and avg_cong > 60:
            st.error("🔴 **CRITICAL CONDITIONS**: High pollution + Heavy congestion. Consider using public transport or postponing trip.")
        elif aqi > 100 and avg_cong > 50:
            st.warning("🟠 **CAUTION**: Moderate-high pollution and congestion. Follow green wave recommendations. Add 15 mins to travel time.")
        elif car_type == "Electric":
            st.success("🟢 **EXCELLENT**: Electric vehicle + manageable conditions. Drive safely! Zero emissions achieved.")
        elif num_passengers >= 4:
            st.success("🟢 **OPTIMAL**: High passenger count reduces per-person emissions significantly. Great carpooling!")
        elif emissions < 5:
            st.success("🟢 **GOOD**: Emissions below average. Maintain current speed and route.")
        else:
            st.info("🟡 **NORMAL**: Conditions are moderate. Check recommendations tab for optimization strategies.")

# TAB 2: AIR QUALITY
with tab2:
    if aqi_data:
        st.markdown(f"## 💨 Air Quality in {location.split('(')[0].strip()}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### AQI Gauge")
            fig = go.Figure(data=[go.Indicator(
                mode="gauge+number",
                value=aqi_data['aqi'],
                title="AQI",
                gauge={
                    'axis': {'range': [0, 500]},
                    'steps': [
                        {'range': [0, 50], 'color': "lightgreen"},
                        {'range': [50, 100], 'color': "lightyellow"},
                        {'range': [100, 150], 'color': "lightsalmon"},
                        {'range': [150, 500], 'color': "lightcoral"}
                    ],
                    'threshold': {'line': {'color': "red"}, 'thickness': 0.4, 'value': 200}
                }
            )])
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("### Pollutant Levels")
            pollutants = {
                'PM2.5': aqi_data.get('pm25', 0),
                'PM10': aqi_data.get('pm10', 0),
                'NO₂': aqi_data.get('no2', 0),
                'O₃': aqi_data.get('o3', 0)
            }
            fig = px.bar(x=list(pollutants.keys()), y=list(pollutants.values()), 
                        labels={'x': 'Pollutant', 'y': 'Concentration (µg/m³)'})
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        st.markdown("### 🏥 Health Impact")
        aqi_val = aqi_data['aqi']
        if aqi_val < 50:
            health_msg = "✅ **Good**: Air quality is satisfactory. Enjoy outdoor activities!"
        elif aqi_val < 100:
            health_msg = "🟡 **Satisfactory**: Air quality is acceptable. Sensitive groups should limit prolonged activities."
        elif aqi_val < 150:
            health_msg = "🟠 **Moderately Polluted**: Members of sensitive groups may experience health effects. Reduce prolonged outdoor activities."
        elif aqi_val < 200:
            health_msg = "🔴 **Poor**: Everyone may experience health effects. Reduce outdoor activities."
        else:
            health_msg = "🟣 **Very Poor**: Serious health effects. Avoid outdoor activities. Use air purifiers and masks."
        
        st.info(health_msg)

# TAB 3: TRAFFIC
with tab3:
    if traffic_data:
        st.markdown(f"## 🚗 Traffic Flow - {location.split('(')[0].strip()}")
        
        df = pd.DataFrame(traffic_data)
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.dataframe(df, use_container_width=True, hide_index=True)
        
        with col2:
            st.markdown("### Summary")
            st.metric("Roads Monitored", len(traffic_data))
            st.metric("Avg Congestion", f"{df['congestion'].mean():.1f}%")
            st.metric("Avg Speed", f"{df['speed'].mean():.0f} km/h")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(df, x='name', y='congestion', title='Congestion by Road (%)', 
                        color='congestion', color_continuous_scale='RdYlGn_r')
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df['name'], y=df['speed'], name='Current Speed', marker_color='steelblue'))
            fig.add_trace(go.Bar(x=df['name'], y=df['ff_speed'], name='Free Flow Speed', marker_color='lightgreen'))
            fig.update_layout(title='Speed Comparison by Road', barmode='group', height=350)
            st.plotly_chart(fig, use_container_width=True)

# TAB 4: SIGNALS
with tab4:
    st.markdown("## 🚦 Traffic Signal Coordination")
    
    coordinator = TrafficSignalCoordinator(city)
    
    scenarios = {
        'INT_001': {'queues': {'north': 35, 'south': 25, 'east': 20, 'west': 28}, 'avg_speed': 20, 'congestion': 53},
        'INT_002': {'queues': {'north': 15, 'south': 20, 'east': 30, 'west': 22}, 'avg_speed': 30, 'congestion': 40},
        'INT_003': {'queues': {'north': 40, 'south': 40, 'east': 15, 'west': 20}, 'avg_speed': 15, 'congestion': 65},
        'INT_004': {'queues': {'north': 25, 'south': 30, 'east': 28, 'west': 22}, 'avg_speed': 25, 'congestion': 50},
        'INT_005': {'queues': {'north': 20, 'south': 18, 'east': 22, 'west': 25}, 'avg_speed': 28, 'congestion': 42},
    }
    
    aqi = aqi_data['aqi'] if aqi_data else 100
    for int_id, traffic in scenarios.items():
        coordinator.update_intersection_data(int_id, traffic, aqi)
    
    status = coordinator.get_network_status()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🌐 Intersections", status['total_intersections'])
    with col2:
        st.metric("⚠️ Critical", status['critical_intersections'])
    with col3:
        st.metric("Avg Congestion", f"{status['avg_network_congestion_percent']:.1f}%")
    with col4:
        st.metric("Avg AQI", f"{status['avg_network_aqi']:.0f}")
    
    st.markdown("---")
    st.markdown("### 💚 Green Wave Coordination")
    
    gw = coordinator.coordinate_green_wave(['INT_001', 'INT_003', 'INT_005'], "Main Corridor - Your Route", 35)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🚦 Travel Time", f"{gw['expected_travel_time_minutes']:.1f} min")
    with col2:
        st.metric("🛑 Stops Reduced", f"{gw['stops_reduced_percent']:.1f}%", delta="⬇️")
    with col3:
        st.metric("💨 Emissions ↓", f"{gw['emissions_reduced_percent']:.1f}%", delta="✅")
    with col4:
        st.metric("📍 Target Speed", f"{gw['target_speed_kmph']:.0f} km/h")
    
    st.info(f"🟢 **Green Wave Active**: Synchronized signals will reduce your stops by {gw['stops_reduced_percent']:.0f}% and emissions by {gw['emissions_reduced_percent']:.0f}%")

# TAB 5: RECOMMENDATIONS
with tab5:
    st.markdown("## 💡 Personalized Recommendations")
    
    if aqi_data and traffic_data:
        aqi = aqi_data['aqi']
        avg_cong = np.mean([r['congestion'] for r in traffic_data])
        emissions = calculate_emissions(current_speed, avg_cong, car_data, trip_distance)
        
        st.markdown("### 🎯 For Your Trip")
        
        recommendations = []
        
        # Air quality recommendations
        if aqi > 150:
            recommendations.append(("🏥 Health Alert", f"AQI {aqi} is very unhealthy. Use N95 masks and limit outdoor exposure."))
        elif aqi > 100:
            recommendations.append(("💨 Air Quality", f"AQI {aqi} - Use air purifier if available. Keep windows closed."))
        else:
            recommendations.append(("🌬️ Air Quality Good", "Current air quality is acceptable. You can open windows for ventilation."))
        
        # Speed recommendations
        if current_speed < 20:
            recommendations.append(("⚡ Speed Alert", "You're driving very slowly. This increases fuel consumption and emissions. Try to maintain 30-50 km/h."))
        elif current_speed > 80:
            recommendations.append(("⚠️ Speeding", "Reduce speed to 50-60 km/h for better fuel efficiency and safety."))
        else:
            recommendations.append(("✅ Optimal Speed", f"Your speed ({current_speed} km/h) is reasonable. Maintain steady acceleration."))
        
        # Vehicle recommendations
        if car_type != "Electric" and aqi > 100:
            recommendations.append(("🔄 Vehicle Suggestion", "Consider using Electric or Hybrid vehicles for days with poor air quality."))
        elif car_type == "Electric":
            recommendations.append(("🌱 Eco-Friendly", "Great! Electric vehicles produce zero emissions. You're helping reduce pollution!"))
        
        # Traffic recommendations
        if avg_cong > 60:
            recommendations.append(("🚗 Traffic Alert", f"Heavy congestion ({avg_cong:.0f}%). Consider leaving earlier or using public transport."))
        else:
            recommendations.append(("✅ Traffic OK", f"Congestion at {avg_cong:.0f}% is manageable. Follow green wave timings for smooth flow."))
        
        # Route recommendations
        if emissions > 8:
            recommended_emissions = emissions * 0.7
            recommendations.append(("🛣️ Route Suggestion", f"Current route generates {emissions:.2f} kg CO₂. Consider slower routes with better air quality (target: {recommended_emissions:.2f} kg)."))
        
        # Passenger recommendations
        if num_passengers == 1:
            recommendations.append(("🚌 Carpooling", "You're alone in the car. Carpooling reduces per-person emissions by 40-50%."))
        elif num_passengers >= 4:
            recommendations.append(("👥 Excellent", f"With {num_passengers} passengers, you're sharing emissions efficiently!"))
        
        for i, (title, text) in enumerate(recommendations, 1):
            st.markdown(f"**{i}. {title}**")
            st.markdown(f"   {text}")
            st.divider()
        
        # ADVANCED RECOMMENDATIONS
        st.markdown("### 🎯 Advanced Optimization Strategies")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("#### ⏱️ Time-Based Strategy")
            if departure_time == "Peak Hours":
                st.warning("Avoid 8-9 AM and 6-7 PM. Leave 30 mins earlier or later for 40% better flow.")
            elif departure_time == "Off-Peak":
                st.success("Excellent timing! Off-peak departure saves 35% emissions.")
            else:
                st.info("Current time not specified. Check peak hours before leaving.")
        
        with col2:
            st.markdown("#### 🛣️ Route Strategy")
            if route_preference == "Eco-Friendly":
                time_diff = 8
                emissions_saved = 3.3
                st.success(f"Eco route adds {time_diff} min but saves {emissions_saved} kg CO₂ (48%)")
            elif route_preference == "Fastest":
                st.warning(f"Fastest route uses {trip_distance * 0.9:.1f}km but 25% more emissions")
            else:
                st.info("Balanced approach provides best overall value")
        
        with col3:
            st.markdown("#### 💚 Sustainability Score")
            sustainability = 60
            if car_type == "Electric":
                sustainability += 40
            elif car_type == "Hybrid":
                sustainability += 25
            if num_passengers > 2:
                sustainability += 15
            if route_preference == "Eco-Friendly":
                sustainability += 10
            sustainability = min(100, sustainability)
            
            st.metric("🌱 Score", f"{sustainability}%", "Excellent!" if sustainability > 75 else "Good")
        
        st.markdown("---")
        
        # COMPARATIVE ANALYSIS
        st.markdown("### 📊 Your Trip vs City Average")
        
        avg_emissions_city = 7.5  # kg CO₂
        avg_cost_city = 65  # rupees
        avg_passengers_city = 1.2
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            user_vs_city_emissions = ((emissions - avg_emissions_city) / avg_emissions_city * 100)
            st.metric("Your Emissions vs City Avg", 
                     f"{'+' if user_vs_city_emissions > 0 else ''}{user_vs_city_emissions:.1f}%",
                     delta=f"{emissions:.2f} vs {avg_emissions_city} kg CO₂")
        
        with col2:
            user_vs_city_cost = ((fuel_cost - avg_cost_city) / avg_cost_city * 100)
            st.metric("Your Cost vs City Avg",
                     f"{'+' if user_vs_city_cost > 0 else ''}{user_vs_city_cost:.1f}%",
                     delta=f"₹{fuel_cost:.0f} vs ₹{avg_cost_city}")
        
        with col3:
            passenger_efficiency = (num_passengers / avg_passengers_city) * 100
            st.metric("Passenger Efficiency",
                     f"{passenger_efficiency:.0f}%",
                     delta=f"{num_passengers} vs {avg_passengers_city:.1f} avg")
        
        st.markdown("---")
        
        # ALERTS & WARNINGS
        st.markdown("### 🚨 Real-Time Alerts")
        
        alerts = []
        if aqi > 200:
            alerts.append(("🟣 VERY POOR AIR QUALITY", "AQI is severe. Postpone non-essential trips.", "error"))
        elif aqi > 150:
            alerts.append(("🔴 POOR AIR", "Use N95 masks. Avoid highways with heavy traffic.", "warning"))
        
        if avg_cong > 70:
            alerts.append(("🚗 SEVERE CONGESTION", f"{avg_cong:.0f}% congestion. Use public transport.", "warning"))
        elif avg_cong > 50:
            alerts.append(("🟠 MODERATE TRAFFIC", "Expect delays. Plan extra time.", "info"))
        
        if current_speed > 80 and emissions > 8:
            alerts.append(("⚡ SPEEDING ALERT", "High speed + traffic = high emissions. Reduce to 60 km/h.", "warning"))
        
        if car_type == "SUV" and emissions > 10:
            alerts.append(("🚙 FUEL INTENSIVE", "Consider carpooling or switching to a sedan.", "info"))
        
        if enable_alerts:
            for alert_title, alert_msg, alert_type in alerts:
                if alert_type == "error":
                    st.error(f"**{alert_title}**: {alert_msg}")
                elif alert_type == "warning":
                    st.warning(f"**{alert_title}**: {alert_msg}")
                else:
                    st.info(f"**{alert_title}**: {alert_msg}")
        
        # IMPACT SUMMARY
        st.markdown("---")
        st.markdown("### 📊 Trip Impact Summary")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            **Emissions Impact**
            - Total CO₂: {emissions:.2f} kg
            - Per km: {emissions/trip_distance:.2f} kg/km
            - Per passenger: {emissions/num_passengers:.2f} kg
            """)
        
        with col2:
            fuel_cost, fuel_liters = calculate_fuel_cost(current_speed, trip_distance, car_data)
            st.markdown(f"""
            **Fuel & Cost**
            - Fuel needed: {fuel_liters:.2f} L
            - Cost: ₹{fuel_cost:.2f}
            - Per km: ₹{fuel_cost/trip_distance:.2f}/km
            """)
        
        with col3:
            est_time = trip_distance / avg_cong * 100 / 25  # Rough estimate
            st.markdown(f"""
            **Time Estimate**
            - Est. duration: {est_time:.0f} minutes
            - Avg speed: {avg_cong:.0f}%
            - Traffic: {np.mean([r['congestion'] for r in traffic_data]):.0f}%
            """)

st.markdown("---")

# TAB 6: ADVANCED ANALYTICS
with tab6:
    st.markdown("## 📈 Advanced Analytics & Predictions")
    
    if aqi_data and traffic_data:
        # HOURLY AQI FORECAST
        st.markdown("### 📊 24-Hour AQI Forecast")
        hours = np.arange(0, 24)
        base_aqi = aqi_data['aqi']
        
        # Simple prediction: peaks at 8am and 6pm (rush hours)
        forecast_aqi = base_aqi + 30 * np.sin((hours - 8) * np.pi / 12) + np.random.normal(0, 5, 24)
        forecast_aqi = np.clip(forecast_aqi, 0, 500)
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hours, y=forecast_aqi, mode='lines+markers', 
                                 name='Predicted AQI', line=dict(color='red', width=2),
                                 fill='tozeroy', fillcolor='rgba(255,0,0,0.2)'))
        fig.add_hline(y=100, line_dash="dash", line_color="orange", annotation_text="⚠️ Moderate")
        fig.add_hline(y=150, line_dash="dash", line_color="red", annotation_text="🔴 Poor")
        fig.update_layout(title='24-Hour Air Quality Forecast', xaxis_title='Hour of Day', yaxis_title='AQI', height=350)
        st.plotly_chart(fig, use_container_width=True)
        
        # TRAFFIC FLOW PREDICTION
        st.markdown("---")
        st.markdown("### 🚗 Traffic Pattern Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Peak hour congestion prediction
            peak_hours = np.array([8, 9, 18, 19])
            off_peak_congestion = 40
            peak_congestion = 75
            
            hourly_congestion = np.array([
                off_peak_congestion + (peak_congestion - off_peak_congestion) * (1 if h in peak_hours else 0.3)
                for h in hours
            ])
            
            fig = px.area(x=hours, y=hourly_congestion, labels={'x': 'Hour of Day', 'y': 'Congestion %'},
                         title='Predicted Hourly Congestion Pattern')
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Emissions throughout day
            emissions_factor = (hourly_congestion / 100) * (120 - 40) + 40  # Speed inversely related to congestion
            daily_emissions = emissions_factor * (trip_distance / 100) * 0.5  # Scaled
            
            fig = go.Figure()
            fig.add_trace(go.Bar(x=hours, y=daily_emissions, name='Emissions (kg CO₂)',
                                marker_color='darkred', opacity=0.7))
            fig.update_layout(title='Estimated Daily Emissions by Hour', xaxis_title='Hour of Day', 
                            yaxis_title='CO₂ (kg)', height=350)
            st.plotly_chart(fig, use_container_width=True)
        
        # ROUTE COMPARISON
        st.markdown("---")
        st.markdown("### 🛣️ Route Optimization Comparison")
        
        routes = {
            'Fastest Route': {'distance': trip_distance * 0.9, 'time': 20, 'congestion': 75, 'emissions': 8.5},
            'Eco-Friendly': {'distance': trip_distance * 1.2, 'time': 28, 'congestion': 40, 'emissions': 5.2},
            'Balanced': {'distance': trip_distance, 'time': 24, 'congestion': 55, 'emissions': 6.8},
            'Scenic': {'distance': trip_distance * 1.4, 'time': 32, 'congestion': 25, 'emissions': 5.0},
        }
        
        route_df = pd.DataFrame(routes).T
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            fig = px.bar(route_df, y=route_df.index, x='emissions', orientation='h', 
                        title='CO₂ Emissions by Route', labels={'emissions': 'CO₂ (kg)'})
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.bar(route_df, y=route_df.index, x='time', orientation='h',
                        title='Travel Time by Route', labels={'time': 'Minutes'})
            st.plotly_chart(fig, use_container_width=True)
        
        with col3:
            fig = px.scatter(route_df, x='time', y='emissions', size='distance', 
                           text=route_df.index, title='Time vs Emissions Trade-off')
            fig.update_traces(textposition='top center', marker=dict(sizemode='diameter', sizeref=2*max(route_df['distance'])/(40.**2)))
            st.plotly_chart(fig, use_container_width=True)
        
        # VEHICLE COMPARISON
        st.markdown("---")
        st.markdown("### 🚙 Vehicle Efficiency Comparison")
        
        vehicle_comparison = pd.DataFrame({
            'Vehicle': list(CAR_TYPES.keys()),
            'CO₂/km': [CAR_TYPES[v]['emissions_factor']/100 for v in CAR_TYPES.keys()],
            'Cost/km': [90/CAR_TYPES[v]['fuel_efficiency'] if CAR_TYPES[v]['fuel_efficiency'] > 0 else 0 for v in CAR_TYPES.keys()],
            'Fuel Efficiency': [CAR_TYPES[v]['fuel_efficiency'] for v in CAR_TYPES.keys()],
        })
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(vehicle_comparison, x='Vehicle', y='CO₂/km', title='Emissions by Vehicle Type',
                        color='CO₂/km', color_continuous_scale='Reds')
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.bar(vehicle_comparison, x='Vehicle', y='Cost/km', title='Cost per km by Vehicle Type',
                        color='Cost/km', color_continuous_scale='Oranges')
            st.plotly_chart(fig, use_container_width=True)
        
        # CUMULATIVE IMPACT
        st.markdown("---")
        st.markdown("### 📊 Weekly Impact Analysis")
        
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        weekly_trips = [2, 2, 2, 1, 2, 1, 0]  # trips per day
        weekly_emissions = np.array(weekly_trips) * 6.8 + np.random.normal(0, 1, 7)
        weekly_cost = np.array(weekly_trips) * 50
        
        fig = go.Figure()
        fig.add_trace(go.Bar(x=days, y=weekly_emissions, name='Emissions (kg CO₂)', yaxis='y', marker_color='red'))
        fig.add_trace(go.Bar(x=days, y=weekly_cost/10, name='Cost (₹/10)', yaxis='y2', marker_color='blue', opacity=0.6))
        
        fig.update_layout(
            title='Weekly Impact Analysis',
            xaxis=dict(title='Day'),
            yaxis=dict(title='Emissions (kg CO₂)'),
            yaxis2=dict(title='Cost (₹/10)', overlaying='y', side='right'),
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # CARBON FOOTPRINT TRACKING
        st.markdown("---")
        st.markdown("### 🌱 Your Carbon Footprint")
        
        col1, col2, col3, col4 = st.columns(4)
        
        monthly_emissions = sum(weekly_emissions) * 4.3  # Approximate
        avg_daily = monthly_emissions / 30
        yearly = monthly_emissions * 12
        
        with col1:
            st.metric("📅 Monthly CO₂", f"{monthly_emissions:.1f} kg", f"{monthly_emissions/100:.0%} of avg")
        
        with col2:
            st.metric("📊 Daily Avg", f"{avg_daily:.2f} kg", "↓ -15% possible")
        
        with col3:
            st.metric("📈 Yearly Est.", f"{yearly:.0f} kg", f"{yearly/1000:.1f} metric tons")
        
        with col4:
            trees_needed = yearly / 21  # 1 tree absorbs ~21 kg CO₂/year
            st.metric("🌳 Trees Needed", f"{trees_needed:.0f}", f"to offset")

st.markdown("---")
st.markdown("✅ **EcoSignal**: Making cities healthier, one adaptive journey at a time 🌍")
