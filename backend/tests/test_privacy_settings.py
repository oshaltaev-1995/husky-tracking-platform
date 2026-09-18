import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_requires_secure_cookie_and_real_privacy_contact() -> None:
    with pytest.raises(ValidationError, match="Secure"):
        Settings(_env_file=None, app_env="production")
    with pytest.raises(ValidationError, match="privacy controller"):
        Settings(
            _env_file=None,
            app_env="production",
            demo_cookie_secure=True,
        )


def test_production_smtp_requires_public_provider_metadata() -> None:
    with pytest.raises(ValidationError, match="SMTP privacy provider"):
        Settings(
            _env_file=None,
            app_env="production",
            demo_cookie_secure=True,
            privacy_contact_email="privacy@example.com",
            privacy_controller_country="Example EEA country",
            privacy_hosting_region="Example EEA region",
            contact_delivery_mode="smtp",
        )
