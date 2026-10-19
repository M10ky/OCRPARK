# Tuto de test — Phase 2 : Broker MQTT + Base de données

> Objectif pédagogique : comprendre le rôle du broker MQTT et de PostgreSQL,
> et savoir les piloter pour vérifier votre installation.

Toutes les commandes se lancent depuis la racine du projet (`SM-Park/`), après :

```bash
cp .env.example .env
docker compose up -d
```

> Si votre terminal n'a pas encore le groupe `docker` actif, préfixez les
> commandes par `sg docker -c "..."`.

---

## Partie A — Eclipse Mosquitto (broker MQTT)

### A.0 Rappels théoriques

- **MQTT** est un protocole de messagerie *publish/subscribe* très léger, idéal
  pour l'IoT (faible bande passante, connexions instables).
- Un **broker** (ici Mosquitto) reçoit les messages publiés sur des **topics**
  et les redistribue aux clients abonnés.
- L'**ESP32** publiera ses états (`parking/state`) et écoutera les
  commandes (`parking/barrier/command`). Le **backend** fera l'inverse.
- L'authentification est obligatoire : seuls les clients avec
  login/mot de passe peuvent se connecter.

### A.1 Vérifier que le broker tourne et écoute

```bash
docker compose ps
```

- **Attendu** : `smpark-mqtt` en **Up (healthy)**, ports `1883` et `9001`.
- **Ce que vous apprenez** : `1883` = MQTT, `9001` = MQTT over WebSockets.
  L'état `(healthy)` vient du *healthcheck* défini dans le compose.

### A.2 Lire les logs du broker

```bash
docker compose logs mqtt-broker
```

- **Attendu** : une ligne `Utilisateur 'smpark' configuré` puis les logs
  d'écoute de Mosquitto.
- **Ce que vous apprenez** : les logs (ici en `stdout`) sont la première source
  de diagnostic d'un conteneur.

### A.3 Publier un message (authentifié)

```bash
docker exec smpark-mqtt mosquitto_pub \
  -h localhost -p 1883 \
  -u smpark -P change_me_mqtt \
  -t smpark/test -m "hello" -r
```

- **Attendu** : aucune erreur (code retour 0). L'option `-r` rend le message
  *retained* : le broker le garde et le redonne aux futurs abonnés.
- **Ce que vous apprenez** : `mosquitto_pub` publie sur un topic. `-u/-P` =
  identifiants. `-r` = persistant côté broker.

### A.4 S'abonner et recevoir le message

```bash
docker exec smpark-mqtt mosquitto_sub \
  -h localhost -p 1883 \
  -u smpark -P change_me_mqtt \
  -t smpark/test -C 1 -W 5
```

- **Attendu** : affiche `hello` puis se termine (`-C 1` = un seul message,
  `-W 5` = timeout 5 s).
- **Ce que vous apprenez** : `mosquitto_sub` s'abonne à un topic. C'est
  exactement ce que fera le backend pour écouter l'ESP32.

### A.5 Vérifier que l'accès ANONYME est refusé

```bash
docker exec smpark-mqtt mosquitto_pub -h localhost -p 1883 -t smpark/test -m "anon"
```

- **Attendu** : `Connection Refused: not authorised` (code retour ≠ 0).
- **Ce que vous apprenez** : la sécurité fonctionne. Sans cette protection,
  n'importe qui sur le réseau pourrait commander vos barrières.

### A.6 Observer le trafic sur tous les topics

```bash
# Terminal 1 : abonnement « joker »
docker exec smpark-mqtt mosquitto_sub -h localhost -p 1883 \
  -u smpark -P change_me_mqtt -t '#' -v

# Terminal 2 : publication
docker exec smpark-mqtt mosquitto_pub -h localhost -p 1883 \
  -u smpark -P change_me_mqtt -t parking/state -q 1 -r \
  -m '{"slots":[{"id":1,"occupied":true},{"id":2,"occupied":false}]}'
```

- **Attendu** : le terminal 1 affiche
  `parking/state {"slots":[{"id":1,"occupied":true},...]}`.
  (Charge canonique : voir `docs/mqtt-contract.md` §D.1.)
- **Ce que vous apprenez** : le joker `#` (multi-niveaux) et `+` (un niveau)
  permettent de s'abonner à des familles de topics. `-v` affiche le topic
  *et* le message. C'est l'outil de debug MQTT à connaître par cœur.

---

## Partie B — PostgreSQL

### B.0 Rappels théoriques

- **PostgreSQL** est un SGBD relationnel open-source, robuste et riche.
- `database/init/*.sql` est exécuté **automatiquement au tout premier démarrage**
  (base vide). Ce n'est pas rejoué ensuite (sinon vos données seraient écrasées).
- Le backend s'y connectera via SQLAlchemy (Phase 3) sur le DSN
  `postgresql+asyncpg://...` défini dans `.env`.

### B.1 Vérifier que le serveur tourne

```bash
docker compose ps
docker compose logs database | tail -5
```

- **Attendu** : `smpark-db` en **Up (healthy)** et le message
  `database system is ready to accept connections`.
- **Ce que vous apprenez** : `pg_isready` (healthcheck) teste si le serveur
  accepte des connexions, sans exécuter de requête.

### B.2 Se connecter en ligne de commande

```bash
docker exec smpark-db psql -U smpark -d smpark -c "\conninfo"
```

- **Attendu** : les informations de connexion (utilisateur `smpark`, base
  `smpark`, port `5432`).
- **Ce que vous apprenez** : `psql` est le client officiel. `\conninfo` et les
  méta-commandes `\...` sont propres à psql (pas du SQL).

### B.3 Vérifier les extensions installées par l'init

```bash
docker exec smpark-db psql -U smpark -d smpark -c "\dx"
```

- **Attendu** : `uuid-ossp` et `pgcrypto` apparaissent.
- **Ce que vous apprenez** : les extensions ajoutent des fonctions à PostgreSQL.
  `uuid-ossp` génère des identifiants uniques (pratiques comme clés primaires) ;
  `pgcrypto` fournit des fonctions de hachage/chiffrement (utile pour les mots de
  passe des utilisateurs du frontend, Phase 3/5).

### B.4 Vérifier la timezone configurée

```bash
docker exec smpark-db psql -U smpark -d smpark -c "SHOW timezone;"
```

- **Attendu** : `Indian/Antananarivo`.
- **Ce que vous apprenez** : la timezone est fixée au niveau de la base ;
  toutes les connexions en héritent. Important pour horodater les passages.

### B.5 Tester une vraie requête SQL (aller-retour)

```bash
docker exec smpark-db psql -U smpark -d smpark -c \
  "SELECT now() AS serveur_heure, version() AS version_pg;"
```

- **Attendu** : la date/heure courante (fuseau Madagascar) et la version.
- **Ce que vous apprenez** : `now()` renvoie l'heure du serveur dans sa timezone.
  Vous venez d'exécuter du SQL réel contre votre base.

### B.6 Vérifier la persistance (volume Docker)

```bash
docker volume ls | grep smpark
docker compose down
docker compose up -d database
docker exec smpark-db psql -U smpark -d smpark -c "SELECT 1;"
```

- **Attendu** : après `down`/`up`, les données survivent (volume
  `smpark_postgres_data` reconnecté). `SELECT 1` fonctionne toujours.
- **Attention** : `docker compose down -v` **supprime** les volumes (donc les
  données). À n'utiliser que pour repartir de zéro.
- **Ce que vous apprenez** : un conteneur est jetable ; les **volumes** sont la
  mémoire persistante. C'est un concept central de Docker.

---

## Récapitulatif de la checklist Phase 2

| Test | Commande | Résultat attendu |
|---|---|---|
| Conteneurs | `docker compose ps` | 2 services `healthy` |
| MQTT pub | `mosquitto_pub ... -r` | succès |
| MQTT sub | `mosquitto_sub ... -C 1` | reçoit `hello` |
| MQTT anonyme | `mosquitto_pub` sans `-u` | `not authorised` |
| Logs MQTT | `docker compose logs mqtt-broker` | user configuré + écoute |
| Postgres | `psql -c "\conninfo"` | base `smpark` |
| Extensions | `psql -c "\dx"` | `uuid-ossp`, `pgcrypto` |
| Timezone | `psql -c "SHOW timezone;"` | `Indian/Antananarivo` |
| Persistance | `down` + `up` | données conservées |
