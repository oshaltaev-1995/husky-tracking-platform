from __future__ import annotations

import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app
from app.services.demo_workspace_service import token_digest


def production_values(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "_env_file": None,
        "app_env": "production",
        "public_base_url": "https://huskytracking.com",
        "database_url": "postgresql+psycopg://app:strong@db:5432/husky_tracking",
        "cors_origins": ["https://huskytracking.com"],
        "allowed_hosts": ["huskytracking.com", "testserver"],
        "demo_session_secret": "a-strong-production-session-secret-12345",
        "demo_cookie_secure": True,
        "demo_origin_check_enabled": True,
        "privacy_controller_name": "Example controller",
        "privacy_contact_email": "privacy@example.com",
        "privacy_controller_country": "Example EEA country",
        "privacy_hosting_region": "Example EEA region",
        "contact_delivery_mode": "disabled",
    }
    values.update(overrides)
    return values


def test_development_configuration_remains_usable() -> None:
    settings = Settings(_env_file=None)
    assert settings.app_env == "development"
    assert settings.public_base_url == "http://localhost:4300"


def test_workspace_token_digest_is_keyed_by_the_runtime_secret() -> None:
    first = token_digest("opaque-token", "first-secret")
    second = token_digest("opaque-token", "second-secret")

    assert first != second
    assert len(first) == 64


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"public_base_url": "http://huskytracking.com"}, "PUBLIC_BASE_URL"),
        ({"demo_session_secret": "weak"}, "DEMO_SESSION_SECRET"),
        ({"demo_cookie_secure": False}, "Secure"),
        ({"demo_origin_check_enabled": False}, "origin checking"),
        ({"privacy_contact_email": "privacy@example.invalid"}, "privacy controller"),
        (
            {"database_url": "postgresql+psycopg://app:password@localhost/test"},
            "DATABASE_URL",
        ),
    ],
)
def test_production_rejects_insecure_configuration(
    override: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        Settings(**production_values(**override))


def test_production_smtp_requires_complete_encrypted_privacy_configuration() -> None:
    with pytest.raises(ValidationError, match="SMTP contact configuration"):
        Settings(**production_values(contact_delivery_mode="smtp"))
    with pytest.raises(ValidationError, match="transport encryption"):
        Settings(
            **production_values(
                contact_delivery_mode="smtp",
                contact_recipient_email="contact@example.com",
                smtp_host="smtp.example.com",
                smtp_from="contact@example.com",
                smtp_starttls=False,
                smtp_use_ssl=False,
                privacy_mail_provider_name="Example Mail",
                privacy_mail_provider_region="EEA",
            )
        )
    with pytest.raises(ValidationError, match="privacy provider"):
        Settings(
            **production_values(
                contact_delivery_mode="smtp",
                contact_recipient_email="contact@example.com",
                smtp_host="smtp.example.com",
                smtp_from="contact@example.com",
            )
        )
    implicit_tls = Settings(
        **production_values(
            contact_delivery_mode="smtp",
            contact_recipient_email="contact@example.com",
            smtp_host="smtp.example.com",
            smtp_from="contact@example.com",
            smtp_starttls=False,
            smtp_use_ssl=True,
            privacy_mail_provider_name="Example Mail",
            privacy_mail_provider_region="EEA",
        )
    )
    assert implicit_tls.smtp_use_ssl is True


def test_production_docs_hosts_headers_cache_and_origin_guard() -> None:
    application = create_app(Settings(**production_values()))
    client = TestClient(application)

    assert client.get("/api/docs").status_code == 404
    rejected_host = client.get("/api/v1/health", headers={"host": "attacker.example"})
    assert rejected_host.status_code == 400

    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["x-request-id"]
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]

    blocked = client.post(
        "/api/v1/demo/reset",
        headers={"cookie": "ht_demo_session=opaque-demo-token"},
    )
    assert blocked.status_code == 403
    assert blocked.json() == {"detail": "Request origin is not allowed"}


def test_production_cors_allows_only_canonical_origin() -> None:
    client = TestClient(create_app(Settings(**production_values())))
    allowed = client.options(
        "/api/v1/health",
        headers={
            "origin": "https://huskytracking.com",
            "access-control-request-method": "GET",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == (
        "https://huskytracking.com"
    )
    denied = client.options(
        "/api/v1/health",
        headers={
            "origin": "https://attacker.example",
            "access-control-request-method": "GET",
        },
    )
    assert denied.status_code == 400


def test_request_logging_excludes_query_and_cookie_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = TestClient(create_app(Settings(**production_values())))
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        response = client.get(
            "/api/v1/health?secret=should-not-be-logged",
            headers={"cookie": "ht_demo_session=opaque-cookie-value"},
        )

    assert response.status_code == 200
    messages = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name == "uvicorn.error"
    )
    assert "path=/api/v1/health" in messages
    assert "should-not-be-logged" not in messages
    assert "opaque-cookie-value" not in messages
