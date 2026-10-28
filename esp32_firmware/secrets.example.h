/**
 * Configuration Secrets Template for ESP32 Smart EV Charging Firmware
 * Copy this file to 'secrets.h' and fill in your actual credentials.
 */

#ifndef SECRETS_H
#define SECRETS_H

// --- Wi-Fi Credentials ---
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// --- HiveMQ MQTT Broker Settings ---
// For HiveMQ Public Broker:
const char* MQTT_BROKER   = "broker.hivemq.com";
const int   MQTT_PORT     = 1883;
const char* MQTT_USERNAME = "";   // Leave empty for public broker
const char* MQTT_PASSWORD = "";   // Leave empty for public broker

// For HiveMQ Cloud (TLS / Cluster):
// const char* MQTT_BROKER   = "xxxxxxxxxxxx.s1.eu.hivemq.cloud";
// const int   MQTT_PORT     = 8883;
// const char* MQTT_USERNAME = "your_hivemq_user";
// const char* MQTT_PASSWORD = "your_hivemq_password";

// --- MQTT Topics ---
const char* TOPIC_TELEMETRY = "smart_ev/telemetry";
const char* TOPIC_CONTROL   = "smart_ev/control";
const char* TOPIC_SCHEDULE  = "smart_ev/schedule";
const char* TOPIC_STATUS    = "smart_ev/status";

#endif // SECRETS_H
