#include <Arduino.h>

#include "barrier.h"
#include "command.h"
#include "config.h"
#include "hardware.h"
#include "mqtt_link.h"
#include "time_util.h"
#include "wifi_link.h"

// =========================================================================
// SM-Park - Firmware ESP32 (orchestration)
// -------------------------------------------------------------------------
// Rôle de `main.cpp` : orchestrer. Toute la logique est dans les modules :
//   - `config.h`      : topics, pinout, temporisations, drapeaux
//   - `wifi_link`     : connexion Wi-Fi non bloquante
//   - `mqtt_link`     : client MQTT + file de commandes (callback = parse)
//   - `barrier`       : machine à états par porte (entry / exit)
//   - `hardware`      : HC-SR04, IR, servos (mesure non bloquante)
//
// Contrat MQTT (source de vérité) : docs/mqtt-contract.md
// Audit et plan de correction : docs/fiches-de-production/phase-C-firmware-audit.md
// =========================================================================

smpark::BarrierController g_barrier;

bool g_occupied[PARKING_SLOT_COUNT] = {false, false, false};

unsigned long g_lastHeartbeat = 0;
unsigned long g_lastSlotPublish = 0;
unsigned long g_lastSlotPoll = 0;
bool g_lastIrEntry = false;
bool g_lastIrExit = false;
/** Dernier `correlation_id` traité (garde anti-doublon QoS 1, F-10). */
String g_lastCorrelationId;

/** Publie l'état de la porte active (ACK si un correlation_id est fourni). */
void publishBarrierState(const char* reason, const String& correlationId) {
  const char* gate = g_barrier.activeGate();
  smpark::mqttPublishBarrierState(
      gate, smpark::barrierPhaseName(g_barrier.activeState().phase), reason, correlationId);
}

/** Publie l'occupation mesurée si elle a changé. */
void publishSlotsIfChanged() {
  bool changed = false;
  for (int i = 0; i < PARKING_SLOT_COUNT; i++) {
    bool occupied = smpark::hw::slotOccupied(i);
    if (occupied != g_occupied[i]) {
      g_occupied[i] = occupied;
      changed = true;
    }
  }
  if (changed) {
    Serial.printf("[slots] 1=%d 2=%d 3=%d\n", g_occupied[0], g_occupied[1], g_occupied[2]);
    smpark::mqttPublishParkingState(g_occupied, PARKING_SLOT_COUNT);
  }
}

/** Traite une commande venue de la file MQTT (exécutée depuis `loop()`). */
void processCommand(const smpark::BarrierCommand& command) {
  if (!command.valid) {
    // JSON illisible : on signale l'état SANS correlation_id => aucun ACK.
    Serial.printf("[cmd] rejetée (%s)\n", command.reason.c_str());
    smpark::mqttPublishBarrierState(g_barrier.activeGate(), "idle", command.reason.c_str(), "");
    return;
  }

  // Doublon QoS 1 : même correlation_id déjà traité => on ne déclenche PAS
  // une seconde ouverture, mais on ré-ACK pour que le backend ne time-out pas.
  if (command.correlationId == g_lastCorrelationId) {
    Serial.printf("[cmd] doublon ignoré (%s)\n", command.correlationId.c_str());
    publishBarrierState("duplicate", command.correlationId);
    return;
  }

  if (!g_barrier.request(command.gate.c_str(), command.action.c_str(),
                          command.correlationId)) {
    // Action / gate / correlation_id invalide : aucun servo déclenché, et
    // AUCUN ACK (le backend doit voir un timeout, pas un faux succès).
    const smpark::CommandReject reject = smpark::validateCommand(
        command.gate.c_str(), command.action.c_str(), command.correlationId.c_str());
    Serial.printf("[cmd] invalide gate=%s action=%s (%s)\n", command.gate.c_str(),
                  command.action.c_str(), smpark::commandRejectReason(reject));
    smpark::mqttPublishBarrierState(g_barrier.activeGate(), "idle",
                                     smpark::commandRejectReason(reject), "");
    return;
  }

  g_lastCorrelationId = command.correlationId;

  // ACK : le PREMIER barrier/state portant ce correlation_id.
  String correlationId = g_barrier.takeCorrelationId(command.gate.c_str());
  Serial.printf("[cmd] %s %s (%s)\n", command.action.c_str(), command.gate.c_str(),
                correlationId.c_str());
  publishBarrierState("command", correlationId);
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("SM-Park ESP32 boot");
  smpark::configLogStatus();

  pinMode(PIN_LED_STATUS, OUTPUT);
  digitalWrite(PIN_LED_STATUS, LOW);

  smpark::hw::begin();
  g_barrier.begin();
  smpark::wifiBegin();
  smpark::mqttBegin();

  g_lastIrEntry = smpark::hw::vehiclePresent("entry");
  g_lastIrExit = smpark::hw::vehiclePresent("exit");
}

void loop() {
  // 1. Réseau
  smpark::wifiLoop();
  if (smpark::wifiConnected()) {
    digitalWrite(PIN_LED_STATUS, HIGH);
    smpark::timeBegin();  // synchro NTP (horodatage ISO-8601 des événements)
  } else {
    digitalWrite(PIN_LED_STATUS, (millis() / 300) % 2);
  }
  smpark::mqttLoop();

  // 2. Commandes MQTT : exécutées ICI, jamais dans le callback.
  smpark::BarrierCommand command;
  while (smpark::mqttTakeCommand(command)) {
    processCommand(command);
  }

  // 3. Matériel (mesures non bloquantes)
  smpark::hw::poll();

  // 4. Séquences de barrière
  if (g_barrier.update()) {
    publishBarrierState("transition", "");
  }

  // 5. Occupation des places
  publishSlotsIfChanged();

  // 6. Événements entrée / sortie (IR)
  bool irEntry = smpark::hw::vehiclePresent("entry");
  bool irExit = smpark::hw::vehiclePresent("exit");
  if (irEntry != g_lastIrEntry) {
    g_lastIrEntry = irEntry;
    if (irEntry) {
      Serial.println("[ir] entree");
      smpark::mqttPublishParkingEvent("entry", "entry");
    }
  }
  if (irExit != g_lastIrExit) {
    g_lastIrExit = irExit;
    if (irExit) {
      Serial.println("[ir] sortie");
      smpark::mqttPublishParkingEvent("exit", "exit");
    }
  }

  // 7. Heartbeat
  if (millis() - g_lastHeartbeat > HEARTBEAT_MS) {
    g_lastHeartbeat = millis();
    publishBarrierState("heartbeat", "");
    smpark::mqttPublishParkingState(g_occupied, PARKING_SLOT_COUNT);
  }
}
