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


def test_safe_residual_swap_is_healthy() -> None:
    state = {"swap_used_mib": 700.0}
    failures, warnings = monitor.assess_memory(
        state,
        available_mib=1900,
        used_swap_mib=700,
        ram_warn_mib=400,
        swap_warn_mib=768,
        swap_growth_mib=256,
    )
    assert failures == {}
    assert warnings == {}


def test_high_stable_swap_is_non_fatal_telemetry() -> None:
    state = {"swap_used_mib": 850.0}
    failures, warnings = monitor.assess_memory(
        state,
        available_mib=1900,
        used_swap_mib=850,
        ram_warn_mib=400,
        swap_warn_mib=768,
        swap_growth_mib=256,
    )
    assert failures == {}
    assert set(warnings) == {"swap_resident_high"}


def test_rapid_swap_growth_is_actionable() -> None:
    state = {"swap_used_mib": 700.0}
    failures, _ = monitor.assess_memory(
        state,
        available_mib=1900,
        used_swap_mib=1000,
        ram_warn_mib=400,
        swap_warn_mib=768,
        swap_growth_mib=256,
    )
    assert set(failures) == {"swap_growth"}


def test_persistent_low_ram_is_actionable_even_with_stable_swap() -> None:
    state = {"swap_used_mib": 850.0, "low_ram_streak": 1}
    failures, _ = monitor.assess_memory(
        state,
        available_mib=300,
        used_swap_mib=850,
        ram_warn_mib=400,
        swap_warn_mib=768,
        swap_growth_mib=256,
    )
    assert set(failures) == {"ram_low"}


def test_oom_increment_is_actionable() -> None:
    state = {"oom_kills": 0}
    assert set(monitor.assess_oom(state, 1)) == {"host_oom"}


def test_non_memory_failures_still_alert_and_recover() -> None:
    state: dict = {}
    failures = {
        "service_backup": "Backup timer or last service run failed",
        "disk_critical": "Host disk space is critically low",
        "public_https": "Public HTTPS homepage is unavailable",
    }
    alerts = monitor.plan_alert_events(state, failures, NOW, 6)
    assert len(alerts) == 3
    assert {event[0] for event in alerts} == {"ALERT"}
    monitor.mark_alerts_sent(state, alerts, NOW)
    recovery = monitor.plan_alert_events(state, {}, NOW + timedelta(minutes=5), 6)
    assert len(recovery) == 3
    assert {event[0] for event in recovery} == {"RECOVERY"}
