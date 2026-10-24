# Tuto de test — Phase C : Firmware MQTT

> Objectif : vérifier le firmware ESP32 **sans matériel** (tests natifs + contrat
> MQTT), puis le chemin réel de l'ESP32 via l'IP LAN.
> Contrat de référence : [`docs/mqtt-contract.md`](../mqtt-contract.md).
> Failles corrigées : [`docs/fiches-de-production/phase-C-firmware-audit.md`](../fiches-de-production/phase-C-firmware-audit.md).

## 0. Prérequis

```bash
cd /home/miokrako/SM-Park
docker compose up -d --build     # stack complète

cp firmware/esp32/secrets.ini.example firmware/esp32/secrets.ini
# MQTT_HOST = IP LAN DU PC qui héberge le broker (ici : 192.168.1.104)
```

> `secrets.ini` est **gitignoré**. PlatformIO ignore silencieusement un
> `extra_configs` manquant : le firmware se compilerait alors avec des
> sentinelles `CHANGE_ME_*` et ne se connecterait jamais (F-13).

## 1. Compilation

```bash
bash scripts/firmware/build.sh
```

**Attendu** : `SUCCESS`, RAM ~14 %, Flash ~61 %, et les lignes de compilation
contiennent `-DSMPARK_ENABLE_SENSORS=1 -DSMPARK_ENABLE_SERVOS=1`
(vérifiable via `pio run -v`).

**Ce que vous apprenez** : `build_src_flags` (drapeaux fonctionnels) et
`build_flags` (secrets) cohabitent sans s'écraser : les secrets restent dans
`secrets.ini`, les fonctions dans `platformio.ini`.

## 2. Tests natifs du firmware (machine hôte, sans ESP32)

```bash
bash scripts/test_firmware_logic.sh
```

**Attendu** : `36 verifications, 0 echec(s)` / `RESULTAT: OK`.

Détail des 5 groupes :

| Groupe | Ce qui est vérifié |
|---|---|
| Validation des commandes | gate inconnu/null → `invalid_gate` ; action inconnue → `unknown_action` ; `correlation_id` vide → `missing_correlation_id` |
| Commande invalide | **aucun** servo déclenché, phase `idle`, aucun `correlation_id` mémorisé (F-05/F-07) |
| Séquence valide | `opening → open → closing → closed` + servo ouvert/fermé + **ACK unique** (correlation_id consommé) |
| Isolation par barrière | une commande `exit` ne touche **jamais** l'état ni le servo `entry` (F-08) |
| Noms de phases | `idle`/`opening`/`open`/`closing`/`closed` (contrat §D.4) |

**Ce que vous apprenez** : on peut tester la **logique pure** d'un firmware sur
la machine hôte, avec un mock Arduino minimal (`test/mocks/Arduino.h`) et un
stub de la couche matérielle — sans flasher, sans PlatformIO native.

> Le compilateur a d'ailleurs détecté un **vrai bug** pendant la mise au point :
> une comparaison de pointeurs `const char*` au lieu de `strcmp`
> (`barrier.cpp`).

## 3. Round-trip MQTT du chemin ESP32 (IP LAN)

```bash
bash scripts/test_connections.sh
```

**Attendu** : `27 OK, 0 FAIL, 0 SKIP`, dont la section « ESP32 → broker » :

- le broker est joignable sur l'**IP LAN** (le chemin réel de l'ESP32) ;
- la publication de `parking/state` est acceptée au format `slots[]` ;
- le payload est livré sur un topic de scratch ;
- la commande `parking/barrier/command` est transmise au format attendu.

**Ce que vous apprenez** : l'ESP32 ne passe jamais par `localhost` : il doit
viser l'IP LAN du PC hôte. Le test compare donc le chemin `lo` et le chemin
`192.168.x.x` pour éviter un faux positif.

## 4. Contrat WebSocket (effet de bord firmware)

```bash
bash scripts/test_ws_events.sh
```

**Attendu** : `6 OK, 0 FAIL` (snapshot / `slots` / `barrier` relayés).

## 5. Smoke test de bout en bout

```bash
bash scripts/smoke_test.sh
```

**Attendu** : `13 OK, 0 FAIL, 0 SKIP`.

## 6. Observez le trafic MQTT

```bash
docker compose exec -T mqtt-broker mosquitto_sub -h localhost -p 1883 \
  -u smpark -P change_me_mqtt -t '#' -v
```

Topics attendus (contrat §C) : `parking/state` (retain),
`parking/events` (sans retain), `barrier/state` (retain),
`parking/barrier/command`.

## 7. Simulation sans ESP32

```bash
docker compose exec -T mqtt-broker sh -s < scripts/barrier_sim.sh
```

Le simulateur joue le rôle du firmware : il écoute `parking/barrier/command` et
publie la séquence d'états sur `barrier/state` en écho du `correlation_id`.

> Une commande invalide ne produit **pas** d'ACK (pas de `correlation_id` sur
> `reason: unknown_action`) : c'est la règle F-07, désormais respectée aussi
> par le simulateur.

## 8. Flash réel (si un ESP32 est disponible)

```bash
bash scripts/firmware/upload.sh    # pio run -t upload
bash scripts/firmware/monitor.sh   # moniteur série 115200
```

**Attendu au boot** :

```
SM-Park ESP32 boot
[config] Wi-Fi + MQTT configures : OK
[config] broker MQTT : 192.168.1.104:1883
[wifi] connexion...
[mqtt] connecte
```

Puis, toutes les ~5 s, le heartbeat `barrier/state` et `parking/state`.

## 9. Dépannage

| Symptôme | Cause probable |
|---|---|
| `[config] CONFIGURATION INCOMPLETE` au boot | `secrets.ini` absent ou sentinelles `CHANGE_ME_*` (F-13) |
| `[mqtt] echec rc=-2` | broker injoignable sur l'IP LAN (`MQTT_HOST` mal renseigné) |
| `[cmd] invalide` en boucle | backend publie un `gate`/`action` non conforme au contrat |
| ESP32 ne démarre pas | broche de strapping (GPIO 12/13/14) tirée au boot par un servo |
| Tests natifs ne compilent pas | `g++` absent du PATH (`sudo apt install g++`) |
