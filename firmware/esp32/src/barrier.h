#pragma once

#include <Arduino.h>

// =========================================================================
// SM-Park - Machine à états de la barrière
// -------------------------------------------------------------------------
// Un état **par porte** (`entry` / `exit`) : c'était la faille F-08 de
// l'ancien firmware, où une seule variable globale `currentGate` pouvait
// basculer le servo d'entry en plein cycle suite à une commande `exit`.
//
// Séquence : idle -> opening -> open -> closing -> closed
// =========================================================================
namespace smpark {

enum class BarrierPhase { Idle, Opening, Open, Closing, Closed };

/** Nom conforme au contrat MQTT (`opening`, `open`, ...). */
const char* barrierPhaseName(BarrierPhase phase);

/** Une porte et son état courant. */
struct BarrierGate {
  BarrierPhase phase = BarrierPhase::Idle;
  unsigned long phaseSince = 0;
  /** `correlation_id` de la commande en cours (à renvoyer dans l'ACK). */
  String correlationId;
  /** Dernière raison (invalide, timeout, ...). */
  String reason;
};

/**
 * Contrôleur des deux barrières.
 *
 * - `request()` valide la commande et démarre la séquence.
 * - `update()` fait avancer les séquences (non bloquant, basé sur millis()).
 * - Les transitions appellent `smpark::hw::setBarrier()` (servo réel).
 */
class BarrierController {
 public:
  void begin();

  /**
   * Demande d'action sur une porte.
   * @return true si la commande est valide et la séquence démarrée,
   *         false si elle est rejetée (action/gate/correlation_id invalides).
   */
  bool request(const char* gate, const char* action, const String& correlationId);

  /**
   * Fait avancer les séquences en cours.
   * @return true si la phase de la porte active a changé pendant l'appel
   *         (à utiliser pour déclencher une publication MQTT).
   */
  bool update();

  /**
   * Récupère (et efface) le `correlation_id` en attente d'ACK.
   * L'ACK doit être le PREMIER `barrier/state` portant cet identifiant.
   */
  String takeCorrelationId(const char* gate);

  /** État d'une porte ("entry" / "exit"). */
  const BarrierGate& state(const char* gate) const;

  /** Porte sur laquelle la dernière commande a porté ("entry" par défaut). */
  const char* activeGate() const;

  /** Dernière porte active (pour la publication MQTT). */
  const BarrierGate& activeState() const;

 private:
  BarrierGate& mutableGate(const char* gate);
  void enterPhase(BarrierGate& gateState, BarrierPhase phase, const char* reason);

  BarrierGate g_entry;
  BarrierGate g_exit;
  const char* g_activeGate = "entry";
};

}  // namespace smpark
