"""Repository contracts for the VPS ingress and maintenance handoff."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]


def render_compose(overlay: str) -> dict[str, object]:
    if shutil.which("docker") is None:
        pytest.skip("Docker Compose is not installed")
    command = [
        "docker",
        "compose",
        "--project-name",
        "husky-tracking-production",
        "--env-file",
        ".env.production.example",
        "-f",
        "compose.production.yml",
        "-f",
        overlay,
        "config",
        "--format",
        "json",
    ]
    result = subprocess.run(
        command,
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_final_ingress_has_no_host_ports_and_frontend_only_proxy_membership() -> None:
    config = render_compose("compose.ingress.yml")
    services = config["services"]
    assert isinstance(services, dict)
    assert all(not service.get("ports") for service in services.values())
    assert set(services["frontend"]["networks"]) == {"default", "ingress"}
    assert services["frontend"]["networks"]["ingress"]["aliases"] == [
        "huskytracking-frontend"
    ]
    assert set(services["backend"]["networks"]) == {"default"}
    assert set(services["db"]["networks"]) == {"default"}
    assert config["networks"]["ingress"]["name"] == "huskytracking_proxy"
    assert set(config["volumes"]) == {"production-postgres-data"}


def test_staging_publication_is_loopback_only() -> None:
    config = render_compose("compose.staging.yml")
    services = config["services"]
    assert isinstance(services, dict)
    assert services["frontend"]["ports"] == [
        {
            "mode": "ingress",
            "host_ip": "127.0.0.1",
            "target": 80,
            "published": "8081",
            "protocol": "tcp",
        }
    ]
    assert not services["backend"].get("ports")
    assert not services["db"].get("ports")


def test_maintenance_never_starts_compose_dependencies() -> None:
    cleanup = (REPOSITORY / "ops/production/cleanup.sh").read_text()
    backup = (REPOSITORY / "ops/production/backup.sh").read_text()
    for script in (cleanup, backup):
        assert "--project-name husky-tracking-production" in script
        assert "--env-file /etc/huskytracking/.env.production" in script
        assert "-f /opt/huskytracking/compose.production.yml" in script
        assert "compose up" not in script
        assert "compose down" not in script
    assert "run --rm --no-deps backend" in cleanup
    assert "compose exec -T db" in backup
    assert "\ncompose run" not in backup


def test_inner_nginx_limits_only_targeted_api_operations() -> None:
    config = (REPOSITORY / "frontend/nginx.conf").read_text()
    assert '"POST:/api/v1/contact"' in config
    assert '"GET:/api/v1/demo/session"' in config
    assert '"POST:/api/v1/demo/reset"' in config
    assert "/teams/generate$" in config
    assert "limit_req_status 429;" in config
    assert "client_max_body_size 256k;" in config
    assert "set_real_ip_from 0.0.0.0/0" not in config
    assert "location /api/ {" in config
    assert "location / {\n        try_files" in config
