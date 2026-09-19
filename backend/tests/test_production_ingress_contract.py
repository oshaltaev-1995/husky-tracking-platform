"""Repository contracts for the VPS ingress and maintenance handoff."""

import json
import shutil
import subprocess
import uuid
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
    assert set(services) == {"backend", "db", "huskytracking-frontend"}
    assert all(not service.get("ports") for service in services.values())
    assert set(services["huskytracking-frontend"]["networks"]) == {"default", "ingress"}
    assert services["huskytracking-frontend"]["networks"]["ingress"]["aliases"] == [
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
    assert services["huskytracking-frontend"]["ports"] == [
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


def test_shared_proxy_dns_never_resolves_husky_as_generic_frontend() -> None:
    """Exercise Docker DNS with a proxy attached to two separate app networks."""
    config = render_compose("compose.ingress.yml")
    service_name = next(
        name
        for name, service in config["services"].items()
        if "ingress" in service.get("networks", {})
    )
    assert service_name == "huskytracking-frontend"

    image = "python:3.13-alpine"
    if (
        subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            check=False,
        ).returncode
        != 0
    ):
        pytest.skip(f"Local Docker image {image} is unavailable")
    if (
        subprocess.run(["docker", "info"], capture_output=True, check=False).returncode
        != 0
    ):
        pytest.skip("Docker daemon is unavailable")

    suffix = uuid.uuid4().hex[:10]
    ko_network = f"ht-dns-ko-{suffix}"
    husky_network = f"ht-dns-husky-{suffix}"
    ko_frontend = f"ht-dns-ko-frontend-{suffix}"
    husky_frontend = f"ht-dns-husky-frontend-{suffix}"
    proxy = f"ht-dns-proxy-{suffix}"
    networks: list[str] = []
    containers: list[str] = []

    def docker(*args: str) -> str:
        result = subprocess.run(
            ["docker", *args], check=True, capture_output=True, text=True
        )
        return result.stdout.strip()

    try:
        for network in (ko_network, husky_network):
            docker("network", "create", network)
            networks.append(network)

        docker(
            "run",
            "-d",
            "--name",
            ko_frontend,
            "--network",
            ko_network,
            "--network-alias",
            "frontend",
            image,
            "sleep",
            "300",
        )
        containers.append(ko_frontend)
        docker(
            "run",
            "-d",
            "--name",
            husky_frontend,
            "--network",
            husky_network,
            "--network-alias",
            service_name,
            "--network-alias",
            "huskytracking-frontend",
            image,
            "sleep",
            "300",
        )
        containers.append(husky_frontend)
        docker(
            "run",
            "-d",
            "--name",
            proxy,
            "--network",
            ko_network,
            image,
            "sleep",
            "300",
        )
        containers.append(proxy)
        docker("network", "connect", husky_network, proxy)

        def network_ip(container: str, network: str) -> str:
            return docker(
                "inspect",
                container,
                "--format",
                f'{{{{(index .NetworkSettings.Networks "{network}").IPAddress}}}}',
            )

        def resolve(name: str) -> set[str]:
            addresses = docker(
                "exec",
                proxy,
                "python",
                "-c",
                "import json,socket,sys; "
                "print(json.dumps(sorted({row[4][0] for row in "
                "socket.getaddrinfo(sys.argv[1], None, family=socket.AF_INET)})))",
                name,
            )
            return set(json.loads(addresses))

        ko_ip = network_ip(ko_frontend, ko_network)
        husky_ip = network_ip(husky_frontend, husky_network)
        assert ko_ip != husky_ip
        assert resolve("frontend") == {ko_ip}
        assert resolve("huskytracking-frontend") == {husky_ip}
    finally:
        for container in reversed(containers):
            subprocess.run(
                ["docker", "rm", "-f", container], check=False, capture_output=True
            )
        for network in reversed(networks):
            subprocess.run(
                ["docker", "network", "rm", network], check=False, capture_output=True
            )


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
