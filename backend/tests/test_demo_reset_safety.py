import pytest

from app.core.config import Settings
from app.demo.service import DemoResetNotAllowedError, assert_reset_is_safe


def test_reset_refuses_production() -> None:
    settings = Settings(
        _env_file=None,
        app_env="production",
        public_base_url="https://huskytracking.com",
        database_url="postgresql+psycopg://app:strong@db:5432/husky_tracking",
        cors_origins=["https://huskytracking.com"],
        allowed_hosts=["huskytracking.com"],
        demo_reset_enabled=True,
        demo_cookie_secure=True,
        demo_origin_check_enabled=True,
        demo_session_secret="a-strong-production-session-secret-12345",
        privacy_controller_name="Example controller",
        privacy_contact_email="privacy@example.com",
        privacy_controller_country="Example EEA country",
        privacy_hosting_region="Example EEA region",
        contact_delivery_mode="disabled",
    )

    with pytest.raises(DemoResetNotAllowedError, match="production"):
        assert_reset_is_safe(settings)


def test_reset_refuses_an_unrelated_database() -> None:
    settings = Settings(
        _env_file=None,
        demo_reset_enabled=True,
        database_url="postgresql+psycopg://demo:demo@localhost/unrelated",
    )

    with pytest.raises(DemoResetNotAllowedError, match="app-owned"):
        assert_reset_is_safe(settings)


def test_reset_requires_explicit_enable_flag() -> None:
    settings = Settings(_env_file=None, demo_reset_enabled=False)

    with pytest.raises(DemoResetNotAllowedError, match="DEMO_RESET_ENABLED"):
        assert_reset_is_safe(settings)
