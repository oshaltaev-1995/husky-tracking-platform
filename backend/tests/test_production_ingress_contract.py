"""Repository contracts for the VPS ingress and maintenance handoff."""

import json
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlsplit

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


def mapped_rate_key(
    config: str, variable: str, method: str, request_target: str
) -> str:
    """Check the repository's simple map rules; real Nginx is tested separately.

    In particular, require normalized $uri rather than query-bearing $request_uri.
    Only literal/regex maps already used by these four zones are interpreted here.
    """
    mapping = re.search(
        rf'map\s+("\$request_method:\$uri"|\$request_method)\s+'
        rf"\${variable}\s*\{{([^}}]*)\}}",
        config,
    )
    assert mapping is not None, f"Missing expected method/$uri map: {variable}"
    source, body = mapping.groups()
    key = (
        f"{method}:{urlsplit(request_target).path}"
        if source.startswith('"')
        else method
    )
    default = None
    for line in body.splitlines():
        rule = re.fullmatch(r'\s*(~\S+|"[^"]+"|\w+)\s+([^;]+);\s*', line)
        if rule is None:
            assert not line.strip(), f"Unrecognized rate-map rule in {variable}"
            continue
        pattern, result = rule.groups()
        assert result in {'""', "$binary_remote_addr"}
        if pattern == "default":
            default = result
        elif (pattern.startswith("~") and re.search(pattern[1:], key)) or (
            not pattern.startswith("~") and pattern.strip('"') == key
        ):
            return result
    assert default == '""', f"Non-targeted requests must not be limited by {variable}"
    return default


@pytest.mark.parametrize(
    ("method", "target", "limited_maps"),
    [
        ("GET", "/api/v1/training-day-example", {"team_generate"}),
        ("GET", "/api/v1/training-day-example?review=1", {"team_generate"}),
        ("POST", "/api/v1/training-day-example/apply", {"team_generate", "mutation"}),
        (
            "POST",
            "/api/v1/training-day-example/apply?review=2",
            {"team_generate", "mutation"},
        ),
        (
            "POST",
            "/api/v1/daily-plans/2026-03-29/activities/test/teams/generate",
            {"team_generate", "mutation"},
        ),
        ("POST", "/api/v1/training-day-example", {"mutation"}),
        ("GET", "/api/v1/training-day-example/apply", set()),
        ("HEAD", "/api/v1/training-day-example", set()),
        ("GET", "/api/v1/training-day-example/not-an-endpoint", set()),
        ("GET", "/api/v1/kennel-map?date=2026-03-31", set()),
        ("GET", "/api/v1/dogs/example-dog/work", set()),
        ("GET", "/api/v1/daily-plans/2026-03-29", set()),
        ("GET", "/api/v1/analytics/overview?from=2025-12-01&to=2026-03-31", set()),
        ("GET", "/", set()),
        ("GET", "/features", set()),
        ("GET", "/media/dogs/example.webp?v=dog-media-v1", set()),
        ("GET", "/main-example.js", set()),
        ("GET", "/api/v1/demo/session", {"demo"}),
        ("POST", "/api/v1/contact", {"contact", "mutation"}),
    ],
)
def test_solver_limit_maps_only_the_expensive_methods_and_ignores_query_strings(
    method: str, target: str, limited_maps: set[str]
) -> None:
    config = (REPOSITORY / "frontend/nginx.conf").read_text()
    actual = {
        name
        for name in ("contact", "demo", "team_generate", "mutation")
        if mapped_rate_key(config, f"{name}_rate_key", method, target)
        == "$binary_remote_addr"
    }
    assert actual == limited_maps


def test_solver_requests_share_existing_policy_and_safe_json_rejection() -> None:
    config = (REPOSITORY / "frontend/nginx.conf").read_text()
    assert len(re.findall(r"limit_req_zone[^;]+team_generate_per_client", config)) == 1
    assert re.search(
        r"limit_req_zone\s+\$team_generate_rate_key\s+"
        r"zone=team_generate_per_client:10m\s+rate=10r/m;",
        config,
    )
    assert re.search(
        r"limit_req\s+zone=team_generate_per_client\s+burst=6\s+nodelay;",
        config,
    )
    assert re.search(
        r"limit_req\s+zone=mutations_per_client\s+burst=30\s+nodelay;",
        config,
    )
    rejected = re.search(
        r"location\s+@rate_limited\s*\{(.*?)^\s*\}", config, re.DOTALL | re.MULTILINE
    )
    assert rejected is not None
    assert "default_type application/json;" in rejected[1]
    body = re.search(r"return\s+429\s+'(.+)';", rejected[1])
    assert body is not None
    assert json.loads(body[1]) == {"detail": "Too many requests"}
    assert "include /etc/nginx/trusted-proxy.conf;" in config
    assert "real_ip_header X-Forwarded-For;" in config
    assert "real_ip_recursive off;" in config


@pytest.mark.parametrize(
    ("method", "path", "limited"),
    [
        ("POST", "/api/v1/operations/review", True),
        ("POST", "/api/v1/operations/review?new-cookie=1", True),
        ("GET", "/api/v1/operations/review", False),
        ("GET", "/api/v1/operations/capabilities", False),
        ("GET", "/api/v1/daily-plans/2026-03-29", False),
        ("POST", "/api/v1/demo/reset", False),
        ("POST", "/api/v1/training-day-example/apply", False),
        ("GET", "/", False),
    ],
)
def test_operations_ingress_boundary_is_exact_and_cookie_independent(
    method: str, path: str, limited: bool
) -> None:
    config = (REPOSITORY / "frontend/nginx.conf").read_text()
    actual = mapped_rate_key(config, "operations_rate_key", method, path)
    assert (actual == "$binary_remote_addr") is limited
    assert re.search(
        r"limit_req_zone\s+\$operations_rate_key\s+"
        r"zone=operations_per_client:10m\s+rate=2r/m;",
        config,
    )
    assert "limit_req zone=operations_per_client burst=1 nodelay;" in config
    assert "limit_conn operations_concurrent_per_client 1;" in config
    assert "limit_conn_status 429;" in config
    assert "proxy_ignore_client_abort off;" in config
    assert "proxy_next_upstream off;" in config
    mapping = re.search(
        r'map "\$request_method:\$uri" \$operations_rate_key \{([^}]+)\}', config
    )
    assert mapping and not re.search(r"cookie|session|http_x", mapping[1], re.I)


def test_agent_compose_flags_remain_explicitly_disabled_and_keys_server_only() -> None:
    config = render_compose("compose.ingress.yml")
    services = config["services"]
    assert isinstance(services, dict)
    environment = services["backend"]["environment"]
    assert environment["AGENT_ENABLED"] == "false"
    assert environment["AGENT_GROQ_FREE_ACCOUNT_CONFIRMED"] == "false"
    frontend = services["huskytracking-frontend"]["environment"]
    assert not any(key.startswith("AGENT_") for key in frontend)


def test_nginx_distinguishes_known_spa_routes_from_unknown_paths() -> None:
    config = (REPOSITORY / "frontend/nginx.conf").read_text()
    assert "location = / {" in config
    assert "^/(features|about|contact|privacy)/?$" in config
    assert "^/demo(?:/dashboard|/dogs(?:/[^/]+)?" in config
    assert "daily(?:/[^/]+/activities/[^/]+/teams)?" in config
    assert "error_page 404 =404 /index.html;" in config
    assert "try_files $uri $uri/ =404;" in config


def test_development_proxy_preserves_the_browser_host_for_backend_validation() -> None:
    proxy = json.loads((REPOSITORY / "frontend/proxy.conf.json").read_text())
    assert proxy["/api"] == {
        "target": "http://backend:8000",
        "secure": False,
        "changeOrigin": False,
    }


def test_caddy_hsts_contract_is_single_origin_only_and_not_duplicated() -> None:
    caddy = (REPOSITORY / "ops/production/caddy-huskytracking.conf.example").read_text()
    nginx = (REPOSITORY / "frontend/nginx.conf").read_text()
    assert caddy.count("Strict-Transport-Security") == 1
    assert 'Strict-Transport-Security "max-age=31536000"' in caddy
    assert "includeSubDomains" not in caddy
    assert "preload" not in caddy
    assert "Strict-Transport-Security" not in nginx
