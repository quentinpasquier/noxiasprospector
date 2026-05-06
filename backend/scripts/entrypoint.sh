#!/usr/bin/env bash
# Container entrypoint — applies any pending Alembic migrations, then either
# starts the FastAPI server (default) or launches an arq worker, depending on
# the ROLE env var.
#
# Usage in Dockerfile:  ENTRYPOINT ["./scripts/entrypoint.sh"]
# Usage in Render:      this is the default ENTRYPOINT for both services;
#                       set ROLE=worker on the worker service.

set -euo pipefail

ROLE="${ROLE:-api}"

echo "[entrypoint] role=${ROLE} env=${ENVIRONMENT:-?}"

# Migrations are idempotent and safe to run on every boot. We only run them
# from the API role to avoid two services racing each other on cold start.
if [[ "${ROLE}" == "api" ]]; then
  echo "[entrypoint] applying alembic migrations"
  alembic upgrade head
fi

case "${ROLE}" in
  api)
    exec uvicorn app.main:app \
      --host 0.0.0.0 \
      --port "${PORT:-8000}" \
      --proxy-headers \
      --forwarded-allow-ips='*'
    ;;
  worker)
    exec arq app.workers.tasks.WorkerSettings
    ;;
  *)
    echo "[entrypoint] unknown ROLE=${ROLE} (expected api|worker)" >&2
    exit 1
    ;;
esac
