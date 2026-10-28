# Node-RED Dashboard for Smart EV Charging Optimization

This directory provides pre-configured Node-RED flow definitions for visualizing live ESP32 sensor telemetry, monitoring optimized EV charging schedules, and remotely controlling charging contactors over HiveMQ MQTT.

---

## 1. Prerequisites

1. Install **Node-RED** (if not already installed):
   ```bash
   npm install -g --unsafe-perm node-red
   ```
2. Install the **Node-RED Dashboard** palette:
   ```bash
   cd ~/.node-red
   npm install node-red-dashboard
   ```

---

## 2. Importing the Flow

1. Start Node-RED:
   ```bash
   node-red
   ```
2. Open your browser and navigate to: `http://localhost:1880`
3. Click the hamburger menu (top right) $\rightarrow$ **Import** $\rightarrow$ **Select a file to import**.
4. Choose the file: `node_red/flows.json`.
5. Click **Import** and then hit the red **Deploy** button (top right).

---

## 3. Accessing the Dashboard

Once deployed, access the interactive dashboard at:
👉 **`http://localhost:1880/ui`**

### Dashboard Features:
- **Live Battery SoC Gauge**: Displays current EV state-of-charge (0 - 100%) in color tiers.
- **Power & Current Gauges**: Real-time kW and Amps reported from ESP32 sensors.
- **Line Voltage & Temperature**: Monitors grid stability and contactor thermal safety.
- **Contactor Relay Toggle**: Remote manual or automated switching of the charging contactor.
- **Cost Savings Analytics Card**: Compares Uncontrolled charging cost vs. Smart Optimized cost, computing live monetary savings (₹ / $) and CO2 reduction!

---

## 4. HiveMQ MQTT Connection

The flow is configured by default to connect to the public HiveMQ broker:
- **Broker**: `broker.hivemq.com`
- **Port**: `1883`
- **Subscribed Topics**:
  - `smart_ev/telemetry`
  - `smart_ev/schedule`
- **Publishing Topic**:
  - `smart_ev/control`
