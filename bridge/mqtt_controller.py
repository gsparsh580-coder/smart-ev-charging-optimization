"""
Smart EV Optimization & MQTT Bridge Controller
Coordinates between HiveMQ broker, optimization engine, and ESP32 actuators.
Runs schedule optimization in real-time and manages autonomous charging control.
"""

import time
import json
import random
import datetime
from typing import Dict, Any, Optional
import paho.mqtt.client as mqtt

from smart_ev_charging_optimization.optimization_engine.ev_optimizer import (
    EVChargingOptimizer, EVSpecs, GridEnvironment
)
from smart_ev_charging_optimization.optimization_engine.tariff_models import (
    StandardTOUTariff, SolarIncentiveTariff, DynamicRealTimeTariff
)

DEFAULT_BROKER = "broker.hivemq.com"
DEFAULT_PORT = 1883

TOPIC_TELEMETRY = "smart_ev/telemetry"
TOPIC_CONTROL = "smart_ev/control"
TOPIC_SCHEDULE = "smart_ev/schedule"
TOPIC_CONFIG = "smart_ev/config"
TOPIC_STATUS = "smart_ev/status"


class EVMQTTBridge:
    def __init__(
        self,
        broker: str = DEFAULT_BROKER,
        port: int = DEFAULT_PORT,
        client_id: Optional[str] = None
    ):
        self.broker = broker
        self.port = port
        self.client_id = client_id or f"EV_Optimizer_Bridge_{random.randint(1000, 9999)}"

        # System state
        self.latest_telemetry: Dict[str, Any] = {
            "battery_soc": 25.0,
            "relay_state": "OFF",
            "mode": "AUTO",
            "voltage": 230.0,
            "current": 0.0,
            "power_kw": 0.0,
            "temperature_c": 27.0
        }

        # User configuration
        self.config = {
            "battery_capacity_kwh": 60.0,
            "target_soc": 85.0,
            "departure_hour": 7,
            "arrival_hour": 18,
            "max_charger_kw": 7.4,
            "tariff_type": "standard_tou",
            "solar_peak_kw": 4.5,
            "auto_control_relay": True
        }

        self.current_schedule: Optional[Dict[str, Any]] = None
        self.last_optimize_time = 0.0

        # Initialize MQTT
        self.client = mqtt.Client(client_id=self.client_id, protocol=mqtt.MQTTv311)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"[Optimizer Bridge] Connected to HiveMQ Broker ({self.broker}:{self.port})")
            client.subscribe(TOPIC_TELEMETRY)
            client.subscribe(TOPIC_CONFIG)
            client.subscribe("smart_ev/trigger_optimize")
            self.run_and_publish_optimization()
        else:
            print(f"[Optimizer Bridge] Connection failed with return code {rc}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            topic = msg.topic

            if topic == TOPIC_TELEMETRY:
                self.latest_telemetry.update(payload)
                self._check_safety_limits(payload)
                self._evaluate_autonomous_control()

            elif topic == TOPIC_CONFIG:
                print(f"[Optimizer Bridge] Config update received: {payload}")
                self.config.update(payload)
                self.run_and_publish_optimization()

            elif topic == "smart_ev/trigger_optimize":
                print("[Optimizer Bridge] Manual optimization trigger received")
                self.run_and_publish_optimization()

        except Exception as e:
            print(f"[Optimizer Bridge] Error processing message: {e}")

    def _check_safety_limits(self, telemetry: Dict[str, Any]):
        """Emergency automatic disconnect if thermal or current thresholds are breached."""
        temp = telemetry.get("temperature_c", 25.0)
        current = telemetry.get("current", 0.0)

        if temp > 60.0 or current > 35.0:
            print(f"[SAFETY ALERT] Critical condition detected! Temp: {temp}C, Current: {current}A. CUTTING RELAY!")
            emergency_cmd = {
                "command": "RELAY_OFF",
                "state": "OFF",
                "reason": "SAFETY_OVERHEAT_OR_OVERCURRENT",
                "mode": "EMERGENCY_STOP",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
            }
            self.client.publish(TOPIC_CONTROL, json.dumps(emergency_cmd), qos=1)

    def _evaluate_autonomous_control(self):
        """In AUTO mode, commands the physical/virtual ESP32 relay according to the optimal schedule."""
        if not self.config.get("auto_control_relay", True):
            return

        current_mode = self.latest_telemetry.get("mode", "AUTO")
        if current_mode != "AUTO":
            return

        if not self.current_schedule:
            return

        current_hour = datetime.datetime.now().hour
        timeline = self.current_schedule.get("timeline", [])
        hour_slot = next((item for item in timeline if item["hour"] == current_hour), None)

        if hour_slot:
            planned_power = hour_slot.get("opt_power_kw", 0.0)
            current_relay = self.latest_telemetry.get("relay_state", "OFF")

            if planned_power > 0.1 and current_relay != "ON":
                print(f"[Optimizer Bridge] Hour {current_hour}:00 is scheduled for charging ({planned_power} kW). Actuating Relay ON.")
                cmd = {
                    "command": "RELAY_ON",
                    "target_current": round((planned_power * 1000.0) / 230.0, 1),
                    "mode": "AUTO",
                    "reason": "OPTIMAL_SCHEDULE_ACTIVE"
                }
                self.client.publish(TOPIC_CONTROL, json.dumps(cmd))

            elif planned_power <= 0.1 and current_relay == "ON":
                print(f"[Optimizer Bridge] Hour {current_hour}:00 is idle/expensive peak. Actuating Relay OFF.")
                cmd = {
                    "command": "RELAY_OFF",
                    "target_current": 0.0,
                    "mode": "AUTO",
                    "reason": "OPTIMAL_SCHEDULE_IDLE"
                }
                self.client.publish(TOPIC_CONTROL, json.dumps(cmd))

    def run_and_publish_optimization(self):
        """Runs the SciPy optimization using latest telemetry and publishes schedule."""
        current_soc = float(self.latest_telemetry.get("battery_soc", self.latest_telemetry.get("soc", 20.0)))
        print(f"[Optimizer Bridge] Running Schedule Optimization (Current SoC: {current_soc}% -> Target: {self.config['target_soc']}%)...")

        # Construct solar curve
        solar_peak = float(self.config.get("solar_peak_kw", 4.5))
        solar_curve = []
        import numpy as np
        for h in range(24):
            if 6 <= h <= 18:
                val = solar_peak * np.sin((h - 6) * np.pi / 12) ** 2
                solar_curve.append(round(float(val), 2))
            else:
                solar_curve.append(0.0)

        # Select tariff
        t_type = self.config.get("tariff_type", "standard_tou")
        if t_type == "solar_tou":
            tariff_model = SolarIncentiveTariff()
        elif t_type == "dynamic_spot":
            tariff_model = DynamicRealTimeTariff()
        else:
            tariff_model = StandardTOUTariff()

        rates = tariff_model.get_hourly_rates()

        specs = EVSpecs(
            battery_capacity_kwh=float(self.config["battery_capacity_kwh"]),
            current_soc_percent=current_soc,
            target_soc_percent=float(self.config["target_soc"]),
            max_charge_power_kw=float(self.config["max_charger_kw"]),
            arrival_hour=int(self.config["arrival_hour"]),
            departure_hour=int(self.config["departure_hour"]),
        )

        grid = GridEnvironment(
            hourly_tariffs=rates,
            solar_generation_kw=solar_curve,
            grid_power_limit_kw=12.0
        )

        optimizer = EVChargingOptimizer(specs, grid)
        result = optimizer.solve()
        result["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
        result["tariff_name"] = tariff_model.name
        self.current_schedule = result

        # Publish retained schedule so Web Dashboard & Node-RED have it instantly
        self.client.publish(TOPIC_SCHEDULE, json.dumps(result), retain=True)
        savings = result['comparison']['savings_percent']
        cost_opt = result['optimized']['total_cost']
        cost_un = result['uncontrolled']['total_cost']
        print(f"[Optimizer Bridge] Schedule published! Uncontrolled: {cost_un} | Optimized: {cost_opt} | Savings: {savings}%")

    def run(self):
        print(f"[Optimizer Bridge] Connecting to {self.broker}:{self.port}...")
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_forever()


if __name__ == "__main__":
    bridge = EVMQTTBridge()
    bridge.run()
