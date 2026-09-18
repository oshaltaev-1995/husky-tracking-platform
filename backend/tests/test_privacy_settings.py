import pytest
from pydantic import ValidationError

from app.core.config import Settings


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
