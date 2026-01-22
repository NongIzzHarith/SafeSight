import streamlit as st
import requests
import time
import joblib
import os
import pandas as pd
import plotly.graph_objects as go
import folium
from folium.plugins import HeatMap
from streamlit_folium import st_folium
import subprocess
import json
from datetime import datetime, timedelta

# --- CONFIGURATION ---
ESP_IP = "http://10.95.226.155/data"  # <--- UPDATED WITH YOUR NEW IP
DATA_PATH = os.path.join('data', 'gas_log.csv')

# --- THRESHOLDS ---
METHANE_SAFE = 500; METHANE_WARNING = 1000
CO_SAFE = 50; CO_WARNING = 200
TEMP_SAFE = 29; TEMP_WARNING = 40

def get_status(value, safe, warning):
    if value <= safe: return "SAFE"
    elif value <= warning: return "WARNING"
    else: return "DANGER"

def get_laptop_gps():
    """Get GPS coordinates from macOS using Core Location via Python"""
    try:
        # Try using PyObjC if available
        import objc
        from Foundation import NSBundle
        
        # Load CoreLocation framework
        bundle = NSBundle.bundleWithPath_('/System/Library/Frameworks/CoreLocation.framework')
        objc.loadBundle('CoreLocation', globals(), bundle)
        
        from CoreLocation import CLLocationManager
        manager = CLLocationManager()
        location = manager.location()
        
        if location:
            return {
                'lat': float(location.coordinate().latitude),
                'lng': float(location.coordinate().longitude)
            }
    except:
        pass
    
    return None

def create_gauge(value, title, max_val, safe_threshold, warning_threshold):
    """Create a gauge chart using Plotly"""
    if value <= safe_threshold:
        color = "green"
        status = "SAFE"
    elif value <= warning_threshold:
        color = "orange"
        status = "WARNING"
    else:
        color = "red"
        status = "DANGER"
    
    fig = go.Figure(data=[go.Indicator(
        mode="gauge+number+delta",
        value=value,
        title={'text': f"{title}<br><sub>{status}</sub>"},
        delta={'reference': safe_threshold},
        gauge={
            'axis': {'range': [0, max_val]},
            'bar': {'color': color},
            'steps': [
                {'range': [0, safe_threshold], 'color': "#90EE90"},
                {'range': [safe_threshold, warning_threshold], 'color': "#FFD700"},
                {'range': [warning_threshold, max_val], 'color': "#FF6B6B"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 2},
                'thickness': 0.75,
                'value': warning_threshold
            }
        }
    )])
    fig.update_layout(margin=dict(l=20, r=20, t=60, b=20), height=300)
    return fig

# --- LOAD AI MODELS ---
try:
    m_model = joblib.load('src/methane_model.pkl')
    c_model = joblib.load('src/co_model.pkl')
    t_model = joblib.load('src/temp_model.pkl')
    ai_ready = True
    st.sidebar.success("✅ AI Models Loaded")
except Exception as e:
    ai_ready = False
    st.sidebar.error(f"❌ AI Model Error: {str(e)[:50]}")

# Add JavaScript for browser geolocation
def inject_geolocation():
    """Inject JavaScript to get browser geolocation"""
    geolocation_script = """
    <script>
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function(position) {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                
                // Store in session storage
                sessionStorage.setItem('latitude', lat);
                sessionStorage.setItem('longitude', lng);
                
                // Try to send to Streamlit
                if (window.parent && window.parent.streamlit) {
                    window.parent.streamlit.setComponentValue({
                        lat: lat,
                        lng: lng,
                        accuracy: position.coords.accuracy
                    });
                }
            },
            function(error) {
                console.log('Geolocation error:', error);
            },
            {enableHighAccuracy: true, timeout: 10000, maximumAge: 0}
        );
    }
    </script>
    """
    st.components.v1.html(geolocation_script, height=0)

# --- UI SETUP ---
st.set_page_config(layout="wide", page_title="Wireless AI Monitor", initial_sidebar_state="expanded")

# Dark theme CSS
st.markdown("""
    <style>
    :root {
        --primary-color: #00D9FF;
        --secondary-color: #0A1428;
        --accent-color: #FF6B6B;
    }
    
    body {
        background-color: #0A1428;
        color: #E8E8E8;
    }
    
    .main {
        background-color: #0A1428;
    }
    
    .stMetric {
        background-color: #1a2a4a;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #00D9FF;
    }
    
    .stTabs [data-baseweb="tab-list"] button {
        background-color: #1a2a4a;
        color: #00D9FF;
        border-radius: 5px;
        border: 1px solid #00D9FF;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #00D9FF !important;
        color: #0A1428 !important;
    }
    
    .css-1d391kg {
        background-color: #1a2a4a;
    }
    </style>
""", unsafe_allow_html=True)

# SIDEBAR
st.sidebar.header("📍 GPS Location")

# Initialize GPS session state
if 'lat' not in st.session_state:
    st.session_state.lat = 3.1412
if 'lng' not in st.session_state:
    st.session_state.lng = 101.6860
if 'gps_enabled' not in st.session_state:
    st.session_state.gps_enabled = False
if 'heatmap_data' not in st.session_state:
    st.session_state.heatmap_data = []  # Store [lat, lng, intensity] for heatmap

# GPS Source Selection
gps_mode = st.sidebar.radio("GPS Source", ["Browser Location", "Manual Input"], horizontal=True)

if gps_mode == "Browser Location":
    if st.sidebar.button("🔄 Get Laptop GPS", use_container_width=True):
        st.session_state.gps_enabled = True
        st.info("📍 Please allow location access in your browser when prompted")
    
    if st.session_state.gps_enabled:
        st.sidebar.success(f"📍 Laptop GPS: {st.session_state.lat:.4f}, {st.session_state.lng:.4f}")
else:
    # Manual GPS Input
    st.session_state.lat = st.sidebar.slider("Latitude", 3.1400, 3.1500, st.session_state.lat, step=0.0001)
    st.session_state.lng = st.sidebar.slider("Longitude", 101.6800, 101.7000, st.session_state.lng, step=0.0001)
    st.sidebar.success(f"📍 Manual GPS: {st.session_state.lat:.4f}, {st.session_state.lng:.4f}")

lat = st.session_state.lat
lng = st.session_state.lng

st.sidebar.info(f"Connected to: {ESP_IP}")

# Add mini map to sidebar
st.sidebar.subheader("📍 Current Location")
mini_map = folium.Map(location=[lat, lng], zoom_start=13)
folium.Marker(
    location=[lat, lng],
    popup="Current Sensor Location",
    icon=folium.Icon(color='red', icon='info-sign')
).add_to(mini_map)
with st.sidebar:
    st_folium(mini_map, width=300, height=250)

# Create main tabs
tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "📈 Analytics", "⚙️ Settings", "📋 Logs"])

with tab1:
    st.subheader("📍 SENSOR LOCATION HEATMAP")

    # Heatmap mode selector
    heatmap_mode = st.selectbox("Heatmap based on:", ["Methane (MQ-4)", "CO (MQ-9)", "Temperature"])

    map_placeholder = st.empty()

# Initialize sensor data in session state
if 'current_gas' not in st.session_state:
    st.session_state.current_gas = 0
if 'current_co' not in st.session_state:
    st.session_state.current_co = 0
if 'current_temp' not in st.session_state:
    st.session_state.current_temp = 0
if 'esp_connected' not in st.session_state:
    st.session_state.esp_connected = False

st.title("🛡️ Wireless Hazard & AI System")

# Inject geolocation script
inject_geolocation()

# Connection Status Indicator
col_status, col_title, col_time = st.columns([1, 3, 1])
with col_status:
    if st.session_state.esp_connected:
        st.success("✅ ESP Connected")
    else:
        st.error("❌ ESP Disconnected")
with col_time:
    st.caption(f"⏰ {datetime.now().strftime('%H:%M:%S')}")

st.subheader("📊 LIVE SENSOR GAUGES")

# Create gauge containers - ALWAYS VISIBLE
col1, col2, col3 = st.columns(3)
gauge_gas = col1.empty()
gauge_co = col2.empty()
gauge_temp = col3.empty()

# Display initial gauges
with col1:
    gauge_gas.plotly_chart(create_gauge(st.session_state.current_gas, "MQ-4 Methane", 2000, METHANE_SAFE, METHANE_WARNING), use_container_width=True)
with col2:
    gauge_co.plotly_chart(create_gauge(st.session_state.current_co, "MQ-9 CO", 500, CO_SAFE, CO_WARNING), use_container_width=True)
with col3:
    gauge_temp.plotly_chart(create_gauge(st.session_state.current_temp, "Temperature", 60, TEMP_SAFE, TEMP_WARNING), use_container_width=True)

st.subheader("📈 LIVE METRICS")
col1, col2, col3 = st.columns(3)
box_gas = col1.empty()
box_co = col2.empty()
box_temp = col3.empty()

# Display initial metrics
box_gas.metric("🔴 MQ-4 Methane", f"{st.session_state.current_gas} ppm", delta=None)
box_co.metric("🔵 MQ-9 CO", f"{st.session_state.current_co} ppm", delta=None)
box_temp.metric("🌡️ Temperature", f"{st.session_state.current_temp}°C", delta=None)

st.subheader("🔮 AI PREDICTION (Next 10s)")
p1, p2, p3 = st.columns(3)
pred_gas = p1.empty()
pred_co = p2.empty()
pred_temp = p3.empty()

# Display initial AI predictions
if ai_ready:
    pred_gas.metric("Pred Methane", "0.0", "SAFE")
    pred_co.metric("Pred CO", "0.0", "SAFE")
    pred_temp.metric("Pred Temp", "0.0", "SAFE")
else:
    pred_gas.warning("AI Model Not Loaded")
    pred_co.warning("AI Model Not Loaded")
    pred_temp.warning("AI Model Not Loaded")

final_alert = st.empty()

# INIT CSV
if not os.path.isfile(DATA_PATH):
    with open(DATA_PATH, 'w') as f:
        f.write("lat,lon,co,gas,temp\n")

# Initialize session state for auto-refresh
if 'running' not in st.session_state:
    st.session_state.running = True

# Placeholder for refresh button
placeholder = st.empty()

# --- MAIN LOOP (POLLING) ---
while st.session_state.running:
    try:
        # FETCH DATA FROM WIFI
        response = requests.get(ESP_IP, timeout=0.5)
        
        if response.status_code == 200:
            data = response.json()
            
            # Parse JSON: {"co": 120, "gas": 400, "temp": 32.5}
            co = int(data['co'])
            gas = int(data['gas'])
            temp = float(data['temp'])
            
            # Store in session state for gauge persistence
            st.session_state.current_gas = gas
            st.session_state.current_co = co
            st.session_state.current_temp = temp
            st.session_state.esp_connected = True

            # Save Data
            with open(DATA_PATH, 'a') as f:
                f.write(f"{lat},{lng},{co},{gas},{temp}\n")
            
            # Add to heatmap data (normalize values to 0-1 scale)
            # Methane: max 2000 ppm
            # CO: max 500 ppm
            # Temp: max 60°C
            gas_intensity = min(gas / 2000, 1.0)
            co_intensity = min(co / 500, 1.0)
            temp_intensity = min(temp / 60, 1.0)
            
            st.session_state.heatmap_data.append({
                'lat': lat,
                'lng': lng,
                'gas': gas_intensity,
                'co': co_intensity,
                'temp': temp_intensity
            })
            
            # Keep only last 100 readings for performance
            if len(st.session_state.heatmap_data) > 100:
                st.session_state.heatmap_data = st.session_state.heatmap_data[-100:]

            # Display Live Metrics
            box_gas.metric("🔴 MQ-4 Methane", f"{gas} ppm", delta=None)
            box_co.metric("🔵 MQ-9 CO", f"{co} ppm", delta=None)
            box_temp.metric("🌡️ Temperature", f"{temp}°C", delta=None)
            
            # Update gauges with new data
            gauge_gas.plotly_chart(create_gauge(gas, "MQ-4 Methane", 2000, METHANE_SAFE, METHANE_WARNING), use_container_width=True, key=f"gas_{time.time()}")
            gauge_co.plotly_chart(create_gauge(co, "MQ-9 CO", 500, CO_SAFE, CO_WARNING), use_container_width=True, key=f"co_{time.time()}")
            gauge_temp.plotly_chart(create_gauge(temp, "Temperature", 60, TEMP_SAFE, TEMP_WARNING), use_container_width=True, key=f"temp_{time.time()}")
            
            # Create and display Heatmap
            m = folium.Map(location=[lat, lng], zoom_start=15)
            
            # Prepare heatmap data based on selected mode
            if heatmap_mode == "Methane (MQ-4)":
                heatmap_points = [[d['lat'], d['lng'], d['gas']] for d in st.session_state.heatmap_data]
                HeatMap(heatmap_points, min_opacity=0.2, max_zoom=18, radius=25, blur=15, 
                       gradient={0.0: 'blue', 0.5: 'yellow', 1.0: 'red'}).add_to(m)
            elif heatmap_mode == "CO (MQ-9)":
                heatmap_points = [[d['lat'], d['lng'], d['co']] for d in st.session_state.heatmap_data]
                HeatMap(heatmap_points, min_opacity=0.2, max_zoom=18, radius=25, blur=15,
                       gradient={0.0: 'green', 0.5: 'orange', 1.0: 'red'}).add_to(m)
            else:  # Temperature
                heatmap_points = [[d['lat'], d['lng'], d['temp']] for d in st.session_state.heatmap_data]
                HeatMap(heatmap_points, min_opacity=0.2, max_zoom=18, radius=25, blur=15,
                       gradient={0.0: 'blue', 0.5: 'purple', 1.0: 'red'}).add_to(m)
            
            # Add current reading marker
            folium.CircleMarker(
                location=[lat, lng],
                radius=10,
                popup=f"<b>Current Reading</b><br>Gas: {gas} ppm<br>CO: {co} ppm<br>Temp: {temp}°C<br>Readings: {len(st.session_state.heatmap_data)}",
                color='red',
                fill=True,
                fillColor='red',
                fillOpacity=0.8
            ).add_to(m)
            
            # Display Heatmap
            map_placeholder.empty()
            with map_placeholder.container():
                st_folium(m, width=1200, height=500)

            # Run AI
            if ai_ready:
                try:
                    inp = [[gas, co, temp]]
                    p_m = m_model.predict(inp)[0]
                    p_c = c_model.predict(inp)[0]
                    p_t = t_model.predict(inp)[0]

                    s_m = get_status(p_m, METHANE_SAFE, METHANE_WARNING)
                    s_c = get_status(p_c, CO_SAFE, CO_WARNING)
                    s_t = get_status(p_t, TEMP_SAFE, TEMP_WARNING)

                    pred_gas.metric("Pred Methane", f"{p_m:.1f}", s_m)
                    pred_co.metric("Pred CO", f"{p_c:.1f}", s_c)
                    pred_temp.metric("Pred Temp", f"{p_t:.1f}", s_t)

                    if "DANGER" in [s_m, s_c, s_t]:
                        final_alert.error("🚨 CRITICAL PREDICTION: DANGER")
                    else:
                        final_alert.success("✅ SYSTEM PREDICTION: SAFE")
                except Exception as e:
                    final_alert.error(f"AI Prediction Error: {str(e)[:100]}")

    except Exception as e:
        # Display error for debugging
        placeholder.warning(f"Waiting for ESP data... ({str(e)[:50]})")
        
    time.sleep(0.5) # Update 2 times per second