#include "wifi_link.h"

#include <WiFi.h>

#include "config.h"

namespace smpark {
namespace {

unsigned long g_lastAttempt = 0;

}  // namespace

void wifiBegin() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // évite les latences de reconnexion
  g_lastAttempt = millis() - WIFI_RETRY_MS;  // première tentative immédiate
}

void wifiLoop() {
  if (!smpark::configIsValid()) return;
  if (WiFi.status() == WL_CONNECTED) return;
  if (millis() - g_lastAttempt < WIFI_RETRY_MS) return;

  g_lastAttempt = millis();
  Serial.println("[wifi] connexion...");
  WiFi.disconnect();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

bool wifiConnected() {
  return WiFi.status() == WL_CONNECTED;
}

String wifiIp() {
  return wifiConnected() ? WiFi.localIP().toString() : String("");
}

}  // namespace smpark
