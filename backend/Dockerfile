# syntax=docker/dockerfile:1.7

# ============================================================
#  Stage 1 — builder: install deps with uv into /app/.venv
# ============================================================
FROM python:3.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# uv is a single static binary — fast, reproducible installs
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy lockfile first so the layer stays cached as long as deps don't change.
COPY pyproject.toml uv.lock* ./

# Sync prod deps only into /app/.venv. Falls back to lock-free sync if uv.lock
# happens to be absent (first build).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev \
    || uv sync --no-install-project --no-dev

# Copy app source + alembic config and install the project itself.
COPY app ./app
COPY alembic.ini ./
COPY scripts ./scripts
RUN --mount=type=cache,target=/root/.cache/uv \
    (uv sync --no-dev --frozen || uv sync --no-dev) \
 && find /app/.venv -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true \
 && find /app/.venv -name '*.pyc' -delete

# ============================================================
#  Stage 2 — runtime: minimal image with the venv + curl
# ============================================================
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8000

# curl for healthchecks, libpq for psycopg2 (sync driver used by Alembic).
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl libpq5 \
 && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd --system --uid 1001 --create-home --home-dir /home/noxias noxias

WORKDIR /app

COPY --from=builder --chown=noxias:noxias /app /app

USER noxias

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost:${PORT:-8000}/health || exit 1

ENTRYPOINT ["./scripts/entrypoint.sh"]
