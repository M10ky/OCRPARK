# Contrat WebSocket — SM-Park

Source de vérité des événements temps réel diffusés par le backend sur
`/ws/events` (Phase D). Le format est **stable** : le frontend peut s'y fier.

## Connexion

- URL : `ws://<backend>/ws/events` (ou `wss://` derrière un reverse-proxy TLS).
- Authentification : `?token=<JWT>` **optionnel**. Si fourni et invalide → fermeture
  code `4401`. Si absent → accepté uniquement quand `WS_REQUIRE_AUTH=false`
  (défaut dev) ; en production `WS_REQUIRE_AUTH=true` exige un token valide.
- À la connexion, le serveur envoie **immédiatement** un événement `snapshot`.
- Ensuite, chaque fait métier produit un événement (voir tableau).

## Enveloppe (tous les événements)

```json
{ "type": "<event>", "payload": { ... }, "ts": "<ISO-8601 UTC>" }
```

## Types d'événements

| `type` | Déclencheur | `payload` |
|---|---|---|
| `snapshot` | connexion WS | `{ "slots": <slots>, "visits": [<visit>…], "barrier": <barrier\|null> }` |
| `slots` | `parking/state` (changement d'occupation) | `<slots>` |
| `visit` | `parking/events` (entry/exit) | `<visit>` |
| `passage` | fin d'orchestration OCR→décision | décision (voir plus bas) |
| `barrier` | `barrier/state` (ACK/heartbeat) ou timeout | `<barrier>` |
| `mqtt` | topic MQTT non routé (fallback debug) | `{ "topic": str, "payload": any }` |

### Objets

`<slots>` :
```json
{ "slots": [ { "id": 1, "occupied": true }, { "id": 2, "occupied": false } ],
  "total": 2, "occupied": 1, "free": 1 }
```

`<visit>` :
```json
{ "id": "…", "plate": "AB123CD", "entry_gate": "entry", "exit_gate": null,
  "status": "inside", "entry_at": "2026-10-19T12:00:00+00:00", "exit_at": null }
```

`<barrier>` :
```json
{ "state": "opening", "gate": "entry", "reason": "command",
  "correlation_id": "…", "ack_status": "acknowledged", "ts": "…" }
```
- `ack_status` vaut `pending` (commande publiée), `acknowledged` (ACK reçu),
  `timeout` (aucun ACK dans `BARRIER_ACK_TIMEOUT_SECONDS`) ou `barrier_ack_status` (voir `passage`).
- Sur timeout, `state` est `null` et `action` est présent.

`passage` (décision d'orchestration) :
```json
{ "id": "…", "plate": "AB123CD", "recognized": true, "confidence": 0.92,
  "authorized": true, "allowed": true, "action": "open", "gate": "entry",
  "barrier_command_sent": true, "barrier_action": "open",
  "barrier_ack_status": "pending", "total_slots": 3, "free_slots": 2,
  "reason": "Plaque autorisée", "source": "orchestrator:upload",
  "correlation_id": "…", "detections": null }
```

## Exemples

Snapshot à la connexion :
```json
{ "type": "snapshot",
  "payload": { "slots": { "slots": [ {"id":1,"occupied":false} ], "total":1, "occupied":0, "free":1 },
               "visits": [], "barrier": null },
  "ts": "2026-10-19T12:00:00+00:00" }
```

Changement d'occupation :
```json
{ "type": "slots",
  "payload": { "slots": [ {"id":1,"occupied":true} ], "total":1, "occupied":1, "free":0 },
  "ts": "2026-10-19T12:00:05+00:00" }
```

## Règles

- Un événement est diffusé **après** la persistance en base (pas de fait fantôme).
- Un client WebSocket défaillant est déconnecté sans impacter les autres ni la
  boucle MQTT.
- Le format ne change pas sans mise à jour de ce document (source de vérité).
- Le backend n'est abonné qu'aux topics du contrat MQTT (`parking/state`,
  `parking/events`, `barrier/state`) ; l'événement `mqtt` ne se déclenche donc que
  pour un topic **abonné mais non routé** (réservé aux évolutions futures).
