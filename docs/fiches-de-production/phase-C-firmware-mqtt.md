# Fiche de Production — Phase C : Firmware MQTT

- **Nom de la phase** : Phase C – Firmware ESP32 (Wi-Fi, MQTT, barrière,
  capteurs).
- **Objectif** : livrer un firmware structuré, conforme au contrat MQTT, avec
  **servos et capteurs réels conservés**, sans `publish()` ni `delay()` bloquant
  dans le callback.
- **Date** : 2026-10-22.
- **Périmètre** : configuration durcie, couche Wi-Fi/MQTT/barrière/matérielle,
  horodatage ISO-8601, idempotence, tests natifs.
- **Hors scope** : câblage physique (broches 12/13/14 = strapping), TLS MQTT,
  OTA, Phase D (OCR/caméra).
- **Référence** : `docs/mqtt-contract.md` (contrat) et
  `docs/fiches-de-production/phase-C-firmware-audit.md` (audit F-01 → F-16,
  avec addendum « matériel réel et conservé »).

## Étapes réalisées

| Étape | Contenu | Statut |
|---|---|---|
| C.1 | Audit firmware (F-01→F-16) + addendum matériel réel | fait |
| C.2 | `config.h` durci + `platformio.ini` + `secrets.ini.example` + scripts | fait |
| C.3 | Restructuration en couches + hardware réel non bloquant | fait |
| C.4 | Validation stricte des commandes, ACK unique, horodatage, tests natifs | fait |
| C.5 | Documentation finale (cette fiche + tuto de test + index) | fait |

## Structure du firmware

```
firmware/esp32/
├── platformio.ini            # extra_configs = secrets.ini ; build_src_flags
├── secrets.ini.example       # modèle (secrets.ini est gitignoré)
└── src/
    ├── main.cpp              # orchestration (~150 lignes) : setup/loop
    ├── config.h              # topics, pinout, temporisations, garde-fou boot
    ├── command.h/.cpp        # validation des commandes (libc seule)
    ├── barrier.h/.cpp        # machine à états PAR PORTE (entry / exit)
    ├── mqtt_link.h/.cpp      # client MQTT + file de commandes (F-04)
    ├── wifi_link.h/.cpp      # connexion Wi-Fi non bloquante
    ├── time_util.h/.cpp      # horodatage ISO-8601 UTC via NTP (F-09)
    └── hardware.h/.cpp       # HC-SR04 (machine à états), IR, servos
```

**Pourquoi splitter ?** `main.cpp` mélangeait 5 responsabilités et faisait 414
lignes. Le découpage rend le **contrat MQTT testable isolément** (tests natifs
hôte) et laisse la Phase hardware ne toucher que `hardware.cpp` + `config.h`.

## Corrections apportées (audit F-01 → F-16)

| Réf. | Faille | Correction |
|---|---|---|
| F-02 | `pulseIn` bloquant (~525 ms/cycle) | machine à états HC-SR04 non bloquante, round-robin |
| F-04 | `publish()` dans le callback MQTT | file de commandes : le callback **parse et mémorise seulement** |
| F-05 | action non validée | validation stricte (`command.h`) : `open`/`close` |
| F-06 | gate non validé | validation stricte : `entry`/`exit` |
| F-07 | ACK d'une erreur | **aucun** `correlation_id` sur erreur (le backend voit un timeout) |
| F-08 | un seul état pour 2 barrières | `BarrierController` : état indépendant entry/exit |
| F-09 | `ts` en `millis()` | NTP + ISO-8601 UTC (`time_util.cpp`) |
| F-10 | pas d'idempotence | garde anti-doublon sur `correlation_id` (ré-ACK sans rouvrir) |
| F-11 | `clientId` 16 bits | `smpark-esp32-<MAC>` complète |
| F-12 | `publish()` retour ignoré | vérification + `Serial.println` en cas d'échec |
| F-13 | `secrets.ini` absent ⇒ sentinelles | garde-fou `configIsValid()` au boot + `scripts/firmware/build.sh` |
| F-14 | topics codés en dur | surchargeables via `-DTOPIC_...` dans `secrets.ini` |
| F-15 | `serializeJson()` non vérifié | contrôle de la taille + refus de publier si tronqué |
| F-16 | aucun log d'erreur | logs MQTT/Wi-Fi explicites |

**Non traités ici** (hors firmware) : F-01 (pinout à confirmer avec le câblage
réel — les broches 12/13/14 sont des broches de strapping), F-03 (IR non
confirmé — le code utilise `INPUT_PULLUP` par sécurité).

## Configuration

Les identifiants Wi-Fi/MQTT viennent de `firmware/esp32/secrets.ini`
(gitignoré) et sont injectés en `-D` par PlatformIO.

```bash
cp firmware/esp32/secrets.ini.example firmware/esp32/secrets.ini
# renseigner WIFI_SSID, WIFI_PASSWORD, MQTT_HOST (IP LAN du PC), MQTT_PASSWORD
```

**Garde-fou** : si une sentinelle `CHANGE_ME_*` subsiste, `configLogStatus()`
affiche le correctif au boot et le firmware **refuse de se connecter** (F-13).

## Checklist de validation

| Vérification | Commande | Attendu |
|---|---|---|
| Compilation | `bash scripts/firmware/build.sh` | `SUCCESS` (RAM ~14 %, Flash ~61 %) |
| Drapeaux appliqués | log `pio run` | `-DSMPARK_ENABLE_SENSORS=1 -DSMPARK_ENABLE_SERVOS=1` |
| Tests natifs (hôte) | `bash scripts/test_firmware_logic.sh` | 36 OK, 0 FAIL |
| Round-trip MQTT firmware | `bash scripts/test_connections.sh` | 27 OK, 0 FAIL, 0 SKIP |
| Contrat WS | `bash scripts/test_ws_events.sh` | 6 OK, 0 FAIL |
| Smoke test | `bash scripts/smoke_test.sh` | 13 OK, 0 FAIL, 0 SKIP |

## Tests natifs (sans ESP32)

`scripts/test_firmware_logic.sh` compile `command.cpp` + `barrier.cpp` avec un
mock Arduino (`test/mocks/Arduino.h`) et vérifie le **contrat** :

- validation stricte de la commande (gate/action/correlation_id) ;
- aucune dérive de servo et aucun ACK sur une commande invalide ;
- séquence `opening → open → closing → closed` ;
- indépendance entry/exit (F-08) ;
- ACK unique (correlation_id repris à l'identique puis consommé).

> Les entrées/sorties matérielles réelles (HC-SR04, IR, servo) ne sont pas
> couvertes ici : elles exigent un ESP32 sur le bureau.

## Risques restants

| Risque | Impact | Atténuation |
|---|---|---|
| Câblage physique non confirmé | ESP32 peut ne pas démarrer si un servo tire un pin de strapping | migration des servos vers GPIO 18/19/21 (voir `config.h`) |
| Pas de flash réel dans l'CI | comportement matériel non vérifié automatiquement | test manuel via `scripts/firmware/upload.sh` + `monitor.sh` |
| NTP indisponible | `ts` omis des événements (champ optionnel du contrat) | `uptime_ms` reste la référence |

## Prochaine phase

**Phase D** (backend live, WebSocket, orchestration) : voir
`docs/fiches-de-production/phase-D-backend-live.md`.
