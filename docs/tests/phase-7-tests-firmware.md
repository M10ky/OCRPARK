# Tuto de test — Phase 7 : Firmware ESP32

> Objectif : compiler, flasher (si matériel présent) et valider la communication
> MQTT avec le broker — **avec** ESP32 ou **sans** ESP32 via un simulateur.

Topologie :
- Commande : `parking/barrier/command` (backend → device)
- État : `barrier/state` (device → backend)

## 1. Vérification structure
```bash
ls -la /home/miokrako/SM-Park/firmware/esp32/platformio.ini \
       /home/miokrako/SM-Park/firmware/esp32/src/main.cpp
```

## 2. Compilation (PlatformIO) — sans matériel
```bash
pio run -d /home/miokrako/SM-Park/firmware/esp32
```
Attendu : `SUCCESS` (`firmware.bin` généré).

---

## Partie A — Sans ESP32 (simulateur)

> Important : la séquence d'états est produite par le « device ». Sans ESP32, on
> utilise le simulateur `scripts/barrier_sim.sh`. Il faut **démarrer le
> simulateur avant** d'envoyer la commande.

### A.1 Terminal 1 — simulateur (joue le rôle de l'ESP32)
```bash
docker compose exec -T mqtt-broker sh -s < scripts/barrier_sim.sh
```
Attendu : `[sim] Barrière simulée en écoute sur 'parking/barrier/command'`.

### A.2 Terminal 2 — écoute des états
```bash
docker compose exec mqtt-broker mosquitto_sub -h localhost -p 1883 \
  -u smpark -P change_me_mqtt -t barrier/state -v
```

### A.3 Terminal 3 — envoi d'une commande
```bash
docker compose exec mqtt-broker mosquitto_pub -h localhost -p 1883 \
  -u smpark -P change_me_mqtt -t parking/barrier/command -m '{"action":"open"}'
```
Attendu (terminal 2) : `opening`, `open`, `closing`, `closed`.

### A.4 Test action inconnue
```bash
docker compose exec mqtt-broker mosquitto_pub -h localhost -p 1883 \
  -u smpark -P change_me_mqtt -t parking/barrier/command -m '{"action":"test"}'
```
Attendu : `idle` avec `reason: "unknown_action"`.

### A.5 Vérifier la commande émise par le backend (optionnel)
Terminal 2 abonné à `parking/barrier/command`, puis déclencher
`POST /api/orchestrate/upload` avec une plaque autorisée (voir Phase 5).
Attendu : la commande `{"action":"open","gate":"entry","plate":...,"correlation_id":...}`
publiée par le backend.

### A.6 Test d'intégration complet (le vrai flux)
1. Ajouter une plaque autorisée : `POST /api/plates` (voir Phase 5).
2. Démarrer le simulateur (A.1) puis, dans un autre terminal, déclencher
   `POST /api/orchestrate/upload` avec une image de cette plaque (plaque autorisée).
3. Attendu : le backend publie `parking/barrier/command`, le « device » répond
   `opening → open → closing → closed` sur `barrier/state`, et le backend
   relaye ces états sur le WebSocket `/ws/events` (voir Phase 5, section 8bis).

---

## Partie B — Avec ESP32

### B.1 Configuration
```bash
cp /home/miokrako/SM-Park/firmware/esp32/secrets.ini.example \
   /home/miokrako/SM-Park/firmware/esp32/secrets.ini
```
Éditer `secrets.ini` et renseigner `WIFI_SSID`, `WIFI_PASSWORD`, `MQTT_HOST`
(= **IP LAN de la machine hôte**, pas `mqtt-broker.local`), `MQTT_PORT`,
`MQTT_USER`, `MQTT_PASSWORD`. `secrets.ini` est ignoré par git. Sans ce fichier,
la compilation utilise les valeurs `CHANGE_ME` de `main.cpp`.

### B.2 Upload & Monitor
```bash
pio run -d /home/miokrako/SM-Park/firmware/esp32 -t upload
pio device monitor -d /home/miokrako/SM-Park/firmware/esp32 --baud 115200
```
Attendu : `online` (retain) après connexion MQTT, puis l'état courant
(`idle`) rafraîchi toutes les 5 s (heartbeat). Si le device se déconnecte sans
prévenir, le broker publie le Last Will `{"state":"offline"}`.

### B.2bis Séquence barrière (machine à états non bloquante)
À réception de `{"action":"open","gate":"entry"}`, le firmware publie
`opening` → `open` (maintien 2 s) → `closing` → `closed`, sans `delay()` :
le callback ne fait que fixer l'état cible, `loop()` avance la séquence via
`millis()`. `gate` est repris dans chaque payload d'état (`entry` par défaut).

### B.3 Test MQTT (avec ESP32)
Terminal 1 (écoute états) :
```bash
docker compose exec mqtt-broker mosquitto_sub -h localhost -p 1883 \
  -u smpark -P change_me_mqtt -t barrier/state -v
```
Terminal 2 (envoi commande) :
```bash
docker compose exec mqtt-broker mosquitto_pub -h localhost -p 1883 \
  -u smpark -P change_me_mqtt -t parking/barrier/command -m '{"action":"open"}'
```
Attendu : séquence `opening`, `open`, `closing`, `closed` sur `barrier/state`.

### B.4 Vérifier que l'ESP32 est bien connecté au broker
```bash
docker compose logs --tail=20 mqtt-broker
```
Attendu : une ligne de connexion du client `smpark-esp32-XXXX` (suffixe = 2
octets de la MAC). En cas d'absence : vérifier `MQTT_HOST` (IP LAN de l'hôte),
le pare-feu (C.3) et que l'ESP32 est sur le même sous-réseau.

## Partie C — Prérequis WSL2 / Windows (dépannage)

### C.1 Déterminer `MQTT_HOST` (IP LAN de l'hôte)
Depuis WSL2, l'IP de la VM WSL (`hostname -I`, ex. `172.25.x.x`) n'est **pas**
joignable par l'ESP32. Il faut l'IP LAN **Windows** :
```bash
/mnt/c/Windows/System32/ipconfig.exe | grep -A4 "Carte Ethernet"
```
Choisir l'interface physique (ex. `Ethernet` → `192.168.1.104`), **pas**
`vEthernet (WSL)`. L'ESP32 et l'hôte doivent être sur le même réseau.
Vérifier que Docker publie bien le port côté Windows :
```bash
/mnt/c/Windows/System32/NETSTAT.EXE -an | grep 1883   # doit montrer 0.0.0.0:1883 LISTENING
```

### C.2 Flasher l'ESP32 depuis WSL2 (USB)
WSL2 ne voit pas les ports USB par défaut. Deux solutions :
- **Attacher le port via usbipd-win** (PowerShell admin côté Windows) :
  ```powershell
  usbipd list
  usbipd bind --busid <BUSID>
  usbipd attach --wsl --busid <BUSID>
  ```
  Puis dans WSL : `ls /dev/ttyUSB* /dev/ttyACM*` et uploader avec
  `pio run -d firmware/esp32 -t upload --upload-port /dev/ttyUSB0`
  (ajouter l'utilisateur au groupe `dialout` si permission refusée :
  `sudo usermod -aG dialout $USER` puis relogin).
- **Flasher depuis Windows** : installer PlatformIO (VS Code ou `pio` Windows),
  ouvrir `firmware/esp32` et lancer l'upload (COMx).

### C.3 Pare-feu Windows
Si l'ESP32 ne se connecte pas au broker alors que le port écoute, autoriser
l'entrée TCP 1883 (PowerShell **admin**) :
```powershell
New-NetFirewallRule -DisplayName "SM-Park MQTT 1883" -Direction Inbound `
  -Protocol TCP -LocalPort 1883 -Action Allow
```
