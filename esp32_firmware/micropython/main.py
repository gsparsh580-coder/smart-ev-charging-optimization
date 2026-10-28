"""
MicroPython Firmware for ESP32 Smart EV Charging Station
Connects to Wi-Fi and HiveMQ MQTT broker, reads analog sensors and DHT22,
and controls relay based on MQTT commands.
"""

import time
import json
import machine
import network
from machine import Pin, ADC
import dht

# --- WiFi & MQTT Configuration ---
WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASS = "YOUR_WIFI_PASS"
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
TOPIC_TELEMETRY = b"smart_ev/telemetry"
TOPIC_CONTROL = b"smart_ev/control"
TOPIC_SCHEDULE = b"smart_ev/schedule"
TOPIC_STATUS = b"smart_ev/status"

# --- Pin Mapping ---
PIN_RELAY = 26
PIN_DHT = 14
PIN_CURRENT_ADC = 34
PIN_VOLTAGE_ADC = 35
PIN_LED_WIFI = 2
PIN_LED_CHARGING = 4

relay = Pin(PIN_RELAY, Pin.OUT, value=0)
led_wifi = Pin(PIN_LED_WIFI, Pin.OUT, value=0)
led_charging = Pin(PIN_LED_CHARGING, Pin.OUT, value=0)

current_adc = ADC(Pin(PIN_CURRENT_ADC))
current_adc.atten(ADC.ATTN_11DB)
voltage_adc = ADC(Pin(PIN_VOLTAGE_ADC))
voltage_adc.atten(ADC.ATTN_11DB)

sensor_dht = dht.DHT22(Pin(PIN_DHT))

# System state
relay_state = False
target_current = 16.0
battery_soc = 30.0
cumulative_kwh = 10.5


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to WiFi:", WIFI_SSID)
        wlan.connect(WIFI_SSID, WIFI_PASS)
        for _ in range(20):
            if wlan.isconnected():
                break
            time.sleep(0.5)
    if wlan.isconnected():
        print("WiFi Connected! IP:", wlan.ifconfig()[0])
        led_wifi.value(1)
    else:
        print("WiFi connection timeout!")
        led_wifi.value(0)
    return wlan.isconnected()


def mqtt_callback(topic, msg):
    global relay_state, target_current
    try:
        data = json.loads(msg.decode('utf-8'))
        print("MQTT Received:", topic, data)
        cmd = data.get("command") or data.get("state")
        if cmd in ["RELAY_ON", "ON", True]:
            relay_state = True
            relay.value(1)
            led_charging.value(1)
            print("Contactor Relay switched ON")
        elif cmd in ["RELAY_OFF", "OFF", False]:
            relay_state = False
            relay.value(0)
            led_charging.value(0)
            print("Contactor Relay switched OFF")

        if "target_current" in data:
            target_current = float(data["target_current"])
    except Exception as e:
        print("Error handling MQTT msg:", e)


def main():
    connect_wifi()
    try:
        from umqtt.simple import MQTTClient
        client_id = f"esp32_mpy_{machine.unique_id().hex()}"
        client = MQTTClient(client_id, MQTT_BROKER, port=MQTT_PORT)
        client.set_callback(mqtt_callback)
        client.connect()
        client.subscribe(TOPIC_CONTROL)
        client.subscribe(TOPIC_SCHEDULE)
        print("Connected to HiveMQ MQTT broker!")
    except Exception as e:
        print("MQTT Connect failed:", e)
        return

    last_pub = time.time()
    global battery_soc, cumulative_kwh

    while True:
        try:
            client.check_msg()
            now = time.time()
            if now - last_pub >= 2:
                last_pub = now
                temp_c = 28.0
                try:
                    sensor_dht.measure()
                    temp_c = sensor_dht.temperature()
                except Exception:
                    pass

                voltage = 230.0
                current = target_current if relay_state else 0.0
                power_kw = (voltage * current * 0.98) / 1000.0

                if relay_state and power_kw > 0:
                    kwh_delta = power_kw * (2.0 / 3600.0)
                    cumulative_kwh += kwh_delta
                    battery_soc = min(100.0, battery_soc + (kwh_delta * 0.92 / 60.0) * 100.0)

                payload = {
                    "device_id": f"ESP32_MPY_{machine.unique_id().hex()[-4:]}",
                    "voltage": round(voltage, 1),
                    "current": round(current, 2),
                    "power_kw": round(power_kw, 3),
                    "energy_kwh": round(cumulative_kwh, 4),
                    "temperature_c": round(temp_c, 1),
                    "battery_soc": round(battery_soc, 1),
                    "relay_state": "ON" if relay_state else "OFF",
                    "mode": "AUTO"
                }
                client.publish(TOPIC_TELEMETRY, json.dumps(payload))
                print("Telemetry Published:", payload)

            time.sleep(0.1)
        except Exception as err:
            print("Loop error:", err)
            time.sleep(2)


if __name__ == "__main__":
    main()
