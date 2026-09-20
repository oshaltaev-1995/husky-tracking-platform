from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path


def load_monitor():
    path = Path(__file__).resolve().parents[1] / "monitor.py"
    spec = importlib.util.spec_from_file_location("husky_monitor", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


monitor = load_monitor()
NOW = datetime(2026, 3, 31, tzinfo=timezone.utc)


def test_alert_duplicate_and_recovery() -> None:
    state: dict = {}
    alert = monitor.plan_alert_events(state, {"backend": "Backend unavailable"}, NOW, 6)
    assert [event[0] for event in alert] == ["ALERT"]
    monitor.mark_alerts_sent(state, alert, NOW)
    assert (
        monitor.plan_alert_events(
            state, {"backend": "Backend unavailable"}, NOW + timedelta(minutes=5), 6
        )
        == []
    )
    recovery = monitor.plan_alert_events(state, {}, NOW + timedelta(minutes=10), 6)
    assert [event[0] for event in recovery] == ["RECOVERY"]
    monitor.mark_alerts_sent(state, recovery, NOW + timedelta(minutes=10))
    assert state["incidents"] == {}


def test_failed_delivery_retries_and_early_recovery_drops_unsent_alert() -> None:
    state: dict = {}
    alert = monitor.plan_alert_events(state, {"backup": "Backup stale"}, NOW, 6)
    assert (
        monitor.plan_alert_events(
            state, {"backup": "Backup stale"}, NOW + timedelta(minutes=5), 6
        )
        == alert
    )
    assert monitor.plan_alert_events(state, {}, NOW + timedelta(minutes=10), 6) == []
    assert state["incidents"] == {}


def test_reminder_only_after_six_hours() -> None:
    state: dict = {}
    alert = monitor.plan_alert_events(state, {"disk": "Disk low"}, NOW, 6)
    monitor.mark_alerts_sent(state, alert, NOW)
    assert (
        monitor.plan_alert_events(
            state, {"disk": "Disk low"}, NOW + timedelta(hours=5), 6
        )
        == []
    )
    reminder = monitor.plan_alert_events(
        state, {"disk": "Disk low"}, NOW + timedelta(hours=6), 6
    )
    assert [event[0] for event in reminder] == ["REMINDER"]


def test_recovery_retries_after_mail_failure() -> None:
    state: dict = {}
    alert = monitor.plan_alert_events(state, {"https": "HTTPS down"}, NOW, 6)
    monitor.mark_alerts_sent(state, alert, NOW)
    recovery = monitor.plan_alert_events(state, {}, NOW + timedelta(minutes=5), 6)
    assert (
        monitor.plan_alert_events(state, {}, NOW + timedelta(minutes=10), 6) == recovery
    )
