#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>

// =========================================================================
// SM-Park - Firmware ESP32 complet
// - 2 servos (barrières entry/exit)
// - 3 HC-SR04 (places)
// - 2 IR (entry/exit)
// - MQTT non bloquant (millis), LWT offline
// - Secrets via build_flags / secrets.ini
// =========================================================================

// --- Pins ---
#define PIN_SERVO_ENTRY 13
#define PIN_SERVO_EXIT  12
#define PIN_LED_STATUS  2

#define PIN_TRIG_1 26
#define PIN_ECHO_1 25
#define PIN_TRIG_2 33
#define PIN_ECHO_2 32
#define PIN_TRIG_3 27
#define PIN_ECHO_3 14

#define PIN_IR_ENTRY 34
#define PIN_IR_EXIT  35

// --- Secrets (fallback uniquement ; vrais valeurs dans secrets.ini) ---
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
#define MQTT_PASSWORD "CHANGE_ME_MQTT_PASSWORD"
#endif

const char* WIFI_SSID_ENV = WIFI_SSID;
const char* WIFI_PASS_ENV = WIFI_PASSWORD;
const char* MQTT_HOST_ENV = MQTT_HOST;
const int   MQTT_PORT_ENV = MQTT_PORT;
const char* MQTT_USER_ENV = MQTT_USER;
const char* MQTT_PASS_ENV = MQTT_PASSWORD;

// --- Topics (contrat MQTT) ---
const char* TOPIC_BARRIER_CMD   = "parking/barrier/command";
const char* TOPIC_BARRIER_STATE = "barrier/state";
const char* TOPIC_PARKING_STATE = "parking/state";
const char* TOPIC_PARKING_EVENTS = "parking/events";

// --- Timing ---
const unsigned long OPENING_DURATION_MS = 600;
const unsigned long OPEN_HOLD_MS        = 2500;
const unsigned long CLOSING_DURATION_MS = 600;
const unsigned long WIFI_RETRY_MS       = 5000;
const unsigned long MQTT_RETRY_MS       = 5000;
const unsigned long HEARTBEAT_MS        = 5000;
const unsigned long SLOT_POLL_MS        = 300;
const unsigned long IR_DEBOUNCE_MS      = 250;

// HC-SR04 : distance < seuil => occupé
const float OCCUPIED_DISTANCE_CM = 30.0;
const int   US_SAMPLES           = 5;

// Angles servo (à ajuster selon mécanique)
const int SERVO_CLOSED_ANGLE = 0;
const int SERVO_OPEN_ANGLE   = 90;

enum BarrierPhase { IDLE, OPENING, OPEN, CLOSING, CLOSED };

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

Servo servoEntry;
Servo servoExit;

BarrierPhase barrierPhase = IDLE;
unsigned long phaseSince = 0;
String currentGate = "entry";
String pendingCorrelationId = "";

unsigned long lastWifiAttempt = 0;
unsigned long lastMqttAttempt = 0;
unsigned long lastHeartbeat = 0;
unsigned long lastSlotPoll = 0;

bool slotOccupied[3] = {false, false, false};
bool lastIrEntry = false;
bool lastIrExit = false;
unsigned long lastIrEntryChange = 0;
unsigned long lastIrExitChange = 0;

const char* phaseName(BarrierPhase p) {
  switch (p) {
    case OPENING: return "opening";
    case OPEN:    return "open";
    case CLOSING: return "closing";
    case CLOSED:  return "closed";
    default:      return "idle";
  }
}

// -------------------------------------------------------------------------
// HC-SR04
// -------------------------------------------------------------------------
float readDistanceCm(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  long duration = pulseIn(echoPin, HIGH, 30000); // timeout 30ms
  if (duration == 0) return 999.0; // pas d'écho
  return duration * 0.0343f / 2.0f;
}

float readDistanceMedianCm(int trigPin, int echoPin) {
  float values[US_SAMPLES];
  for (int i = 0; i < US_SAMPLES; i++) {
    values[i] = readDistanceCm(trigPin, echoPin);
    delay(5); // court, hors callback MQTT
  }
  // tri simple
  for (int i = 0; i < US_SAMPLES - 1; i++) {
    for (int j = i + 1; j < US_SAMPLES; j++) {
      if (values[j] < values[i]) {
        float t = values[i];
        values[i] = values[j];
        values[j] = t;
      }
    }
  }
  return values[US_SAMPLES / 2];
}

bool measureOccupied(int trigPin, int echoPin) {
  float d = readDistanceMedianCm(trigPin, echoPin);
  return d < OCCUPIED_DISTANCE_CM;
}

// -------------------------------------------------------------------------
// MQTT publish helpers
// -------------------------------------------------------------------------
void publishBarrierState(const char* state, const char* reason = nullptr) {
  if (!mqttClient.connected()) return;

  JsonDocument doc;
  doc["state"] = state;
  doc["gate"] = currentGate;
  if (reason) doc["reason"] = reason;
  if (pendingCorrelationId.length() > 0) {
    doc["correlation_id"] = pendingCorrelationId;
    pendingCorrelationId = "";
  }
  doc["uptime_ms"] = millis();

  char buf[256];
  serializeJson(doc, buf);
  mqttClient.publish(TOPIC_BARRIER_STATE, buf, true); // retain
}

void publishParkingState() {
  if (!mqttClient.connected()) return;

  JsonDocument doc;
  JsonArray slots = doc["slots"].to<JsonArray>();
  for (int i = 0; i < 3; i++) {
    JsonObject s = slots.add<JsonObject>();
    s["id"] = i + 1;
    s["occupied"] = slotOccupied[i];
  }
  doc["ts"] = millis();

  char buf[256];
  serializeJson(doc, buf);
  mqttClient.publish(TOPIC_PARKING_STATE, buf, true);
}

void publishParkingEvent(const char* type, const char* gate) {
  if (!mqttClient.connected()) return;

  JsonDocument doc;
  doc["type"] = type;   // "entry" | "exit"
  doc["gate"] = gate;   // "entry" | "exit"
  doc["ts"] = millis();

  char buf[192];
  serializeJson(doc, buf);
  mqttClient.publish(TOPIC_PARKING_EVENTS, buf, false);
}

// -------------------------------------------------------------------------
// Servos
// -------------------------------------------------------------------------
void writeGateServo(const String& gate, int angle) {
  if (gate == "exit") {
    servoExit.write(angle);
  } else {
    servoEntry.write(angle);
  }
}

void setPhase(BarrierPhase next) {
  barrierPhase = next;
  phaseSince = millis();

  if (next == OPENING || next == OPEN) {
    writeGateServo(currentGate, SERVO_OPEN_ANGLE);
  } else if (next == CLOSING || next == CLOSED || next == IDLE) {
    writeGateServo(currentGate, SERVO_CLOSED_ANGLE);
  }

  publishBarrierState(phaseName(next));
}

// -------------------------------------------------------------------------
// MQTT callback : ne bloque pas
// -------------------------------------------------------------------------
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  if (strcmp(topic, TOPIC_BARRIER_CMD) != 0) return;

  char msg[512];
  if (length >= sizeof(msg)) length = sizeof(msg) - 1;
  memcpy(msg, payload, length);
  msg[length] = '\0';

  JsonDocument doc;
  if (deserializeJson(doc, msg)) {
    publishBarrierState("idle", "invalid_json");
    return;
  }

  currentGate = String(doc["gate"] | "entry");
  pendingCorrelationId = String(doc["correlation_id"] | "");

  const char* action = doc["action"] | "none";
  if (strcmp(action, "open") == 0) {
    setPhase(OPENING);
  } else if (strcmp(action, "close") == 0) {
    setPhase(CLOSING);
  } else {
    publishBarrierState("idle", "unknown_action");
  }
}

// -------------------------------------------------------------------------
// Wi-Fi / MQTT non bloquants
// -------------------------------------------------------------------------
void ensureWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  if (millis() - lastWifiAttempt < WIFI_RETRY_MS) return;
  lastWifiAttempt = millis();
  Serial.println("[wifi] connexion...");
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID_ENV, WIFI_PASS_ENV);
}

void ensureMQTT() {
  if (mqttClient.connected()) return;
  if (millis() - lastMqttAttempt < MQTT_RETRY_MS) return;
  lastMqttAttempt = millis();

  char clientId[40];
  snprintf(clientId, sizeof(clientId), "smpark-esp32-%04X",
           (uint16_t)(ESP.getEfuseMac() & 0xFFFF));

  // LWT offline
  if (mqttClient.connect(clientId, MQTT_USER_ENV, MQTT_PASS_ENV,
                         TOPIC_BARRIER_STATE, 1, true,
                         "{\"state\":\"offline\"}")) {
    mqttClient.subscribe(TOPIC_BARRIER_CMD);
    Serial.println("[mqtt] connecté");
    publishBarrierState("online");
    publishParkingState();
  } else {
    Serial.printf("[mqtt] échec rc=%d\n", mqttClient.state());
  }
}

// -------------------------------------------------------------------------
// Séquence barrière
// -------------------------------------------------------------------------
void updateBarrier() {
  unsigned long elapsed = millis() - phaseSince;
  switch (barrierPhase) {
    case OPENING:
      if (elapsed >= OPENING_DURATION_MS) setPhase(OPEN);
      break;
    case OPEN:
      // auto-fermeture après maintien
      if (elapsed >= OPEN_HOLD_MS) setPhase(CLOSING);
      break;
    case CLOSING:
      if (elapsed >= CLOSING_DURATION_MS) setPhase(CLOSED);
      break;
    default:
      break;
  }
}

// -------------------------------------------------------------------------
// Capteurs
// -------------------------------------------------------------------------
void updateSlots() {
  if (millis() - lastSlotPoll < SLOT_POLL_MS) return;
  lastSlotPoll = millis();

  bool s1 = measureOccupied(PIN_TRIG_1, PIN_ECHO_1);
  bool s2 = measureOccupied(PIN_TRIG_2, PIN_ECHO_2);
  bool s3 = measureOccupied(PIN_TRIG_3, PIN_ECHO_3);

  bool changed = (s1 != slotOccupied[0]) || (s2 != slotOccupied[1]) || (s3 != slotOccupied[2]);
  slotOccupied[0] = s1;
  slotOccupied[1] = s2;
  slotOccupied[2] = s3;

  if (changed) {
    Serial.printf("[slots] 1=%d 2=%d 3=%d\n", s1, s2, s3);
    publishParkingState();
  }
}

void updateIR() {
  bool irEntry = digitalRead(PIN_IR_ENTRY) == LOW; // souvent actif bas ; inverser si besoin
  bool irExit  = digitalRead(PIN_IR_EXIT) == LOW;

  unsigned long now = millis();

  if (irEntry != lastIrEntry && (now - lastIrEntryChange) > IR_DEBOUNCE_MS) {
    lastIrEntry = irEntry;
    lastIrEntryChange = now;
    if (irEntry) {
      Serial.println("[ir] entry pulse");
      publishParkingEvent("entry", "entry");
    }
  }

  if (irExit != lastIrExit && (now - lastIrExitChange) > IR_DEBOUNCE_MS) {
    lastIrExit = irExit;
    lastIrExitChange = now;
    if (irExit) {
      Serial.println("[ir] exit pulse");
      publishParkingEvent("exit", "exit");
    }
  }
}

// -------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("SM-Park ESP32 boot");

  pinMode(PIN_LED_STATUS, OUTPUT);
  digitalWrite(PIN_LED_STATUS, LOW);

  pinMode(PIN_TRIG_1, OUTPUT);
  pinMode(PIN_ECHO_1, INPUT);
  pinMode(PIN_TRIG_2, OUTPUT);
  pinMode(PIN_ECHO_2, INPUT);
  pinMode(PIN_TRIG_3, OUTPUT);
  pinMode(PIN_ECHO_3, INPUT);

  pinMode(PIN_IR_ENTRY, INPUT);
  pinMode(PIN_IR_EXIT, INPUT);

  servoEntry.attach(PIN_SERVO_ENTRY);
  servoExit.attach(PIN_SERVO_EXIT);
  servoEntry.write(SERVO_CLOSED_ANGLE);
  servoExit.write(SERVO_CLOSED_ANGLE);

  WiFi.mode(WIFI_STA);
  lastWifiAttempt = millis() - WIFI_RETRY_MS;

  mqttClient.setServer(MQTT_HOST_ENV, MQTT_PORT_ENV);
  mqttClient.setCallback(mqttCallback);
  mqttClient.setBufferSize(512);
}

void loop() {
  ensureWiFi();

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(PIN_LED_STATUS, HIGH);
    ensureMQTT();
    mqttClient.loop();
  } else {
    digitalWrite(PIN_LED_STATUS, (millis() / 300) % 2);
  }

  updateBarrier();
  updateSlots();
  updateIR();

  if (millis() - lastHeartbeat > HEARTBEAT_MS) {
    lastHeartbeat = millis();
    publishBarrierState(phaseName(barrierPhase));
    publishParkingState();
  }
}