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

- Table `Blacklist` avec `POST /api/blacklist` ; tous les enrichissements la consultent.
- `DELETE /api/prospects/{id}` retire la fiche de la DB **et** de Pipedrive (note de
  suppression conservée 3 ans pour traçabilité).
- Logs structurés sans PII : numéros et emails sont anonymisés (`+33***45`, `j***@noxias.fr`).
- Sentry initialisé avec `send_default_pii=False`.

Détails complets en Phase 6.

## État d'avancement

- [x] **Phase 0** — Cadrage, hypothèses, questions
- [x] **Phase 1** — Scaffold + infra dev (back/front bootent, CI verte, pre-commit OK)
- [ ] Phase 2 — Modèle de données + auth Auth0
- [ ] Phase 3 — Pipeline d'enrichissement
- [ ] Phase 4 — Front utilisateur
- [ ] Phase 5 — Intégration Pipedrive
- [ ] Phase 6 — RGPD + observabilité
- [ ] Phase 7 — Mise en prod

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
