# 🛡️ Wireless Hazard & AI System

Real-time air quality monitoring with wireless sensors (MQ-4, MQ-9) and temperature monitoring via ESP32, featuring AI-based predictions and interactive heatmaps.

## Features

✅ **Live Sensor Gauges** - Radial gauges for MQ-4 (Methane), MQ-9 (CO), and Temperature  
✅ **Interactive Heatmap** - Color-coded intensity maps showing hazard zones  
✅ **AI Predictions** - Machine learning models predict next 10s sensor values  
✅ **GPS Integration** - Browser-based geolocation with mini map in sidebar  
✅ **Real-time Updates** - Connected via WiFi to ESP32 using ESP-NOW  
✅ **Data Logging** - All readings saved to CSV with GPS coordinates  

## Project Structure

```
├── dashboard.py          # Streamlit web dashboard
├── train_ai.py          # AI model training script
├── src/
│   ├── methane_model.pkl
│   ├── co_model.pkl
│   └── temp_model.pkl
└── data/
    └── gas_log.csv      # Sensor readings log
```

## Installation

1. **Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
```

2. **Install dependencies:**
```bash
pip install streamlit pyserial pandas scikit-learn joblib plotly folium streamlit-folium
```

3. **Train AI models:**
```bash
python train_ai.py
```

## Usage

**Start the dashboard:**
```bash
streamlit run dashboard.py
```

The app will open at `http://localhost:8501`

### Dashboard Features

- **GPS Location**: Toggle between browser GPS and manual coordinates
- **Heatmap Mode**: Select between Methane, CO, or Temperature heatmaps
- **Live Metrics**: Real-time sensor readings with status (SAFE/WARNING/DANGER)
- **AI Predictions**: ML models predict next 10s values
- **Mini Map**: Sidebar map showing current sensor location

## Sensor Thresholds

| Sensor | Safe | Warning | Danger |
|--------|------|---------|--------|
| MQ-4 (Methane) | ≤500 ppm | ≤1000 ppm | >1000 ppm |
| MQ-9 (CO) | ≤50 ppm | ≤200 ppm | >200 ppm |
| Temperature | ≤29°C | ≤40°C | >40°C |

## ESP32 Configuration

Connect ESP to WiFi and configure it to send JSON data to dashboard:

```json
{
  "co": 120,
  "gas": 400,
  "temp": 32.5
}
```

**ESP IP**: `http://10.95.226.155/data` (update in `dashboard.py`)

## Data Format

Sensor readings are saved to `data/gas_log.csv`:
```csv
lat,lon,co,gas,temp
3.1412,101.6860,120,400,32.5
```

## Technologies Used

- **Streamlit** - Web dashboard framework
- **Plotly** - Interactive gauges and charts
- **Folium** - Interactive maps
- **Scikit-learn** - AI model training
- **Pandas** - Data handling
- **ESP32** - Wireless sensor node

## License

MIT

## Author

Capstone Project - Air Quality Monitoring System
