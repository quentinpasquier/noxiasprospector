# NoxiasProspect

> Outil web interne de prospection commerciale B2B pour l'équipe Noxias (10 commerciaux).

## Phase 0 — Cadrage

### Compréhension du projet (en 10 lignes)

NoxiasProspect est un MVP V1 destiné à industrialiser la prospection sortante de Noxias.
Le produit prend une **requête métier** (ex. « courtier en travaux Lyon ») et un périmètre
géographique (villes Auvergne-Rhône-Alpes), puis exécute un **pipeline d'enrichissement
automatique** : scraping Google Maps via Bright Data → dédoublonnage par `place_id` →
enrichissement légal via API publique `recherche-entreprises.api.gouv.fr` (SIREN, dirigeant,
NAF, effectifs) → scraping Pappers via Bright Data web unlocker (CA, résultat) → extraction
des réseaux sociaux depuis le footer du site → **scoring 0-100** (rating, reviews, présence
site/téléphone) avec étiquettes Hot/Warm/Cold/À qualifier. Les prospects sont stockés en
PostgreSQL, consultables en front Next.js, et **exportables vers Pipedrive** avec
dédoublonnage par téléphone E.164 puis SIREN. Le tout est conforme RGPD (blacklist opt-out,
suppression sur demande, logs anonymisés). Stack : FastAPI + SQLAlchemy + Celery/Redis côté
back, Next.js 14 + shadcn/ui côté front, Auth0 SSO Google, Sentry pour l'observabilité.
Déploiement Render/Fly.io + Vercel.

### Hypothèses techniques prises (non-explicites dans le prompt)

1. **Worker async** : je pars sur **arq** plutôt que Celery — plus léger, asyncio-natif,
   s'aligne mieux avec FastAPI. Si tu préfères Celery (par habitude équipe / écosystème),
   je bascule.
2. **SSE plutôt que WebSocket** pour la progression de recherche — plus simple côté
   FastAPI (StreamingResponse) et suffisant pour un flux unidirectionnel back→front.
3. **Gestionnaire de paquets** : **uv** côté backend (10× plus rapide que Poetry, lockfile
   reproductible) et **pnpm** côté frontend. Si l'équipe a déjà du Poetry/npm en place,
   on s'aligne.
4. **Liste des communes ARA** : JSON statique généré depuis le dataset officiel INSEE
   (communes filtrées sur les 12 départements ARA), embarqué dans le repo front
   (`frontend/lib/communes-ara.json`).
5. **Rétention 3 ans** des notes de suppression Pipedrive : interprétation libre du
   « droit à l'oubli » + obligation comptable. À confirmer avec le DPO Noxias.
6. **Taux de polling Bright Data** : 30 s comme indiqué dans le prompt, avec back-off
   exponentiel si le snapshot dépasse 5 min.
7. **Séparation jobs** : 1 tâche arq par recherche (orchestrator), qui lance des
   sous-tâches parallèles (`asyncio.gather`) pour insee/pappers/socials sur chaque
   prospect, avec semaphore (concurrence max = 5) pour respecter les quotas.
8. **Tests** : pytest + respx pour mocker Bright Data + factory-boy pour les fixtures DB.
9. **Front** : `next-auth` v5 comme client Auth0 (officiellement supporté), pas de SDK
   Auth0 maison.
10. **CI** : GitHub Actions avec un seul workflow `ci.yml` (lint + tests back + lint +
    typecheck front), pas de matrix complexe.

### 3 questions de clarification (bloquantes)

#### Q1 — Le CDC est-il disponible ?

Le prompt mentionne `CDC_outil_prospection_noxias.md` à la racine comme **source de
vérité**, avec des références précises (sections 3, 4.3, 5, 7). **Ce fichier n'est pas
présent dans le repo** (seul `.git` existe). Trois options :

- **(a)** Tu colles le CDC dans le repo et je relis intégralement avant de continuer.
- **(b)** Je continue avec ce que dit déjà le prompt (qui couvre 80 % des décisions :
  stack, archi, schéma de données implicite, scoring, RGPD…), en marquant les zones
  d'ombre au fur et à mesure pour validation.
- **(c)** Tu me résumes oralement les sections critiques manquantes (3, 4.3, 5, 7) et
  on s'aligne ainsi.

Ma préférence : **(a)** — pour ne pas réinventer le schéma de données qui doit
matcher exactement la section 7. Le risque sinon : refaire les migrations à la phase 2.

#### Q2 — Périmètre Auvergne-Rhône-Alpes : strict ou évolutif ?

Le front a un « multi-select villes ARA chargé depuis JSON statique ». Question :

- Doit-on **hardcoder ARA uniquement** (12 départements : 01, 03, 07, 15, 26, 38, 42,
  43, 63, 69, 73, 74) au niveau du modèle de données (`Search.region` enum) et
  rejeter toute autre région côté API ?
- Ou bien **ARA par défaut** au front, mais l'API accepte n'importe quelle commune
  française (pour ouvrir d'autres régions sans refacto en V2) ?

Ma préférence : **#2** — la contrainte « ARA » reste UI uniquement. Pas de surcoût,
on évite une migration V2.

#### Q3 — Pipedrive : un compte unique partagé ou un compte par commercial ?

Pour l'export, deux modèles possibles :

- **(a)** Un seul `PIPEDRIVE_API_TOKEN` global Noxias → tous les exports atterrissent
  dans le même pipeline, owner = utilisateur technique commun.
- **(b)** Chaque commercial connecte son propre compte Pipedrive (OAuth), les deals
  sont créés sous son ownership.

Le prompt suggère **(a)** (1 seul token en `.env`), ce qui est plus simple pour le MVP
mais pose un souci de traçabilité (« qui a importé ce prospect ? »). **(b)** est plus
propre métier mais ajoute un flow OAuth Pipedrive (1 jour de boulot supplémentaire).

Ma préférence : **(a) avec custom field « Importé par » = email user Auth0** sur les
deals créés. On garde la trace sans complexité OAuth. OK pour toi ?

---

**Je m'arrête ici. J'attends ton retour sur ces 3 questions avant de passer à la
Phase 1 (scaffold + infra).**
