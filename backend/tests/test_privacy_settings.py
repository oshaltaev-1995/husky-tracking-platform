from datetime import date

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.routes import demo_workspace as privacy_routes
from app.core.config import Settings, get_settings
from app.main import app
from app.operations.provider_models import ProviderSettings


def production_values() -> dict[str, object]:
    return {
        "_env_file": None,
        "app_env": "production",
        "public_base_url": "https://huskytracking.com",
        "database_url": "postgresql+psycopg://app:strong@db:5432/husky_tracking",
        "cors_origins": ["https://huskytracking.com"],
        "allowed_hosts": ["huskytracking.com"],
        "demo_session_secret": "a-strong-production-session-secret-12345",
        "demo_cookie_secure": True,
        "demo_origin_check_enabled": True,
        "privacy_controller_name": "Example controller",
        "privacy_contact_email": "privacy@example.com",
        "privacy_controller_country": "Example EEA country",
        "privacy_hosting_region": "Example EEA region",
        "contact_delivery_mode": "disabled",
    }


def test_production_requires_secure_cookie_and_real_privacy_contact() -> None:
    insecure = production_values() | {"demo_cookie_secure": False}
    with pytest.raises(ValidationError, match="Secure"):
        Settings(**insecure)  # type: ignore[arg-type]

    placeholder = production_values() | {
        "privacy_contact_email": "privacy@example.invalid"
    }
    with pytest.raises(ValidationError, match="privacy controller"):
        Settings(**placeholder)  # type: ignore[arg-type]


def test_production_smtp_requires_public_provider_metadata() -> None:
    values = production_values() | {
        "contact_delivery_mode": "smtp",
        "contact_recipient_email": "contact@example.com",
        "smtp_host": "smtp.example.com",
        "smtp_from": "contact@example.com",
    }
    with pytest.raises(ValidationError, match="SMTP privacy provider"):
        Settings(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("published_date", [None, date(2026, 12, 3)])
def test_candidate_privacy_date_is_explicit_and_publication_can_override_it(
    monkeypatch: pytest.MonkeyPatch, published_date: date | None
) -> None:
    values = production_values()
    if published_date is not None:
        values["privacy_effective_date"] = published_date
    configuration = Settings(**values)  # type: ignore[arg-type]
    expected = published_date or date(2026, 11, 22)
    assert configuration.privacy_effective_date == expected
    monkeypatch.setitem(app.dependency_overrides, get_settings, lambda: configuration)
    monkeypatch.setattr(
        privacy_routes, "get_provider_settings", lambda: ProviderSettings(enabled=False)
    )

    client = TestClient(app)
    response = client.get("/api/v1/public/privacy")

    assert response.status_code == 200
    assert response.json()["effective_date"] == expected.isoformat()
    assert response.json()["demo_workspace_ttl_hours"] == 24
    assert response.json()["operations_review_enabled"] is False
    assert response.json()["operations_review_providers"] == []
    assert response.json()["controller_name"] == configuration.privacy_controller_name
    assert response.json()["hosting_region"] == configuration.privacy_hosting_region
    assert "set-cookie" not in response.headers
    assert not client.cookies
    assert response.headers["Cache-Control"] == "no-store"
