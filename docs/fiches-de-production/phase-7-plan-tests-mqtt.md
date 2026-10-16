# Plan validé — Phase 7 : tester le MQTT avec et sans ESP32

- **Date** : 2026-10-14
- **Contexte** : le test « C) Test MQTT (sans ESP32) » de la fiche Phase 7 ne
  fonctionnait pas. Ce document décrit le diagnostic et le plan validé mis en œuvre.

## 1. Diagnostic

### 1.1 Le test « sans ESP32 » ne pouvait pas fonctionner
La séquence attendue `opening → open → closing → closed` est produite
**uniquement par le firmware ESP32** (`firmware/esp32/src/main.cpp`). Sans
ESP32, aucun client n'est abonné à `parking/barrier/command` et rien ne publie
sur `barrier/state` : publier une commande n'a donc aucun effet. Le titre
« sans ESP32 » de la fiche Phase 7 était trompeur.

### 1.2 Incohérence des topics (backend ↔ ESP32)
| Source | Commande | État |
|---|---|---|
| `.env` (avant) | `MQTT_TOPIC_BARRIER_CMD=smpark/barrier/command` | `MQTT_TOPIC_BARRIER_STATE=smpark/barrier/state` |
| `backend/app/core/config.py` | `MQTT_TOPIC_BARRIER_COMMAND=parking/barrier/command` | `MQTT_TOPIC_BARRIER_STATE=barrier/state` |
| Backend réel | publiait `parking/barrier/command` (défaut) | s'abonnait à `smpark/barrier/state` |
| Firmware | écoutait `parking/barrier/command` | publiait `barrier/state` |

Deux problèmes :
1. Le nom de variable `.env` `MQTT_TOPIC_BARRIER_CMD` ne correspondait pas au
   champ attendu par Pydantic (`MQTT_TOPIC_BARRIER_COMMAND`), donc la valeur
   `.env` était **ignorée**.
2. Le préfixe `smpark/` de `.env` désalignait l'état : le backend écoutait
   `smpark/barrier/state` alors que l'ESP32 publie `barrier/state`.

### 1.3 Autres constats
- `MQTT_HOST` du firmware par défaut = `mqtt-broker.local` (non résolvable sur
  le LAN).
- Identifiants Wi-Fi réels **committés en clair** dans `main.cpp`.
- Pas de `retain` sur les états : un abonné tardif ne voit rien.
- `backend/app/services/mqtt.py` ne fait que *logger* les messages reçus
  (remontée WebSocket = Phase 8).

## 2. Décisions validées

| Décision | Choix |
|---|---|
| Convention de topics | **Sans préfixe** : `parking/state`, `parking/events`, `parking/barrier/command`, `barrier/state` |
| Test sans ESP32 | Simulateur via tools Mosquitto (zéro dépendance) |
| Périmètre | Tests + alignement des topics |
| Matériel ESP32 | Pas encore disponible → configuration prête à flasher |

## 3. Actions réalisées

### 3.1 Alignement des topics
- `.env` et `.env.example` :
  - `MQTT_TOPIC_BARRIER_CMD` → `MQTT_TOPIC_BARRIER_COMMAND`
  - valeurs `smpark/...` → sans préfixe
- `config.py` et le firmware étaient déjà sans préfixe (référence).
- Un redémarrage du backend est nécessaire pour recharger `env_file`.

### 3.2 Simulateur sans ESP32
- `scripts/barrier_sim.sh` : joue le rôle du firmware (écoute la commande,
  publie la séquence d'états). Voir le tuto de test Phase 7.

### 3.3 Firmware ESP32
- `main.cpp` : plus d'identifiants en clair, `retain` activé sur les états.
- Secrets via **`firmware/esp32/secrets.ini`** (gitignoré) chargé par
  `extra_configs` + `build_flags` ; modèle `secrets.ini.example`.
  Sans `secrets.ini`, compilation tolérée avec les valeurs `CHANGE_ME`.
- `.gitignore` : ajout de `secrets.ini`.
- Compilation vérifiée : `pio run -d firmware/esp32` → SUCCESS.

## 4. Procédures de test

### 4.1 Sans ESP32 (simulateur)
```bash
# Terminal 1 : simulateur (device)
docker compose exec -T mqtt-broker sh -s < scripts/barrier_sim.sh

# Terminal 2 : écoute des états
docker compose exec mqtt-broker mosquitto_sub -h localhost -p 1883 \
  -u smpark -P change_me_mqtt -t barrier/state -v

# Terminal 3 : envoi d'une commande
docker compose exec mqtt-broker mosquitto_pub -h localhost -p 1883 \
  -u smpark -P change_me_mqtt -t parking/barrier/command -m '{"action":"open"}'
```
Attendu (terminal 2) : `opening`, `open`, `closing`, `closed`.

### 4.2 Avec ESP32
1. `cp firmware/esp32/secrets.ini.example firmware/esp32/secrets.ini`
   puis renseigner SSID/clé Wi-Fi et `MQTT_HOST` = **IP LAN de la machine hôte**.
2. `pio run -d firmware/esp32` puis `pio run -d firmware/esp32 -t upload`.
3. `pio device monitor -d firmware/esp32 --baud 115200`
   → attendu : `initialized`/`idle` puis `heartbeat` toutes les 5 s.
4. Rejouer le test mosquito du §4.1 (sans le simulateur).

## 5. Vérification finale
- `/api/health` → `mqtt: up`.
- Test simulateur : séquence complète observée.
- Test action inconnue : `idle` + `reason: "unknown_action"`.

## 6. Hors périmètre (Phase 8)
- Remonter `barrier/state` du backend vers le WebSocket/dashboard
  (`mqtt.py` ne fait que logger aujourd'hui).
