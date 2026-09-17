# Husky Tracking

Husky Tracking is an independent, portfolio-quality kennel-management platform
demonstration built entirely from fictional data. Its core product loop is:

**Kennel Map → Dog Profile → Daily Plan → Team Builder → Daily Entry → Analytics**

The intended public hostname is `huskytracking.com`; domain purchase and DNS are not
assumed. This repository is a new implementation, not a migration or copy of either
reference project.

## P1 foundation

- Angular 22, TypeScript, and SCSS frontend
- FastAPI, SQLAlchemy, Alembic, and PostgreSQL 18 backend foundation
- Docker Compose development environment
- fixed, validated demo clock shared through the backend health contract
- linting, typing, build, and test infrastructure
- canonical product, data, domain, architecture, reference-audit, and roadmap docs

Major domain features intentionally begin in P2. See
[`docs/IMPLEMENTATION_ROADMAP.md`](docs/IMPLEMENTATION_ROADMAP.md).

## Demo time

The dataset never ages with the host clock:

- season: `2025-12-01` through `2026-03-31`
- reference date: `2026-03-31`
- label: **Demo season — Winter 2025–2026**

Domain code must obtain this date from the application demo clock. It must not use the
machine's current date for age, class, status, housing, or workload interpretation.

## Local development with Docker

Requirements: Docker with Compose.

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- frontend: <http://localhost:4300>
- API health: <http://localhost:8030/api/v1/health>
- API docs: <http://localhost:8030/api/docs>

Stop the stack with `docker compose down`. The PostgreSQL volume persists until it is
explicitly removed.

## Local checks

Backend development requires Python 3.11+ and [uv](https://docs.astral.sh/uv/):

```bash
cd backend
uv sync --dev
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```

Frontend development uses Node 24 (the Docker image is the canonical runtime):

```bash
cd frontend
npm ci
npm run lint
npm run test:ci
npm run build
```

Run the aggregate checks from the repository root with `make check` when both runtimes
are available.

## Configuration and data safety

Copy `.env.example`; never commit `.env`. This repository may contain only fictional
dogs, people, housing, notes, and generated assets. Never import production Kennel
Operations data, photographs, exports, topology, customer records, employee names, or
secrets.

## Canonical documentation

- [`PRODUCT_SCOPE.md`](docs/PRODUCT_SCOPE.md)
- [`REFERENCE_AUDIT.md`](docs/REFERENCE_AUDIT.md)
- [`DEMO_DATA_SPEC.md`](docs/DEMO_DATA_SPEC.md)
- [`DOMAIN_MODEL.md`](docs/DOMAIN_MODEL.md)
- [`ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`IMPLEMENTATION_ROADMAP.md`](docs/IMPLEMENTATION_ROADMAP.md)
