# train_ai.py
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
import joblib
import os

print("Training AI Models...")

# Dummy Data to mimic sensors
data = pd.DataFrame({
    "Methane ppm": np.random.randint(100, 2000, 500),
    "CO ppm": np.random.randint(10, 500, 500),
    "Temp C": np.random.uniform(20.0, 50.0, 500)
})
# Targets
data["methane_next"] = data["Methane ppm"] + 50
data["co_next"] = data["CO ppm"] + 10
data["temp_next"] = data["Temp C"] + 0.5

X = data[["Methane ppm", "CO ppm", "Temp C"]]

# Train
m_model = RandomForestRegressor().fit(X, data["methane_next"])
c_model = RandomForestRegressor().fit(X, data["co_next"])
t_model = RandomForestRegressor().fit(X, data["temp_next"])

# Save to 'src' folder
if not os.path.exists('src'): os.makedirs('src')
joblib.dump(m_model, 'src/methane_model.pkl')
joblib.dump(c_model, 'src/co_model.pkl')
joblib.dump(t_model, 'src/temp_model.pkl')

print("✅ AI Models Created in 'src' folder!")