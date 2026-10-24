#include "time_util.h"

#include <time.h>

#include <esp_system.h>

namespace smpark {
namespace {

bool g_started = false;

}  // namespace

void timeBegin() {
  if (g_started) return;
  g_started = true;
  // Décalage 0 = UTC. Serveurs publics : pool.ntp.org, time.nist.gov.
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
}

bool timeSynced() {
  return (unsigned long)time(nullptr) > 1600000000UL;  // après 2020-09-13
}

String nowIso8601() {
  if (!timeSynced()) return String("");

  time_t now = time(nullptr);
  struct tm timeinfo;
  if (!gmtime_r(&now, &timeinfo)) return String("");

  char buffer[24];
  if (strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &timeinfo) == 0) {
    return String("");
  }
  return String(buffer);
}

}  // namespace smpark
