#pragma once

// =========================================================================
// SM-Park - Validation des commandes MQTT
// -------------------------------------------------------------------------
// Ce module ne dépend QUE de la libc (`<string.h>`) : il est donc
// compilable et testable sur la machine hôte (tests natifs), sans ESP32.
//
// Contrat de référence : docs/mqtt-contract.md §D.3 (commande) et §D.4
// (ACK). Règle fondamentale : une commande invalide ne doit JAMAIS
// déclencher un servo et ne doit JAMAIS produire un ACK (le backend doit voir
// un timeout, pas un faux succès).
// =========================================================================
namespace smpark {

/** Motif de rejet d'une commande (repris dans `barrier/state.reason`). */
enum class CommandReject {
  None,
  InvalidJson,          // payload illisible
  InvalidGate,          // gate != "entry" / "exit"
  UnknownAction,        // action != "open" / "close"
  MissingCorrelationId  // correlation_id absent ou vide
};

/** Libellé textuel du motif (valeur stable pour le contrat MQTT). */
const char* commandRejectReason(CommandReject reject);

/** `gate` valide ? ("entry" ou "exit") */
bool isValidGate(const char* gate);

/** `action` valide ? ("open" ou "close") */
bool isValidAction(const char* action);

/**
 * Valide une commande de barrière.
 * @return CommandReject::None si la commande est acceptable.
 */
CommandReject validateCommand(const char* gate, const char* action,
                               const char* correlationId);

}  // namespace smpark
