# Fiche de Production — Phase B : Frontend métier

- **Nom de la phase** : Phase B – Frontend Next.js métier (auth, dashboard
  temps réel, historique, CRUD plaques, orchestration).
- **Objectif** : livrer l'interface web de supervision du parking, branchée sur
  l'API REST et le WebSocket temps réel du backend.
- **Date** : 2026-10-22.
- **Périmètre** : session JWT, dashboard live (places / barrière / véhicules /
  journal), historique, CRUD des plaques, déclenchement de l'orchestration.
- **Hors scope** : OCR embarqué côté navigateur, upload webcam (le backend
  répond `503` sans caméra), TLS MQTT, multi-parking.
- **Référence** : `docs/fiches-de-production/phase-B-frontend-architecture.md`
  (décisions DA-1 → DA-8), `docs/websocket-contract.md`,
  `docs/mqtt-contract.md`.

## Étapes réalisées

| Étape | Contenu | Statut |
|---|---|---|
| B.1 | Architecture frontend (décisions DA-1→DA-8, pièges, arborescence, types) | validée |
| B.2 | Auth + coquille applicative (login, session JWT, layout, primitives UI) | fait |
| B.3 | Dashboard temps réel (WebSocket unique, snapshot, journal 100 entrées) | fait |
| B.4 | Historique, CRUD plaques, orchestration | fait |
| B.5 | Tests de connexion inter-conteneurs + contrat WS + smoke test | fait |
| B.6 | Documentation finale (cette fiche + tuto de test + index) | fait |

## Décisions d'architecture (rappel)

| Réf. | Décision | Justification |
|---|---|---|
| DA-1 | Navigateur → backend en direct | pas de proxy Next.js, CORS restreint à `http://localhost:3000` |
| DA-2 | JWT en `localStorage` + garde React | simplicité de démo ; validation par `/api/auth/me` |
| DA-3 | Un seul WebSocket (`LiveProvider`) | évite N connexions ; journal unique |
| DA-4 | Pas de Zustand / SWR / React Query / MUI | React context + Tailwind suffisent |
| DA-5 | Pages authentifiées en `"use client"` | la session vit dans le navigateur |
| DA-6 | `NEXT_PUBLIC_*` figées au build | lues statiquement dans `lib/config.ts` |
| DA-7 | Tailwind v4 (CSS-first) | pas de `tailwind.config.js` |
| DA-8 | Vitest + script bash d'intégration | tests unitaires rapides + tests bout-en-bout réels |

## Fichiers créés / modifiés

### Configuration & types
| Fichier | Rôle |
|---|---|
| `frontend/src/lib/config.ts` | `API_BASE_URL`, `WS_URL`, `PARKING_NAME` (lues au build) |
| `frontend/src/lib/types.ts` | types alignés sur les schémas Pydantic du backend |
| `frontend/src/lib/api.ts` | wrapper HTTP : `ApiError`, form-urlencoded (login), multipart (upload), purge 401 |

### Session & temps réel
| Fichier | Rôle |
|---|---|
| `components/providers/AuthProvider.tsx` | JWT `localStorage`, validation `/api/auth/me`, purge sur 401 |
| `components/providers/LiveProvider.tsx` | WebSocket unique : snapshot REST initial, backoff 1→10 s, ping 25 s, code `4401` ⇒ `logout()` |
| `hooks/useAuth.ts` / `hooks/useLive.ts` | points d'entrée publics des contextes |

### Interface
| Fichier | Rôle |
|---|---|
| `components/ui/{Card,Button,Input,Badge}.tsx` | primitives UI (Tailwind) |
| `components/layout/{RequireAuth,AppShell}.tsx` | garde d'authentification + coquille |
| `components/dashboard/{SlotGrid,BarrierPanel,EventLog}.tsx` | places, barrière, journal |
| `app/login/page.tsx` | formulaire de connexion (rendu serveur, `next` lu à la soumission) |
| `app/(app)/layout.tsx` | `RequireAuth` + `LiveProvider` autour des pages privées |
| `app/(app)/dashboard/page.tsx` | KPI + vues live |
| `app/page.tsx` | redirection `/` → `/dashboard` |
| `app/layout.tsx`, `app/globals.css` | racine Next.js + Tailwind v4 |

## Pièges backend gérés (faits constatés)

| # | Piège | Traitement |
|---|---|---|
| 1 | Login en `application/x-www-form-urlencoded`, pas JSON | `api.login()` utilise `form:` |
| 2 | `GET /api/slots` renvoie `label`/`updated_at`, l'événement WS `slots` non | `Slot.label`/`updated_at` optionnels (`types.ts`) |
| 3 | `ack_status: null` = heartbeat, **pas** un ACK | l'UI n'affiche « acquitté » que sur `ack_status` non nul |
| 4 | CRUD plaques par UUID | `api.ts` sérialise l'`id` complet |
| 5 | OCR/caméra absents ⇒ `503` | message explicite, pas de crash |
| 6 | CORS limité à `http://localhost:3000` | variables `NEXT_PUBLIC_*` alignées |
| 7 | `NEXT_PUBLIC_*` figées au build | lues statiquement, jamais par index dynamique |

## Checklist de validation

| Vérification | Commande | Attendu |
|---|---|---|
| Lint | `cd frontend && npm run lint` | aucune erreur |
| Build | `cd frontend && npm run build` | compilation OK, routes statiques |
| Pages servies | `curl -s -o /dev/null -w '%{http_code}' localhost:3000/login` | `200` |
| Redirection racine | `curl -s -o /dev/null -w '%{http_code}' localhost:3000/` | `307` → `/dashboard` |
| Dashboard | `curl -s -o /dev/null -w '%{http_code}' localhost:3000/dashboard` | `200` |
| Flux auth | register 200 → login (JWT) → `/api/auth/me` 200 → sans token 401 | conforme |
| Conteneurs | `bash scripts/test_connections.sh` | 27 OK, 0 FAIL, 0 SKIP |
| Contrat WS | `bash scripts/test_ws_events.sh` | 6 OK, 0 FAIL |
| Smoke test | `bash scripts/smoke_test.sh` | 13 OK, 0 FAIL, 0 SKIP |

> ⚠️ `npm audit` signale 8 vulnérabilités (7 high, 1 critical) dans les
> dépendances de build Next.js : **non traitées** dans cette phase (voir
> « Suivi »).

## Prochaine phase

**Phase C** (firmware ESP32 Wi-Fi/MQTT/barrière), avec **servos et capteurs
conservés**. Voir `docs/fiches-de-production/phase-C-firmware-audit.md`.

## Suivi / dette assumée

- `npm audit` : 8 vulnérabilités de dépendances frontend à traiter (mise à jour
  Next.js), sans impact fonctionnel connu sur la démo.
- Le rendu serveur du dashboard affiche « Vérification de la session… » : garde
  client assumée (la session vit dans `localStorage`).
