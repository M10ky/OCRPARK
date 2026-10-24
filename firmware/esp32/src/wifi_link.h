#pragma once

#include <Arduino.h>

// =========================================================================
// SM-Park - Couche Wi-Fi
// -------------------------------------------------------------------------
// Connexion NON BLOQUANTE : `WiFi.begin()` est asynchrone, on surveille
// `WiFi.status()` dans la boucle. Aucun `delay()` de 10 s comme le font
// beaucoup d'exemples.
// =========================================================================
namespace smpark {

/** Démarre la connexion Wi-Fi (mode station). */
void wifiBegin();

/** Relance une tentative de connexion si nécessaire. */
void wifiLoop();

/** Le Wi-Fi est-il associé ? */
bool wifiConnected();

/** Adresse IP locale (vide si non connecté). */
String wifiIp();

}  // namespace smpark
