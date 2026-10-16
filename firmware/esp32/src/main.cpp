#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

#ifndef WIFI_SSID
#define WIFI_SSID "CHANGE_ME_WIFI_SSID"
#endif
#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD "CHANGE_ME_WIFI_PASSWORD"
#endif
#ifndef MQTT_HOST
#define MQTT_HOST "192.168.1.100"
#endif
#ifndef MQTT_PORT
#define MQTT_PORT 1883
#endif
#ifndef MQTT_USER
#define MQTT_USER "smpark"
#endif
#ifndef MQTT_PASSWORD
#define MQTT_PASSWORD "change_me_mqtt"
#endif

const char* WIFI_SSID_ENV = WIFI_SSID;
const char* WIFI_PASS_ENV = WIFI_PASSWORD;
const char* MQTT_HOST_ENV = MQTT_HOST;
int MQTT_PORT_ENV = MQTT_PORT;
const char* MQTT_USER_ENV = MQTT_USER;
const char* MQTT_PASS_ENV = MQTT_PASSWORD;

const char* TOPIC_BARRIER_CMD = "parking/barrier/command";
const char* TOPIC_BARRIER_STATE = "barrier/state";

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

unsigned long lastStatePublish = 0;
const unsigned long stateInterval = 5000;

void connectWiFi() {
  WiFi.begin(WIFI_SSID_ENV, WIFI_PASS_ENV);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
}

void publishBarrierState(const char* state, const char* reason = nullptr) {
  JsonDocument doc;
  doc["state"] = state;
  if (reason) doc["reason"] = reason;
  doc["uptime_ms"] = millis();
  char buf[256];
  serializeJson(doc, buf);
  mqttClient.publish(TOPIC_BARRIER_STATE, buf, true);
}

void callback(char* topic, byte* payload, unsigned int length) {
  if (strcmp(topic, TOPIC_BARRIER_CMD) == 0) {
    char msg[512];
    if (length >= sizeof(msg)) length = sizeof(msg) - 1;
    memcpy(msg, payload, length);
    msg[length] = '\0';
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, msg);
    if (err) {
      publishBarrierState("error", "invalid_json");
      return;
    }
    const char* action = doc["action"] | "none";
    if (strcmp(action, "open") == 0) {
      publishBarrierState("opening");
      delay(500);
      publishBarrierState("open");
      delay(2000);
      publishBarrierState("closing");
      delay(500);
      publishBarrierState("closed");
    } else if (strcmp(action, "close") == 0) {
      publishBarrierState("closing");
      delay(500);
      publishBarrierState("closed");
    } else {
      publishBarrierState("idle", "unknown_action");
    }
  }
}

void connectMQTT() {
  while (!mqttClient.connected()) {
    if (mqttClient.connect("smpark-esp32", MQTT_USER_ENV, MQTT_PASS_ENV)) {
      mqttClient.subscribe(TOPIC_BARRIER_CMD);
      publishBarrierState("idle");
    } else {
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  connectWiFi();
  mqttClient.setServer(MQTT_HOST_ENV, MQTT_PORT_ENV);
  mqttClient.setCallback(callback);
  connectMQTT();
  publishBarrierState("initialized");
}

void loop() {
  if (!mqttClient.connected()) {
    connectMQTT();
  }
  mqttClient.loop();
  if (millis() - lastStatePublish > stateInterval) {
    lastStatePublish = millis();
    publishBarrierState("heartbeat");
  }
}
