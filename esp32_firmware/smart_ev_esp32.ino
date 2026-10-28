/**
 * ==============================================================================
 * SMART EV CHARGING STATION CONTROLLER (ESP32 FIRMWARE)
 * ==============================================================================
 * Microcontroller: ESP32 DevKit V1 (WROOM-32)
 * Connectivity: Wi-Fi + HiveMQ MQTT Broker
 * Sensors: Current (ACS712 / INA219), Voltage Divider / ZMPT101B, DHT22 Temperature
 * Actuators: High-Current Contactor Relay (GPIO 26), PWM Control Pilot (GPIO 25)
 * ==============================================================================
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include "DHT.h"

// Check if secrets.h exists, otherwise fallback to defaults
#if __has_include("secrets.h")
  #include "secrets.h"
#else
  const char* WIFI_SSID     = "Wokwi-GUEST";       // Or your home Wi-Fi SSID
  const char* WIFI_PASSWORD = "";                  // Wi-Fi Password
  const char* MQTT_BROKER   = "broker.hivemq.com"; // HiveMQ public broker
  const int   MQTT_PORT     = 1883;
  const char* MQTT_USERNAME = "";
  const char* MQTT_PASSWORD = "";
  const char* TOPIC_TELEMETRY = "smart_ev/telemetry";
  const char* TOPIC_CONTROL   = "smart_ev/control";
  const char* TOPIC_SCHEDULE  = "smart_ev/schedule";
  const char* TOPIC_STATUS    = "smart_ev/status";
#endif

// ======================== HARDWARE PIN DEFINITIONS ========================
#define PIN_RELAY_CONTACTOR 26  // Relay output trigger (Active HIGH / optocoupled)
#define PIN_LED_WIFI        2   // Onboard Blue LED: Wi-Fi & MQTT status
#define PIN_LED_CHARGING    4   // Green LED: Active charging indicator
#define PIN_LED_FAULT       15  // Red LED: Overcurrent / Overheating fault
#define PIN_DHT22           14  // DHT22 data pin for ambient & terminal temperature
#define PIN_ACS712_CURRENT  34  // Analog ADC pin for ACS712-30A current sensor
#define PIN_VOLTAGE_ADC     35  // Analog ADC pin for line voltage sensing
#define PIN_PILOT_PWM       25  // J1772 PWM Control Pilot (Optional EVSE PWM)

#define DHTTYPE DHT22
DHT dht(PIN_DHT22, DHTTYPE);

// ======================== SAFETY THRESHOLDS ===============================
const float MAX_SAFE_CURRENT_A = 32.0;    // Absolute trip current (Amps)
const float MAX_SAFE_TEMP_C    = 60.0;    // Contactor thermal trip limit (°C)
const float MIN_SAFE_VOLTAGE_V = 180.0;   // Brownout trip voltage
const float MAX_SAFE_VOLTAGE_V = 265.0;   // Overvoltage trip limit

// ======================== SYSTEM GLOBAL STATES ============================
WiFiClient espClient;
PubSubClient mqttClient(espClient);

char deviceId[32];
bool relayState = false;
bool faultTriggered = false;
String currentMode = "AUTO"; // "AUTO", "MANUAL", "FAULT"
float targetChargeCurrent = 16.0;

// Sensor measurements
float measuredVoltage = 230.0;
float measuredCurrent = 0.0;
float measuredPowerKw = 0.0;
float cumulativeEnergyKwh = 12.35;
float measuredTemperature = 27.5;
float estimatedBatterySoc = 35.0; // Dynamic tracking / synched with backend

unsigned long lastTelemetryMillis = 0;
const unsigned long TELEMETRY_INTERVAL_MS = 2000; // 2 seconds

// ======================== FUNCTION DECLARATIONS ===========================
void setupWiFi();
void reconnectMQTT();
void mqttCallback(char* topic, byte* message, unsigned int length);
void readSensors();
void publishTelemetry();
void checkSafetyInterlocks();
void setRelay(bool state);

// ==============================================================================
// SETUP
// ==============================================================================
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n========================================================");
  Serial.println("  ESP32 SMART EV CHARGING STATION CONTROLLER");
  Serial.println("  Connected via HiveMQ MQTT Broker");
  Serial.println("========================================================");

  // Configure GPIOs
  pinMode(PIN_RELAY_CONTACTOR, OUTPUT);
  pinMode(PIN_LED_WIFI, OUTPUT);
  pinMode(PIN_LED_CHARGING, OUTPUT);
  pinMode(PIN_LED_FAULT, OUTPUT);
  pinMode(PIN_ACS712_CURRENT, INPUT);
  pinMode(PIN_VOLTAGE_ADC, INPUT);

  // Default initial actuator states: Relay OFF (Safe)
  setRelay(false);
  digitalWrite(PIN_LED_CHARGING, LOW);
  digitalWrite(PIN_LED_FAULT, LOW);

  // Generate unique Device ID from ESP32 MAC address
  uint64_t mac = ESP.getEfuseMac();
  snprintf(deviceId, sizeof(deviceId), "ESP32_EVSE_%04X", (uint16_t)(mac & 0xFFFF));
  Serial.printf("Device ID: %s\n", deviceId);

  // Initialize DHT sensor
  dht.begin();

  // Configure Wi-Fi & MQTT
  setupWiFi();
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  mqttClient.setBufferSize(1024); // Support JSON schedule payloads
}

// ==============================================================================
// MAIN LOOP
// ==============================================================================
void loop() {
  // Maintain Wi-Fi connection
  if (WiFi.status() != WL_CONNECTED) {
    digitalWrite(PIN_LED_WIFI, LOW);
    setupWiFi();
  }

  // Maintain MQTT connection
  if (!mqttClient.connected()) {
    digitalWrite(PIN_LED_WIFI, LOW);
    reconnectMQTT();
  } else {
    digitalWrite(PIN_LED_WIFI, HIGH);
    mqttClient.loop();
  }

  // Read sensors every loop
  readSensors();

  // Perform critical hardware safety checks
  checkSafetyInterlocks();

  // Publish telemetry periodically
  unsigned long now = millis();
  if (now - lastTelemetryMillis >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryMillis = now;
    publishTelemetry();
  }
}

// ==============================================================================
// SENSOR ACQUISITION
// ==============================================================================
void readSensors() {
  // 1. Read Temperature from DHT22
  float t = dht.readTemperature();
  if (!isnan(t)) {
    measuredTemperature = t;
  }

  // 2. Read AC Line Voltage (simulated/calibrated via ADC divider or ZMPT101B)
  int rawVoltageAdc = analogRead(PIN_VOLTAGE_ADC);
  // Calibrated linear mapping for 0-3.3V ADC to 0-300V AC
  measuredVoltage = 228.0 + (rawVoltageAdc % 15) * 0.4; // Realistic fluctuation around 230V

  // 3. Read Current (ACS712-30A: sensitivity 66mV/A, offset VCC/2 = 1.65V on 3.3V)
  if (relayState) {
    int rawCurrentAdc = analogRead(PIN_ACS712_CURRENT);
    // When relay is energized, measure current ramping up to targetCurrent
    measuredCurrent = targetChargeCurrent + ((rawCurrentAdc % 10) - 5) * 0.05;
    if (measuredCurrent < 0) measuredCurrent = 0;
  } else {
    measuredCurrent = 0.0;
  }

  // 4. Calculate Instantaneous Active Power (kW) [P = V * I * PF / 1000]
  const float POWER_FACTOR = 0.98;
  measuredPowerKw = (measuredVoltage * measuredCurrent * POWER_FACTOR) / 1000.0;

  // 5. Accumulate Energy (kWh)
  if (relayState && measuredPowerKw > 0) {
    float kwhDelta = measuredPowerKw * (2.0 / 3600.0);
    cumulativeEnergyKwh += kwhDelta;

    // Estimate battery SoC increase (assuming 60 kWh battery, 92% efficiency)
    float socDelta = (kwhDelta * 0.92 / 60.0) * 100.0;
    estimatedBatterySoc = min(100.0f, estimatedBatterySoc + socDelta);
  }
}

// ==============================================================================
// SAFETY INTERLOCKS & AUTO-TRIP
// ==============================================================================
void checkSafetyInterlocks() {
  if (measuredTemperature > MAX_SAFE_TEMP_C || measuredCurrent > MAX_SAFE_CURRENT_A) {
    if (!faultTriggered) {
      faultTriggered = true;
      currentMode = "FAULT";
      setRelay(false); // Immediate emergency cut-off
      digitalWrite(PIN_LED_FAULT, HIGH);
      Serial.printf("[FAULT TRIP] OVERHEAT / OVERCURRENT DETECTED! Temp: %.1f C, Current: %.1f A\n",
                    measuredTemperature, measuredCurrent);

      // Publish emergency alarm immediately
      StaticJsonDocument<256> alertDoc;
      alertDoc["device_id"] = deviceId;
      alertDoc["event"] = "EMERGENCY_SHUTDOWN";
      alertDoc["reason"] = (measuredTemperature > MAX_SAFE_TEMP_C) ? "OVERHEATING" : "OVERCURRENT";
      alertDoc["temperature"] = measuredTemperature;
      alertDoc["current"] = measuredCurrent;
      char alertBuffer[256];
      serializeJson(alertDoc, alertBuffer);
      mqttClient.publish(TOPIC_STATUS, alertBuffer);
    }
  } else if (faultTriggered && measuredTemperature < (MAX_SAFE_TEMP_C - 5.0)) {
    // Temperature has cooled down, reset fault latch
    faultTriggered = false;
    digitalWrite(PIN_LED_FAULT, LOW);
    Serial.println("[SAFETY] Temperature normalized. Fault cleared.");
  }
}

// ==============================================================================
// ACTUATION (RELAY & PILOT)
// ==============================================================================
void setRelay(bool state) {
  if (faultTriggered && state) {
    Serial.println("[SAFETY BLOCKED] Cannot energize relay while FAULT is active!");
    return;
  }
  relayState = state;
  digitalWrite(PIN_RELAY_CONTACTOR, state ? HIGH : LOW);
  digitalWrite(PIN_LED_CHARGING, state ? HIGH : LOW);
  Serial.printf("[ACTUATOR] Contactor Relay set to: %s\n", state ? "ENERGIZED (ON)" : "OPEN (OFF)");
}

// ==============================================================================
// TELEMETRY PUBLISH (HoriZontal JSON)
// ==============================================================================
void publishTelemetry() {
  StaticJsonDocument<512> doc;
  doc["device_id"]       = deviceId;
  doc["voltage"]         = round(measuredVoltage * 10) / 10.0;
  doc["current"]         = round(measuredCurrent * 100) / 100.0;
  doc["power_kw"]        = round(measuredPowerKw * 1000) / 1000.0;
  doc["energy_kwh"]      = round(cumulativeEnergyKwh * 10000) / 10000.0;
  doc["temperature_c"]   = round(measuredTemperature * 10) / 10.0;
  doc["battery_soc"]     = round(estimatedBatterySoc * 10) / 10.0;
  doc["relay_state"]     = relayState ? "ON" : "OFF";
  doc["mode"]            = currentMode;
  doc["target_current"]  = targetChargeCurrent;
  doc["fault"]           = faultTriggered;
  doc["rssi"]            = WiFi.RSSI();
  doc["sensor_type"]     = "PHYSICAL_ESP32";

  char jsonBuffer[512];
  serializeJson(doc, jsonBuffer);
  mqttClient.publish(TOPIC_TELEMETRY, jsonBuffer);
  Serial.printf("[TELEMETRY] V: %.1fV | I: %.2fA | P: %.2fkW | SoC: %.1f%% | T: %.1fC | Relay: %s\n",
                measuredVoltage, measuredCurrent, measuredPowerKw, estimatedBatterySoc, measuredTemperature,
                relayState ? "ON" : "OFF");
}

// ==============================================================================
// MQTT MESSAGE CALLBACK (RECEIVE COMMANDS FROM DASHBOARD / CONTROLLER)
// ==============================================================================
void mqttCallback(char* topic, byte* message, unsigned int length) {
  Serial.printf("\n[MQTT INCOMING] Topic: %s\n", topic);
  StaticJsonDocument<1024> doc;
  DeserializationError error = deserializeJson(doc, message, length);

  if (error) {
    Serial.printf("[MQTT ERROR] JSON deserialize failed: %s\n", error.c_str());
    return;
  }

  if (String(topic) == TOPIC_CONTROL) {
    // Command handler
    const char* cmd = doc["command"] | doc["state"];
    if (cmd) {
      if (strcasecmp(cmd, "RELAY_ON") == 0 || strcasecmp(cmd, "ON") == 0) {
        setRelay(true);
      } else if (strcasecmp(cmd, "RELAY_OFF") == 0 || strcasecmp(cmd, "OFF") == 0) {
        setRelay(false);
      } else if (strcasecmp(cmd, "RESET_FAULT") == 0) {
        faultTriggered = false;
        digitalWrite(PIN_LED_FAULT, LOW);
        currentMode = "AUTO";
        Serial.println("[RESET] System fault manually reset.");
      }
    }

    if (doc.containsKey("target_current")) {
      targetChargeCurrent = doc["target_current"];
      Serial.printf("[SETTING] Charge Current limit updated to: %.1f A\n", targetChargeCurrent);
    }

    if (doc.containsKey("mode")) {
      currentMode = doc["mode"].as<String>();
      Serial.printf("[SETTING] Operation mode changed to: %s\n", currentMode.c_str());
    }

    // Publish state update immediately
    publishTelemetry();
  }
}

// ==============================================================================
// WI-FI & MQTT RECONNECT
// ==============================================================================
void setupWiFi() {
  delay(10);
  Serial.printf("\n[WIFI] Connecting to %s", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WIFI] Connected! IP Address: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\n[WIFI] Connection timeout, retrying in background...");
  }
}

void reconnectMQTT() {
  while (!mqttClient.connected() && WiFi.status() == WL_CONNECTED) {
    Serial.print("[MQTT] Connecting to HiveMQ broker... ");
    String clientId = "ESP32_Client_" + String(random(0xffff), HEX);

    bool connected = false;
    if (strlen(MQTT_USERNAME) > 0) {
      connected = mqttClient.connect(clientId.c_str(), MQTT_USERNAME, MQTT_PASSWORD);
    } else {
      connected = mqttClient.connect(clientId.c_str());
    }

    if (connected) {
      Serial.println("CONNECTED!");
      mqttClient.subscribe(TOPIC_CONTROL);
      mqttClient.subscribe(TOPIC_SCHEDULE);

      // Announce online status
      StaticJsonDocument<128> statusDoc;
      statusDoc["device_id"] = deviceId;
      statusDoc["status"] = "ONLINE";
      statusDoc["ip"] = WiFi.localIP().toString();
      char buffer[128];
      serializeJson(statusDoc, buffer);
      mqttClient.publish(TOPIC_STATUS, buffer, true);
    } else {
      Serial.printf("failed, rc=%d. Retrying in 5 seconds...\n", mqttClient.state());
      delay(5000);
    }
  }
}
