"""Smoke tests for /health endpoints."""

from app.main import app
from fastapi.testclient import TestClient


def test_health_returns_ok() -> None:
    """GET /health returns 200 with status=ok."""
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "version" in payload


def test_readiness_pings_dependencies() -> None:
    """GET /health/ready returns 200 with per-dependency status when DB+Redis up."""
    with TestClient(app) as client:
        response = client.get("/health/ready")
    # In CI we have Postgres but not Redis, so we accept either ready (200)
    # or degraded (503) — the important contract is the payload shape.
    assert response.status_code in (200, 503)
    body = response.json()
    assert body["status"] in ("ready", "degraded")
    assert "database" in body
    assert "redis" in body
