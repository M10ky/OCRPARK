#pragma once

#include <Arduino.h>

// =========================================================================
// SM-Park - Horodatage
// -------------------------------------------------------------------------
// Le contrat MQTT (`docs/mqtt-contract.md` §D.2) attend un `ts` ISO-8601 UTC
// pour `parking/events`. L'ESP32 n'a pas d'horloge RTC : l'heure est donc
// synchronisée par NTP dès que le Wi-Fi est disponible.
//
// Tant que l'heure n'est pas synchronisée, `nowIso8601()` renvoie une chaîne
// vide : le champ `ts` est alors **omis** (il est optionnel dans le contrat),
// et `uptime_ms` reste la référence temporelle.
namespace smpark {

/** Lance la synchronisation NTP (idempotent). */
void timeBegin();

/** Vrai si l'heure système est synchronisée. */
bool timeSynced();

/** Horodatage ISO-8601 UTC ("2026-01-01T00:00:00Z"), chaîne vide si non sync. */
String nowIso8601();

}  // namespace smpark
