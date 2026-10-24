# Fiche de conception — Phase B.1 : Architecture du frontend

- **Nom de l'étape** : B.1 — Architecture frontend (structure, stratégie auth,
  stratégie WebSocket, modèle de données, découpage).
- **Date** : 2026-10-22.
- **Objectif** : fixer **avant d'écrire la moindre ligne d'UI** l'architecture du
  frontend métier SM-Park, de manière à ce que les étapes B.2 → B.6 soient de
  l'application mécanique d'un plan validé.
- **Périmètre** : conception uniquement. **Aucun code UI n'est écrit à ce stade.**
- **Sources de vérité** : `docs/mqtt-contract.md`, `docs/websocket-contract.md`,
  `backend/app/api/routes/*`, `backend/app/schemas/*`.
- **Hors scope** : pinout capteurs/servos (Phase C-hardware), TLS, app mobile,
  paiement, multi-parking.

---

## 1. Constat de l'existant

| Élément | État constaté | Conséquence |
|---|---|---|
| `frontend/` | Scaffold `create-next-app` **intact** : Next.js `15.3.2` (App Router), React `19`, TypeScript `strict`, Tailwind CSS `v4`, ESLint `9` flat config | Base technique saine, mais **zéro** code métier |
| `src/app/page.tsx` | Écran d'accueil Next.js par défaut (logo, liens Vercel) | Aucun écran de parking |
| `src/app/layout.tsx` | `metadata = { title: "Create Next App" }`, polices Geist via `next/font/google` | À remplacer |
| `src/` | 4 fichiers seulement (`layout.tsx`, `page.tsx`, `globals.css`, `favicon.ico`) | Ni `lib/`, ni `hooks/`, ni `components/` |
| Client HTTP | **Aucun** (`fetch`/`axios` absents de `src/`) | À créer |
| WebSocket | **Aucun** | À créer |
| Auth | **Aucune** | À créer |
| `next.config.ts` | `{ output: "standalone" }` | Docker déjà prévu ✅ |
| `Dockerfile` | Multi-stage (deps → build → runner), `nextjs` non-root, `NEXT_PUBLIC_*` en **build args** | Déjà conforme ✅ |
| `docker-compose.yml` | Service `frontend` avec `build.args.NEXT_PUBLIC_BACKEND_URL` / `NEXT_PUBLIC_WS_URL` | Déjà conforme ✅ |
| Tests | **Aucun** runner (`package.json` = `dev`/`build`/`start`/`lint` seulement) | À définir en B.6 |
| Dépendances | 3 prod (`next`, `react`, `react-dom`) + 7 dev | Zéro bibliothèque métier |

**Verdict** : le conteneur Next.js fonctionne déjà ; il manque toute la couche
« métier » (données, auth, temps réel, composants).

---

## 2. Contraintes figées par le backend (non négociables)

Le frontend est un **client** du backend existant. Il n'a **aucun** pouvoir de
modifier les formats d'échange. Les contraintes suivantes sont déduites du code
backend et s'imposent au frontend.

### 2.1 Authentification

| Contrainte | Source | Impact frontend |
|---|---|---|
| `POST /api/auth/login` attend un **formulaire OAuth2** (`application/x-www-form-urlencoded`, champs `username` + `password`), **pas du JSON** | `backend/app/api/routes/auth.py:67-80` | Le client doit envoyer un `URLSearchParams`, **jamais** un `JSON.stringify` |
| Réponse : `{ "access_token": "<JWT>", "token_type": "bearer" }` | `backend/app/schemas/auth.py` | Le token est dans `access_token` |
| Le JWT porte `sub` = **username** (pas d'id) et `exp` | `backend/app/core/security.py:75-82` | `GET /api/auth/me` pour reconstituer le profil |
| `GET /api/auth/me` → `{ username, email, is_active, is_admin }` | `backend/app/api/routes/auth.py:83-87` | Afficher le nom + badge admin |
| Le token doit être envoyé en `Authorization: Bearer <token>` | `backend/app/api/deps.py:13` | Wrapper HTTP unique |

### 2.2 WebSocket

| Contrainte | Source | Impact frontend |
|---|---|---|
| URL : `ws://<backend>/ws/events` | `backend/app/api/routes/ws.py:16` | `NEXT_PUBLIC_WS_URL` |
| Auth **optionnelle** via `?token=<JWT>` ; si fourni et invalide → fermeture `4401` | `ws.py:27-35` | Le front transmet le token ; il doit gérer le code `4401` (token expiré → re-login) |
| En dev `WS_REQUIRE_AUTH=false` → connexion sans token acceptée | `.env` | Le front envoie quand même le token (compatible prod) |
| À la connexion : événement **`snapshot`** immédiat | `ws.py:39-49` | Le front **ne doit pas** attendre un événement MQTT pour afficher l'état initial |
| Enveloppe : `{ type, payload, ts }` | `docs/websocket-contract.md` | Un seul type d'événement à discriminer |
| Types : `snapshot`, `slots`, `visit`, `passage`, `barrier`, `mqtt` | idem | 6 cas dans un `switch` |

### 2.3 Pièges de forme (traps) — à connaître **avant** de typer le front

> **TRAP 1 — `slots` a deux formes différentes.**
> `GET /api/slots` renvoie `{ slots: [{ id, label, occupied, updated_at }], total, occupied, free }`
> (schéma `ParkingSlotRead`, avec `label` et `updated_at`).
> Mais l'événement WS `slots` renvoie `{ slots: [{ id, occupied }], total, occupied, free }`
> (`mqtt_handlers._slots_snapshot()`, **sans** `label` ni `updated_at`).
> → Le type TS `Slot` doit déclarer `label?` et `updated_at?` en optionnels,
> et l'UI ne doit **pas** afficher `label` sans repli sur `Place n° id`.

> **TRAP 2 — `barrier/state` : `ack_status` peut valoir `null`.**
> Le backend ne renseigne `ack_status` que si le message MQTT portait un
> `correlation_id` (`mqtt_handlers.handle_barrier_state`, l. 232-243).
> Un heartbeat (sans `correlation_id`) → `ack_status: null`.
> → L'UI doit distinguer 3 cas : `acknowledged` / `pending` / `timeout` /
> `null` (= heartbeat, pas un ACK).

> **TRAP 3 — `parking/state` n'est publié par personne en Phase C.**
> Tant que les capteurs ne sont pas câblés, l'occupation vient du **seed** en
> base (3 places libres). Le cas « parking plein » ne se déclenche donc pas
> spontanément : il se provoque en injectant `parking/state` via
> `mosquitto_pub` (cf. `docs/tests/phase-D-tests-backend-live.md`).
> → L'UI doit afficher la source de l'occupation (« capteur » vs « seed ») ou,
> au minimum, ne pas prétendre que la mesure est réelle.

> **TRAP 4 — `POST /api/orchestrate/upload` peut renvoyer 503.**
> Le service OCR n'est pas disponible → `httpx.RequestError` → `HTTPException(503)`
> (`backend/app/services/ocr_client.py:22-26`). Le cas "OCR indisponible" doit
> être affiché proprement, pas comme une erreur serveur.

> **TRAP 5 — `POST /api/orchestrate/scan` renvoie 503 sans webcam.**
> `ocr-service` répond 503 si `/dev/video0` n'est pas monté. Le bouton « scan
> caméra » doit donc être neutralisé (désactivé + tooltip) quand aucune
> caméra n'est disponible.

> **TRAP 6 — CRUD plaques : update/delete utilisent l'UUID, pas la plaque.**
> `POST /api/plates` et `GET /api/plates/{plate}` utilisent le **texte** de la
> plaque ; `PUT /api/plates/{plate_id}` et `DELETE /api/plates/{plate_id}`
> utilisent l'**UUID** (`id`). Une implémentation naïve qui envoie la plaque
> à l'UPDATE reçoit un `422` (UUID invalide).

> **TRAP 7 — CORS strict.**
> `CORS_ORIGINS=http://localhost:3000`. Le navigateur envoie `Origin:
> http://localhost:3000`. Accéder à l'UI via `http://127.0.0.1:3000` ou via
> l'IP de la machine → **blocage CORS**. Règle de démo : toujours passer par
> `http://localhost:3000`, et ajouter les origines utiles dans `.env`.

### 2.4 Récapitulatif des endpoints consommés

| Endpoint | Méthode | Auth | Consommé par |
|---|---|---|---|
| `/api/auth/login` | POST | ✗ | B.2 (login) |
| `/api/auth/me` | GET | ✓ | B.2 (profil) |
| `/api/slots` | GET | ✓ | B.3 (dashboard) |
| `/api/barrier/state` | GET | ✓ | B.3 (dashboard) |
| `/api/visits/current` | GET | ✓ | B.3 (dashboard) |
| `/api/passages?limit=…` | GET | ✓ | B.3 (dashboard) + B.4 (historique) |
| `/api/passages/stats` | GET | ✓ | B.4 (historique) |
| `/api/passages?plate&source&allowed&date_from&date_to` | GET | ✓ | B.4 (filtres cumulatifs) |
| `/api/visits?status&plate&date_from&date_to` | GET | ✓ | B.4 (onglet visites) |
| `/api/plates` | GET/POST | ✓ | B.4 (CRUD) |
| `/api/plates/{plate_id}` | PUT/DELETE | ✓ | B.4 (CRUD, UUID) |
| `/api/orchestrate/upload?gate=` | POST (multipart) | ✓ | B.5 |
| `/api/orchestrate/scan?gate=` | POST | ✓ | B.5 (désactivé sans caméra) |
| `/ws/events?token=` | WS | ✓ (optionnel) | B.3 (temps réel) |

---

## 3. Décisions d'architecture (DA)

Chaque décision est arbitrée, avec l'option rejetée et sa raison. C'est la
grille de lecture de toutes les étapes suivantes.

### DA-1 — Le navigateur appelle **directement** le backend (pas de BFF Next.js)

| | **Retenu : direct** | Rejeté : BFF (Route Handlers proxy) |
|---|---|---|
| Code | 1 wrapper `fetch` (~80 lignes) | Proxy + gestion de cookies + SSR |
| CORS | Déjà supporté (`CORS_ORIGINS`) | Neutralisé (proxy same-origin) |
| Latence | 1 saut | 2 sauts |
| Token | `localStorage` → `Authorization` | Passé par cookie `httpOnly` |
| Risque | CORS si origine ≠ `localhost:3000` | Complexité inutile pour une démo |

**Justification** : le backend expose déjà une API REST complète, CORS est déjà
configuré, et le frontend doit rester « lisible en soutenance ». Le BFF
n'apporterait de valeur que pour la protection du token (voir DA-2).

> **Conséquence assumée** : le token vit dans `localStorage`, donc lisible par
> un script de la page (risque XSS). Le **vrai** rempart de sécurité reste le
> backend (`get_current_user` sur chaque route). Une note le rappellera dans la
> fiche de production finale.

### DA-2 — Auth **client-side** : `localStorage` + garde de route React

Le `localStorage` est **inaccessible au serveur Next.js** (le middleware ne
peut pas lire le JWT : il n'est ni dans un cookie ni dans un header serveur).
Conséquence : **la protection des routes est purement visuelle** ; la sécurité
réelle est appliquée par le backend.

```
Route non protégée  ──▶ <RequireAuth>  ──(pas de token / 401)──▶ redirect /login
                                            (sinon) ▶ rendu de la page
```

| Option | Retenu | Rejeté |
|---|---|---|
| `localStorage` + garde client | ✅ simple, survive au reload | — |
| Cookie `httpOnly` | — | nécessite un BFF (DA-1 rejeté) |
| `middleware.ts` Next.js | — | ne peut pas lire un JWT en `localStorage` |

**Cycle de vie du token** :
1. `POST /api/auth/login` (form) → `access_token`.
2. Stockage `localStorage["smpark_token"]` + `localStorage["smpark_user"]`.
3. Au montage de l'app : si token présent → `GET /api/auth/me` pour **valider**
   (le backend peut avoir redémarré avec une autre `JWT_SECRET_KEY`) ; si 401
   → purge + redirect `/login`.
4. Expiration (401 sur n'importe quel appel) → purge + redirect `/login?next=…`.
5. `POST /api/auth/logout` **n'existe pas** (pas de refresh token) → le
   « logout » est local : purge du stockage + fermeture du WebSocket.

### DA-3 — Un **unique** WebSocket partagé, géré par un Provider React

Un seul socket pour toute l'application, ouvert au montage du layout
authentifié, fermé au logout.

```
<LiveProvider>            1 socket
 ├── <AuthProvider>       1 token
 └── pages (consommateurs via useLive())
```

- Reconnexion automatique avec **backoff exponentiel** borné : 1 s → 2 s → 4 s → 8 s → 10 s (plafond).
- Reconnexion **immédiate** si le socket est fermé par le serveur (`code 4401`
  → purge du token + redirect `/login`, pas de boucle de reconnexion).
- `ping` applicatif : le backend ne gère pas de ping WS ; la détection de
  mort de connexion se fait par l'absence d'événement + un `setInterval` de
  contrôle (le navigateur ne signale pas une connexion TCP morte). →
  **Reconnexion sur erreur `close`**, et un garde-fou : si aucun message reçu
  depuis 30 s, on force une reconnexion. *(Le backend émet un heartbeat
  `barrier/state` toutes les 5 s lorsque l'ESP32 est connecté → utile comme
  signal de vie, mais **pas fiable** si l'ESP32 est hors ligne ; on ne
  l'utilise donc pas comme unique signal.)*

### DA-4 — Pas de bibliothèque de state ni de data-fetching

| Besoin | Solution retenue | Rejeté |
|---|---|---|
| État global (auth + live) | 2 Context React (`AuthProvider`, `LiveProvider`) | Redux / Zustand (dépendance externe) |
| Fetch REST | `src/lib/api.ts` (wrapper `fetch` typé) | axios / SWR / React Query |
| Formulaires | `<form>` natif + `useState` | React Hook Form / Zod |
| Graphiques | CSS + Tailwind (jauge, barres) | Recharts / Chart.js |
| Composants UI | Primitives maison (`Card`, `Badge`, `Table`…) | MUI / shadcn (copie de code) |

**Justification** : le sujet est l'IoT, pas le front. Chaque dépendance ajoutée
est un point de rupture possible (et une question en soutenance). Tout ce qui
est utilisé est **MIT / gratuit** : Next.js, React, Tailwind, ESLint.

### DA-5 — Les pages authentifiées sont des **Client Components**

Le token étant dans `localStorage`, il n'est pas accessible pendant le rendu
serveur. Conséquence : `src/app/(app)/**` est en `"use client"`, et le premier
rendu est un squelette de chargement.

> Alternative rejetée : passer le token via un cookie pour permettre du SSR →
> impose le BFF (DA-1) et un `middleware.ts` qui vérifie le JWT côté serveur.
> Choix : lisibilité > performance de premier rendu.

### DA-6 — `NEXT_PUBLIC_*` figés au **build**, comme le backend l'exige déjà

`NEXT_PUBLIC_BACKEND_URL` et `NEXT_PUBLIC_WS_URL` sont des **build args** dans
`docker-compose.yml` (services `frontend`, lignes « NEXT_PUBLIC_* »). Elles sont
donc figées dans le bundle au moment de `docker compose build`.

Corollaires à respecter :
- Rebuild obligatoire après changement de `.env` (`docker compose build frontend`).
- Une seule valeur pour le build → **le front parle toujours au backend via
  l'URL publique** (`http://localhost:8000`), y compris depuis le navigateur.
- Le client ne lit **jamais** `process.env` côté serveur pour ces URLs.

> **Amélioration possible (non retenue en B.1)** : lire `BACKEND_URL` côté
> serveur (Route Handler `/api/config`) pour gérer le cas « front sur un
> autre hôte que le back ». Écarté : complexité inutile pour la démo
> mono-machine.

### DA-7 — Un design system **Tailwind v4 CSS-first**, sans bibliothèque

Tailwind v4 est déjà installé (config CSS-first dans `globals.css`, via
`@theme`). On ajoute des **jetons sémantiques** :

| Jeton | Usage |
|---|---|
| `--color-surface` / `--color-surface-2` | cartes, panneaux |
| `--color-brand` | accent principal (BLEU) |
| `--color-ok` / `--color-warn` / `--color-danger` | place libre / parking plein / refus |

Plus 3 primitives réutilisables : `Card`, `Badge` (statut), `Button`.
Pas de dark mode forcé : `prefers-color-scheme` conservé, mais **la démo se fait
en clair** (lisibilité en vidéoprojection).

### DA-8 — Stratégie de tests : **Vitest** (unités) + **script bash** (intégration)

Le dépôt n'a **aucun** runner de test. Deux options :

| Option | Retenu | Rejeté |
|---|---|---|
| Vitest (MIT) sur `src/lib/**` (pure) | ✅ rapide, 1 dépendance dev | — |
| Playwright / Cypress | — | poids lourd, réseau, hors scope |
| Aucun runner (tests manuels documentés) | — | pas de non-régression |

Complément : `scripts/smoke_test_phase_b.sh` (bash, même style que
`smoke_test_phase_d.sh`) qui vérifie en ligne de commande que le front build,
que les endpoints répondent et que le WS diffuse.

---

## 4. Arborescence cible

```
frontend/
├── Dockerfile                      (existant, inchangé sauf ajout de stage de test)
├── next.config.ts                  (existant, inchangé)
├── package.json                    (scripts dev/build/lint/test)
├── vitest.config.ts                (nouveau)
├── src/
│   ├── app/
│   │   ├── layout.tsx              (racine : métadonnées SM-Park + <Providers>)
│   │   ├── globals.css             (design tokens Tailwind v4)
│   │   ├── page.tsx                ("/" → redirect vers /dashboard ou /login)
│   │   ├── login/
│   │   │   └── page.tsx            (B.2)
│   │   └── (app)/                  (groupe de routes : layout authentifié)
│   │       ├── layout.tsx          (B.2 : nav + garde <RequireAuth> + <LiveProvider>)
│   │       ├── dashboard/page.tsx  (B.3)
│   │       ├── historique/page.tsx (B.4)
│   │       ├── plaques/page.tsx    (B.4)
│   │       └── orchestration/page.tsx (B.5)
│   ├── components/
│   │   ├── providers/
│   │   │   ├── AuthProvider.tsx    (token, user, login, logout)
│   │   │   └── LiveProvider.tsx    (WebSocket + état temps réel)
│   │   ├── layout/                 (AppNav, Sidebar, UserBadge, LiveIndicator)
│   │   ├── ui/                     (Card, Badge, Button, Table, Input, Select, Spinner, EmptyState)
│   │   ├── dashboard/              (SlotsGrid, OccupancyBadge, BarrierCard, EventsFeed, StatsCards)
│   │   ├── historique/             (PassageFilters, PassageTable, VisitTable, StatsRow)
│   │   ├── plaques/                (PlateForm, PlateTable, PlateDeleteButton)
│   │   └── orchestration/          (UploadPanel, DecisionCard, BarrierFeedback)
│   ├── hooks/
│   │   ├── useAuth.ts              (context typé)
│   │   ├── useLive.ts              (context typé + sélecteurs)
│   │   └── useFetch.ts             (GET/POST typés : loading, error, data, refetch)
│   ├── lib/
│   │   ├── config.ts               (API_BASE_URL, WS_URL, lecture NEXT_PUBLIC_*)
│   │   ├── api.ts                  (wrapper fetch + 9 fonctions endpoint)
│   │   ├── ws.ts                   (client WebSocket + backoff)
│   │   ├── format.ts               (dates FR, libellés, durées)
│   │   └── types.ts                (types TS alignés sur les schémas backend)
│   └── types/                      (déclarations TS globales si besoin)
└── tests/                          (tests unitaires Vitest, ex. format.test.ts)
```

**Règles de nommage** : pages en français (`/dashboard`, `/historique`,
`/plaques`, `/orchestration`) car l'UI est en français ; fichiers et
identifiants techniques en anglais (convention déjà en place côté backend).

---

## 5. Modèle de données côté frontend (`src/lib/types.ts`)

Types miroir des schémas Pydantic, **sans** duplication de logique.

```ts
// --- Auth ---
export interface Token { access_token: string; token_type: string }
export interface User { username: string; email: string | null; is_active: boolean; is_admin: boolean }

// --- Slots (TRAP 1 : label/updated_at optionnels) ---
export interface Slot { id: number; occupied: boolean; label?: string | null; updated_at?: string }
export interface SlotsSummary { slots: Slot[]; total: number; occupied: number; free: number }

// --- Barrière (TRAP 2 : ack_status nullable) ---
export type BarrierStateName =
  | "online" | "offline" | "idle" | "opening" | "open" | "closing" | "closed";
export type AckStatus = "pending" | "acknowledged" | "timeout";
export interface BarrierState {
  state: BarrierStateName | null;
  gate: "entry" | "exit" | null;
  reason: string | null;
  correlation_id: string | null;
  ack_status: AckStatus | null;   // null = heartbeat (pas un ACK)
  ts: string | null;
}
export interface BarrierCommand {
  correlation_id: string; passage_id: string | null; action: string; gate: string;
  status: "pending" | "acknowledged" | "timeout"; created_at: string; acked_at: string | null;
}
export interface BarrierStatus { state: BarrierState | null; last_command: BarrierCommand | null }

// --- Visites / passages ---
export interface Visit {
  id: string; plate: string | null; entry_gate: string; exit_gate: string | null;
  status: "inside" | "closed"; entry_at: string; exit_at: string | null;
  entry_passage_id: string | null; exit_passage_id: string | null;
}
export interface Passage {
  id: string; plate: string | null; recognized: boolean; confidence: number | null;
  allowed: boolean; source: string | null; action: string | null;
  barrier_command_sent: boolean; barrier_action: string | null;
  mqtt_topic: string | null; reason: string | null;
  ocr_detections: unknown; raw_image_ref: string | null; created_at: string;
}
export interface PassageStats {
  total: number; authorized: number; denied: number; recognized: number; unrecognized: number;
}

// --- Plaques ---
export interface AllowedPlate {
  id: string; plate: string; description: string | null; active: boolean;
  created_at: string; updated_at: string;
}

// --- Décision d'orchestration ---
export interface OrchestrateResult {
  plate: string | null; recognized: boolean; confidence: number | null;
  authorized: boolean; allowed: boolean; action: string | null; gate: string;
  barrier_command_sent: boolean; barrier_action: string | null;
  barrier_ack_status: AckStatus | null; total_slots: number | null;
  free_slots: number | null; reason: string | null; source: string;
  correlation_id: string | null; detections: unknown;
}

// --- WebSocket ---
export type WsEventType = "snapshot" | "slots" | "visit" | "passage" | "barrier" | "mqtt";
export interface WsEvent<T = unknown> { type: WsEventType; payload: T; ts: string }
export interface SnapshotPayload { slots: SlotsSummary; visits: Visit[]; barrier: BarrierState | null }
```

> `Passage.ocr_detections` est `dict | list | None` côté Pydantic → typé
> `unknown` côté TS (le front n'affiche pas la structure OCR brute).

---

## 6. Stratégie Auth (détail B.2)

```
src/lib/api.ts
  apiFetch<T>(path, { method, token, body, isForm })
     ├─ GET/POST/PUT/DELETE JSON
     ├─ POST form-urlencoded (login)
     ├─ POST multipart (upload)
     └─ si 401 → purge token + window.location = "/login"

src/components/providers/AuthProvider.tsx
  state : { token, user, status: "loading" | "authenticated" | "anonymous" }
  actions: login(username, password), logout()
  effets : au montage → si token → GET /api/auth/me (valide / 401 → purge)

src/components/providers/RequireAuth.tsx   (ou intégré au layout (app))
  status === "loading"    → squelette
  status === "anonymous"  → redirect /login
  status === "authenticated" → children
```

**Points de vigilance**
- Le login doit poster `username`/`password` en **`application/x-www-form-urlencoded`**.
- `GET /api/auth/me` peut échouer si le backend a redémarré avec une autre clé
  → traiter 401 comme « session expirée ».
- Le `token` est joint à l'URL du WebSocket : `?token=<JWT>`.

---

## 7. Stratégie WebSocket (détail B.3)

```
src/lib/ws.ts
  class LiveSocket {
    connect(url, token)
    on(type, handler) → unsubscribe
    close()
  }
  - backoff : 1000 → 2000 → 4000 → 8000 → 10000 (max), reset sur message reçu
  - close(4401) → callback "unauthorized" (pas de reconnexion)
  - close(n'importe quoi d'autre) → reconnexion planifiée

src/components/providers/LiveProvider.tsx
  state : {
    connection: "connecting" | "open" | "closed",
    slots: SlotsSummary | null,
    visits: Visit[],
    barrier: BarrierState | null,
    lastPassage: OrchestrateResult | null,
    events: { type, ts, summary }[]     // journal des 20 derniers événements
  }
  à la réception :
    "snapshot" → hydrate slots + visits + barrier
    "slots"    → remplace slots
    "visit"    → met à jour visits (inside ⇄ closed)
    "passage"  → journalise + mémorise la dernière décision
    "barrier"  → remplace barrier
    "mqtt"     → journalise (debug)
```

**Alimentation du dashboard** : l'état initial vient du **snapshot WS** (une
requête), puis le temps réel prend le relais. Un `GET /api/slots` /
`GET /api/barrier/state` en parallèle reste utile comme filet de sécurité si le
WebSocket est indisponible (bandeau « temps réel déconnecté » + bouton
« recharger »).

> Le dashboard consomme donc **2 sources** : REST (état initial fiable) et WS
> (temps réel). Le WS écrase le REST dès le snapshot reçu.

---

## 8. Matrice pages × sources de données

| Page | REST initial | WS | Contenu | Étape |
|---|---|---|---|---|
| `/login` | `POST /api/auth/login` | ✗ | formulaire, message d'erreur | B.2 |
| `/dashboard` | `GET /slots`, `/barrier/state`, `/visits/current`, `/passages?limit=8` | ✓ snapshot + slots/visit/passage/barrier | jauge places libres, état barrière, feed événements, compteurs | B.3 |
| `/historique` | `GET /passages` (filtres) + `GET /passages/stats` + `GET /visits` | ✓ `passage` (nouvelle ligne en haut) | filtres cumulatifs (plaque, source, allowed, dates) + pagination | B.4 |
| `/plaques` | `GET /plates` | ✗ (pas d'événement dédié) | CRUD complet (tableau + formulaire + suppression) | B.4 |
| `/orchestration` | `POST /orchestrate/upload` (ou `/scan`) | ✓ `passage` + `barrier` | upload image, décision détaillée, retour d'acquittement barrière | B.5 |

**Navigation** : sidebar ou barre supérieure avec 4 entrées + badge « live »
(état WS) + bouton « logout ».

---

## 9. Variables d'environnement

| Variable | Rôle | Valeur par défaut | Déjà câblée ? |
|---|---|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | Base des appels REST | `http://localhost:8000` | ✅ `docker-compose.yml` + `Dockerfile` |
| `NEXT_PUBLIC_WS_URL` | URL du WebSocket | `ws://localhost:8000` | ✅ idem |
| `NEXT_PUBLIC_PARKING_NAME` | Nom affiché dans l'en-tête | `SM-Park` | 🆕 (optionnel, défaut dans le code) |

`src/lib/config.ts` centralise la lecture :

```ts
export const API_BASE_URL = (process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const WS_URL = (process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000").replace(/\/$/, "");
```

> `NEXT_PUBLIC_*` est remplacé **à la compilation** par Next.js : le code doit
> lire `process.env.NEXT_PUBLIC_X` de façon **statique** (pas de
> `process.env["..."]`, pas de variable dynamique).

---

## 10. Docker

Le `Dockerfile` existant est **déjà conforme** aux exigences :

| Exigence | État | Commentaire |
|---|---|---|
| Multi-stage | ✅ | `deps` → `builder` → `runner` |
| Build dans l'image (`.next/` gitignoré) | ✅ | `.dockerignore` exclut `.next` |
| `NEXT_PUBLIC_*` en build args | ✅ | `ARG` + `ENV` dans le stage `builder` |
| Image finale minimale | ✅ | `node:24-alpine` |
| Non-root | ✅ | `nextjs:nextjs` (uid 1001) |
| Fonctionnel après `git clone` | ⚠️ | nécessite `npm ci` (lockfile présent ✅) ; le build réseau est requis |

**Adaptations prévues en B.6** : ajout d'un `stage` de test (`npm run test`)
non utilisé en production, et vérification que `next build` réussit avec les
nouvelles pages.

---

## 11. Pièges / risques identifiés

| # | Risque | Impact | Traitement |
|---|---|---|---|
| R1 | Origine `127.0.0.1` vs `localhost` → blocage CORS | UI inutilisable | Règle de démo `localhost` ; documenter `CORS_ORIGINS` |
| R2 | Backend redémarre avec un autre `JWT_SECRET_KEY` → 401 sur tout | Session perdue | `GET /api/auth/me` au montage → purge + re-login |
| R3 | OCR indisponible (503) | Écran d'orchestration en erreur | Message explicite + bouton réessayer |
| R4 | WS fermé par le backend (`4401`) | Bandeau rouge permanent | Traitement 4401 → purge + redirect |
| R5 | `NEXT_PUBLIC_*` modifiées dans `.env` sans rebuild | Le front parle à l'ancien backend | Documenter `docker compose build frontend` |
| R6 | `label`/`updated_at` absents des slots WS | Affichage `undefined` | Repli sur `Place n° id` (TRAP 1) |
| R7 | `ack_status: null` sur heartbeat | « ACK » affiché à tort | Distinguer heartbeat / ACK (TRAP 2) |
| R8 | Backend lent au démarrage → premier rendu vide | Page blanche | Squelette de chargement + messages d'erreur explicites |
| R9 | Aucune persistance de session → refresh = re-login | Friction en démo | `localStorage` conserve le token ✅ (solved) |

---

## 12. Découpage B.2 → B.6 (rappel, avec livrables vérifiables)

| Étape | Contenu | Livrable vérifiable |
|---|---|---|
| **B.1** | Architecture (ce document) | ✅ ce document, validé |
| **B.2** | Auth + layout authentifié | `/login` fonctionne, `/dashboard` protégé, logout OK |
| **B.3** | Dashboard live | places + barrière + événements temps réel via WS |
| **B.4** | Historique + plaques | filtres cumulatifs + CRUD complet |
| **B.5** | Orchestration (upload) | image → décision → ACK barrière affiché |
| **B.6** | Docker + tests + fiche Phase B | `docker compose up --build` OK, `npm run test` OK, `docs/fiches-de-production/phase-B-frontend.md` + `docs/tests/phase-B-tests-frontend.md` |

**Ordre d'implémentation imposé** : `lib/` (config, types, api, ws) →
`providers/` → `ui/` → `layout/` → pages. Les pages ne s'écrivent qu'après
les fondations, pour éviter les réécritures.

---

## 13. Hors scope (Phase B)

- TLS / HTTPS, cookies `httpOnly`, refresh token, RBAC fin (seul `is_admin` existe).
- Internationalisation (l'UI est en français, une seule langue).
- Tests end-to-end navigateur (Playwright), tests de charge.
- Responsive « mobile » avancé (la maquette est pensée desktop-first, lisible
  jusqu'à ~768 px).
- Persistance locale des filtres, export CSV, pagination infinie.

---

## 14. Checklist de validation de l'étape B.1

- [x] État des lieux du frontend documenté (constat factuel, fichiers vérifiés).
- [x] Contraintes backend extraites du code réel (routes, schémas, WS).
- [x] 6 pièges de forme (TRAP 1 → 7) identifiés **avant** l'implémentation.
- [x] 8 décisions d'architecture arbitrées (DA-1 → DA-8) avec alternatives rejetées.
- [x] Arborescence cible définie.
- [x] Types TypeScript miroir des schémas Pydantic.
- [x] Stratégie Auth et WebSocket définies.
- [x] Matrice pages × sources de données.
- [x] Variables `NEXT_PUBLIC_*` vérifiées (déjà câblées côté Docker).
- [x] Risques identifiés et traités.
- [x] Découpage B.2 → B.6 avec livrables vérifiables.
- [ ] **Validation de l'utilisateur** (point d'arrêt demandé).
