#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// =========================================================================
// SM-Park - Firmware ESP32 : nœud barrière (2 servos prévus)
// -------------------------------------------------------------------------
// - Aucun delay() bloquant : machine à états pilotée par millis(), le
//   callback MQTT ne fait que fixer l'état cible.
// - Reconnexion Wi-Fi et MQTT non bloquantes (backoff).
// - Last Will "offline" + état "online" retenu : le backend sait si le
//   device est hors ligne.
// - La config Wi-Fi/MQTT provient de secrets.ini (build_flags), jamais du code.
// =========================================================================

// --- Brochage (adapter selon le câblage ; 2 barrières = 2 servos) ---
#define PIN_SERVO_ENTRY 13
#define PIN_SERVO_EXIT  12
#define PIN_LED_STATUS  2

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

// --- Temporisation de la séquence (identique à l'ancien enchaînement) ---
const unsigned long OPENING_DURATION_MS = 500;
const unsigned long OPEN_HOLD_MS = 2000;
const unsigned long CLOSING_DURATION_MS = 500;
const unsigned long WIFI_RETRY_MS = 5000;
const unsigned long MQTT_RETRY_MS = 5000;
const unsigned long STATE_HEARTBEAT_MS = 5000;

enum BarrierState { IDLE, OPENING, OPEN, CLOSING, CLOSED };

const char* WIFI_STATE_NAMES[] = {"idle", "opening", "open", "closing", "closed"};

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

BarrierState barrierState = IDLE;
unsigned long stateSince = 0;
String currentGate = "entry";

unsigned long lastStatePublish = 0;
unsigned long lastWifiAttempt = 0;
unsigned long lastMqttAttempt = 0;

// --- Publication des états (retain=true pour que le backend voit le dernier) ---
void publishBarrierState(const char* state, const char* reason = nullptr) {
  JsonDocument doc;
  doc["state"] = state;
  doc["gate"] = currentGate;
  if (reason) doc["reason"] = reason;
  doc["uptime_ms"] = millis();
  char buf[256];
  serializeJson(doc, buf);
  mqttClient.publish(TOPIC_BARRIER_STATE, buf, true);
}

void setState(BarrierState next) {
  barrierState = next;
  stateSince = millis();
  publishBarrierState(WIFI_STATE_NAMES[next]);
}

// --- Callback MQTT : ne bloque PAS, fixe seulement l'état cible ---
void callback(char* topic, byte* payload, unsigned int length) {
  if (strcmp(topic, TOPIC_BARRIER_CMD) != 0) return;

  char msg[512];
  if (length >= sizeof(msg)) length = sizeof(msg) - 1;
  memcpy(msg, payload, length);
  msg[length] = '\0';

  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, msg);
  if (err) {
    publishBarrierState("idle", "invalid_json");
    return;
  }

  const char* gate = doc["gate"] | "entry";
  currentGate = gate;

  const char* action = doc["action"] | "none";
  if (strcmp(action, "open") == 0) {
    setState(OPENING);
  } else if (strcmp(action, "close") == 0) {
    setState(CLOSING);
  } else {
    publishBarrierState("idle", "unknown_action");
  }
}

// --- Wi-Fi non bloquant : relance périodique, reprise automatique ---
void ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  if (millis() - lastWifiAttempt < WIFI_RETRY_MS) return;
  lastWifiAttempt = millis();
  Serial.println("[wifi] connexion...");
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID_ENV, WIFI_PASS_ENV);
}

// --- MQTT non bloquant avec backoff + Last Will ---
void ensureMQTT() {
  if (mqttClient.connected()) return;
  if (millis() - lastMqttAttempt < MQTT_RETRY_MS) return;
  lastMqttAttempt = millis();

  char clientId[40];
  snprintf(clientId, sizeof(clientId), "smpark-esp32-%04X", (uint16_t)(ESP.getEfuseMac() & 0xFFFF));

  // Last Will : publié par le broker si le device se déconnecte sans prévenir.
  if (mqttClient.connect(clientId, MQTT_USER_ENV, MQTT_PASS_ENV,
                         TOPIC_BARRIER_STATE, 1, true,
                         "{\"state\":\"offline\"}")) {
    mqttClient.subscribe(TOPIC_BARRIER_CMD);
    Serial.println("[mqtt] connecté, état online publié");
    publishBarrierState("online");
  } else {
    Serial.printf("[mqtt] échec connexion (rc=%d), retry dans %lums\n",
                  mqttClient.state(), MQTT_RETRY_MS);
  }
}

// --- Avancement de la séquence barrière, sans delay() ---
void updateBarrier() {
  unsigned long elapsed = millis() - stateSince;
  switch (barrierState) {
    case OPENING:
      if (elapsed >= OPENING_DURATION_MS) setState(OPEN);
      break;
    case OPEN:
      if (elapsed >= OPEN_HOLD_MS) setState(CLOSING);
      break;
    case CLOSING:
      if (elapsed >= CLOSING_DURATION_MS) setState(CLOSED);
      break;
    case IDLE:
    case CLOSED:
    default:
      break;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED_STATUS, OUTPUT);
  pinMode(PIN_SERVO_ENTRY, OUTPUT);
  pinMode(PIN_SERVO_EXIT, OUTPUT);

  WiFi.mode(WIFI_STA);
  // Premier essai immédiat.
  lastWifiAttempt = millis() - WIFI_RETRY_MS;

  mqttClient.setServer(MQTT_HOST_ENV, MQTT_PORT_ENV);
  mqttClient.setCallback(callback);
}

void loop() {
  ensureWiFi();

  if (WiFi.status() == WL_CONNECTED) {
    ensureMQTT();
    mqttClient.loop();
  }

  updateBarrier();

  if (millis() - lastStatePublish > STATE_HEARTBEAT_MS) {
    lastStatePublish = millis();
    publishBarrierState(WIFI_STATE_NAMES[barrierState]);
  }
}
