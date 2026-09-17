from datetime import date

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.demo_clock import DemoClock


def test_demo_clock_uses_canonical_dates() -> None:
    clock = DemoClock.from_settings(Settings(_env_file=None))

    assert clock.season_start == date(2025, 12, 1)
    assert clock.season_end == date(2026, 3, 31)
    assert clock.reference_date == date(2026, 3, 31)
    assert clock.season_label == "Demo season — Winter 2025–2026"


def test_reference_date_must_be_inside_season() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, demo_reference_date=date(2026, 4, 1))


def test_cors_origins_accept_comma_separated_environment_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "CORS_ORIGINS", "https://huskytracking.com,http://localhost:4300"
    )

    settings = Settings(_env_file=None)

    assert settings.cors_origins == [
        "https://huskytracking.com",
        "http://localhost:4300",
    ]
