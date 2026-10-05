"""Small host-side monitor for the Husky Tracking production stack only.

Run from the dedicated systemd timer. No demo session or database mutation is made.
SMTP credentials and the private recipient come from the existing root-only runtime
environment and are never included in logs or monitor state.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shutil
import smtplib
import ssl
import subprocess
import sys
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

STATE_DIR = Path("/var/lib/huskytracking-monitor")
STATE_FILE = STATE_DIR / "alert-state.json"
BACKUP_DIR = Path("/var/backups/huskytracking")
HUSKY_STATE_DIR = Path("/var/lib/huskytracking")
CONTAINERS = {
    "frontend": "husky-tracking-production-huskytracking-frontend-1",
    "backend": "husky-tracking-production-backend-1",
    "database": "husky-tracking-production-db-1",
}
SERVICES = {
    "backup": ("huskytracking-backup.timer", "huskytracking-backup.service"),
    "cleanup": ("huskytracking-cleanup.timer", "huskytracking-cleanup.service"),
    "ingress": (
        "huskytracking-ingress-network.timer",
        "huskytracking-ingress-network.service",
    ),
}
UTC = timezone.utc


def setting_int(name: str, default: int) -> int:
    value = int(os.environ.get(name, str(default)))
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def run(command: list[str], *, timeout: int = 8) -> str:
    # Never return a subprocess error message: it may contain environment data.
    result = subprocess.run(
        command, capture_output=True, text=True, timeout=timeout, check=False
    )
    if result.returncode != 0:
        raise RuntimeError("check command failed")
    return result.stdout.strip()


def safe_check(
    failures: dict[str, str], code: str, label: str, check: Callable[[], None]
) -> None:
    try:
        check()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        failures[code] = label


def require_https() -> None:
    request = urllib.request.Request("https://huskytracking.com/", method="GET")
    with urllib.request.urlopen(
        request, timeout=8, context=ssl.create_default_context()
    ) as response:
        if response.status != 200:
            raise RuntimeError("unexpected HTTP status")


def require_private_readiness() -> None:
    code = (
        "import urllib.request; "
        "request=urllib.request.Request('http://127.0.0.1:8000/api/v1/ready',"
        "headers={'Host':'huskytracking.com'}); "
        "urllib.request.urlopen(request,timeout=3).read()"
    )
    run(["docker", "exec", CONTAINERS["backend"], "/opt/venv/bin/python", "-c", code])


def container_state(name: str) -> tuple[bool, str, int]:
    template = (
        "{{.State.Running}}|{{if .State.Health}}{{.State.Health.Status}}"
        "{{else}}none{{end}}|{{.RestartCount}}"
    )
    running, health, restarts = run(
        ["docker", "inspect", "--format", template, name]
    ).split("|")
    return running == "true", health, int(restarts)


def service_is_healthy(timer: str, service: str) -> bool:
    active = run(["systemctl", "is-active", timer]) == "active"
    result = run(["systemctl", "show", service, "--property=Result", "--value"])
    return active and result == "success"


def require_service(timer: str, service: str) -> None:
    if not service_is_healthy(timer, service):
        raise RuntimeError("Husky maintenance service is not healthy")


def latest_backup_age(now: datetime) -> timedelta:
    timestamp = (HUSKY_STATE_DIR / "last-successful-backup").read_text().strip()
    if not re.fullmatch(r"20\d{6}T\d{6}Z", timestamp):
        raise ValueError("invalid backup timestamp")
    created = datetime.strptime(timestamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    if created > now + timedelta(minutes=5):
        raise ValueError("backup timestamp is in the future")
    backup = BACKUP_DIR / timestamp
    if not backup.is_dir():
        raise ValueError("backup directory missing")
    for name in ("database.dump", "database.dump.sha256", "manifest.txt"):
        if (backup / name).stat().st_size == 0:
            raise ValueError("backup artifact empty")
    manifest = (backup / "manifest.txt").read_text()
    if f"timestamp_utc={timestamp}" not in manifest or "dump_sha256=" not in manifest:
        raise ValueError("backup manifest incomplete")
    return now - created


def meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, _, value = line.partition(":")
        if key in {"MemAvailable", "SwapTotal", "SwapFree"}:
            values[key] = int(value.strip().split()[0]) * 1024
    if len(values) != 3:
        raise ValueError("memory information incomplete")
    return values


def oom_kills() -> int:
    for line in Path("/proc/vmstat").read_text().splitlines():
        if line.startswith("oom_kill "):
            return int(line.split()[1])
    raise ValueError("OOM counter unavailable")


def assess_memory(
    state: dict,
    *,
    available_mib: float,
    used_swap_mib: float,
    ram_warn_mib: int,
    swap_warn_mib: int,
    swap_growth_mib: int,
) -> tuple[dict[str, str], dict[str, str]]:
    """Classify host memory without treating cold resident swap as pressure."""
    failures: dict[str, str] = {}
    warnings: dict[str, str] = {}

    low_ram = available_mib < ram_warn_mib
    state["low_ram_streak"] = state.get("low_ram_streak", 0) + 1 if low_ram else 0
    if state["low_ram_streak"] >= 2:
        failures["ram_low"] = "Available host RAM has remained low"

    previous_swap = state.get("swap_used_mib", used_swap_mib)
    state["swap_used_mib"] = used_swap_mib
    if used_swap_mib >= swap_warn_mib:
        warnings["swap_resident_high"] = (
            f"Host resident swap is {used_swap_mib:.0f} MiB"
        )
    if used_swap_mib - previous_swap >= swap_growth_mib:
        failures["swap_growth"] = "Host swap use grew rapidly since the previous check"

    return failures, warnings


def assess_oom(state: dict, current_oom: int) -> dict[str, str]:
    failures: dict[str, str] = {}
    previous_oom = state.get("oom_kills")
    if previous_oom is not None and current_oom > previous_oom:
        failures["host_oom"] = "Host OOM-kill counter increased"
    state["oom_kills"] = current_oom
    return failures


def collect_failures(
    state: dict, now: datetime, warnings: dict[str, str] | None = None
) -> dict[str, str]:
    failures: dict[str, str] = {}
    if warnings is None:
        warnings = {}
    safe_check(
        failures, "public_https", "Public HTTPS homepage is unavailable", require_https
    )
    safe_check(
        failures,
        "backend_ready",
        "Private backend readiness failed",
        require_private_readiness,
    )

    previous_restarts = state.setdefault("restart_counts", {})
    for role, name in CONTAINERS.items():
        try:
            running, health, restarts = container_state(name)
            if not running or health != "healthy":
                failures[f"container_{role}"] = f"Husky {role} container is not healthy"
            previous = previous_restarts.get(role)
            if previous is not None and restarts > previous:
                failures[f"restart_{role}"] = f"Husky {role} restart count increased"
            previous_restarts[role] = restarts
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            failures[f"container_{role}"] = (
                f"Husky {role} container state is unavailable"
            )

    for role, (timer, service) in SERVICES.items():
        safe_check(
            failures,
            f"service_{role}",
            f"Husky {role} timer or last service run failed",
            lambda timer=timer, service=service: require_service(timer, service),
        )

    try:
        age = latest_backup_age(now)
        if age > timedelta(hours=setting_int("HT_MONITOR_BACKUP_MAX_AGE_HOURS", 30)):
            failures["backup_stale"] = "Husky PostgreSQL backup is stale"
    except (OSError, ValueError):
        failures["backup_stale"] = "Husky PostgreSQL backup evidence is missing"

    try:
        free_gib = shutil.disk_usage("/").free / (1024**3)
        if free_gib < setting_int("HT_MONITOR_DISK_CRIT_GIB", 8):
            failures["disk_critical"] = "Host disk space is critically low"
        elif free_gib < setting_int("HT_MONITOR_DISK_WARN_GIB", 15):
            failures["disk_warning"] = "Host disk space is low"
    except (OSError, ValueError):
        failures["disk_unknown"] = "Host disk availability is unknown"

    try:
        memory = meminfo()
        available_mib = memory["MemAvailable"] / (1024**2)
        used_swap_mib = (memory["SwapTotal"] - memory["SwapFree"]) / (1024**2)
        memory_failures, memory_warnings = assess_memory(
            state,
            available_mib=available_mib,
            used_swap_mib=used_swap_mib,
            ram_warn_mib=setting_int("HT_MONITOR_RAM_WARN_MIB", 400),
            swap_warn_mib=setting_int("HT_MONITOR_SWAP_WARN_MIB", 768),
            swap_growth_mib=setting_int("HT_MONITOR_SWAP_GROWTH_MIB", 256),
        )
        failures.update(memory_failures)
        warnings.update(memory_warnings)
    except (OSError, ValueError):
        failures["memory_unknown"] = "Host memory information is unavailable"

    try:
        failures.update(assess_oom(state, oom_kills()))
    except (OSError, ValueError):
        failures["oom_unknown"] = "Host OOM counter is unavailable"

    return failures


def plan_alert_events(
    state: dict, failures: dict[str, str], now: datetime, reminder_hours: int
) -> list[tuple[str, str, str]]:
    """Update incident state and return events needing mail; delivery is committed separately."""
    incidents = state.setdefault("incidents", {})
    events: list[tuple[str, str, str]] = []
    for code in sorted(set(incidents) | set(failures)):
        incident = incidents.get(code)
        if code in failures:
            if incident is None or not incident.get("active", False):
                incident = {
                    "active": True,
                    "alerted": False,
                    "pending": "ALERT",
                    "last_sent": None,
                }
                incidents[code] = incident
            incident["description"] = failures[code]
            if not incident.get("pending") and incident.get("alerted"):
                last = datetime.fromisoformat(incident["last_sent"])
                if now - last >= timedelta(hours=reminder_hours):
                    incident["pending"] = "REMINDER"
        elif incident is not None and incident.get("active"):
            if incident.get("alerted"):
                incident["active"] = False
                incident["pending"] = "RECOVERY"
            else:
                del incidents[code]
                continue
        if incident and incident.get("pending"):
            events.append((incident["pending"], code, incident["description"]))
    return events


def mark_alerts_sent(
    state: dict, events: list[tuple[str, str, str]], now: datetime
) -> None:
    incidents = state["incidents"]
    for kind, code, _ in events:
        if kind == "RECOVERY":
            incidents.pop(code, None)
        else:
            incident = incidents[code]
            incident["alerted"] = True
            incident["last_sent"] = now.isoformat()
            incident["pending"] = None


def send_mail(subject: str, body: str) -> None:
    if (
        os.environ.get("SMTP_STARTTLS", "").lower() != "true"
        or os.environ.get("SMTP_USE_SSL", "").lower() != "false"
    ):
        raise ValueError("Monitor requires certificate-verified STARTTLS")
    host = os.environ["SMTP_HOST"]
    port = int(os.environ["SMTP_PORT"])
    username = os.environ["SMTP_USERNAME"]
    password = os.environ["SMTP_PASSWORD"]
    recipient = os.environ["CONTACT_RECIPIENT_EMAIL"]
    sender = os.environ["SMTP_FROM"]
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(host, port, timeout=10) as client:
        client.ehlo()
        client.starttls(context=ssl.create_default_context())
        client.ehlo()
        client.login(username, password)
        client.send_message(message)


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text())


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = STATE_DIR / ".alert-state.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(state, handle, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, STATE_FILE)


def rehearse() -> None:
    now = datetime(2026, 3, 31, tzinfo=UTC)
    state: dict = {}
    alert = plan_alert_events(
        state, {"injected": "Injected monitor test condition"}, now, 6
    )
    assert [event[0] for event in alert] == ["ALERT"]
    mark_alerts_sent(state, alert, now)
    duplicate = plan_alert_events(
        state,
        {"injected": "Injected monitor test condition"},
        now + timedelta(minutes=5),
        6,
    )
    assert duplicate == []
    recovery = plan_alert_events(state, {}, now + timedelta(minutes=10), 6)
    assert [event[0] for event in recovery] == ["RECOVERY"]
    mark_alerts_sent(state, recovery, now + timedelta(minutes=10))
    assert state["incidents"] == {}
    print(
        "Monitor rehearsal passed: one ALERT, duplicate suppressed, one RECOVERY; no mail sent."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--test-alert",
        action="store_true",
        help="Send exactly one monitoring test email",
    )
    parser.add_argument(
        "--rehearse",
        action="store_true",
        help="Exercise alert transitions without mail or live changes",
    )
    args = parser.parse_args()
    if args.rehearse:
        rehearse()
        return 0
    if args.test_alert:
        try:
            send_mail(
                "[Husky Tracking] Monitoring test",
                "This is the one-time Husky Tracking production monitoring test. No incident was created.",
            )
        except (OSError, ValueError, KeyError, smtplib.SMTPException) as error:
            print(
                f"Monitoring test delivery failed ({type(error).__name__}); no secret details logged.",
                file=sys.stderr,
            )
            return 2
        print("Monitoring test accepted by SMTP relay; no incident state changed.")
        return 0

    STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    with Path("/run/lock/huskytracking-monitor.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = load_state()
        now = datetime.now(UTC)
        warnings: dict[str, str] = {}
        failures = collect_failures(state, now, warnings)
        events = plan_alert_events(
            state, failures, now, setting_int("HT_MONITOR_REMINDER_HOURS", 6)
        )
        delivery_failed = False
        if events:
            lines = [
                f"{kind}: {code} — {description}" for kind, code, description in events
            ]
            subject = f"[Husky Tracking] Monitoring update ({len(events)} check{'s' if len(events) != 1 else ''})"
            try:
                send_mail(
                    subject,
                    "Husky Tracking production monitor\n\n" + "\n".join(lines) + "\n",
                )
                mark_alerts_sent(state, events, now)
            except (OSError, ValueError, KeyError, smtplib.SMTPException) as error:
                delivery_failed = True
                print(
                    f"Alert delivery pending retry ({type(error).__name__}); no secret details logged.",
                    file=sys.stderr,
                )
        save_state(state)
        warning_codes = ",".join(sorted(warnings)) or "none"
        print(
            f"Husky monitor: {len(failures)} failing checks; "
            f"{len(warnings)} non-fatal warnings ({warning_codes}); "
            f"{len(events)} alert events considered."
        )
        return 2 if delivery_failed else 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
