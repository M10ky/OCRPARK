# Plan de tests fonctionnel matériel - SM-Park (Phase Hardware)

**Objectif** : Valider le fonctionnement complet entre ESP32, MQTT, capteurs/actionneurs et intégration backend en environnement local 100 % Docker/WSL.

**Contexte** : ESP32 flashé, tout le matériel connecté (2 servos barrière entrée/sortie, 3x HC-SR04 places, 2x IR entrée/sortie). Stack locale : `mqtt-broker`, `backend`, `database`, `ocr-service`, `frontend` (si disponible).

**Référence contrat MQTT** : `docs/mqtt-contract.md`  
**Topics de référence** : 
- `parking/barrier/command` (backend/PC → ESP32)
- `barrier/state` (ESP32 → broker)
- `parking/state` (ESP32 → broker)
- `parking/events` (ESP32 → broker)

**Identifiants MQTT (depuis `.env`)** : `MQTT_USERNAME=smpark`, `MQTT_PASSWORD=change_me_mqtt` (adapter si modifiés)

**Prérequis globaux** :
- Accès au terminal WSL/Linux (ou Windows + WSL)
- `docker`, `docker compose` fonctionnels
- `mosquitto-clients` installé (`mosquitto_sub`, `mosquitto_pub`) 
- Moniteur série ESP32 accessible (ex. `pio device monitor`, `screen`, `minicom`, `cu`, `arduino-cli monitor`) sur le port COM/tty (Windows : `COMx`, WSL : `/dev/ttyUSBx` ou via USBIPD)
- Matériel branché et alimenté

> **Règle d'exécution** : Exécuter les tests **dans l'ordre T1 → T9**. Ne passer au test suivant qu'après avoir consigné le résultat du précédent.

---

## T1 — Santé de la stack Docker

### Objectif
Vérifier que tous les services requis sont up, healthy et que le broker MQTT est accessible.

### Prérequis
- `.env` présent
- `docker-compose.yml` valide
- Aucune modification non justifiée

### Actions concrètes

#### T1.1 - État des conteneurs
```bash
cd /home/miokrako/SM-Park
docker compose ps
```

#### T1.2 - Healthcheck détaillé
```bash
cd /home/miokrako/SM-Park
docker inspect --format='{{.Name}}: {{.State.Health.Status}}' smpark-mqtt smpark-db smpark-backend smpark-ocr smpark-frontend 2>&1 | head -10
```

#### T1.3 - Test publish/subscribe local sur le broker (authentifié)
Ouvrir **2 terminaux** ou exécuter en arrière-plan.

**Terminal A (abonnement) :**
```bash
# Dans WSL/Linux
mosquitto_sub -h 127.0.0.1 -p 1883 -u smpark -P change_me_mqtt -t 'test/health' -v -C 1 -W 5
```

**Terminal B (publication) :**
```bash
mosquitto_pub -h 127.0.0.1 -p 1883 -u smpark -P change_me_mqtt -t 'test/health' -m '{"test":"ok"}' -q 1
```

**Variante depuis l'intérieur du conteneur (si mosquitto_clients indisponible) :**
```bash
docker compose exec mqtt-broker sh -c 'mosquitto_sub -h localhost -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" -t test/health -v -C 1 -W 3 & sleep 1 && mosquitto_pub -h localhost -p 1883 -u "$MQTT_USERNAME" -P "$MQTT_PASSWORD" -t test/health -m "{\"test\":\"ok\"}" -q 1'
```

### Résultat attendu
- `docker compose ps` : `smpark-mqtt`, `smpark-db`, `smpark-backend`, `smpark-ocr` en `Up` (et `healthy` si healthcheck OK). `smpark-frontend` peut être up selon état.
- `docker inspect` : `healthy` pour `mqtt`, `db`, `backend` (au minimum). `ocr` peut prendre du temps au premier démarrage.
- Publication/abonnement fonctionne : Terminal A reçoit `test/health {"test":"ok"}` dans les 5s.

### Critère PASS / FAIL
- **PASS** : Broker accessible + auth OK + pub/sub fonctionnel.
- **FAIL** : Connexion refusée / auth échouée / timeout.

### Que faire en cas d'échec
- Vérifier `.env` (MQTT_USERNAME/PASSWORD)
- `docker compose logs mqtt-broker | tail -30`
- Vérifier port 1883 libre : `ss -tlnp | grep 1883` ou `netstat -tlnp | grep 1883`
- Relancer si besoin : `docker compose up -d mqtt-broker && sleep 10`

**Résultat T1** : [ ] PASS  [ ] FAIL  | Observations : ___________________________  
**Vérifié par / Date / Heure** : ___________________________

---

## T2 — Présence ESP32 sur MQTT

### Objectif
Confirmer que l'ESP32 est connecté au broker, émet son état et publie l'occupation des places.

### Prérequis
- T1 OK
- ESP32 alimenté + flashé
- Connexion série disponible

### Actions concrètes

#### T2.1 - Moniteur série (vérifier boot/config)
**PlatformIO :**
```bash
cd /home/miokrako/SM-Park/firmware/esp32
pio device monitor -b 115200
```

**Alternatives :**
```bash
screen /dev/ttyUSB0 115200  # ou /dev/ttyACM0
# ou minicom -D /dev/ttyUSB0 -b 115200
```

Vérifier dans les logs série :
- `[config] Wi-Fi + MQTT configures : OK`
- Connexion Wi-Fi réussie
- Connexion MQTT réussie (client ID type `smpark-esp32-...`)
- Absence de `CHANGE_ME_*`

#### T2.2 - Sniffer MQTT global
Ouvrir un terminal et écouter **tout** :
```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -u smpark -P change_me_mqtt -t '#' -v
```

Laisser tourner au moins 60s. Observer l'apparition des messages.

#### T2.3 - Cibler les topics attendus
Dans un autre terminal (ou après avoir vu le flux) :
```bash
# Écouter uniquement les topics clés
mosquitto_sub -h 127.0.0.1 -p 1883 -u smpark -P change_me_mqtt -t 'barrier/state' -t 'parking/state' -t 'parking/events' -v
```

### Résultat attendu
- Série : ESP32 connecté Wi-Fi + MQTT, pas de boucle de reconnexion excessive
- `barrier/state` apparaît périodiquement (heartbeat ~5s selon `HEARTBEAT_MS`) avec `{"state":"online", ...}` ou `idle`. Possiblement `retain=true`.
- `parking/state` apparaît périodiquement (polling slots ~300ms selon `SLOT_POLL_MS`) avec structure :
  ```json
  {"slots":[{"id":1,"occupied":false},{"id":2,"occupied":false},{"id":3,"occupied":false}]}
  ```
- `parking/events` peut être silencieux si aucun passage détecté

### Critère PASS / FAIL
- **PASS** : Au moins un message sur `barrier/state` et/ou `parking/state` dans les 60s
- **FAIL** : Aucun message MQTT malgré ESP32 allumé/flashé + broker up

### Que faire en cas d'échec
- Vérifier `firmware/esp32/secrets.ini` (WIFI_SSID/PASSWORD, MQTT_HOST = IP/hostname joignable depuis ESP32. Si broker sur PC local, utiliser IP LAN du PC, pas `localhost`)
- Vérifier que l'ESP32 est sur le même réseau que le broker
- Vérifier logs série : erreurs WiFi/MQTT
- Vérifier auth MQTT depuis ESP32 (mêmes creds)
- Si `MQTT_HOST` pointe sur `mqtt-broker` (nom Docker) depuis réseau LAN, ça ne fonctionnera pas - utiliser IP hôte

**Résultat T2** : [ ] PASS  [ ] FAIL  | Observations : ___________________________  
**barrier/state vu (oui/non)** : ____ | **parking/state vu (oui/non)** : ____  
**Vérifié par / Date / Heure** : ___________________________

---

## T3 — Commande barrière entrée

### Objectif
Valider le cycle commande `parking/barrier/command` → action servo entrée → états `barrier/state` avec corrélation si présente.

### Prérequis
- T2 OK (ESP32 connecté + MQTT actif)
- Servo entrée visible/accessible pour observation (mouvement)
- Moniteur série ouvert pour logs (facultatif mais utile)
- Sniffer MQTT sur `barrier/state` actif

### Actions concrètes

#### T3.1 - Préparer écoute
Terminal A :
```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -u smpark -P change_me_mqtt -t 'barrier/state' -v
```

#### T3.2 - Envoyer commande ouverture barrière ENTRÉE
Terminal B (avec `correlation_id` UUID v4 pour traçabilité) :
```bash
mosquitto_pub -h 127.0.0.1 -p 1883 -u smpark -P change_me_mqtt -t 'parking/barrier/command' -q 1 -m '{"action":"open","gate":"entry","correlation_id":"b7f3a9e2-8c42-4d71-b902-7e61ab584c13"}'
```

**Variante sans correlation_id** (test minimal) :
```bash
mosquitto_pub -h 127.0.0.1 -p 1883 -u smpark -P change_me_mqtt -t 'parking/barrier/command' -q 1 -m '{"action":"open","gate":"entry"}'
```

### Résultat attendu
Observer dans Terminal A (ordre typique selon firmware) :
1. `barrier/state` avec `state: "opening"`, `gate: "entry"`, `correlation_id` identique si fourni, `reason: "command"`
2. `barrier/state` avec `state: "open"`, `gate: "entry"`, même `correlation_id`
3. Après `OPEN_HOLD_MS` (~2500ms), `closing` puis `closed` (cycle complet)
4. **Mouvement physique** : servo entrée se lève/ouvre puis se referme
5. Si `SMPARK_ENABLE_SERVOS=0` dans firmware : pas de mouvement physique mais transitions d'états logiques possibles

Observer aussi sur série (si monitor ouvert) : logs de réception commande, pilotage servo.

### Critère PASS / FAIL
- **PASS** : Réception commande confirmée, séquence `opening` → `open` → `closing` → `closed`, mouvement servo entrée visible (ou logs cohérents si mode simulation)
- **FAIL** : Aucune réaction / mauvais gate / servo ne bouge alors qu'attendu / états incohérents

### Que faire en cas d'échec
- Vérifier que `gate` est bien `entry` (firmware route par gate)
- Vérifier logs série pour parsing JSON / validation
- Vérifier `SMPARK_ENABLE_SERVOS` et câblage `PIN_SERVO_ENTRY` (13)
- Si commande ignorée : regarder `reason` dans `barrier/state` (peut indiquer `invalid_json`, `unknown_action`)
- Tester à nouveau avec JSON valide et `correlation_id`

**Résultat T3** : [ ] PASS  [ ] FAIL  | 
**correlation_id repris (oui/non/na)** : ____ | **Mouvement servo entrée (oui/non)** : ____ |  
**Séquence observée** : ___________________________  
**Vérifié par / Date / Heure** : ___________________________

---

## T4 — Commande barrière sortie

### Objectif
Valider le même cycle pour la barrière de sortie.

### Prérequis
- T3 OK
- Sniffer `barrier/state` actif

### Actions concrètes

#### T4.1 - Écoute
```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -u smpark -P change_me_mqtt -t 'barrier/state' -v
```

#### T4.2 - Envoyer commande ouverture barrière SORTIE
```bash
mosquitto_pub -h 127.0.0.1 -p 1883 -u smpark -P change_me_mqtt -t 'parking/barrier/command' -q 1 -m '{"action":"open","gate":"exit","correlation_id":"9c82db71-6f43-4a25-8e07-2ac65f931874"}'
```

### Résultat attendu
- Même séquence d'états : `opening/open/closing/closed` avec `gate: "exit"`
- Même `correlation_id` repris si fourni
- **Mouvement physique** : servo sortie actionné
- Barrière entrée non affectée

### Critère PASS / FAIL
- **PASS** : Routage correct vers sortie, mouvement servo sortie, états cohérents
- **FAIL** : Ouvre la mauvaise barrière / pas de mouvement / pas de réaction

### Que faire en cas d'échec
- Vérifier routage par `gate` dans firmware
- Vérifier câblage `PIN_SERVO_EXIT` (12)
- Observer logs série
- S'assurer qu'aucune commande en cours n'interfère

**Résultat T4** : [ ] PASS  [ ] FAIL  | 
**gate correct (entry/exit)** : ____ | **Mouvement servo sortie (oui/non)** : ____ |  
**Observations** : ___________________________  
**Vérifié par / Date / Heure** : ___________________________

---

## T5 — HC-SR04 place par place

### Objectif
Vérifier la détection d'occupation/libération par ultrasons et publication correcte sur `parking/state` (structure conforme au contrat).

### Prérequis
- T2 OK
- 3 capteurs HC-SR04 accessibles (places 1,2,3)
- Objet pour simuler occupation (main, carton, objet ~10-20cm) ou véhicule factice
- Sniffer `parking/state` actif

### Actions concrètes

#### T5.1 - Écoute continue
```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -u smpark -P change_me_mqtt -t 'parking/state' -v
```

Noter l'état initial : toutes libres ? `occupied: false` pour slots 1,2,3

#### T5.2 - Occuper place par place
**Place 1** : approcher/placer un objet à **< 30 cm** devant HC-SR04 place 1 (respecter `OCCUPIED_DISTANCE_CM` + hystérésis `OCCUPIED_HYSTERESIS_CM`).
Attendre 2-5 secondes (polling ~300ms). Observer `parking/state`.

**Place 2** : idem.
**Place 3** : idem.

#### T5.3 - Libérer place par place
Éloigner l'objet progressivement au-delà du seuil (idéal > ~40cm pour franchir hystérésis). Observer passage `occupied: true` → `occupied: false`.

### Résultat attendu
Structure conforme D.1 :
```json
{"slots":[{"id":1,"occupied":true},{"id":2,"occupied":false},{"id":3,"occupied":false}]}
```
- Détection cohérente par place
- Changement d'état visible après délai raisonnable
- Pas de basculement erratique au seuil (hystérésis atténue le clignotement)
- Retour à `false` lors de libération
- Messages `retain=true` sur `parking/state` (comportement broker/firmware)

### Critère PASS / FAIL
- **PASS** : 3/3 places détectent occupation/libération correctement
- **FAIL** : Faux positif/négatif systématique, inversion de place, structure JSON incorrecte

### Que faire en cas d'échec
- Ajuster position/angle HC-SR04
- Vérifier câblage TRIG/ECHO (26/25, 33/32, 27/14)
- Observer série pour distances mesurées
- Ajuster `OCCUPIED_DISTANCE_CM` / `OCCUPIED_HYSTERESIS_CM` si nécessaire (documenter dans T9)
- Vérifier `SMPARK_ENABLE_SENSORS=1`

**Résultat T5** : [ ] PASS  [ ] FAIL  
**Place 1** : occupe [ ]OK/[ ]KO | libère [ ]OK/[ ]KO  
**Place 2** : occupe [ ]OK/[ ]KO | libère [ ]OK/[ ]KO  
**Place 3** : occupe [ ]OK/[ ]KO | libère [ ]OK/[ ]KO  
**Structure JSON conforme** : [ ]OUI/[ ]NON  
**Observations** : ___________________________  
**Vérifié par / Date / Heure** : ___________________________

---

## T6 — IR entrée / sortie

### Objectif
Vérifier la détection de passage par capteurs IR (entrée/sortie), génération d'événements `parking/events` et effet debounce.

### Prérequis
- T2 OK
- 2x IR (entrée/sortie) câblés (GPIO 34 entrée, 35 sortie - entrées uniquement)
- Sniffer `parking/events` actif

### Actions concrètes

#### T6.1 - Écoute événements
```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -u smpark -P change_me_mqtt -t 'parking/events' -v
```

#### T6.2 - Déclencher IR ENTRÉE
Passer la main/devant le capteur IR entrée (interrompre faisceau/réflexion selon type). Observer message.

Attendu (conforme D.2) :
```json
{"type":"entry","gate":"entry","ts":"..."}
```

#### T6.3 - Déclencher IR SORTIE
Idem pour IR sortie :
```json
{"type":"exit","gate":"exit","ts":"..."}
```

#### T6.4 - Test debounce (anti-spam)
Passer rapidement/rebonds devant même capteur plusieurs fois en < 500ms. Observer s'il y a un seul événement ou plusieurs.

### Résultat attendu
- Événement généré à chaque passage légitime
- `type` et `gate` cohérents avec le capteur déclenché
- `ts` présent si firmware le renseigne (ISO 8601 UTC)
- `retain=false` sur `parking/events` (ne doit pas rester "collé" au broker)
- Debounce actif : pas de spam excessif (limité par `IR_DEBOUNCE_MS` ~250ms)

### Critère PASS / FAIL
- **PASS** : entry/sortie détectés correctement, pas de spam excessif
- **FAIL** : Pas de détection / inversion / spam > 1 événement par passage clair

### Que faire en cas. d'échec
- Vérifier polarité/config IR (NO/NC) et branchement sur GPIO 34/35
- Vérifier `INPUT` uniquement (GPIO 34/35 pas de pull interne)
- Observer série
- Ajuster position/hauteur capteur
- Vérifier debounce dans firmware

**Résultat T6** : [ ] PASS  [ ] FAIL  
**IR entrée → event entry** : [ ]OK/[ ]KO  
**IR sortie → event exit** : [ ]OK/[ ]KO  
**Debounce effectif** : [ ]OUI/[ ]NON  
**Observations** : ___________________________  
**Vérifié par / Date / Heure** : ___________________________

---

## T7 — Scénario fonctionnel mini parking

### Objectif
Valider un enchaînement réaliste bout-en-bout cohérent avec le fonctionnement attendu.

### Prérequis
- T1-T6 OK
- Sniffer actif sur `barrier/state`, `parking/state`, `parking/events`

### Scénario à exécuter dans l'ordre

**Étape 1** : État initial
- Vérifier `parking/state` : places libres (`occupied:false`)

**Étape 2** : Détection IR entrée (si utilisé dans scénario)
- Déclencher IR entrée → observer `parking/events` type `entry`, gate `entry`

**Étape 3** : Commande ouverture barrière entrée
```bash
mosquitto_pub -h 127.0.0.1 -p 1883 -u smpark -P change_me_mqtt -t 'parking/barrier/command' -q 1 -m '{"action":"open","gate":"entry","correlation_id":"scen-001-entry"}'
```
Vérifier cycle `barrier/state` avec même correlation_id, mouvement servo entrée.

**Étape 4** : Occupation d'une place
- Placer véhicule/objet sur **une** place (ex. place 1) devant HC-SR04
- Attendre mise à jour `parking/state` → `{"id":1,"occupied":true,...}`

**Étape 5** : Demande sortie / IR sortie
- Déclencher IR sortie OU envoyer commande ouverture sortie :
```bash
mosquitto_pub -h 127.0.0.1 -p 1883 -u smpark -P change_me_mqtt -t 'parking/barrier/command' -q 1 -m '{"action":"open","gate":"exit","correlation_id":"scen-002-exit"}'
```
Vérifier `barrier/state` pour sortie, mouvement servo sortie.
Observer `parking/events` si IR sortie déclenché.

**Étape 6** : Libération place
- Retirer objet de la place occupée
- Vérifier `parking/state` → place repasse `occupied:false`

### Résultat attendu
- Enchaînement fluide, pas de blocage
- États cohérents entre événements, commandes, occupation
- Barrières s'ouvrent/ferment correctement par gate
- Occupation reflétée en temps réel

### Critère PASS / FAIL
- **PASS** : Scénario complet réalisé sans incohérence majeure
- **FAIL** : Blocage, routage erroné, occupation non mise à jour, barrière ne répond pas

### Que faire en cas d'échec
- Revenir au test concerné (T3/T4/T5/T6)
- Vérifier logs série + MQTT simultanément
- Documenter point de défaillance précisément

**Résultat T7** : [ ] PASS  [ ] FAIL  
**Étapes complétées** : 1[ ] 2[ ] 3[ ] 4[ ] 5[ ] 6[ ]  
**Incohérences observées** : ___________________________  
**Vérifié par / Date / Heure** : ___________________________

---

## T8 — Intégration backend (si service up)

### Objectif
Vérifier que le backend consomme bien les topics MQTT et expose son API/health.

### Prérequis
- T1 OK (backend up/healthy)
- MQTT actif avec trafic (idéalement pendant T2/T7)

### Actions concrètes

#### T8.1 - Health API backend
```bash
curl -s http://127.0.0.1:8000/api/health/live
echo
curl -s http://127.0.0.1:8000/api/health/ready
echo
```

#### T8.2 - Logs backend MQTT
```bash
docker compose logs backend --tail=60
```

Chercher : abonnements aux topics (`parking/state`, `parking/events`, `barrier/state`), messages reçus, erreurs MQTT.

#### T8.3 - Consommation événements (si trafic généré)
Pendant que T7 tourne, observer logs backend pour montrer qu'il voit les événements/états.

#### T8.4 - Orchestration OCR (optionnel)
Si `ocr-service` up et frontend/backend liés :
```bash
curl -s http://127.0.0.1:8001/health/live
echo
```
Observer si pertinent (upload scan → commande barrière). Non bloquant si non testé.

### Résultat attendu
- `/api/health/live` et `/ready` renvoient statut OK (200)
- Logs backend montrent connexion MQTT réussie et souscriptions actives
- Backend réagit au trafic MQTT généré (logs sans erreur critique)
- Pas d'erreurs d'auth MQTT côté backend

### Critère PASS / FAIL
- **PASS** : API healthy + backend connecté MQTT + logs cohérents
- **FAIL** : Health KO / backend ne se connecte pas au broker / erreurs MQTT répétés

### Que faire en cas d'échec
- Vérifier `.env` backend (MQTT_HOST=mqtt-broker, creds identiques)
- `docker compose logs mqtt-broker backend | tail -40`
- Vérifier réseau Docker `smpark-net`
- Vérifier `backend/app/core/config.py` et `backend/app/services/mqtt.py` si besoin

**Résultat T8** : [ ] PASS  [ ] FAIL  
**/api/health/live** : [ ]200/[ ]KO  | **/api/health/ready** : [ ]200/[ ]KO  
**Backend connecté MQTT (logs)** : [ ]OUI/[ ]NON  
**Observations** : ___________________________  
**Vérifié par / Date / Heure** : ___________________________

---

## T9 — Synthèse

### Objectif
Faire le bilan global, lister bugs/réglages, conclure sur la préparation matérielle.

### Actions concrètes
Remplir le tableau ci-dessous à partir de T1-T8.

### Tableau PASS/FAIL global
| Test | Statut | Critique (Oui/Non) | Commentaire |
|---|---|---|---|
| T1 - Santé stack Docker | [ ]PASS [ ]FAIL | ____ | ___________________________ |
| T2 - Présence ESP32 sur MQTT | [ ]PASS [ ]FAIL | ____ | ___________________________ |
| T3 - Commande barrière entrée | [ ]PASS [ ]FAIL | ____ | ___________________________ |
| T4 - Commande barrière sortie | [ ]PASS [ ]FAIL | ____ | ___________________________ |
| T5 - HC-SR04 place par place | [ ]PASS [ ]FAIL | ____ | ___________________________ |
| T6 - IR entrée/sortie | [ ]PASS [ ]FAIL | ____ | ___________________________ |
| T7 - Scénario fonctionnel mini parking | [ ]PASS [ ]FAIL | ____ | ___________________________ |
| T8 - Intégration backend | [ ]PASS [ ]FAIL | ____ | ___________________________ |

### Bugs observés
1. ___________________________
2. ___________________________
3. ___________________________

### Réglages à faire
- **Seuil distance HC-SR04** (`OCCUPIED_DISTANCE_CM`) : actuel ____ | proposé ____ | raison _____________
- **Hystérésis** (`OCCUPIED_HYSTERESIS_CM`) : actuel ____ | proposé ____ | raison _____________
- **Polarité IR** : ___________________________
- **Angles servo** (`SERVO_CLOSED_ANGLE` / `SERVO_OPEN_ANGLE`) : entrée (____/____) | sortie (____/____) | observations _____________
- **Autres** : ___________________________

### Conclusion
- [ ] **Matériel PRÊT** pour la suite (Frontend / soutenance)
- [ ] **Matériel PARTIELLEMENT PRÊT** - corrections mineures à effectuer
- [ ] **Matériel NON PRÊT** - corrections majeures nécessaires

**Justification** : ___________________________

**Validé par** : ___________________________  
**Date** : ____/____/______  
**Heure** : ____:____

---

## Annexe - Commandes rapides (copier-coller)

```bash
# Stack
cd /home/miokrako/SM-Park && docker compose ps

# Sniffer tout MQTT
mosquitto_sub -h 127.0.0.1 -p 1883 -u smpark -P change_me_mqtt -t '#' -v

# Topics clés
mosquitto_sub -h 127.0.0.1 -p 1883 -u smpark -P change_me_mqtt -t 'barrier/state' -t 'parking/state' -t 'parking/events' -v

# Ouvrir barrière entrée
mosquitto_pub -h 127.0.0.1 -p 1883 -u smpark -P change_me_mqtt -t 'parking/barrier/command' -q 1 -m '{"action":"open","gate":"entry","correlation_id":"'"$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid)"'"}'

# Ouvrir barrière sortie
mosquitto_pub -h 127.0.0.1 -p 1883 -u smpark -P change_me_mqtt -t 'parking/barrier/command' -q 1 -m '{"action":"open","gate":"exit","correlation_id":"'"$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid)"'"}'

# Health backend
curl -s http://127.0.0.1:8000/api/health/live && echo && curl -s http://127.0.0.1:8000/api/health/ready && echo

# Logs
docker compose logs mqtt-broker backend --tail=30
```

**Notes Windows/WSL** : Si `mosquitto_*` indisponible dans WSL, utiliser `docker compose exec mqtt-broker ...` ou installer `mosquitto-clients`. Si ESP32 non visible en WSL, utiliser USBIPD-WIN pour partager le port série vers WSL.
