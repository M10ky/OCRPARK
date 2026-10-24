#pragma once

#include <Arduino.h>

// =========================================================================
// SM-Park - Couche MQTT
// -------------------------------------------------------------------------
// Règle structurante (F-04) : le callback PubSubClient ne fait QUE parser et
// MEMORISER la commande. Il ne publie JAMAIS, ne fait JAMAIS de delay() et ne
// touche JAMAIS au matériel : tout est exécuté depuis `loop()`.
//
// C'est indispensable : `publish()` depuis le callback peut écrire des
// fragments de paquet dans le buffer réseau et produire des trames MQTT
// corrompues (symptôme : "ça marche 1 fois sur 3").
// =========================================================================
namespace smpark {

/** Commande de barrière reçue sur `parking/barrier/command`. */
struct BarrierCommand {
  /** false => commande rejetée (JSON illisible) : à signaler sans ACK. */
  bool valid = false;
  /** Motif du rejet (JSON illisible). */
  String reason;
  String gate;
  String action;
  String correlationId;
};

/** Configure le client MQTT (serveur, callback, keepalive). */
void mqttBegin();

/** Connexion / reconnexion / lecture réseau. Non bloquant. */
void mqttLoop();

/** Le client est-il connecté au broker ? */
bool mqttConnected();

/**
 * Publie l'état de la barrière sur `barrier/state` (retain=true).
 * @param correlationId vide => aucun ACK (heartbeat ou erreur).
 */
void mqttPublishBarrierState(const char* gate, const char* state, const char* reason,
                             const String& correlationId);

/** Publie l'occupation des places sur `parking/state` (retain=true). */
void mqttPublishParkingState(const bool occupied[], int count);

/** Publie un événement d'entrée/sortie sur `parking/events` (retain=false). */
void mqttPublishParkingEvent(const char* type, const char* gate);

/** Retire une commande de la file (appelée par `loop()`). */
bool mqttTakeCommand(BarrierCommand& command);

/** Nombre de commandes en attente. */
uint8_t mqttPendingCommands();

}  // namespace smpark
