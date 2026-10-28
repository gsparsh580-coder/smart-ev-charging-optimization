"""
Virtual ESP32 Hardware Simulator for Smart EV Charging
Emulates physical sensors (Voltage, Current, Power, Energy, Temperature, Relay contactor)
and connects directly to HiveMQ MQTT broker to mirror physical ESP32 hardware behavior.
"""

import time
import json
import random
import datetime
from typing import Optional
import paho.mqtt.client as mqtt

# MQTT Configuration (HiveMQ Public Broker)
DEFAULT_BROKER = "broker.hivemq.com"
DEFAULT_PORT = 1883
TOPIC_TELEMETRY = "smart_ev/telemetry"
TOPIC_CONTROL = "smart_ev/control"
TOPIC_SCHEDULE = "smart_ev/schedule"
TOPIC_STATUS = "smart_ev/status"


class VirtualESP32:
    """
    Simulates physical ESP32 microcontroller with:
    - Current sensor (ACS712 / INA219)
    - AC Voltage sensor (ZMPT101B)
    - Temperature sensor (DS18B20 / DHT22)
    - High-current Relay module
    - Battery SoC tracking
    """

    def __init__(
        self,
        broker: str = DEFAULT_BROKER,
        port: int = DEFAULT_PORT,
        device_id: str = "ESP32_VIRTUAL_EVSE_01",
        battery_capacity_kwh: float = 60.0,
        initial_soc: float = 24.5,
    ):
        self.broker = broker
        self.port = port
        self.device_id = device_id
        self.battery_capacity_kwh = battery_capacity_kwh
        self.battery_soc = initial_soc

        # Hardware states
        self.relay_state = "OFF"
        self.mode = "AUTO"
        self.target_current = 16.0  # Amperes (Level 2 default)
        self.measured_current = 0.0
        self.measured_voltage = 230.0
        self.measured_power_kw = 0.0
        self.cumulative_energy_kwh = 14.82
        self.temperature_c = 28.5
        self.connected_plug = True
        self.running = False

        # Current schedule slot
        self.current_schedule_power_kw = 0.0

        # Initialize MQTT client
        self.client = mqtt.Client(
            client_id=f"{self.device_id}_{random.randint(1000, 9999)}",
            protocol=mqtt.MQTTv311
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"[Virtual ESP32] Connected successfully to HiveMQ broker ({self.broker}:{self.port})")
            client.subscribe(TOPIC_CONTROL)
            client.subscribe(TOPIC_SCHEDULE)
            # Announce status
            status_payload = {
                "device_id": self.device_id,
                "status": "ONLINE",
                "firmware_version": "v2.4.1-virtual",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
            }
            client.publish(TOPIC_STATUS, json.dumps(status_payload), retain=True)
        else:
            print(f"[Virtual ESP32] Connection failed with code {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            topic = msg.topic
            print(f"[Virtual ESP32] Received MQTT on [{topic}]: {payload}")

            if topic == TOPIC_CONTROL:
                cmd = payload.get("command") or payload.get("state")
                if cmd in ["RELAY_ON", "ON", True]:
                    self.relay_state = "ON"
                    print("[Virtual ESP32] Relay contactor switched ON")
                elif cmd in ["RELAY_OFF", "OFF", False]:
                    self.relay_state = "OFF"
                    print("[Virtual ESP32] Relay contactor switched OFF")

                if "target_current" in payload:
                    self.target_current = float(payload["target_current"])
                if "mode" in payload:
                    self.mode = str(payload["mode"]).upper()

                # Publish immediate telemetry feedback
                self.publish_telemetry()

            elif topic == TOPIC_SCHEDULE:
                # Received new schedule from optimization engine
                if "hourly_plan" in payload:
                    print(f"[Virtual ESP32] Received updated schedule with {len(payload['hourly_plan'])} slots")
        except Exception as e:
            print(f"[Virtual ESP32] Error parsing MQTT message: {e}")

    def update_physics(self, dt_seconds: float = 2.0):
        """Simulates electrical and thermal sensor readings based on current state."""
        # Voltage fluctuations
        self.measured_voltage = round(230.0 + random.uniform(-4.0, 4.0), 1)

        if self.relay_state == "ON" and self.connected_plug:
            # Active charging: current ramps smoothly towards target_current
            target_i = min(32.0, max(6.0, self.target_current))
            noise = random.uniform(-0.3, 0.3)
            self.measured_current = round(target_i + noise, 2)
            # Active power (P = V * I * PF / 1000)
            power_factor = 0.98
            self.measured_power_kw = round((self.measured_voltage * self.measured_current * power_factor) / 1000.0, 3)

            # Energy accumulation
            kwh_delta = (self.measured_power_kw * (dt_seconds / 3600.0))
            self.cumulative_energy_kwh = round(self.cumulative_energy_kwh + kwh_delta, 4)

            # Battery State of Charge increase (92% charging efficiency)
            soc_delta = (kwh_delta * 0.92 / self.battery_capacity_kwh) * 100.0
            self.battery_soc = round(min(100.0, self.battery_soc + soc_delta), 2)

            # Thermal model: gentle warming under load (up to ~42°C)
            target_temp = 28.0 + (self.measured_current / 32.0) * 14.0
            self.temperature_c = round(self.temperature_c + (target_temp - self.temperature_c) * 0.05 + random.uniform(-0.1, 0.1), 1)
        else:
            # Relay OFF: zero current and power
            self.measured_current = 0.0
            self.measured_power_kw = 0.0
            # Cool down towards ambient (26°C)
            self.temperature_c = round(self.temperature_c + (26.0 - self.temperature_c) * 0.03, 1)

    def publish_telemetry(self):
        """Publishes live sensor packet to HiveMQ broker."""
        telemetry_payload = {
            "device_id": self.device_id,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "voltage": self.measured_voltage,
            "current": self.measured_current,
            "power_kw": self.measured_power_kw,
            "energy_kwh": self.cumulative_energy_kwh,
            "temperature_c": self.temperature_c,
            "battery_soc": self.battery_soc,
            "relay_state": self.relay_state,
            "mode": self.mode,
            "plug_connected": self.connected_plug,
            "target_current": self.target_current,
            "sensor_type": "VIRTUAL_SYNTHETIC"
        }
        self.client.publish(TOPIC_TELEMETRY, json.dumps(telemetry_payload))

    def run(self, interval_seconds: float = 2.0):
        """Starts the simulator loop."""
        print(f"[Virtual ESP32] Connecting to {self.broker}:{self.port}...")
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()
        self.running = True
        print(f"[Virtual ESP32] Publishing telemetry every {interval_seconds}s to '{TOPIC_TELEMETRY}'")
        print("[Virtual ESP32] Listening for control commands on 'smart_ev/control'...")

        try:
            while self.running:
                self.update_physics(interval_seconds)
                self.publish_telemetry()
                time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\n[Virtual ESP32] Stopping simulator...")
        finally:
            self.client.loop_stop()
            self.client.disconnect()


if __name__ == "__main__":
    sim = VirtualESP32()
    sim.run()
