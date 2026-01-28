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
import json
from datetime import datetime, timedelta

# --- CONFIGURATION ---
ESP_IP = "http://10.159.194.155/data"
DATA_PATH = os.path.join('data', 'gas_log.csv')

# --- THRESHOLDS ---
METHANE_SAFE = 500; METHANE_WARNING = 1000
CO_SAFE = 50; CO_WARNING = 200
TEMP_SAFE = 29; TEMP_WARNING = 40

def get_status(value, safe, warning):
    if value <= safe: return "SAFE"
    elif value <= warning: return "WARNING"
    else: return "DANGER"

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
                {'range': [0, safe_threshold], 'color': "#27AE60"},
                {'range': [safe_threshold, warning_threshold], 'color': "#E67E22"},
                {'range': [warning_threshold, max_val], 'color': "#E74C3C"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 2},
                'thickness': 0.75,
                'value': warning_threshold
            }
        }
    )])
    fig.update_layout(margin=dict(l=20, r=20, t=60, b=20), height=300, paper_bgcolor="#1A1A2E", plot_bgcolor="#0F0F1E", font=dict(color="#F0F0F0", size=12))
    return fig

def create_trend_chart(df, column, title, color):
    """Create trend line chart"""
    if len(df) == 0:
        return go.Figure()
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df[column],
        mode='lines+markers',
        name=title,
        line=dict(color=color, width=3),
        marker=dict(size=6)
    ))
    fig.update_layout(
        title=title,
        xaxis_title="Time",
        yaxis_title="Value",
        hovermode='x unified',
        paper_bgcolor="#1A1A2E",
        plot_bgcolor="#0F0F1E",
        font=dict(color="#F0F0F0", size=11),
        title_font=dict(size=14, color="#2E8B9E")
    )
    return fig

def inject_geolocation():
    """Inject JavaScript to continuously get browser geolocation"""
    geolocation_script = """
    <script>
    // Store GPS data in window object for Streamlit
    window.gpsData = {lat: 2.925340509334203, lng: 101.64186097827847};
    
    if (navigator.geolocation) {
        // Get location continuously
        navigator.geolocation.watchPosition(
            function(position) {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                
                // Update window object
                window.gpsData = {lat: lat, lng: lng};
                
                // Store in session storage
                sessionStorage.setItem('gps_lat', lat);
                sessionStorage.setItem('gps_lng', lng);
                sessionStorage.setItem('gps_updated', new Date().toISOString());
                
                // Trigger Streamlit rerun
                if (window.parent && window.parent.streamlit) {
                    window.parent.streamlit.setComponentValue({
                        lat: lat,
                        lng: lng,
                        accuracy: position.coords.accuracy
                    });
                }
            },
            function(error) {
                console.log('Geolocation error:', error.message);
            },
            {
                enableHighAccuracy: true,
                maximumAge: 0,
                timeout: 5000
            }
        );
    }
    </script>
    """
    st.components.v1.html(geolocation_script, height=0)

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

# --- UI SETUP ---
st.set_page_config(layout="wide", page_title="Wireless AI Monitor", initial_sidebar_state="expanded")

# Professional Corporate Theme CSS
st.markdown("""
    <style>
    /* Main background */
    .stApp {
        background-color: #0F0F1E;
    }
    
    [data-testid="stAppViewContainer"] {
        background-color: #0F0F1E;
    }
    
    [data-testid="stHeader"] {
        background-color: #0F0F1E;
    }
    
    /* Text colors */
    body, .stApp, .stMarkdown {
        color: #F0F0F0 !important;
    }
    
    /* Metrics */
    [data-testid="metric-container"] {
        background-color: #1A1A2E;
        padding: 18px;
        border-radius: 8px;
        border-left: 4px solid #2E8B9E;
        box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    }
    
    /* Tabs */
    [data-baseweb="tab-list"] {
        background-color: transparent;
    }
    
    [data-baseweb="tab"] {
        background-color: #1A1A2E !important;
        color: #B0B0B0 !important;
    }
    
    [data-baseweb="tab"][aria-selected="true"] {
        background-color: #2E8B9E !important;
        color: #FFFFFF !important;
    }
    
    /* Buttons */
    .stButton > button {
        background-color: #2E8B9E !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 10px 20px !important;
        font-weight: 600 !important;
    }
    
    .stButton > button:hover {
        background-color: #1F5F6A !important;
    }
    
    /* Select boxes and sliders */
    [data-baseweb="select"] {
        background-color: #1A1A2E !important;
    }
    
    .stSelectbox label, .stSlider label, .stRadio label {
        color: #F0F0F0 !important;
    }
    
    /* Alert boxes */
    .stSuccess {
        background-color: rgba(39, 174, 96, 0.2) !important;
        border-left: 4px solid #27AE60 !important;
    }
    
    .stError {
        background-color: rgba(231, 76, 60, 0.2) !important;
        border-left: 4px solid #E74C3C !important;
    }
    
    .stWarning {
        background-color: rgba(230, 126, 34, 0.2) !important;
        border-left: 4px solid #E67E22 !important;
    }
    
    .stInfo {
        background-color: rgba(46, 139, 158, 0.2) !important;
        border-left: 4px solid #2E8B9E !important;
    }
    
    /* Dividers */
    hr {
        border-color: #2E8B9E !important;
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: #F0F0F0 !important;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #0F0F1E !important;
    }
    
    [data-testid="stSidebarContent"] {
        background-color: #0F0F1E !important;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🛡️ Wireless Hazard & AI System")
inject_geolocation()

# SIDEBAR
st.sidebar.header("📍 GPS Location")

# Initialize GPS session state
if 'lat' not in st.session_state:
    st.session_state.lat = 2.925340509334203  # Default location
if 'lng' not in st.session_state:
    st.session_state.lng = 101.64186097827847  # Default location
if 'gps_enabled' not in st.session_state:
    st.session_state.gps_enabled = True  # Always enabled for browser GPS

gps_mode = st.sidebar.radio("GPS Source", ["🌍 Browser (Live)", "📍 Manual"], horizontal=True)

if gps_mode == "🌍 Browser (Live)":
    st.sidebar.info("📡 Requesting your current location...\nAllow location access to track movements in real-time")
    
    # Try to get location from browser
    try:
        # This will be populated by JavaScript
        col1, col2 = st.sidebar.columns(2)
        with col1:
            st.metric("Latitude", f"{st.session_state.lat:.6f}")
        with col2:
            st.metric("Longitude", f"{st.session_state.lng:.6f}")
        
        st.sidebar.success(f"✅ Live GPS Active")
        st.session_state.gps_enabled = True
    except:
        st.sidebar.warning("Enable location in browser settings")
else:
    # Manual GPS Input
    st.session_state.lat = st.sidebar.number_input("Latitude", value=st.session_state.lat, format="%.6f")
    st.session_state.lng = st.sidebar.number_input("Longitude", value=st.session_state.lng, format="%.6f")
    st.sidebar.success(f"📍 Manual GPS: {st.session_state.lat:.6f}, {st.session_state.lng:.6f}")
    st.session_state.gps_enabled = False

lat = st.session_state.lat
lng = st.session_state.lng

st.sidebar.info(f"Connected to: {ESP_IP}")

# JavaScript to update location from browser geolocation
st.markdown("""
<script>
    function updateGPS() {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(function(position) {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                
                // Store in sessionStorage for Streamlit
                sessionStorage.setItem('gps_lat', lat);
                sessionStorage.setItem('gps_lng', lng);
                
                // Trigger Streamlit update
                if (window.parent.streamlit) {
                    window.parent.streamlit.setComponentValue({
                        lat: lat,
                        lng: lng,
                        updated: true
                    });
                }
            });
        }
    }
    
    // Update GPS every 5 seconds
    setInterval(updateGPS, 5000);
    updateGPS(); // Initial call
</script>
""", unsafe_allow_html=True)

# Auto-refresh the app every 5 seconds for GPS updates
auto_refresh = st.checkbox("🔄 Auto-update GPS (every 5s)", value=False)
if auto_refresh:
    time.sleep(5)
    st.rerun()

# Initialize remaining session state
if 'heatmap_data' not in st.session_state:
    st.session_state.heatmap_data = []
if 'current_gas' not in st.session_state:
    st.session_state.current_gas = 0
if 'current_co' not in st.session_state:
    st.session_state.current_co = 0
if 'current_temp' not in st.session_state:
    st.session_state.current_temp = 0
if 'esp_connected' not in st.session_state:
    st.session_state.esp_connected = False
if 'readings_count' not in st.session_state:
    st.session_state.readings_count = 0
if 'alert_history' not in st.session_state:
    st.session_state.alert_history = []
if 'last_update' not in st.session_state:
    st.session_state.last_update = datetime.now()

# Mini map to sidebar
st.sidebar.subheader("📍 Current Location")
mini_map = folium.Map(location=[lat, lng], zoom_start=13)
folium.Marker(
    location=[lat, lng],
    popup="Current Sensor Location",
    icon=folium.Icon(color='red', icon='info-sign')
).add_to(mini_map)
with st.sidebar:
    st_folium(mini_map, width=300, height=250)

# Connection Status & Stats
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.session_state.esp_connected:
        st.success("✅ ESP Connected")
    else:
        st.error("❌ ESP Disconnected")
with col2:
    st.metric("📊 Readings", st.session_state.readings_count)
with col3:
    st.caption(f"⏰ Last Update: {st.session_state.last_update.strftime('%H:%M:%S')}")
with col4:
    st.metric("🎯 AI Status", "Ready" if ai_ready else "N/A")

st.divider()

# Create main tabs
tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "📈 Analytics", "⚙️ Settings", "📋 Logs"])

with tab1:
    st.subheader("📍 SENSOR LOCATION HEATMAP")
    
    heatmap_mode = st.selectbox("Heatmap based on:", ["Methane (MQ-4)", "CO (MQ-9)", "Temperature"])
    map_placeholder = st.empty()
    
    st.subheader("📊 LIVE SENSOR GAUGES")
    
    col1, col2, col3 = st.columns(3)
    gauge_gas = col1.empty()
    gauge_co = col2.empty()
    gauge_temp = col3.empty()
    
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
    
    box_gas.metric("🔴 MQ-4 Methane", f"{st.session_state.current_gas} ppm", delta=None)
    box_co.metric("🔵 MQ-9 CO", f"{st.session_state.current_co} ppm", delta=None)
    box_temp.metric("🌡️ Temperature", f"{st.session_state.current_temp}°C", delta=None)
    
    st.subheader("🔮 AI PREDICTION")
    p1, p2, p3 = st.columns(3)
    pred_gas = p1.empty()
    pred_co = p2.empty()
    pred_temp = p3.empty()
    
    if ai_ready:
        pred_gas.metric("Pred Methane", "0.0", "SAFE")
        pred_co.metric("Pred CO", "0.0", "SAFE")
        pred_temp.metric("Pred Temp", "0.0", "SAFE")
    
    final_alert = st.empty()

with tab2:
    st.subheader("📈 HISTORICAL TRENDS")
    
    if os.path.isfile(DATA_PATH):
        df = pd.read_csv(DATA_PATH)
        
        if len(df) > 0:
            col1, col2 = st.columns(2)
            
            with col1:
                fig_gas = create_trend_chart(df.reset_index(), 'gas', 'Methane Levels (ppm)', '#00D9FF')
                st.plotly_chart(fig_gas, use_container_width=True)
                
                fig_co = create_trend_chart(df.reset_index(), 'co', 'CO Levels (ppm)', '#FF6B6B')
                st.plotly_chart(fig_co, use_container_width=True)
            
            with col2:
                fig_temp = create_trend_chart(df.reset_index(), 'temp', 'Temperature (°C)', '#FFD700')
                st.plotly_chart(fig_temp, use_container_width=True)
            
            st.subheader("📊 STATISTICS")
            stats_col1, stats_col2, stats_col3 = st.columns(3)
            
            with stats_col1:
                st.metric("🔴 Methane Max", f"{df['gas'].max():.0f} ppm", f"Avg: {df['gas'].mean():.0f}")
                st.metric("🔴 Methane Min", f"{df['gas'].min():.0f} ppm")
            
            with stats_col2:
                st.metric("🔵 CO Max", f"{df['co'].max():.0f} ppm", f"Avg: {df['co'].mean():.0f}")
                st.metric("🔵 CO Min", f"{df['co'].min():.0f} ppm")
            
            with stats_col3:
                st.metric("🌡️ Temp Max", f"{df['temp'].max():.1f}°C", f"Avg: {df['temp'].mean():.1f}")
                st.metric("🌡️ Temp Min", f"{df['temp'].min():.1f}°C")
            
            st.subheader("📥 DATA EXPORT")
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download as CSV",
                data=csv,
                file_name=f"sensor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        else:
            st.info("📊 No data available yet. Connect ESP to start logging.")
    else:
        st.info("📊 No data file found.")

with tab3:
    st.subheader("⚙️ SYSTEM SETTINGS")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**ESP Configuration**")
        new_ip = st.text_input("ESP IP Address", value=ESP_IP)
        if new_ip != ESP_IP:
            st.info(f"✅ Update ESP_IP in dashboard.py to: {new_ip}")
        
        update_interval = st.slider("Update Interval (ms)", 100, 1000, 500, 50)
        st.caption(f"Current: {update_interval}ms updates")
    
    with col2:
        st.markdown("**Sensor Thresholds**")
        methane_safe_new = st.slider("Methane Safe (ppm)", 0, 1000, METHANE_SAFE, 50)
        methane_warn_new = st.slider("Methane Warning (ppm)", 500, 2000, METHANE_WARNING, 50)
        co_safe_new = st.slider("CO Safe (ppm)", 0, 100, CO_SAFE, 5)
        co_warn_new = st.slider("CO Warning (ppm)", 50, 500, CO_WARNING, 10)

with tab4:
    st.subheader("📋 ALERT HISTORY")
    
    if len(st.session_state.alert_history) > 0:
        alert_df = pd.DataFrame(st.session_state.alert_history)
        st.dataframe(alert_df, use_container_width=True)
        
        st.download_button(
            label="📥 Download Alert Log",
            data=alert_df.to_csv(index=False),
            file_name=f"alerts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    else:
        st.info("📋 No alerts recorded yet.")

# INIT CSV
if not os.path.isfile(DATA_PATH):
    with open(DATA_PATH, 'w') as f:
        f.write("lat,lon,co,gas,temp\n")

# Initialize session state for auto-refresh
if 'running' not in st.session_state:
    st.session_state.running = True

placeholder = st.empty()

# --- MAIN LOOP (POLLING) ---
while st.session_state.running:
    try:
        response = requests.get(ESP_IP, timeout=0.5)
        
        if response.status_code == 200:
            data = response.json()
            
            co = int(data['co'])
            gas = int(data['gas'])
            temp = float(data['temp'])
            
            st.session_state.current_gas = gas
            st.session_state.current_co = co
            st.session_state.current_temp = temp
            st.session_state.esp_connected = True
            st.session_state.readings_count += 1
            st.session_state.last_update = datetime.now()

            with open(DATA_PATH, 'a') as f:
                f.write(f"{lat},{lng},{co},{gas},{temp}\n")
            
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
            
            if len(st.session_state.heatmap_data) > 100:
                st.session_state.heatmap_data = st.session_state.heatmap_data[-100:]

            box_gas.metric("🔴 MQ-4 Methane", f"{gas} ppm")
            box_co.metric("🔵 MQ-9 CO", f"{co} ppm")
            box_temp.metric("🌡️ Temperature", f"{temp}°C")
            
            gauge_gas.plotly_chart(create_gauge(gas, "MQ-4 Methane", 2000, METHANE_SAFE, METHANE_WARNING), use_container_width=True, key=f"gas_{time.time()}")
            gauge_co.plotly_chart(create_gauge(co, "MQ-9 CO", 500, CO_SAFE, CO_WARNING), use_container_width=True, key=f"co_{time.time()}")
            gauge_temp.plotly_chart(create_gauge(temp, "Temperature", 60, TEMP_SAFE, TEMP_WARNING), use_container_width=True, key=f"temp_{time.time()}")
            
            m = folium.Map(location=[lat, lng], zoom_start=15)
            
            if heatmap_mode == "Methane (MQ-4)":
                heatmap_points = [[d['lat'], d['lng'], d['gas']] for d in st.session_state.heatmap_data]
                HeatMap(heatmap_points, min_opacity=0.2, max_zoom=18, radius=25, blur=15, 
                       gradient={0.0: '#27AE60', 0.5: '#E67E22', 1.0: '#E74C3C'}).add_to(m)
            elif heatmap_mode == "CO (MQ-9)":
                heatmap_points = [[d['lat'], d['lng'], d['co']] for d in st.session_state.heatmap_data]
                HeatMap(heatmap_points, min_opacity=0.2, max_zoom=18, radius=25, blur=15,
                       gradient={0.0: '#27AE60', 0.5: '#E67E22', 1.0: '#E74C3C'}).add_to(m)
            else:
                heatmap_points = [[d['lat'], d['lng'], d['temp']] for d in st.session_state.heatmap_data]
                HeatMap(heatmap_points, min_opacity=0.2, max_zoom=18, radius=25, blur=15,
                       gradient={0.0: '#27AE60', 0.5: '#E67E22', 1.0: '#E74C3C'}).add_to(m)
            
            folium.CircleMarker(
                location=[lat, lng],
                radius=10,
                popup=f"<b>Current Reading</b><br>Gas: {gas} ppm<br>CO: {co} ppm<br>Temp: {temp}°C",
                color='red',
                fill=True,
                fillColor='red',
                fillOpacity=0.8
            ).add_to(m)
            
            map_placeholder.empty()
            with map_placeholder.container():
                st_folium(m, width=1200, height=500)

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
                        st.session_state.alert_history.append({
                            'Time': datetime.now().strftime('%H:%M:%S'),
                            'Type': 'DANGER',
                            'Methane': f"{p_m:.1f}",
                            'CO': f"{p_c:.1f}",
                            'Temp': f"{p_t:.1f}"
                        })
                    else:
                        final_alert.success("✅ SYSTEM PREDICTION: SAFE")
                except Exception as e:
                    final_alert.error(f"AI Error: {str(e)[:50]}")

    except Exception as e:
        st.session_state.esp_connected = False
        placeholder.warning(f"Waiting for ESP... ({str(e)[:30]})")
        
    time.sleep(0.5)
