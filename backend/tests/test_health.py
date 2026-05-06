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


def test_readiness_returns_ready() -> None:
    """GET /health/ready returns 200."""
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
