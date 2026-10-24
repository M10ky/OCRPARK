#include "mqtt_link.h"

#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>

#include "config.h"
#include "time_util.h"

namespace smpark {
namespace {

WiFiClient g_wifiClient;
PubSubClient g_mqtt(g_wifiClient);

constexpr uint8_t kQueueSize = 4;
BarrierCommand g_queue[kQueueSize];
uint8_t g_queueHead = 0;
uint8_t g_queueTail = 0;

unsigned long g_lastMqttAttempt = 0;

void pushCommand(const BarrierCommand& command) {
  uint8_t next = (g_queueTail + 1) % kQueueSize;
  if (next == g_queueHead) {
    // File pleine : on écrase la plus ancienne (une commande périmée ne
    // sert plus à rien, et le broker réémet en QoS 1 si nécessaire).
    g_queueHead = (g_queueHead + 1) % kQueueSize;
  }
  g_queue[g_queueTail] = command;
  g_queueTail = next;
}

/**
 * Callback MQTT : PARSE ET MEMORISE UNIQUEMENT.
 * Aucun publish, aucun delay, aucun accès matériel ici.
 */
void onMessage(char* topic, byte* payload, unsigned int length) {
  if (strcmp(topic, TOPIC_BARRIER_COMMAND) != 0) return;

  BarrierCommand command;

  char buffer[512];
  if (length >= sizeof(buffer)) length = sizeof(buffer) - 1;
  memcpy(buffer, payload, length);
  buffer[length] = '\0';

  JsonDocument doc;
  if (deserializeJson(doc, buffer)) {
    command.valid = false;
    command.reason = "invalid_json";
    pushCommand(command);
    return;
  }

  command.valid = true;
  command.gate = String(doc["gate"] | "");
  command.action = String(doc["action"] | "");
  command.correlationId = String(doc["correlation_id"] | "");
  pushCommand(command);
}

}  // namespace

void mqttBegin() {
  g_queueHead = 0;
  g_queueTail = 0;
  g_lastMqttAttempt = 0;

  g_mqtt.setServer(MQTT_HOST, MQTT_PORT);
  g_mqtt.setCallback(onMessage);
  g_mqtt.setBufferSize(512);
  g_mqtt.setKeepAlive(MQTT_KEEPALIVE);
}

bool mqttConnected() {
  return g_mqtt.connected();
}

void mqttLoop() {
  if (!smpark::configIsValid()) return;

  if (!g_mqtt.connected()) {
    if (millis() - g_lastMqttAttempt < MQTT_RETRY_MS) return;
    g_lastMqttAttempt = millis();

    char clientId[40];
    snprintf(clientId, sizeof(clientId), "smpark-esp32-%04X%08X",
             (uint16_t)(ESP.getEfuseMac() & 0xFFFF), (uint32_t)ESP.getEfuseMac());

    // Last Will : "offline" retenu par le broker si l'ESP32 disparaît.
    if (g_mqtt.connect(clientId, MQTT_USER, MQTT_PASSWORD, TOPIC_BARRIER_STATE, 1, true,
                        "{\"state\":\"offline\"}")) {
      g_mqtt.subscribe(TOPIC_BARRIER_COMMAND, 1);
      Serial.println("[mqtt] connecte");
    } else {
      Serial.printf("[mqtt] echec rc=%d\n", g_mqtt.state());
    }
    return;
  }

  g_mqtt.loop();
}

void mqttPublishBarrierState(const char* gate, const char* state, const char* reason,
                             const String& correlationId) {
  if (!g_mqtt.connected()) return;

  JsonDocument doc;
  doc["state"] = state;
  doc["gate"] = gate;
  if (reason != nullptr && reason[0] != '\0') doc["reason"] = reason;
  // ⚠️ Un ACK ne doit être envoyé QUE pour une commande acceptée : si le
  // correlation_id est vide, le backend ne doit pas le considérer acquitté.
  if (correlationId.length() > 0) doc["correlation_id"] = correlationId;
  doc["uptime_ms"] = millis();
  char buffer[256];
  size_t size = serializeJson(doc, buffer);
  if (size == 0 || size >= sizeof(buffer)) {
    Serial.println("[mqtt] publication barrier/state trop grande");
    return;
  }
  if (!g_mqtt.publish(TOPIC_BARRIER_STATE, buffer, true)) {
    Serial.println("[mqtt] echec publication barrier/state");
  }
}

void mqttPublishParkingState(const bool occupied[], int count) {
  if (!g_mqtt.connected()) return;

  JsonDocument doc;
  JsonArray slots = doc["slots"].to<JsonArray>();
  for (int i = 0; i < count; i++) {
    JsonObject slot = slots.add<JsonObject>();
    slot["id"] = i + 1;
    slot["occupied"] = occupied[i];
  }
  doc["ts"] = nowIso8601();

  char buffer[256];
  size_t size = serializeJson(doc, buffer);
  if (size == 0 || size >= sizeof(buffer)) {
    Serial.println("[mqtt] publication parking/state trop grande");
    return;
  }
  if (!g_mqtt.publish(TOPIC_PARKING_STATE, buffer, true)) {
    Serial.println("[mqtt] echec publication parking/state");
  }
}

void mqttPublishParkingEvent(const char* type, const char* gate) {
  if (!g_mqtt.connected()) return;

  JsonDocument doc;
  doc["type"] = type;  // "entry" | "exit"
  doc["gate"] = gate;  // "entry" | "exit"
  const String ts = nowIso8601();
  if (ts.length() > 0) doc["ts"] = ts;

  char buffer[192];
  size_t size = serializeJson(doc, buffer);
  if (size == 0 || size >= sizeof(buffer)) {
    Serial.println("[mqtt] publication parking/events trop grande");
    return;
  }
  if (!g_mqtt.publish(TOPIC_PARKING_EVENTS, buffer, false)) {
    Serial.println("[mqtt] echec publication parking/events");
  }
}

bool mqttTakeCommand(BarrierCommand& command) {
  if (g_queueHead == g_queueTail) return false;
  command = g_queue[g_queueHead];
  g_queueHead = (g_queueHead + 1) % kQueueSize;
  return true;
}

uint8_t mqttPendingCommands() {
  return (uint8_t)((g_queueTail - g_queueHead + kQueueSize) % kQueueSize);
}

}  // namespace smpark
