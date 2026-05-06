# NoxiasProspect

> Outil web interne de prospection commerciale B2B pour l'équipe Noxias (10 commerciaux).

## Démarrage en local

```bash
cp .env.example .env                    # remplir les secrets en Phase 2+
make setup                              # uv sync (back) + pnpm install (front)
make dev                                # docker-compose up + uvicorn + next dev
```

| Service        | URL                              |
| -------------- | -------------------------------- |
| Frontend       | http://localhost:3000            |
| Backend (Swagger) | http://localhost:8000/docs    |
| Adminer (DB)   | http://localhost:8080            |
| Postgres       | `localhost:5432` (`noxias/noxias`) |
| Redis          | `localhost:6379`                 |

Autres commandes utiles : `make lint`, `make test`, `make format`, `make migrate`.

## Architecture

```
backend/    FastAPI 0.115 + SQLAlchemy 2.0 (async) + Alembic + arq workers
frontend/   Next.js 14 App Router + TS strict + Tailwind + shadcn/ui
docker-compose.yml   Postgres 15 + Redis 7 + Adminer
```

Pipeline d'enrichissement (Phase 3) : **Bright Data GMaps → INSEE
`recherche-entreprises.api.gouv.fr` → Pappers (web unlocker) → réseaux sociaux footer →
scoring 0-100 → Pipedrive** (dédoublonnage tél E.164 + SIREN).

## Mode démo (sans Auth0)

Pour tester l'application sans configurer Auth0, exporte ces variables avant
le boot (ou règle-les côté Render / Vercel) :

```bash
# Backend
AUTH_DISABLED=true
# Frontend (build-time)
AUTH_DISABLED=true
```

Effets :

- Le backend ignore le header `Authorization` et résout chaque requête comme
  un user `demo@noxias.fr` (créé en DB au premier appel).
- Le front skippe NextAuth, l'URL `/` redirige direct vers `/dashboard`, et
  l'header affiche un badge **« Mode démo »** à la place de la déconnexion.

Pour rebrancher Auth0 plus tard : remettre `AUTH_DISABLED=false` (ou supprimer
la variable) et renseigner les `AUTH0_*` côté back + front. Aucun code à
changer.

> ⚠️ Ne jamais activer ce flag en production — l'app devient ouverte.

## Stack et décisions

| Couche | Techno | Pourquoi |
| ------ | ------ | -------- |
| Backend | FastAPI + Pydantic v2 | Typage, doc OpenAPI auto |
| ORM | SQLAlchemy 2.0 async + asyncpg | Cohérent avec FastAPI async |
| Workers | **arq** (Redis-based) | Plus léger que Celery, asyncio natif |
| Front | Next.js 14 App Router + shadcn/ui | DX moderne, composants accessibles |
| Auth | Auth0 (front : `next-auth` v5) | SSO Google clé en main |
| Scraping | Bright Data SDK | POC validé sur 200 fiches |
| Données légales | API gouv `recherche-entreprises` | Gratuite, sans clé |
| CRM | API Pipedrive v1 | Déjà en place chez Noxias |
| Hosting | Render/Fly.io (back) + Vercel (front) | Setup minimal, scale auto |
| Observabilité | Sentry + structlog JSON | PII anonymisée par défaut |

Décisions validées (cf. journal Phase 0) :

- **Q1** : pas de CDC dans le repo, on construit sur le prompt seul.
- **Q2** : périmètre ARA = contrainte **UI uniquement**, le modèle accepte toute commune FR.
- **Q3** : 1 token Pipedrive global Noxias + custom field « Importé par » (pas d'OAuth par
  commercial).

## Conformité RGPD

NoxiasProspect traite des données personnelles de prospects B2B (article 6 (1)(f) du
RGPD — intérêt légitime de prospection). Le produit implémente les obligations
suivantes côté technique :

### Droit d'opposition (art. 21) — opt-out

- Table `Blacklist` (`siren`, `phone_e164`, `reason`, `note`, `added_by`).
- API : `GET /api/v1/blacklist`, `POST /api/v1/blacklist`, `DELETE /api/v1/blacklist/{id}`.
- UI : page **Blacklist (RGPD)** dans la sidebar — formulaire d'ajout + tableau.
- L'orchestrateur d'enrichissement consulte la blacklist **avant** chaque écriture
  (`app/enrichment/blacklist.py::is_blacklisted`). Toute fiche dont le SIREN ou le
  téléphone E.164 est inscrit est automatiquement écartée — couvert par les tests
  `test_orchestrator_full_pipeline` et `test_blacklisted_siren_is_filtered_by_orchestrator`.

### Droit à l'effacement (art. 17)

- `DELETE /api/v1/prospects/{id}` enchaîne :
  1. **Pipedrive** — suppression du Deal, puis Person, puis Organization (best-effort,
     une erreur Pipedrive n'empêche pas la suite).
  2. **Auto opt-out** — insertion d'une ligne `Blacklist` (siren + tél) pour bloquer
     les futures fiches.
  3. **Audit RGPD** — insertion d'une ligne `DeletionLog` minimisée :
     - SIREN intégral (donnée légale publique, art. 4-1)
     - téléphone : 4 derniers chiffres uniquement
     - nom commercial
     - email du commercial qui a supprimé
     - IDs Pipedrive originaux
     - `created_at` (utilisé pour la purge automatique à 3 ans)
  4. **Suppression locale** du `Prospect` (cascade vers `PipedriveMapping`).
- Bouton « Supprimer (RGPD) » visible sur la fiche prospect, avec confirmation modale
  qui détaille les conséquences (irréversible).

### Minimisation et anti-fuite PII

- `app/core/logging.py` expose `anonymize_phone()` et `anonymize_email()`. Tous les
  appels qui logguent un identifiant passent par ces helpers (`+33***22`, `j***@noxias.fr`).
- `app/core/http.py` enregistre **uniquement** le verbe, l'host, le path, le code et
  la durée — jamais les bodies de requête / réponse.
- Sentry initialisé avec `sendDefaultPii: false` (front + back).
- Les payloads bruts de Bright Data / Pappers sont stockés en JSONB côté DB (pour
  replay/debug) mais ne sortent pas du périmètre Noxias (ni Sentry, ni logs).

### Rétention

| Donnée | Durée | Mécanisme |
| ------ | ----- | --------- |
| `Prospect` (actif) | 24 mois après dernier enrichissement | purge périodique à brancher (V2) |
| `DeletionLog` | **3 ans** (à confirmer DPO) | filtre sur `created_at` < `now() - 3 years` |
| `Blacklist` | indéfini (opt-out volontaire) | retirable via `DELETE /api/v1/blacklist/{id}` |
| Logs Sentry | 30 jours (rétention par défaut) | configuré côté Sentry SaaS |

### Process d'opt-out (à documenter au DPO)

1. Demande reçue (email DPO ou directement par le contact).
2. Le commercial ouvre la fiche dans NoxiasProspect → bouton « Supprimer (RGPD) ».
3. Confirmation : suppression DB + Pipedrive + opt-out automatique.
4. Une ligne `DeletionLog` est conservée 3 ans (preuve de traitement art. 30 RGPD).
5. Si la demande arrive par email, l'admin peut ajouter directement le SIREN ou le
   téléphone via la page **Blacklist** sans qu'une fiche existe en DB.

### Observabilité conforme

- `structlog` JSON renderer en prod (consommable par Datadog / Loki / CloudWatch).
- Chaque appel HTTP externe (Bright Data, INSEE, Pappers, Pipedrive) loggué avec
  durée, status code, host. Les requêtes > 5 s déclenchent un `http.slow` WARN.
- Sentry capture les exceptions avec contexte minimal (pas de PII).

---

## État d'avancement

- [x] **Phase 0** — Cadrage, hypothèses, questions
- [x] **Phase 1** — Scaffold + infra dev
- [x] **Phase 2** — Modèle de données + auth Auth0
- [x] **Phase 3** — Pipeline d'enrichissement
- [x] **Phase 4** — Front utilisateur
- [x] **Phase 5** — Intégration Pipedrive
- [x] **Phase 6** — RGPD + observabilité
- [x] **Phase 7** — Mise en prod

## Déploiement

L'architecture cible utilise **Render** pour tout le backend (API + worker + Postgres + Redis)
et **Vercel** pour le front Next.js. Les deux fournisseurs branchent directement sur la
branche `main` du repo.

### Vue d'ensemble

```
                                ┌──────────────────────────────────────┐
                                │            Vercel (front)            │
                                │   Next.js 14 / Auth.js v5 / Sentry   │
   GitHub ───── push main ─────▶│   region: cdg1 (Paris)               │
                                └──────────────┬───────────────────────┘
                                               │ HTTPS + Bearer
                                               ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │                        Render (backend, FRA)                     │
   │  ┌────────────────────┐    ┌──────────────────┐                  │
   │  │ noxiasprospect-api │    │ noxiasprospect-  │                  │
   │  │ (Docker, public)   │    │      worker      │                  │
   │  │  uvicorn :8000     │    │   arq runner     │                  │
   │  └────┬───────┬───────┘    └─────┬────────────┘                  │
   │       │       │                  │                                │
   │       ▼       ▼                  ▼                                │
   │  ┌──────────┐  ┌──────────────────────┐                           │
   │  │ Redis    │  │ Postgres 15 (managed)│                           │
   │  └──────────┘  └──────────────────────┘                           │
   └──────────────────────────────────────────────────────────────────┘
```

### Backend — Render (Blueprint)

```bash
# 1. Push to main (CI must be green)
git push origin main

# 2. Provision the full stack from render.yaml
render blueprint launch        # or: paste render.yaml in the Render UI
```

`render.yaml` declare 4 services :

| Service | Type | Rôle |
| ------- | ---- | ---- |
| `noxiasprospect-api` | web | Uvicorn + FastAPI, public sur 8000, applique les migrations Alembic au boot |
| `noxiasprospect-worker` | worker | `arq` consomme les jobs depuis Redis (orchestrateur d'enrichissement) |
| `noxiasprospect-db` | postgres | PG 15 managé, exposé via `${DATABASE_URL}` aux deux services |
| `noxiasprospect-redis` | redis | broker + cache, `${REDIS_URL}` |

Les secrets (Auth0, Bright Data, Pipedrive, Sentry) sont marqués `sync: false`
dans le blueprint — il faut les renseigner une seule fois via le dashboard Render.

### Frontend — Vercel

```bash
# 1. Connecter le repo dans le dashboard Vercel.
# 2. Sélectionner « Root directory: frontend ».
# 3. Renseigner les variables d'environnement (cf. tableau ci-dessous).
# 4. La première mise en ligne se déclenche au premier push sur main.

# Local CLI :
vercel link
vercel env pull frontend/.env.production.local
vercel --prod
```

`frontend/vercel.json` règle déjà : framework Next.js, région `cdg1` (Paris),
en-têtes de sécurité (`X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`).

### Variables d'environnement par service

| Variable | API (Render) | Worker (Render) | Front (Vercel) |
| -------- | :-: | :-: | :-: |
| `DATABASE_URL` | ✅ auto (DB) | ✅ auto (DB) | — |
| `REDIS_URL` | ✅ auto (Redis) | ✅ auto (Redis) | — |
| `AUTH0_DOMAIN` | ✅ | — | ✅ |
| `AUTH0_CLIENT_ID` | ✅ | — | ✅ |
| `AUTH0_CLIENT_SECRET` | ✅ | — | ✅ |
| `AUTH0_AUDIENCE` | ✅ | — | ✅ |
| `AUTH_SECRET` | — | — | ✅ (NextAuth random secret) |
| `NEXTAUTH_URL` | — | — | ✅ (`https://app.noxias.fr`) |
| `BRIGHTDATA_API_TOKEN` | ✅ | ✅ | — |
| `BRIGHTDATA_GMAPS_DATASET_ID` | ✅ | ✅ | — |
| `BRIGHTDATA_UNLOCKER_ZONE` | ✅ | ✅ | — |
| `PIPEDRIVE_API_TOKEN` | ✅ | ✅ | — |
| `PIPEDRIVE_COMPANY_DOMAIN` | ✅ | ✅ | — |
| `PIPEDRIVE_SIREN_FIELD_KEY` | ✅ | — | — |
| `PIPEDRIVE_IMPORTED_BY_FIELD_KEY` | ✅ | — | — |
| `SENTRY_DSN` | ✅ | ✅ | — |
| `NEXT_PUBLIC_SENTRY_DSN` | — | — | ✅ |
| `NEXT_PUBLIC_API_URL` | — | — | ✅ (`https://api.noxias.fr`) |

### Healthchecks

| Endpoint | Code | Usage |
| -------- | :--: | ----- |
| `GET /health` | 200 si process up | Liveness (Render, Docker) |
| `GET /health/ready` | 200 si DB+Redis OK, 503 sinon | Readiness — empêche Render de router du trafic vers une instance dégradée |

### Migrations

Idempotentes par construction. L'entrypoint Docker (`scripts/entrypoint.sh`)
exécute `alembic upgrade head` à chaque boot **uniquement** depuis le service
`api` (le worker s'abstient pour éviter une course au démarrage).

### Image Docker

Multi-stage `python:3.11-slim-bookworm`, `uv` pour la résolution des deps,
bytecode pré-compilé, runtime non-root (`uid 1001`), `__pycache__` purgés.
Cible : **< 200 Mo** (mesurée via `docker images`).

### Premier déploiement de staging

```bash
# 1. Backend
git checkout -b release/staging
git push origin release/staging
render blueprint launch        # crée 4 services en région Frankfurt

# 2. Frontend
vercel --target=staging        # déploiement preview, URL https://noxiasprospect-<sha>.vercel.app

# 3. Synchroniser les vars Auth0 (callback URLs, allowed origins)
#    → Auth0 Dashboard > Applications > NoxiasProspect
#       Allowed Callback URLs : https://noxiasprospect-staging.vercel.app/api/auth/callback/auth0
#       Allowed Logout URLs   : https://noxiasprospect-staging.vercel.app
#       Allowed Web Origins   : https://noxiasprospect-staging.vercel.app

# 4. Vérifier
curl -fsS https://noxiasprospect-api.onrender.com/health
curl -fsS https://noxiasprospect-api.onrender.com/health/ready
open https://noxiasprospect-staging.vercel.app
```

## Journal Phase 0 — décisions et hypothèses

10 hypothèses techniques validées implicitement par le prompt :

1. **Workers** : `arq` plutôt que Celery (asyncio natif, plus léger).
2. **Progression** : SSE plutôt que WebSocket (suffisant pour back→front uni).
3. **Package managers** : `uv` (back), `pnpm` (front).
4. **Communes ARA** : JSON statique embarqué (`frontend/lib/communes-ara.json`, à
   générer en Phase 4 depuis le référentiel INSEE filtré sur 01/03/07/15/26/38/42/43/63/69/73/74).
5. **Rétention notes Pipedrive** : 3 ans (à confirmer avec DPO Noxias).
6. **Polling Bright Data** : 30 s avec back-off exponentiel si snapshot > 5 min.
7. **Concurrence enrichissement** : semaphore = 5 (réglable via
   `ENRICHMENT_MAX_CONCURRENCY`).
8. **Tests** : pytest + respx (HTTP mocks) + factory-boy (DB fixtures).
9. **Auth front** : `next-auth` v5 comme client Auth0.
10. **CI** : un seul workflow `ci.yml`, deux jobs (`backend`, `frontend`).
