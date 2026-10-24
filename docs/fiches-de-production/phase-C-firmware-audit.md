# Fiche d'audit — Phase C.1 : audit du firmware `main.cpp` actuel

- **Nom de l'étape** : C.1 — Audit du firmware existant (constat, écarts au
  contrat MQTT, blocages, plan de correction minimal).
- **Date** : 2026-10-22.
- **Objectif** : savoir précisément **ce qui marche déjà** et **ce qui doit
  être corrigé** avant de stabiliser le firmware, **sans encore réécrire le
  firmware**.
- **Source de vérité** : `docs/mqtt-contract.md` (§B à §I).
- **Fichiers audités** :
  - `firmware/esp32/src/main.cpp` (414 lignes)
  - `firmware/esp32/platformio.ini`
  - `firmware/esp32/secrets.ini.example` / `secrets.ini` (gitignoré)
- **Hors scope** : TLS, et le **câblage physique définitif** (l'audit porte sur
  le code, pas sur le montage).

---

## 0. Addendum — décision du 2026-10-22 : le matériel est RÉEL et CONSERVÉ

> **Cet addendum prime sur les sections suivantes.** L'audit a été réalisé
> avant la confirmation matériel ; l'utilisateur a ensuite précisé
> **« j'ai déjà tous les capteurs »** et **« ne retire pas les servo »**.
> Le matériel (2 servos, 3 HC-SR04, 2 barrettes IR) est donc **réel** et
> reste **piloté** par le firmware.

### Points ANNULÉS

| §Audit | Ce qui était prévu | Nouveau traitement |
|---|---|---|
| §4.1 | « le pinout est inventé, ces définitions doivent disparaître » | Le pinout est **centralisé dans `src/config.h`** (un seul endroit à modifier) et **conservé**. Les broches 12/13/14 restent signalées comme **strapping** : à confirmer avec le câblage réel. |
| §4.3, F-01 | « Retirer `ESP32Servo` de `lib_deps` » | `ESP32Servo@^1.2.1` est **conservée** et pilotée réellement. |
| §4.3, F-01 | « `setup()` ne fait plus aucun `pinMode`/`attach` » | `setup()` configure les HC-SR04, les IR en `INPUT_PULLUP` (GPIO 34/35 n'ont pas de pull-up interne) et **attache les 2 servos**. |
| F-02 | « Ne plus publier `parking/state` tant que les capteurs n'existent pas » | `parking/state` est publié avec la **mesure réelle**. Le flag `SMPARK_ENABLE_SENSORS` (défaut **1**) permet de le neutraliser si le câblage n'est pas prêt. |
| F-03 | « `updateIR()` est retiré de `loop()` » | La lecture IR est **conservée**, avec pull-up interne et anti-rebond. |
| §8 | `hardware.h/.cpp` en **STUBS** | `hardware.h/.cpp` devient la **couche matérielle réelle** ; le découpage en couches est conservé, seul le contenu change. |
| §9 | « séquence cible (mode logiciel, **sans servo**) » | La séquence d'états est conservée ; le **mouvement réel du servo** est ajouté par la couche matérielle. |

### Points qui RESTENT VALIDES (et deviennent plus urgents)

| Point | Pourquoi c'est plus important avec le matériel réel |
|---|---|
| **F-02** (blocage `pulseIn`) | La mesure devient **réelle** : le blocage prive alors `mqttClient.loop()` de son temps CPU → ACK hors délai. À corriger en C.3. |
| **F-04** (`publish()` dans le callback) | Inchangé, et le nombre de publications augmente (3 HC-SR04 + IR + 2 servos). → C.3 |
| **F-05 / F-06 / F-07** (validation `action`/`gate`/`correlation_id`, ne jamais acquitter une erreur) | Inchangé : une commande invalide ne doit pas déclencher un servo. → C.4 |
| **F-08** (un état par barrière) | D'autant plus critique que les **2 servos** sont réels : une commande `exit` pendant une séquence `entry` basculait le servo d'entry. → C.4 |
| **F-09 à F-16** | Inchangés (horodatage, idempotence, `clientId`, logs, secrets). |

### Risque spécifique ajouté

> Les **broches de strapping 12/13/14** ne sont plus un défaut théorique :
> elles pilotent désormais un servo (12, 13) et un ECHO (14). Si un servo tire
> une de ces broches au LOW au démarrage, **l'ESP32 peut ne pas booter**.
> → vérifier le câblage avant la démo, ou migrer servo entry/exit vers des
> broches non-strapping (ex. 18, 19) et ECHO 3 vers 21.

### Avancement

| Point | Statut |
|---|---|
| F-13 (secrets durcis, garde-fou au boot, script de build) | ✅ **C.2 livré** |
| F-01 / F-02 / F-03 (partiel) — pinout centralisé, flags `build_src_flags`, sentinelles `CHANGE_ME_*` | ✅ **C.2 livré** |
| F-04 (file de commandes), F-05→F-08, F-09, F-10, F-11, F-12, F-14, F-15, F-16 | ✅ **C.3 / C.4 livré** |
| Tests natifs (validation + machine à états, 36 vérifications) | ✅ **C.4 livré** |

> Le firmware a été restructuré en couches (`command` / `barrier` / `mqtt_link`
> / `wifi_link` / `time_util` / `hardware`) ; voir
> `docs/fiches-de-production/phase-C-firmware-mqtt.md`.
>
> **Bug réel détecté par le compilateur pendant la restructuration** : une
> comparaison de pointeurs `const char*` (`==`) au lieu de `strcmp` dans
> `barrier.cpp` — corrigé.

---

## 1. Verdict en une phrase

> Le firmware **compile, se flashe et se connecte** ; il est **globalement
> conforme au contrat MQTT sur les topics, le JSON et la sémantique
> d'ACK**. En revanche il **invente un pinout**, **lit des capteurs non
> branchés** (avec un `pulseIn()` bloquant de ~30 ms par capteur),
> **publie une occupation qui n'est pas mesurée**, et **publie depuis le
> callback MQTT** (danger connu avec PubSubClient). Ces 4 points doivent être
> corrigés avant toute démonstration.

---

## 2. Ce qui marche déjà (✅ à conserver)

| # | Élément | Preuve | Verdict |
|---|---|---|---|
| 1 | Projet PlatformIO fonctionnel | `platformio.ini` : `espressif32@6.9.0`, `board = esp32dev`, `framework = arduino` ; `pio run` OK | ✅ conserver tel quel |
| 2 | Dépendances adaptées | `PubSubClient@^2.8`, `ArduinoJson@^7.2.1` (le seul qui importe) ; `ESP32Servo@^1.2.1` (à neutraliser) | ✅ / ⚠️ cf. §4 |
| 3 | Connexion Wi-Fi **non bloquante** | `ensureWiFi()` l. 263-270 : retry toutes les 5 s sur `millis()`, pas de `delay()` | ✅ excellent |
| 4 | Machine à états **non bloquante** | `updateBarrier()` l. 296-311 : `millis() - phaseSince`, transitions `OPENING→OPEN→CLOSING→CLOSED` | ✅ excellent |
| 5 | Séquence d'états conforme au contrat | `opening → open → closing → closed` (identique à `barrier_sim.sh` et à l'attendu §E du contrat) | ✅ |
| 6 | Topics **exactement conformes** | l. 59-62 : `parking/barrier/command`, `barrier/state`, `parking/state`, `parking/events` | ✅ |
| 7 | **Sémantique d'ACK correcte** | `pendingCorrelationId` (l. 165-167) : le `correlation_id` n'est renvoyé que sur le **premier** `barrier/state` suivant la commande → conforme à §D.4 | ✅ (un cas à corriger, cf. F-06) |
| 8 | Last Will / Retain | `mqttClient.connect(..., TOPIC_BARRIER_STATE, 1, true, "{\"state\":\"offline\"}")` l. 282-284 → `offline` retenu en cas de coupure | ✅ (`offline` est un état autorisé §D.4) |
| 9 | `retain` conforme | `barrier/state` et `parking/state` en `retain=true` ; `parking/events` en `retain=false` (l. 173, 190, 203) | ✅ conforme §C |
| 10 | JSON via ArduinoJson 7 | `JsonDocument`, `serializeJson` → structures correctes | ✅ |
| 11 | `uptime_ms` = `millis()` | l. 169 → conforme à §D.4 | ✅ |
| 12 | Secrets externalisés | `secrets.ini` + `extra_configs` + `-D` build flags ; `.gitignore` protège le fichier | ✅ mécanisme à durcir (F-13) |
| 13 | `mqttClient.setBufferSize(512)` | l. 390 : évite la troncature à 256 octets (défaut PubSubClient) | ✅ |
| 14 | Sécurité arithmétique de `millis()` | toutes les comparaisons sont de la forme `millis() - t0` → sûres au wrap-around | ✅ |
| 15 | `clientId` unique | `smpark-esp32-%04X` sur les 16 derniers bits de la MAC | ⚠️cf. F-11 |

---

## 3. Analyse du caractère **bloquant** (le point le plus critique)

### 3.1 Le timer de mesure des capteurs

`readDistanceCm()` (l. 119-129) utilise `pulseIn(echoPin, HIGH, 30000)` :

```cpp
long duration = pulseIn(echoPin, HIGH, 30000); // timeout 30ms
```

`pulseIn` est une **attente bloquante**. Sur une entrée non câblée :

| Situation | Comportement de `pulseIn` | Durée |
|---|---|---|
| Broche au repos (LOW) | attend le front HIGH → timeout | **30 ms** |
| Broche flottante qui lit HIGH | attend le front LOW → timeout | **30 ms** |
| Capteur présent | mesure réelle | ~2–10 ms |

Or `updateSlots()` (l. 318-335) appelle `measureOccupied()` sur **3 paires**,
et `readDistanceMedianCm()` (l. 131-148) fait **5 échantillons** avec
`delay(5)` entre chaque (l. 135).

```
coût par cycle de 300 ms  =  3 × 5 × (30 ms + 5 ms)  =  525 ms   ← PIOR
```

> **Le firmware passe plus de temps à attendre des capteurs inexistants qu'à
> faire quoi que ce soit d'utile.** Le cycle `SLOT_POLL_MS = 300` (l. 71)
> est largement dépassé : la boucle réelle tourne à ~1,7 Hz au lieu de 3,3 Hz,
> et `mqttClient.loop()` est appelé **beaucoup moins souvent** que prévu.
> C'est la cause n°1 de « l'ESP32 ne répond pas de façon fiable ».

### 3.2 Les autres blocages

| Emplacement | Nature | Verdict |
|---|---|---|
| `delay(200)` l. 365 | dans `setup()`, une seule fois | ✅ acceptable |
| `delay(5)` l. 135 | dans la boucle de mesure | 🔴 à supprimer (F-02) |
| `pulseIn` l. 126 | dans la boucle de mesure | 🔴 à supprimer (F-02) |
| `WiFi.begin()` l. 269 | appel bloquant court (~1 s) mais **hors** callback MQTT | ⚠️ acceptable, à déplacer si possible |

### 3.3 Le `publish()` **dans le callback MQTT** (danger PubSubClient)

`mqttCallback()` (l. 233-258) appelle `setPhase()` (l. 251/253), qui appelle
`publishBarrierState()` (l. 227), qui appelle `mqttClient.publish()` (l. 173).

**PubSubClient n'est pas ré-entrant** : publier depuis le callback, pendant
que la bibliothèque est en train de lire le message courant, peut écrire des
fragments de paquet dans le buffer réseau et produire des trames MQTT
corrompues. Le symptôme en démo est intermittent et très difficile à
diagnostiquer (« ça marche 1 fois sur 3 »).

**Correction : le callback ne fait que *parser et mémoriser* ; c'est `loop()`
qui exécute et publie.** → F-04.

---

## 4. Analyse du pinout / matériel

### 4.1 Le pinout est **inventé** (interdit par le cahier des charges)

`main.cpp` l. 17-29 :

```cpp
#define PIN_SERVO_ENTRY 13
#define PIN_SERVO_EXIT  12
#define PIN_LED_STATUS  2
#define PIN_TRIG_1 26 / PIN_ECHO_1 25
#define PIN_TRIG_2 33 / PIN_ECHO_2 32
#define PIN_TRIG_3 27 / PIN_ECHO_3 14
#define PIN_IR_ENTRY 34 / PIN_IR_EXIT 35
```

Le cahier des charges impose : *« ne pas imposer de pinout HC-SR04 / IR / servo
pour le moment »*. Ces définitions doivent **disparaître** du code d'exécution.

### 4.2 Risques électriques et de démarrage de ce pinout

| Broche | Usage actuel | Risque |
|---|---|---|
| **GPIO 12** (MTDI) | servo exit | ⚠️ **broche de strapping** (niveau de boot) : un servo qui tire la broche au LOW au démarrage peut empêcher le boot de l'ESP32 |
| **GPIO 13** (MTDO) | servo entry | ⚠️ **broche de strapping** : même risque (GPIO13 est à LOW au boot par défaut → Pull-down interne actif) |
| **GPIO 14** (MTMS) | ECHO 3 | ⚠️ broche de strapping (boot) |
| GPIO 15, 2 | — | strapping (2 utilisé pour la LED, acceptable) |
| GPIO 34, 35 | IR | entrées **uniquement** (pas de pull-up ni pull-down interne) → **lecture flottante non déterministe** |
| GPIO 6–11 | — | SPI flash : non utilisés ✅ |

> **Conclusion** : même si le pinout était correct, l'usage de 12/13/14 est
> **dangereux pour le démarrage** de la carte. C'est un argument de plus pour
> tout mettre derrière un stub.

### 4.3 Conséquences immédiates sur la démo (sans aucun capteur branché)

| Effet | Mécanisme | Conséquence visible en soutenance |
|---|---|---|
| **Occupation fantôme « tout libre »** | `pulseIn` → 0 → `readDistanceCm` → 999 cm → `occupied=false` (l. 127) → `publishParkingState()` l. 190 | L'UI affiche « 3 places libres » alors que **rien n'est mesuré**. C'est une information **fausse** présentée comme vraie. |
| **Publication d'occupation toutes les 5 s** | heartbeat l. 409-414 qui republic `parking/state` | Le backend réécrit en boucle `parking_slots` avec une valeur non mesurée. |
| **Événements de passage possibles** | `updateIR()` l. 337-355 lit des entrées flottantes (34/35) sans pull-up → valeur indéfinnie → peut déclencher `publishParkingEvent("entry")` | **Visites créées en base sans véhicule** → historique et compteur de passages faussés. |
| **Consommation CPU ~50 %** | cf. §3.1 | `mqttClient.loop()` est Starvé → commandes reçues en retard, ACK hors délai (le backend time-out après 5 s). |
| **Servos pouvant être « attachés »** | `servoEntry.attach(13)` / `servoExit.attach(12)` l. 381-382 | Le ESP32Servo pilote des broches **inconnues** ; si un servo est branché au mauvais endroit, il peut être endommagé. |

---

## 5. Écarts au contrat MQTT (tableau de référence)

### 5.1 Conformité topic par topic

| §Contrat | Exigence | Firmware actuel | Verdict |
|---|---|---|---|
| §C | `parking/barrier/command` (backend → ESP32) | souscrit l. 285 | ✅ |
| §C | `barrier/state` (retain=true, QoS1) | publié l. 173 avec retain=true | ✅ (QoS 0, cf. limitation §I) |
| §C | `parking/state` (retain=true) | publié l. 190 | ⚠️ **contenu non mesuré** (F-02) |
| §C | `parking/events` (retain=false) | publié l. 203 | ⚠️ **déclenchement non fiable** (F-03) |
| §D.3 | champ `gate` **requis** | `currentGate = String(doc["gate"] \| "entry")` l. 247 — **non validé** | 🔴 F-07 |
| §D.3 | champ `action` ∈ {`open`,`close`} | `strcmp(action,"open")` / `strcmp(action,"close")` l. 251-256 — **non validé**, et `action` peut valoir `nullptr` | 🔴 F-07 |
| §D.3 | `correlation_id` **requis** | repris tel quel l. 248 | ⚠️ F-06 |
| §D.4 | ACK = **premier** `barrier/state` avec le même `correlation_id` | l. 165-167 | ✅ (sauf F-06) |
| §D.4 | `state` ∈ {online, offline, idle, opening, open, closing, closed} | `phaseName()` l. 106-114 | ✅ |
| §D.4 | `gate` (optionnel) | toujours publié | ✅ |
| §D.4 | `reason` (optionnel) | publié sur erreur seulement | ✅ (ajouter `reason:"command"` en phase normale) |
| §D.4 | `uptime_ms` = `millis()` | l. 169 | ✅ |
| §D.2 | `ts` = horodatage **ISO 8601 UTC** | `doc["ts"] = millis()` l. 186 et 199 → **entier d'uptime, pas un ISO 8601** | 🔴 F-09 |
| §F.1 | idempotence | pas de déduplication en mémoire | ⚠️ F-10 |
| §F.2 | routage par `gate` (ignorer la commande de l'autre barrière) | `currentGate` est **global** et muté par le callback → une commande `exit` pendant une séquence `entry` bascule la servo d'**entry** | 🔴 F-08 |
| §F.4 | `clientId` = `smpark-esp32-<MAC>` | `smpark-esp32-%04X` (16 bits seulement) | ⚠️ F-11 |
| §F.5 | **aucun échec silencieux** | `mqttClient.publish(...)` : valeur de retour **ignorée** l. 173, 190, 203 | 🔴 F-12 |
| §G | topics issus des variables d'environnement backend | codés en dur l. 59-62 | ⚠️ F-14 (amélioration) |

### 5.2 Synthèse des écarts

| ID | Écart | Gravité | Bloquant démo ? |
|---|---|---|---|
| **F-01** | Pinout inventé + servos attachés au boot | 🔴 Critique | Oui |
| **F-02** | `pulseIn`/`delay` bloquants (~525 ms/cycle) + occupation non mesurée publiée | 🔴 Critique | Oui |
| **F-03** | IR sur entrées flottantes → événements de passage aléatoires | 🔴 Critique | Oui |
| **F-04** | `publish()` appelé depuis le callback MQTT (PubSubClient non ré-entrant) | 🔴 Critique | Oui (intermittent) |
| **F-05** | Pas de validation de `action` / `gate` / `correlation_id` | 🟠 Majeur | Non |
| **F-06** | Un état d'**erreur** porte le `correlation_id` → le backend marque la commande **`acknowledged`** alors qu'aucune barrière ne s'est ouverte | 🟠 Majeur | Non (mais fausse trace en base) |
| **F-07** | `doc["action"]` peut valoir `nullptr` → `strcmp(nullptr, …)` | 🟠 Majeur | Non |
| **F-08** | `currentGate` global → mélange des barrières entry/exit | 🟠 Majeur | Non |
| **F-09** | `ts` envoyé en `millis()` au lieu d'ISO 8601 | 🟠 Majeur | Non (champ optionnel) |
| **F-10** | Pas de déduplication `correlation_id` (idempotence §F.1) | 🟡 Mineur | Non |
| **F-11** | `clientId` sur 16 bits de MAC au lieu de la MAC complète | 🟡 Mineur | Non |
| **F-12** | Valeur de retour de `publish()` ignorée (violation §F.5) | 🟡 Mineur | Non |
| **F-13** | `secrets.ini` **absent** → le firmware compile avec des identifiants **de substitution** silencieux (`CHANGE_ME_WIFI_SSID`, `192.168.1.100`) | 🟠 Majeur | Oui (après `git clone`) |
| **F-14** | Topics codés en dur (non alignables par env) | 🟡 Mineur | Non |
| **F-15** | `serializeJson()` : retour non vérifié → troncature possible du JSON publié | 🟡 Mineur | Non |
| **F-16** | Aucune journalisation d'erreur MQTT autre que `rc=%d` | 🟡 Mineur | Non |

---

## 6. Détail des corrections (à traiter en C.3 / C.4 / C.5)

### F-01 — Supprimer le pinout, isoler le matériel derrière des stubs

- Retirer les `#define PIN_*` de l'exécution (garder `PIN_LED_STATUS = 2`, seul
  pin connu et sûr).
- Retirer `ESP32Servo` de `lib_deps` (plus aucune dépendance servo).
- `setup()` ne fait plus aucun `pinMode`/`attach` de capteur ou de servo.
- Créer `src/hardware.h/.cpp` :

```cpp
// src/hardware.h
// TODO(Phase C-hardware) : le pinout définitif n'est pas connu.
// Ces stubs ne touchent AUCUNE broche : ils simulent le comportement.
// Ils seront remplacés par les vraies lectures/écritures quand le câblage
// sera fourni (voir docs/fiches-de-production/phase-C-firmware-audit.md §10).

bool hw_barrier_move(const char* gate, bool open);   // false = non câblé
bool hw_slot_read(int slot_id, bool& occupied);        // false = non câblé
bool hw_vehicle_present(const char* gate);             // false = non câblé
```

- Aucune dépendance **runtime** aux capteurs : le firmware reste fonctionnel
  (Wi-Fi + MQTT + barrière logique) sans aucun matériel.

### F-02 — Supprimer le blocage de mesure

- Supprimer `readDistanceCm` / `readDistanceMedianCm` / `measureOccupied` de
  `main.cpp` (ils passent dans `hardware.cpp` comme stubs inactifs).
- **Ne plus publier `parking/state`** tant que les capteurs n'existent pas :
  ne pas publier de donnée non mesurée (cf. TRAP 3 côté front).
  - Décision : la publication de `parking/state` est **conditionnée par un
    flag de compilation** `SMPARK_ENABLE_SENSORS` (défaut `0`), ce qui prépare
    la Phase C-hardware sans code supplémentaire.
- `parking/events` : idem, conditionné par le même flag.

### F-03 — Supprimer la lecture IR

- `updateIR()` est retiré de `loop()`.
- La publication de `parking/events` suit le même flag.

### F-04 — Découpler le callback MQTT de la publication

```
callback (interruption)          loop() (tâche de fond)
─────────────────────────         ───────────────────────────────────────
parser le JSON                    dépiler la commande
  ↓                                ↓
mémoriser (action, gate,           exécuter la machine à états
  correlation_id)                   ↓
  (RIEN d'autre)                    publier barrier/state
```

- Implémentation : une **file de commandes** de taille 1–2 (ou une simple
  variable « commande en attente »), consommée par `loop()`.
- Le callback ne fait **jamais** de `publish()`, **jamais** de `delay()`,
  **jamais** d'accès aux capteurs.

### F-05 / F-07 — Valider la commande reçue

```cpp
// action
const char* action = doc["action"] | "";   // pas de "none" implicite
if (!doc["action"].is<const char*>()) { /* commande invalide */ }
if (action != "open" && action != "close") { /* rejet → état idle + reason */ }

// gate
const char* gate = doc["gate"] | "";
if (gate != "entry" && gate != "exit") { /* rejet */ }

// correlation_id
const char* cid = doc["correlation_id"] | "";
if (strlen(cid) == 0) { /* commande rejetée : pas d'ACK possible */ }
```

Rejet → publier `barrier/state` avec `state:"idle"` et
`reason:"invalid_command"` (ou `unknown_action` / `invalid_json` selon le
cas), **sans `correlation_id`** (cf. F-06).

### F-06 — Ne jamais acquitter une erreur

Problème actuel : l. 248 mémorise le `correlation_id`, puis l. 256-257 publie
`idle` + `unknown_action` **avec** le `correlation_id` → le backend fait
basculer la commande de `pending` à **`acknowledged`** (`mqtt_handlers.handle_barrier_state`,
l. 238-241) → **la base affirme qu'une barrière a été ouverte alors que
rien ne s'est passé**.

Correction : le `correlation_id` n'est mis en file d'attente **qu'après**
validation complète de la commande. Toute commande rejetée est publiée **sans**
`correlation_id` → le backend ne l'acquitte pas → la commande reste `pending`
puis passe en `timeout` (le timeout de 5 s est le comportement correct).

### F-08 — Un état par barrière

```cpp
struct GateState {
  const char* gate;          // "entry" | "exit"
  BarrierPhase phase;
  unsigned long phaseSince;
  char correlationId[40];    // "" si aucun
};
GateState gates[2];          // entry, exit
```

- Chaque barrière a sa propre phase, son propre `correlation_id`, son propre
  servo (stub).
- Une commande `exit` n'affecte plus la séquence `entry` en cours.

### F-09 — `ts` ISO 8601

Deux options :
- **(a)** **Ne pas publier** `ts` (champ optionnel §D.2) → solution immédiate,
  zéro dépendance. ✔ **Retenu pour la Phase C.**
- **(b)** Synchroniser l'heure par NTP (`configTime()` + `time()`) → ~15
  lignes, mais l'ESP32 n'a pas d'horloge RTC avant la synchro NTP (donc `ts`
  inexistant au premier démarrage) et ajoute une dépendance réseau.
  *À reconsidérer en Phase C-hardware.*

### F-10 — Idempotence

Mémoriser le dernier `correlation_id` traité par barrière ; si un message
arrive avec le même `correlation_id`, l'ignorer (journaliser « doublon ignoré »).
Conforme à §F.1 (les consommateurs sont idempotents).

### F-11 — `clientId` conforme

```cpp
uint8_t mac[6]; ESP.getEfuseMac(mac);
snprintf(clientId, sizeof(clientId), "smpark-esp32-%02X%02X%02X%02X%02X%02X",
         mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
```
→ conforme §F.4, et unique même avec 2 ESP32 sur le même réseau.

### F-12 / F-16 — Journaliser les échecs

```cpp
if (!mqttClient.publish(TOPIC_BARRIER_STATE, buf, true)) {
  Serial.printf("[mqtt] échec publication %s\n", TOPIC_BARRIER_STATE);
}
```
Conforme à §F.5 (« aucun échec silencieux »).

### F-13 — Durcir `secrets.ini`

Constat vérifié : `extra_configs = secrets.ini` **ne fait pas échouer** le
build quand le fichier est absent. Le code de PlatformIO
(`platformio/project/config.py`, `ProjectConfig.read`) fait
`for item in glob.glob(pattern): self.read(item)` → un fichier introuvable
produit **zéro correspondance, sans erreur ni avertissement**.
Vérifié : `pio project config` sans `secrets.ini` s'exécute normalement et
n'ajoute **aucun** `-D` de build → le firmware compile avec :

```cpp
#define WIFI_SSID "CHANGE_ME_WIFI_SSID"
#define MQTT_HOST "192.168.1.100"
```

et **ne se connecte jamais**, sans message d'erreur explicite. C'est le piège
n°1 après un `git clone`.

Corrections :
1. `secrets.ini.example` déjà présent ✅ → le renommer clairement et ajouter un
   en-tête explicite.
2. Ajouter au firmware un **détecteur de configuration absente** :
   ```cpp
   #if defined(WIFI_SSID) && !defined(SMPARK_SECRETS_OK)
   // ...
   #endif
   ```
   → plus simple : comparer la valeur à la sentinelle `CHANGE_ME_...` au boot
   et afficher un bandeau d'erreur SERIAL clair + refuser de démarrer la
   connexion MQTT.
3. Ajouter `scripts/firmware/build.sh` (ou `make`) qui crée `secrets.ini` à
   partir de l'exemple s'il manque, puis lance `pio run`.

### F-14 — Topics paramétrables

Rendre les 4 topics surchargeables par `-D` (avec les valeurs du contrat en
défaut), pour que le firmware et le backend puissent être alignés sans
modifier le code :

```cpp
#ifndef TOPIC_BARRIER_COMMAND
#define TOPIC_BARRIER_COMMAND "parking/barrier/command"
#endif
```
et les définir dans `secrets.ini` (ou `platformio.ini`).

### F-15 — Vérifier la sérialisation

```cpp
size_t n = serializeJson(doc, buf, sizeof(buf));
if (n == 0) { Serial.println("[json] sérialisation vide"); return; }
if (n >= sizeof(buf)) { Serial.println("[json] payload tronqué"); }
```

---

## 7. Plan de correction minimal (ordonné par priorité)

| Ordre | Action | Corrige | Étape cible | Bloquant démo |
|---|---|---|---|---|
| 1 | Retirer le pinout, `ESP32Servo`, les `pinMode`/`attach` | F-01 | **C.2** | ✅ oui |
| 2 | Durcir `secrets.ini` + garde-fou au boot + script de build | F-13 | **C.2** | ✅ oui |
| 3 | Supprimer `pulseIn`/`delay`/IR ; `parking/state` & `parking/events` sous flag | F-02, F-03 | **C.3** | ✅ oui |
| 4 | Découpler callback ↔ publication (file de commandes) | F-04 | **C.3** | ✅ oui |
| 5 | Valider `action`/`gate`/`correlation_id` ; ne jamais acquitter une erreur | F-05, F-06, F-07 | **C.4** | non |
| 6 | Un état par barrière (`entry`/`exit`) | F-08 | **C.4** | non |
| 7 | `ts` : ne plus publier de `millis()` ; `uptime_ms` conservé | F-09 | **C.4** | non |
| 8 | Idempotence `correlation_id` | F-10 | **C.4** | non |
| 9 | `clientId` MAC complète ; topics paramétrables | F-11, F-14 | **C.2** | non |
| 10 | Vérifier `publish()` / `serializeJson()` ; logs d'erreur | F-12, F-15, F-16 | **C.3** | non |
| 11 | Stubs `hardware.h/.cpp` documentés | — | **C.5** | non |

> Les 4 actions marquées « ✅ oui » sont **préalables à toute démonstration** :
> sans elles, la démo affiche une occupation fausse et peut créer des visites
> fantômes.

---

## 8. Structure cible du firmware

```
firmware/esp32/
├── platformio.ini            (+ topic/sensor flags paramétrables)
├── secrets.ini.example       (inchangé + en-tête explicite)
├── src/
│   ├── main.cpp              setup() / loop() : orchestration, ~120 lignes
│   ├── config.h              topics, durées, drapeaux, lecture des -D
│   ├── wifi_link.h/.cpp      connexion Wi-Fi non bloquante
│   ├── mqtt_link.h/.cpp      connect / subscribe / publish + file de commandes
│   ├── barrier.h/.cpp        machine à états par barrière (entry/exit)
│   └── hardware.h/.cpp       STUBS (HC-SR04 / IR / servo) — aucun pinout
└── test/                     (README actuel ; tests unitaires natifs possibles)
```

**Pourquoi splitter ?** `main.cpp` fait aujourd'hui 414 lignes et mélange 5
responsabilités. Le découpage :
- rend le **contrat MQTT testable** isolément ;
- rend les **stubs** explicites (un seul fichier à remplacer en Phase C-hardware) ;
- est plus **défendable en soutenance** (« architecture en couches »).

**Coût** : 6 fichiers au lieu de 1, ~80 lignes de déclarations en plus.
**Bénéfice** : la Phase C-hardware ne touchera que `hardware.cpp` + `config.h`.

---

## 9. Séquence cible (mode logiciel, sans servo)

```
backend                     ESP32                          broker
   │                          │                              │
   │ publishes                │                              │
   ├─────────────────────────▶│  parking/barrier/command     │
   │  {action:"open",         │  {action,gate,correlation_id}│
   │   gate:"entry",          │                              │
   │   correlation_id:"3f1…"} │                              │
   │                          │ [callback] parse + validation│
   │                          │   ✗ invalide → idle, reason,  │
   │                          │     SANS correlation_id       │
   │                          │                              │
   │                          │ [loop] exécute la séquence    │
   │                          │   publish barrier/state      │
   │                          │   {state:"opening",           │
   │                          │    gate:"entry",              │
   │                          │    correlation_id:"3f1…"} ───┼──▶  ACK
   │                          │                              │
   │                          │   publish barrier/state      │
   │                          │   {state:"open", gate:"entry"}│  (sans correlation_id)
   │                          │                              │
   │                          │   publish barrier/state      │
   │                          │   {state:"closing"}           │
   │                          │                              │
   │                          │   publish barrier/state      │
   │                          │   {state:"closed"}            │
   │                          │                              │
   │◀──── WebSocket "barrier" ─┼──── barrier/state (retain) ──┤
   │      {ack_status:"acknowledged"}                        │
```

**Points clés**
- Un seul message porte le `correlation_id` : c'est **l'ACK** (§D.4).
- Les états suivants (`open`, `closing`, `closed`) sont publiés **sans**
  `correlation_id` → le backend ne les confond pas avec un nouvel ACK.
- Le heartbeat (5 s) est publié **sans** `correlation_id` → l'UI distingue
  « heartbeat » de « ACK » (TRAP 2 côté front).
- Si l'ESP32 ne répond pas, le backend bascule la commande en `timeout` après
  `BARRIER_ACK_TIMEOUT_SECONDS` (5 s) → l'UI affiche « pas d'acquittement ».

---

## 10. Stratégie Phase C-hardware (préparée, non exécutée)

Le fichiers `hardware.cpp` sera le **seul** fichier à modifier quand le câblage
sera connu :

| Stub actuel | Phase C-hardware | Informations nécessaires |
|---|---|---|
| `hw_barrier_move(gate, open)` | `servo.attach(pin)` + `write(angle)` | PIN servo entry / exit, angles ouvert/fermé,_source d'alimentation |
| `hw_slot_read(id, occupied)` | `pulseIn` **non bloquant** (ou `esp_timer` + ISR) | PIN TRIG/ECHO des 3 HC-SR04, seuil de détection |
| `hw_vehicle_present(gate)` | lecture IR + anti-rebond | PIN IR entry / exit, niveau actif (Haut/Bas) |

Plus, dans `config.h` : les `#define PIN_*` correspondants, et le flag
`SMPARK_ENABLE_SENSORS` passé à `1`.

---

## 11. Risques de la démo (rappel)

| Risque | Cause | Traitement |
|---|---|---|
| UI affiche une occupation **fausse** | `parking/state` publié sans capteur | F-02 (ne plus publier) |
| Historique pollution par des **visites fantômes** | IR sur entrées flottantes | F-03 |
| Commandes reçues **en retard** / ACK hors délai | `pulseIn` bloquant | F-02 |
| Trame MQTT **corrompue** (intermittent) | publish dans le callback | F-04 |
| Base de données : commande marquée `acknowledged` à tort | état d'erreur porteur du `correlation_id` | F-06 |
| ESP32 **ne se connecte pas** après un `git clone` | `secrets.ini` manquant + fallback silencieux | F-13 |
| ESP32 **ne démarre pas** si un servo est branché sur 12/13 | broches de strapping | F-01 |

---

## 12. Découpage C.2 → C.6 (rappel, avec livrables vérifiables)

| Étape | Contenu | Livrable vérifiable |
|---|---|---|
| **C.1** | Audit (ce document) | ✅ ce document, validé |
| **C.2** | Config & secrets (`secrets.ini.example`, garde-fou, topics paramétrables, retrait du pinout mort) | `pio run` passe, aucun `PIN_*` capteur/servo dans le code |
| **C.3** | MQTT robuste non bloquant (file de commandes, plus de `publish` dans le callback, plus de `delay`) | `loop()` sans blocage, commande reçue → ACK publié |
| **C.4** | Alignement strict au contrat (validation `action`/`gate`/`correlation_id`, idempotence, `ts`, `clientId`) | `mosquitto_sub` montre exactement la séquence attendue |
| **C.5** | Stubs hardware documentés (`hardware.h/.cpp`, TODO pinout) | aucune dépendance runtime aux capteurs |
| **C.6** | Tests firmware + fiche Phase C | `docs/fiches-de-production/phase-C-firmware-mqtt.md` + `docs/tests/phase-C-tests-firmware-mqtt.md` |

---

## 13. Hors scope (Phase C)

- Pinout définitif, câblage, branchement physique des capteurs/servos.
- Lecture réelle des distances, lecture IR réelle, mouvement réel des servos.
- TLS MQTT, MQTT 5, multi-ESP32 / multi-parking.
- OTA (mise à jour du firmware sans fil), deep sleep / gestion d'énergie.
- Tests unitaires natifs PlatformIO (possibles, mais hors périmètre de la
  version actuelle : la vérification se fera par `pio run` + `pio monitor` +
  `mosquitto_sub`).

---

## 14. Checklist de validation de l'étape C.1

- [x] Fichiers audités lus intégralement (`main.cpp`, `platformio.ini`, `secrets.ini*`).
- [x] Ce qui fonctionne est listé et sera **conservé** (15 points ✅).
- [x] Tous les blocages sont quantifiés (`pulseIn` ≈ 525 ms/cycle, `publish` dans le callback).
- [x] Le pinout inventé est analysé (risques de strapping GPIO 12/13/14).
- [x] Les 7 écarts au contrat MQTT sont référencés **par section du contrat** (§C, §D.2–D.4, §F).
- [x] 16 écarts numérotés (F-01 → F-16) avec gravité et impact.
- [x] Plan de correction minimal **ordonné par priorité** et rattaché aux étapes C.2 → C.5.
- [x] Structure cible du firmware proposée (6 modules) et justification.
- [x] Séquence ACK cible schématisée.
- [x] Stratégie Phase C-hardware préparée (un seul fichier à modifier).
- [x] Risques de démo listés.
- [ ] **Validation de l'utilisateur** (point d'arrêt demandé).
