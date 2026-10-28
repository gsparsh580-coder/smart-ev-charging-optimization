"""
Interactive Streamlit Dashboard for Smart EV Charging Optimization
Provides interactive scenario analysis, tariff comparisons, and synthetic data export.
"""

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from optimization_engine.ev_optimizer import EVChargingOptimizer, EVSpecs, GridEnvironment
from optimization_engine.tariff_models import StandardTOUTariff, SolarIncentiveTariff, DynamicRealTimeTariff
from simulator.synthetic_data_generator import SyntheticDataGenerator

st.set_page_config(
    page_title="Smart EV Charging Optimizer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⚡ Smart EV Charging Schedule Optimization")
st.markdown("Mathematical optimization engine minimizing electricity costs, shaving grid peak load, and maximizing solar PV utilization.")

# --- SIDEBAR CONFIGURATION ---
st.sidebar.header("🚗 EV Battery Specifications")
battery_cap = st.sidebar.slider("Battery Capacity (kWh)", 20.0, 100.0, 60.0, 5.0)
start_soc = st.sidebar.slider("Current Battery SoC (%)", 5.0, 90.0, 25.0, 5.0)
target_soc = st.sidebar.slider("Target SoC at Departure (%)", 50.0, 100.0, 85.0, 5.0)
charger_kw = st.sidebar.slider("Max Charger Power (kW)", 1.4, 22.0, 7.4, 0.5)

st.sidebar.header("⏰ Plug-In Time Window")
arr_hour = st.sidebar.selectbox("Arrival Time", range(24), index=18, format_func=lambda h: f"{h:02d}:00")
dep_hour = st.sidebar.selectbox("Departure Time", range(24), index=7, format_func=lambda h: f"{h:02d}:00")

st.sidebar.header("☀️ Solar & Grid Settings")
solar_peak = st.sidebar.slider("Rooftop Solar PV Peak (kW)", 0.0, 15.0, 4.5, 0.5)
tariff_option = st.sidebar.selectbox(
    "Electricity Tariff Model",
    ["3-Tier Time-of-Use (Standard)", "Solar-Friendly Duck Curve", "Dynamic Spot Market"]
)

# Build Solar Curve
solar_curve = []
for h in range(24):
    if 6 <= h <= 18:
        val = solar_peak * np.sin((h - 6) * np.pi / 12) ** 2
        solar_curve.append(round(float(val), 2))
    else:
        solar_curve.append(0.0)

# Build Tariff Model
if "Solar-Friendly" in tariff_option:
    tariff_model = SolarIncentiveTariff()
elif "Dynamic Spot" in tariff_option:
    tariff_model = DynamicRealTimeTariff()
else:
    tariff_model = StandardTOUTariff()

rates = tariff_model.get_hourly_rates()

# Execute Optimization
specs = EVSpecs(
    battery_capacity_kwh=battery_cap,
    current_soc_percent=start_soc,
    target_soc_percent=target_soc,
    max_charge_power_kw=charger_kw,
    arrival_hour=arr_hour,
    departure_hour=dep_hour
)

grid = GridEnvironment(
    hourly_tariffs=rates,
    solar_generation_kw=solar_curve,
    grid_power_limit_kw=11.0
)

optimizer = EVChargingOptimizer(specs, grid)
res = optimizer.solve()

comp = res["comparison"]
opt = res["optimized"]
un = res["uncontrolled"]

# --- METRIC CARDS ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Uncontrolled Cost", f"₹{un['total_cost']:.2f}")
col2.metric("Smart Optimized Cost", f"₹{opt['total_cost']:.2f}", delta=f"-₹{comp['cost_savings']:.2f} ({comp['savings_percent']}%)", delta_color="inverse")
col3.metric("Net Cost Savings", f"₹{comp['cost_savings']:.2f}", f"{comp['savings_percent']}% Saved")
col4.metric("CO2 Avoided", f"{comp['co2_saved_kg']:.2f} kg", f"Shaved: {comp['peak_power_shaved_kw']} kW")

# --- INTERACTIVE 24-HOUR TIMELINE PLOT ---
df_timeline = pd.DataFrame(res["timeline"])

fig = make_subplots(specs=[[{"secondary_y": true}]])

# Optimized Power Bars
fig.add_trace(
    go.Bar(
        x=df_timeline["hour_label"],
        y=df_timeline["opt_power_kw"],
        name="Optimized Charging (kW)",
        marker_color="#06b6d4"
    ),
    secondary_y=False
)

# Uncontrolled Power (Dashed)
fig.add_trace(
    go.Bar(
        x=df_timeline["hour_label"],
        y=df_timeline["uncontrolled_power_kw"],
        name="Uncontrolled Power (kW)",
        marker_color="rgba(244, 63, 94, 0.3)"
    ),
    secondary_y=False
)

# Solar Area
fig.add_trace(
    go.Scatter(
        x=df_timeline["hour_label"],
        y=df_timeline["solar_kw"],
        name="Solar PV (kW)",
        fill="tozeroy",
        line=dict(color="#10b981", width=2)
    ),
    secondary_y=False
)

# Tariff Line
fig.add_trace(
    go.Scatter(
        x=df_timeline["hour_label"],
        y=df_timeline["tariff"],
        name="Tariff (₹/kWh)",
        line=dict(color="#f59e0b", width=3, shape="hv")
    ),
    secondary_y=True
)

fig.update_layout(
    title="24-Hour Power Allocation vs Time-of-Use Tariff & Solar Generation",
    template="plotly_dark",
    barmode="overlay",
    height=450,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
fig.update_yaxes(title_text="Power (kW)", secondary_y=False)
fig.update_yaxes(title_text="Tariff (₹/kWh)", secondary_y=True)

st.plotly_chart(fig, use_container_width=True)

# --- HOURLY BREAKDOWN & CSV EXPORT ---
with st.expander("📊 View Hourly Schedule Breakdown Table"):
    st.dataframe(df_timeline, use_container_width=True)

    csv = df_timeline.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Schedule as CSV",
        data=csv,
        file_name="optimized_ev_charging_schedule.csv",
        mime="text/csv"
    )
