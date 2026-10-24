// =========================================================================
// SM-Park - Configuration centrale du firmware ESP32
// -------------------------------------------------------------------------
// Les valeurs sensibles (Wi-Fi, MQTT) proviennent de `secrets.ini`, injectées
// en `-D` par PlatformIO (voir `firmware/esp32/secrets.ini.example`).
//
// ATTENTION : PlatformIO ignore SILENCIEUSEMENT un `extra_configs`
// introuvable (dans `ProjectConfig.read`, `glob.glob()` ne renvoie rien -> ni
// erreur, ni avertissement). Si `secrets.ini` est absent, ce fichier se
// compile avec les sentinelles `CHANGE_ME_*` et le firmware REFUSE alors de
// démarrer la connexion (voir `smpark::configLogStatus()`).
//
// CE FICHIER EST LE SEUL ENDROIT À MODIFIER pour :
//   - les identifiants de repli ;
//   - le pinout matériel (à CONFIRMER avec le câblage réel) ;
//   - les topics MQTT (contrat : docs/mqtt-contract.md §C).
// =========================================================================
#pragma once

#include <Arduino.h>
#include <string.h>

// -------------------------------------------------------------------------
// Topics MQTT — contrat : docs/mqtt-contract.md §C
// Surchargeables en build (`-DTOPIC_...="..."` dans secrets.ini).
// -------------------------------------------------------------------------
#ifndef TOPIC_PARKING_STATE
#define TOPIC_PARKING_STATE "parking/state"
#endif
#ifndef TOPIC_PARKING_EVENTS
#define TOPIC_PARKING_EVENTS "parking/events"
#endif
#ifndef TOPIC_BARRIER_COMMAND
#define TOPIC_BARRIER_COMMAND "parking/barrier/command"
#endif
#ifndef TOPIC_BARRIER_STATE
#define TOPIC_BARRIER_STATE "barrier/state"
#endif

// -------------------------------------------------------------------------
// Identifiants Wi-Fi / MQTT — fournis par secrets.ini
// Les valeurs ci-dessous ne sont que des SENTINELLES : si elles subsistent
// au boot, c'est que `secrets.ini` n'a pas été lu (voir §F-13 de l'audit).
// -------------------------------------------------------------------------
#ifndef WIFI_SSID
#define WIFI_SSID "CHANGE_ME_WIFI_SSID"
#endif
#ifndef WIFI_PASSWORD
#define WIFI_PASSWORD "CHANGE_ME_WIFI_PASSWORD"
#endif
#ifndef MQTT_HOST
#define MQTT_HOST "CHANGE_ME_MQTT_HOST"
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
#ifndef MQTT_KEEPALIVE
#define MQTT_KEEPALIVE 60
#endif

// -------------------------------------------------------------------------
// Pinout matériel
// -------------------------------------------------------------------------
// ⚠️  À CONFIRMER AVEC LE CÂBLAGE RÉEL.
//     Regroupés ici (et uniquement ici) pour être ajustés en un seul endroit.
//     Rappel : GPIO 12/13/14 sont des broches de STRAPPING (niveau de boot) :
//     un servo qui tire la broche au LOW peut empêcher l'ESP32 de démarrer.
//     GPIO 34/35 sont des ENTRÉES UNIQUEMENT (IR) et n'ont pas de
//     pull-up/pull-down interne : c'est pourquoi `INPUT_PULLUP` est utilisé.
// -------------------------------------------------------------------------
#define PIN_LED_STATUS 2

#define PIN_SERVO_ENTRY 13
#define PIN_SERVO_EXIT 12

#define PIN_TRIG_1 26
#define PIN_ECHO_1 25
#define PIN_TRIG_2 33
#define PIN_ECHO_2 32
#define PIN_TRIG_3 27
#define PIN_ECHO_3 14

#define PIN_IR_ENTRY 34
#define PIN_IR_EXIT 35

// -------------------------------------------------------------------------
// Drapeaux fonctionnels (injectionnés via `build_src_flags`)
//   SMPARK_ENABLE_SENSORS : 1 = lecture HC-SR04 + IR, publication
//                            `parking/state` et `parking/events`
//                         0 = mode « sans matériel » (démo B+D seule)
//   SMPARK_ENABLE_SERVOS  : 1 = pilotage réel des servos
//                         0 = simulation logicielle (états uniquement)
// -------------------------------------------------------------------------
#ifndef SMPARK_ENABLE_SENSORS
#define SMPARK_ENABLE_SENSORS 1
#endif
#ifndef SMPARK_ENABLE_SERVOS
#define SMPARK_ENABLE_SERVOS 1
#endif

// -------------------------------------------------------------------------
// Temporisations (ms)
// -------------------------------------------------------------------------
#define OPENING_DURATION_MS 600
#define OPEN_HOLD_MS 2500
#define CLOSING_DURATION_MS 600
#define WIFI_RETRY_MS 5000
#define MQTT_RETRY_MS 5000
#define HEARTBEAT_MS 5000
#define SLOT_POLL_MS 300
#define IR_DEBOUNCE_MS 250
#define ULTRASONIC_ECHO_TIMEOUT_US 30000

// -------------------------------------------------------------------------
// Seuils & géométrie
// -------------------------------------------------------------------------
#define OCCUPIED_DISTANCE_CM 30.0f
// Hystérésis : une place n'est libérée qu'au-delà de ce seuil, ce qui évite
// le clignotement de l'occupation quand la mesure oscille autour du seuil.
#define OCCUPIED_HYSTERESIS_CM 10.0f
#define US_SAMPLES 5
#define SERVO_CLOSED_ANGLE 0
#define SERVO_OPEN_ANGLE 90
#define PARKING_SLOT_COUNT 3

// -------------------------------------------------------------------------
// Helpers
// -------------------------------------------------------------------------
namespace smpark {

/** Vrai si la valeur est une sentinelle « non configurée ». */
inline bool isPlaceholder(const char* value) {
  return value == nullptr || value[0] == '\0' ||
         strncmp(value, "CHANGE_ME", 9) == 0;
}

/** Vrai si Wi-Fi + MQTT sont réellement configurés. */
inline bool configIsValid() {
  return !isPlaceholder(WIFI_SSID) && !isPlaceholder(WIFI_PASSWORD) &&
         !isPlaceholder(MQTT_HOST) && !isPlaceholder(MQTT_PASSWORD);
}

/**
 * Affiche l'état de la configuration au boot.
 * Si une sentinelle subsiste, on explique clairement quoi faire : sans cela,
 * un `git clone` + `pio run` produit un firmware qui ne se connecte jamais,
 * sans message d'erreur explicite.
 */
inline void configLogStatus() {
  if (configIsValid()) {
    Serial.println("[config] Wi-Fi + MQTT configures : OK");
    Serial.printf("[config] broker MQTT : %s:%d\n", MQTT_HOST, MQTT_PORT);
    return;
  }
  Serial.println("[config] ==============================================");
  Serial.println("[config] CONFIGURATION INCOMPLETE");
  if (isPlaceholder(WIFI_SSID) || isPlaceholder(WIFI_PASSWORD)) {
    Serial.println("[config]   - WIFI_SSID / WIFI_PASSWORD non definis");
  }
  if (isPlaceholder(MQTT_HOST)) {
    Serial.println("[config]   - MQTT_HOST non defini (IP LAN du PC qui "
                   "heberge le broker)");
  }
  if (isPlaceholder(MQTT_PASSWORD)) {
    Serial.println("[config]   - MQTT_PASSWORD non defini");
  }
  Serial.println("[config] Correctif :");
  Serial.println("[config]   cp firmware/esp32/secrets.ini.example "
                 "firmware/esp32/secrets.ini");
  Serial.println("[config]   puis renseigner les valeurs et recompiler.");
  Serial.println("[config] ==============================================");
}

}  // namespace smpark
