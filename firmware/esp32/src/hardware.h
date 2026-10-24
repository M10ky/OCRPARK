#pragma once

#include <Arduino.h>

// =========================================================================
// SM-Park - Couche matérielle ESP32
// -------------------------------------------------------------------------
// Isole TOUT le matériel réel (HC-SR04, barrettes IR, servos) derrière une
// interface simple. Aucun `publish()`, aucun `delay()` bloquant de longue
// durée : les mesures se font par machine à états, une broche à la fois.
//
// ⚠️ Le pinout est centralisé dans `config.h` (à confirmer avec le câblage
// réel). Les broches 12/13/14 sont des broches de STRAPPING : voir l'avertis-
// sement de `config.h`.
// =========================================================================
namespace smpark::hw {

/** Configure les broches et attache les servos. */
void begin();

/**
 * Avance les machines à états matérielles.
 * À appeler dans `loop()` : ne bloque pas (hors `delayMicroseconds` de 10 µs
 * pour le trigger HC-SR04).
 */
void poll();

/** Distance mesurée (cm) pour un slot. Valeur négative si jamais mesuré. */
float lastDistanceCm(int slotIndex);

/** Place occupée d'après la dernière mesure (seuil + hystérésis). */
bool slotOccupied(int slotIndex);

/** Force l'état "occupée/libre" (utile pour les tests sans matériel). */
void setSlotOccupied(int slotIndex, bool occupied);

/** Véhicule présent sur la porte indiquée ("entry" / "exit") ? */
bool vehiclePresent(const char* gate);

/** Pilote le servo de la porte (angle ouvert / fermé). */
void setBarrier(const char* gate, bool open);

/** Angle actuellement appliqué à une porte (-1 si porte inconnue). */
int barrierAngle(const char* gate);

/**
 * Angle appliqué à la porte au moment de la dernière transition (utile pour
 * detecting un servo réellement bloqué).
 */
bool barrierMoved(const char* gate);

}  // namespace smpark::hw
