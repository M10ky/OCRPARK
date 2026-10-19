# Contrat MQTT SM-Park

**Source de vérité unique** pour tous les échanges MQTT entre l'ESP32, le backend
FastAPI et le broker Eclipse Mosquitto. Tout code (backend, firmware, simulateur,
scripts) doit s'y conformer. En cas de divergence, ce document prévaut.

## A. Vue d'ensemble

```
      +--------------------+                                    +----------------+
      |  ESP32 /           |   parking/state      (retain, QoS1) |  Backend       |
      |  simulateur        |   -------------------------------->  |  FastAPI       |
      |  (barrière +       |   parking/events     (QoS1)         |                |
      |   capteurs)        |   -------------------------------->  |  - décide      |
      |                    |   barrier/state      (retain, QoS1) |  - publie      |
      |                    |   -------------------------------->  |  - historise   |
      |                    |                                     |                |
      |                    |   parking/barrier/command (QoS1)    |                |
      |                    |   <-------------------------------- |                |
      +--------------------+                                    +----------------+
                \                                                      /
                 \----------------- Eclipse Mosquitto ---------------/
```

Principe : le backend **décide**, l'ESP32 **exécute** et **rend compte**. L'ESP32
**mesure** l'occupation et publie les événements de passage.

## B. Règles de nommage

| Règle | Valeur |
|---|---|
| Style | minuscules, segments séparés par `/`, sans espaces ni accents |
| Racine | **sans préfixe projet** (pas de `smpark/`) |
| Barrière | `parking/barrier/command` (backend → ESP32) ; `barrier/state` (ESP32 → backend) |
| Occupation | `parking/state` (ESP32 → backend) |
| Événements | `parking/events` (ESP32 → backend) |
| `gate` | toujours `entry` ou `exit` (enum `VALID_GATES`, `orchestrator.py:18`) |
| `correlation_id` | UUID v4 sous forme de chaîne ; identifie une commande et son ACK |
| Payload | JSON UTF-8, racine = objet `{...}` |

## C. Topics (source de vérité)

| Topic | Direction | QoS | Retain | Contenu |
|---|---|---|---|---|
| `parking/state` | ESP32 → backend | 1 | **true** | Occupation des places |
| `parking/events` | ESP32 → backend | 1 | false | Entrée / sortie détectée |
| `parking/barrier/command` | backend → ESP32 | 1 | false | Ordre d'ouverture/fermeture |
| `barrier/state` | ESP32 → backend | 1 | **true** | État barrière + ACK corrélé |

### Justification QoS / retain
- **QoS 1** partout : on ne perd ni une commande d'ouverture ni un événement. Les
  consommateurs sont **idempotents** (un doublon QoS 1 avec le même `correlation_id`
  est ignoré).
- **retain=true** sur `parking/state` et `barrier/state` : le backend connaît le
  dernier état dès la (re)connexion, sans attendre le prochain message.
- **retain=false** sur commande et événements : messages instantanés ; un retain
  ferait rouvrir la barrière ou rejouer un événement au redémarrage.

## D. Spécification des payloads

### D.1 `parking/state` — ESP32 → backend (retain=true, QoS 1)
```json
{
  "slots": [
    { "id": 1, "occupied": true },
    { "id": 2, "occupied": false }
  ]
}
```
| Champ | Requis | Description |
|---|---|---|
| `slots` | oui | tableau d'objets `{ "id": int ≥ 1, "occupied": bool }` |

> Ancienne forme `{"slot":1,"occupied":true}` **abandonnée** (voir `docs/tests/phase-2-*`).

### D.2 `parking/events` — ESP32 → backend (retain=false, QoS 1)
```json
{ "type": "entry", "gate": "entry", "ts": "2026-01-01T00:00:00Z", "plate": "AB123CD" }
```
| Champ | Requis | Description |
|---|---|---|
| `type` | oui | `"entry"` ou `"exit"` |
| `gate` | oui | `"entry"` ou `"exit"` |
| `ts` | non | horodatage ISO 8601 UTC |
| `plate` | non | plaque normalisée (Phase D) : renseigne directement la visite ; si absente, le backend rattache le dernier passage autorisé du portail |

### D.3 `parking/barrier/command` — backend → ESP32 (retain=false, QoS 1)
```json
{
  "action": "open",
  "gate": "entry",
  "correlation_id": "3f1c2c9e-2a7b-4b0e-9f5e-2d3a4b5c6d7e",
  "plate": "AB123CD",
  "reason": "Plaque autorisée",
  "source": "orchestrator:upload"
}
```
| Champ | Requis | Description |
|---|---|---|
| `action` | oui | `"open"` ou `"close"` |
| `gate` | oui | `"entry"` ou `"exit"` |
| `correlation_id` | oui | UUID du passage (`orchestrator.py:71`) |
| `plate` | non | plaque normalisée |
| `reason` | non | motif lisible |
| `source` | non | `orchestrator:upload` / `orchestrator:scan` |

> Phase A : l'orchestrateur n'émet que `action:"open"`. `"close"` est réservé à une
> fermeture automatique ultérieure ; à garder symétrique dans le firmware.

### D.4 `barrier/state` — ESP32 → backend (retain=true, QoS 1)
```json
{
  "state": "opening",
  "gate": "entry",
  "correlation_id": "3f1c2c9e-2a7b-4b0e-9f5e-2d3a4b5c6d7e",
  "reason": "command",
  "uptime_ms": 123456
}
```
| Champ | Requis | Description |
|---|---|---|
| `state` | oui | `online`, `offline` (Last Will), `idle`, `opening`, `open`, `closing`, `closed` |
| `gate` | non | `entry` / `exit` (défaut `entry`) |
| `correlation_id` | oui si ACK | repris **à l'identique** de la commande |
| `reason` | non | `command`, `invalid_json`, `unknown_action`, ... |
| `uptime_ms` | non | `millis()` à la publication |

L'ACK est le **premier** `barrier/state` publié en réaction à une commande, portant le
même `correlation_id`. Sans `correlation_id`, le message n'est **pas** un ACK
(heartbeat ou changement d'état spontané).

## E. Mapping API ↔ MQTT ↔ firmware simulé

| Action API | Topic publié | Consommateur | Réponse attendue |
|---|---|---|---|
| `POST /api/orchestrate/upload` (autorisée) | `parking/barrier/command` `{action:open, gate, correlation_id}` | ESP32 / `barrier_sim.sh` | `barrier/state` `opening→open→closing→closed` avec **même** `correlation_id` |
| `POST /api/orchestrate/scan` (autorisée) | idem | idem | idem |
| `POST /api/orchestrate/*` (refusée) | *aucun publish* (décision `deny` persistée) | — | — |
| ESP32 détecte un véhicule | `parking/events` | backend (relais WebSocket) | — |
| ESP32 cycle capteurs places | `parking/state` | backend | — |
| `GET /api/passages`, `/stats`, `/health` | *aucun MQTT* | — | — |

## F. Règles transverses
1. **Idempotence** : tolérer un doublon QoS 1 (même `correlation_id`).
2. **Routage par gate** : un ESP32 multi-barrières ignore la commande destinée à l'autre.
3. **Authentification obligatoire** (`allow_anonymous false`).
4. **Client IDs uniques** : backend `smpark-backend` ; ESP32 `smpark-esp32-<MAC>` ;
   simulateur `smpark-sim-<pid>`.
5. **Aucun échec silencieux** : `mqtt_client.publish` retourne `False` si non connecté
   (`mqtt.py:109-123`) et l'orchestrateur le journalise.
6. **Traçabilité** : `correlation_id` = UUID du `Passage`, persisté *avant* publication
   (jamais de barrière ouverte sans trace, `orchestrator.py:88-103`).

## G. Variables d'environnement (source unique)
`backend/app/core/config.py:35-38` + `.env.example:40-43` :
```
MQTT_TOPIC_PARKING_STATE=parking/state
MQTT_TOPIC_PARKING_EVENTS=parking/events
MQTT_TOPIC_BARRIER_COMMAND=parking/barrier/command
MQTT_TOPIC_BARRIER_STATE=barrier/state
```

## H. Exemples de vérification
```bash
# S'abonner à tout
docker compose exec mqtt-broker mosquitto_sub -h localhost -p 1883 \
  -u smpark -P change_me_mqtt -t '#' -v

# Événement d'entrée
mosquitto_pub -h localhost -p 1883 -u smpark -P change_me_mqtt -t parking/events -q 1 \
  -m '{"type":"entry","gate":"entry","ts":"2026-01-01T00:00:00Z"}'

# Occupation (retain)
mosquitto_pub -h localhost -p 1883 -u smpark -P change_me_mqtt -t parking/state -q 1 -r \
  -m '{"slots":[{"id":1,"occupied":true},{"id":2,"occupied":false}]}'

# Commande barrière
mosquitto_pub -h localhost -p 1883 -u smpark -P change_me_mqtt -t parking/barrier/command -q 1 \
  -m '{"action":"open","gate":"entry","correlation_id":"test-1"}'
```

## I. Conformité et limitations connues
Aligné en Phase A :
- Backend : souscription/publication en **QoS 1**, commande `retain=false` (`mqtt.py`).
- Firmware : écho du `correlation_id` dans le premier `barrier/state` (ACK), `retain=true`.
- `barrier_sim.sh` : écho `correlation_id` + production `parking/events` et
  `parking/state` (retain).

Limitations assumées :
- **PubSubClient (ESP32) ne publie qu'en QoS 0** : le firmware émet ses états en QoS 0
  (retain activé). Le backend tolère cette dégradation (idempotence).
- Le firmware réel **ne produit pas encore** `parking/state` / `parking/events`
  (capteurs matériels requis) : produit par le simulateur en Phase A, par le
  firmware matériel en Phase D.
- L'orchestrateur n'émet que `action:"open"` (pas de `close` automatique).
