from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_without_crashing():
    with TestClient(app) as client:
        r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] in {"ok", "degraded"}
