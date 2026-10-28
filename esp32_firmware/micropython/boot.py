# MicroPython boot.py for ESP32 Smart EV Charging
import esp
import gc
import network
import time

esp.osdebug(None)
gc.collect()

print("ESP32 MicroPython Booted")
