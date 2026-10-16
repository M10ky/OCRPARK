# Fiche de Production — Phase 7 : Firmware ESP32

- **Nom de la phase** : Phase 7 – Firmware ESP32
- **Objectif** : Fournir un firmware ESP32 minimal mais fonctionnel (Wi-Fi + MQTT + ArduinoJson + PubSubClient) simulant la logique barrière en réponse aux commandes `parking/barrier/command` et publiant des états sur `barrier/state`, conforme aux topics définis.
- **Date** : 2026-10-12

## Ce qui a été réalisé

### 1) Structure PlatformIO
- `firmware/esp32/platformio.ini` : environnement `esp32dev`, framework Arduino, `monitor_speed 115200`, dépendances `knolleary/PubSubClient@^2.8`, `bblanchon/ArduinoJson@^7.2.1`.
- Arborescence `src/`, `include/`, `lib/`, `test/`, `.gitignore` (`.pio`, `.vscode`, `.DS_Store`).

### 2) Firmware (src/main.cpp)
- Connexion Wi-Fi (avec fallbacks via defines), connexion MQTT authentifiée (user/pass), reconnexion automatique.
- Abonnement : `parking/barrier/command`.
- Publication : `barrier/state` (états: `initialized`, `idle`, `opening`, `open`, `closing`, `closed`, `error`, `heartbeat`).
- Logique simulée : à réception `action=open` → séquence `opening` → `open` (2s) → `closing` → `closed` (simulation temporelle). `action=close` → `closing` → `closed`. Inconnu → `idle` avec `reason`.
- Payload JSON via ArduinoJson (inclut `uptime_ms`, `reason` si pertinent).

### 3) Cohérence avec l'existant
- Topics alignés avec backend/orchestrateur (`MQTT_TOPIC_BARRIER_COMMAND=parking/barrier/command`, `barrier/state`).
- Authentification via `MQTT_USER/MQTT_PASSWORD` cohérents avec Mosquitto.
- Structure claire, minimal, prête à extension (capteurs/servo/porte IR, etc.).

## Fichiers créés
| Fichier | État |
|---|---|
| `firmware/esp32/platformio.ini` | créé |
| `firmware/esp32/src/main.cpp` | créé |
| `firmware/esp32/.gitignore` | créé |
| `firmware/esp32/include/` | créé (vide) |
| `firmware/esp32/lib/` | créé (vide) |
| `firmware/esp32/test/` | créé (vide) |
| `firmware/esp32/secrets.ini.example` | créé (modèle de configuration, gitignoré si copié en `secrets.ini`) |
| `scripts/barrier_sim.sh` | créé (simulateur sans ESP32) |
| `docs/fiches-de-production/phase-7.md` | créé |
| `docs/fiches-de-production/phase-7-plan-tests-mqtt.md` | créé (plan validé) |
| `docs/tests/phase-7-tests-firmware.md` | créé |

## Tests de connexion et de fonctionnement attendus
### A) Configuration (local)
- Copier `firmware/esp32/secrets.ini.example` vers `firmware/esp32/secrets.ini`
  (gitignoré) puis adapter `WIFI_SSID`, `WIFI_PASSWORD`, `MQTT_HOST` (IP LAN de
  l'hôte), `MQTT_PORT`, `MQTT_USER`, `MQTT_PASSWORD`.
- Compiler avec PlatformIO : `pio run -d firmware/esp32`.

### B) Upload/monitor
- `pio run -d firmware/esp32 -t upload` (si ESP32 connecté)
- `pio device monitor -d firmware/esp32` (baud 115200)

### C) Test MQTT (sans ESP32)
> La séquence d'états est produite par le « device ». Sans ESP32, utiliser le
> simulateur `scripts/barrier_sim.sh` (il faut le démarrer **avant** d'envoyer
> la commande). Détails : `docs/tests/phase-7-tests-firmware.md`.

```bash
# Terminal 1 - simulateur (joue le rôle de l'ESP32)
docker compose exec -T mqtt-broker sh -s < scripts/barrier_sim.sh
# Terminal 2 - écoute des états
docker compose exec mqtt-broker mosquitto_sub -h localhost -p 1883 -u smpark -P change_me_mqtt -t barrier/state -v
# Terminal 3 - envoi d'une commande
docker compose exec mqtt-broker mosquitto_pub -h localhost -p 1883 -u smpark -P change_me_mqtt -t parking/barrier/command -m '{"action":"open"}'
```
Attendu : publication séquentielle `barrier/state` (opening/open/closing/closed).

> Convention de topics : **sans préfixe** (`parking/barrier/command`,
> `barrier/state`). Voir `docs/fiches-de-production/phase-7-plan-tests-mqtt.md`.

### D) Intégration backend
Orchestrateur publie `parking/barrier/command` quand plaque autorisée + MQTT connecté (Phase 5). ESP32 répond sur `barrier/state`.

## Checklist de validation
- [x] Structure PlatformIO conforme.
- [x] Dépendances correctes.
- [x] Abonnements/publications alignés aux topics projet.
- [x] Reconnexion Wi-Fi/MQTT gérée.
- [x] Simulation barrière claire et traçable.
- [x] Fiches/documentation au format unifié.
- [x] Code minimal, sans logique inutile.

## Prochaine phase
**Phase 8 – Intégration et tests complets** (ne pas traiter maintenant).
