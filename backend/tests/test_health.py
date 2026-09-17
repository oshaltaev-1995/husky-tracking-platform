from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_contract_exposes_demo_clock() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Husky Tracking API",
        "version": "0.1.0",
        "demo_season": "Demo season — Winter 2025–2026",
        "demo_season_start": "2025-12-01",
        "demo_season_end": "2026-03-31",
        "demo_reference_date": "2026-03-31",
    }
