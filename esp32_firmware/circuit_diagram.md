# ESP32 Smart EV Charging Station: Hardware & Circuit Guide

This document describes the circuit schematic, hardware wiring, pin mappings, and safety isolation for interfacing the **ESP32 DevKit** with EV charging equipment, sensors, and relays.

---

## 1. Hardware Bill of Materials (BOM)

| Component | Specification | Purpose |
| :--- | :--- | :--- |
| **Microcontroller** | ESP32 DevKit V1 (30-pin / 38-pin, WROOM-32) | Core compute, Wi-Fi & MQTT engine |
| **Current Sensor** | ACS712-30A (Hall-effect) or INA219 (I2C) | Measures continuous AC/DC charging current |
| **Voltage Sensor** | ZMPT101B (AC Transformer) or calibrated divider | Measures AC mains grid voltage (200-250V AC) |
| **Relay Contactor** | 30A / 40A 250VAC Heavy-Duty Relay Module (5V/12V trigger) | Switched line conductor cut-off |
| **Temperature Sensor**| DHT22 / DS18B20 Digital Sensor | Monitors contactor & terminal temperature |
| **Status LEDs** | Blue (WiFi/MQTT), Green (Charging), Red (Fault) | Physical operational status indicators |
| **Power Supply** | 5V 2A Regulated DC Power Supply (HLK-PM01 or adapter)| Powers ESP32 and relay coil |
| **Terminal Blocks** | 30A High-Current DIN Rail / Screw Terminals | Safe high-voltage wiring junction |

---

## 2. ESP32 Pin Mapping Table

| ESP32 GPIO | Pin Mode | Connected Device | Function |
| :--- | :--- | :--- | :--- |
| **GPIO 26** | OUTPUT | Contactor Relay Module (IN) | High = Relay Energized (Charging ON), Low = OFF |
| **GPIO 34** | ANALOG IN | ACS712 Current Sensor (OUT) | Analog ADC voltage representing charging current |
| **GPIO 35** | ANALOG IN | ZMPT101B Voltage Sensor (OUT)| Analog ADC voltage representing grid voltage |
| **GPIO 14** | DIGITAL I/O| DHT22 Data Pin (Pull-up 10kΩ)| Measures ambient and thermal junction temp |
| **GPIO 2** | OUTPUT | Blue Onboard LED | Wi-Fi & HiveMQ MQTT connection status |
| **GPIO 4** | OUTPUT | Green LED (220Ω resistor) | Active charging indicator |
| **GPIO 15** | OUTPUT | Red LED (220Ω resistor) | Overheat / Overcurrent Fault Alarm indicator |
| **GPIO 25** | PWM OUT | J1772 Control Pilot (1 kHz) | PWM duty cycle defines max pilot current |
| **GND** | GROUND | Common Ground | Common return path for logic signals |
| **VIN / 5V** | POWER IN | +5V DC Rail | Regulated 5V input from power supply |

---

## 3. Circuit Wiring Schematic

```text
               +-------------------------------------------------------+
               |                  ESP32 DEVKIT V1                      |
               |                                                       |
               |  [GPIO 26] ------------------------> [Relay IN]       |
               |                                         |             |
               |  [GPIO 34] <--- (Analog Out) ------- [ACS712 Sensor]  |
               |                                         |             |
               |  [GPIO 35] <--- (Analog Out) ------- [ZMPT101B AC]    |
               |                                         |             |
               |  [GPIO 14] <---> (Data + 10k Pullup)- [DHT22 Temp]    |
               |                                                       |
               |  [GPIO 2]  -------- [Blue LED] -----> GND             |
               |  [GPIO 4]  -------- [Green LED] ----> GND             |
               |  [GPIO 15] -------- [Red LED] ------> GND             |
               |                                                       |
               |  [VIN / 5V] <----------------------- [+5V Power]      |
               |  [GND]      ------------------------ [GND Rail]       |
               +-------------------------------------------------------+

       HIGH-VOLTAGE AC MAINS POWER PATH (ISOLATED VIA HEAVY RELAY):
       ============================================================

       [Grid AC Line (L)] ----+
                              |
                              v
                        [ACS712 Current] 
                              |
                              v
                      [Relay COM -> NO] ----------------> [EV Plug Line (L)]
                                                                |
       [Grid AC Neutral (N)] ---------------------------> [EV Plug Neutral (N)]
                                                                |
       [Earth Ground (PE)] -----------------------------> [EV Plug Ground (PE)]
```

---

## 4. Hardware Safety & Isolation Requirements

> [!WARNING]
> High voltage AC (230V/400V) can cause serious injury or electrical fires. Ensure adherence to the following:

1. **Optocoupler Isolation**: The relay module MUST include optical isolation between the ESP32 low-voltage logic (3.3V) and the relay switching coil (5V/12V).
2. **Current Rating Overhead**: For an EV drawing 16A continuous, use a contactor rated for at least **25A to 32A continuous resistive load**. For 32A EV charging, use a **40A or 50A modular AC contactor**.
3. **Thermal Trip Interlock**: The firmware executes a hard hardware cut-off if the sensor reports temperatures $\ge 60^\circ\text{C}$ to prevent thermal runaway of the terminal lugs.
4. **Earth Fault / RCD**: Connect the circuit through a dedicated Type-B or Type-A EV Residual Current Device (RCD/GFCI) and 32A MCB breaker on the main distribution panel.
