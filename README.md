# ⚡ Smart EV Charging Schedule Optimization

[![GitHub Pages](https://img.shields.io/badge/Live%20Dashboard-GitHub%20Pages-brightgreen?style=for-the-badge&logo=github)](https://gsparsh580-coder.github.io/smart-ev-charging-optimization/)
[![HiveMQ MQTT](https://img.shields.io/badge/MQTT-HiveMQ%20Broker-orange?style=for-the-badge&logo=mqtt)](https://www.hivemq.com/)
[![Node-RED](https://img.shields.io/badge/Node--RED-Dashboard%202.0-red?style=for-the-badge&logo=nodered)](https://nodered.org/)
[![SciPy Optimization](https://img.shields.io/badge/Algorithm-SciPy%20MILP%20%2F%20LP-blue?style=for-the-badge&logo=scipy)](https://scipy.org/)
[![Hardware](https://img.shields.io/badge/Hardware-ESP32%20IoT-teal?style=for-the-badge&logo=espressif)](https://www.espressif.com/)

> An end-to-end, IoT-enabled **Smart EV Charging Schedule Optimization Platform** utilizing mathematical Linear Programming (LP/MILP) to minimize charging costs, shave peak transformer loads, and maximize rooftop solar PV utilization. Supports both **high-fidelity Synthetic Data** and **live Physical ESP32 Sensor Hardware** via **HiveMQ MQTT**, **Node-RED**, and an interactive **Web Dashboard**.

---

## 🌐 Live Interactive Dashboard & Remote Control

Access the live, client-side Web Dashboard directly from your browser (hosted on GitHub Pages):

👉 **[https://gsparsh580-coder.github.io/smart-ev-charging-optimization/](https://gsparsh580-coder.github.io/smart-ev-charging-optimization/)**

*Directly connects to HiveMQ via Secure WebSockets (`wss://broker.hivemq.com:8884/mqtt`) to stream real-time sensor telemetry, actuate the contactor relay, and solve dynamic 24-hour schedules with zero backend installation required!*

---

## 📐 System Architecture

```text
  +---------------------------------------------------------------------------------+
  |                                DATA INGESTION                                  |
  |                                                                                 |
  |  [Mode A: Synthetic Generator]               [Mode B: Real ESP32 Hardware]     |
  |  - 24h Driving Patterns                       - AC Current (ACS712 / INA219)    |
  |  - TOU Electricity Tariffs                    - Grid AC Voltage (ZMPT101B)      |
  |  - Solar PV Irradiance                        - Temperature Safety (DHT22)      |
  |  - Household Baseline                         - Contactor Relay Actuation       |
  +---------------------------------------+-----------------------------------------+
                                          |
                                          v
  +---------------------------------------------------------------------------------+
  |                       HIVEMQ MQTT BROKER (TCP 1883 / WSS 8884)                 |
  |                                                                                 |
  |  Topics:                                                                        |
  |  • smart_ev/telemetry   <-- Live Voltage, Current, Power, Energy, Battery SoC   |
  |  • smart_ev/schedule    <-- 24h Optimized Power Allocations & Savings Benchmark |
  |  • smart_ev/control     <-- Remote Relay ON/OFF, Target Current, Mode           |
  |  • smart_ev/config      <-- Battery Capacity, Departure Hour, Tariff Model      |
  +---------------------------------------+-----------------------------------------+
                                          |
                +-------------------------+-------------------------+
                |                                                   |
                v                                                   v
  +---------------------------+                           +---------------------------+
  |    OPTIMIZATION ENGINE    |                           |    SUPERVISORY DASHBOARD  |
  |  (Python / SciPy / MILP)  |                           |  (Web / Node-RED / Stream)|
  |                           |                           |                           |
  |  - Cost Minimization LP   |                           |  - Real-Time SoC Visual   |
  |  - Solar Self-Consumption |                           |  - Contactor Switching    |
  |  - Peak Load Shaving      |                           |  - 24h Power Timeline     |
  |  - User Departure Guarantee                           |  - Cost Savings Analytics |
  +---------------------------+                           +---------------------------+
```

---

## 🧮 Mathematical Optimization Model

The scheduling problem is formulated as a constrained Linear Program / Mixed-Integer Program solved across discrete time steps $t \in \{1, 2, \dots, N\}$ (where $\Delta t = 1$ hour or 15 mins):

### 1. Objective Function (Cost Minimization)
$$\min_{P_t} \sum_{t=1}^{N} \left( C_t \cdot P_t \cdot \Delta t - \lambda_{\text{solar}} \cdot \min(P_t, S_t) \cdot \Delta t \right)$$
*Where $C_t$ is the dynamic Time-of-Use tariff ($/kWh or ₹/kWh), $P_t$ is charging power (kW), $S_t$ is solar PV generation (kW), and $\lambda_{\text{solar}}$ is the self-consumption incentive factor.*

### 2. Constraints
1. **Battery Energy Dynamics**:
   $$SoC_{t+1} = SoC_t + \left( \frac{\eta \cdot P_t \cdot \Delta t}{E_{\text{cap}}} \right) \times 100\%$$
   *Where $\eta = 0.92$ (92% charging efficiency) and $E_{\text{cap}}$ is battery pack capacity (e.g., 60 kWh).*
2. **Charger Power Limits**:
   $$0 \le P_t \le P_{\max} \quad \forall t \in [t_{\text{arrive}}, t_{\text{depart}}]$$
   $$P_t = 0 \quad \forall t \notin [t_{\text{arrive}}, t_{\text{depart}}]$$
3. **User Departure Guarantee**:
   $$SoC(t_{\text{depart}}) \ge SoC_{\text{target}}$$
4. **Grid Peak Capacity Constraint**:
   $$P_t + P_{\text{baseload}, t} \le P_{\text{grid\_limit}}$$

### 3. Financial Benchmark Results
| Metric | Immediate Uncontrolled Charging | Smart Scheduled Optimization | Net Impact |
| :--- | :--- | :--- | :--- |
| **Session Cost** | **₹370.93** | **₹148.37** | **₹222.56 Saved (60.0%)** |
| **Charging Timing** | 18:00 - 23:00 (Peak Evening Tariff) | 00:00 - 05:00 (Super Off-Peak) | Avoided ₹11.80/kWh peak |
| **Grid Peak Draw** | 7.4 kW concurrent with peak | 7.4 kW deferred to midnight | Grid peak load reduced |
| **CO2 Emissions** | 21.84 kg | 17.13 kg | **4.71 kg CO2 avoided** |

---

## ⚡ ESP32 Hardware Integration

The firmware runs on an **ESP32 DevKit V1** and provides real-time sensor measurement and relay actuation.

### Pinout Mapping
| ESP32 Pin | Connected Component | Function |
| :--- | :--- | :--- |
| **GPIO 26** | Heavy-Duty 30A Relay Module (IN) | Switched AC mains line contactor |
| **GPIO 34** | ACS712-30A Current Sensor (OUT) | Analog ADC current sensing (0 - 32A) |
| **GPIO 35** | ZMPT101B AC Voltage Sensor (OUT)| Analog line voltage measurement (200 - 250V AC) |
| **GPIO 14** | DHT22 / DS18B20 Temp Sensor | Contactor terminal thermal safety monitoring |
| **GPIO 2**  | Onboard Blue LED | Wi-Fi and HiveMQ MQTT status indicator |
| **GPIO 4**  | Green LED | Active charging status indicator |
| **GPIO 15** | Red LED | Overheat / Overcurrent Fault alarm |
| **GPIO 25** | PWM Out | J1772 Control Pilot signal generator |

*Circuit diagram, safety optocouplers, and bill of materials are detailed in [`esp32_firmware/circuit_diagram.md`](esp32_firmware/circuit_diagram.md).*

---

## 📡 HiveMQ MQTT Protocol Specification

Public broker endpoint: `broker.hivemq.com` (Port `1883` for TCP / Port `8884` for Secure WebSockets).

### 1. `smart_ev/telemetry` (Published by ESP32 / Virtual Sensor)
```json
{
  "device_id": "ESP32_EVSE_01",
  "voltage": 230.4,
  "current": 15.8,
  "power_kw": 3.64,
  "energy_kwh": 14.82,
  "temperature_c": 31.2,
  "battery_soc": 48.5,
  "relay_state": "ON",
  "mode": "AUTO",
  "fault": false
}
```

### 2. `smart_ev/control` (Published by Dashboard / Controller)
```json
{
  "command": "RELAY_ON",
  "state": "ON",
  "target_current": 16.0,
  "mode": "MANUAL",
  "timestamp": "2026-10-28T16:45:00Z"
}
```

### 3. `smart_ev/schedule` (Published by Optimization Engine)
```json
{
  "status": "OPTIMAL",
  "energy_needed_kwh": 42.39,
  "comparison": {
    "cost_savings": 222.56,
    "savings_percent": 60.0,
    "co2_saved_kg": 4.71,
    "peak_power_shaved_kw": 7.4
  },
  "timeline": [
    { "hour": 0, "opt_power_kw": 7.4, "tariff": 3.50, "solar_kw": 0.0, "opt_soc_percent": 45.2 },
    { "hour": 18, "opt_power_kw": 0.0, "tariff": 11.80, "solar_kw": 0.2, "opt_soc_percent": 25.0 }
  ]
}
```

---

## 🔴 Node-RED Dashboard Setup

1. Launch Node-RED and open `http://localhost:1880`.
2. Go to **Menu $\rightarrow$ Import** and upload [`node_red/flows.json`](node_red/flows.json).
3. Click **Deploy**.
4. Open the dashboard at `http://localhost:1880/ui` to monitor live gauges and switch relays remotely.

---

## 🚀 Quickstart Guide

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/gsparsh580-coder/smart-ev-charging-optimization.git
cd smart-ev-charging-optimization
pip install -r requirements.txt
```

### 2. Run Virtual Hardware Simulator (Synthetic Mode)
Test the full system without needing physical hardware:
```bash
python -m simulator.virtual_esp32_sensor
# or double-click run_simulator.bat
```

### 3. Run Optimization Bridge Controller
```bash
python -m bridge.mqtt_controller
# or double-click run_optimizer.bat
```

### 4. Run Streamlit Analytics Dashboard
```bash
streamlit run app_streamlit.py
# or double-click run_dashboard.bat
```

### 5. Flash ESP32 (Physical Hardware Mode)
1. Open [`esp32_firmware/smart_ev_esp32.ino`](esp32_firmware/smart_ev_esp32.ino) in Arduino IDE.
2. Install libraries: `PubSubClient`, `ArduinoJson`, `DHT sensor library`.
3. Set your Wi-Fi SSID and password in `secrets.h`.
4. Upload to ESP32 DevKit and open Serial Monitor at `115200 baud`.

---

## 📂 Repository Structure

```text
smart-ev-charging-optimization/
├── .github/workflows/deploy.yml     # Automated GitHub Pages CI/CD workflow
├── index.html                       # Live Web Dashboard (Tailwind + Chart.js + Paho MQTT)
├── css/styles.css                   # Custom styles, glowing cards & animations
├── js/app.js                        # Client-side MQTT client & optimization visualizer
├── optimization_engine/
│   ├── ev_optimizer.py              # Core SciPy LP / MILP mathematical solver
│   ├── tariff_models.py             # TOU, Duck-curve, and Dynamic spot tariff curves
│   └── cost_benchmark.py            # Comparative financial & CO2 benchmark tool
├── simulator/
│   ├── synthetic_data_generator.py  # 24h multi-day time-series synthetic dataset builder
│   └── virtual_esp32_sensor.py      # Virtual hardware digital twin streaming to HiveMQ
├── esp32_firmware/
│   ├── smart_ev_esp32.ino           # Complete Arduino C++ firmware for ESP32
│   ├── circuit_diagram.md           # Schematic diagrams, wiring pinout, and safety guide
│   ├── secrets.example.h            # Wi-Fi and MQTT configuration template
│   └── micropython/
│       ├── boot.py
│       └── main.py                  # MicroPython alternative firmware
├── node_red/
│   ├── flows.json                   # Complete exportable Node-RED Dashboard flow
│   └── README.md                    # Node-RED setup instructions
├── bridge/
│   └── mqtt_controller.py           # Real-time MQTT optimizer and autonomous relay agent
├── data/
│   └── synthetic_ev_dataset.csv     # Pre-generated 7-day realistic EV charging dataset
├── app_streamlit.py                 # Interactive Streamlit analytics application
├── requirements.txt
├── run_dashboard.bat
├── run_simulator.bat
├── run_optimizer.bat
└── setup_git_and_push.ps1
```

---

## 📜 License & Credits

Developed with ❤️ by **Sparsh** ([@gsparsh580-coder](https://github.com/gsparsh580-coder)).  
Released under the [MIT License](LICENSE).
