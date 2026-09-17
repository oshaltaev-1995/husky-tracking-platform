# Husky Tracking

Husky Tracking is an independent, portfolio-quality kennel-management platform
demonstration built entirely from fictional data. Its core product loop is:

**Kennel Map → Dog Profile → Daily Plan → Team Builder → Daily Entry → Analytics**

The intended public hostname is `huskytracking.com`; domain purchase and DNS are not
assumed. This repository is a new implementation, not a migration or copy of either
reference project.

## P5 application foundation

- Angular 22, TypeScript, and a token-based Sass/SCSS design system
- FastAPI, SQLAlchemy, Alembic, and PostgreSQL 18 backend
- Docker Compose development environment
- fixed, validated demo clock shared through the backend health contract
- normalized dogs, litters/pedigree, dated class/lifecycle/availability/housing,
  locations, roles, relationships, and work-session persistence
- deterministic `winter-2025-2026-v1` demo reset with 50 active and 10 archived
  fictional dogs
- persistent desktop application sidebar, accessible mobile drawer, and standard/wide
  content modes ready for later operational modules
- responsive `/dogs`, `/archive`, `/kennel`, `/daily`, and deep-linked `/dogs/:dogId`
  product routes
- server-supported registry/archive search, domain filters, and focused sorting
- one lifecycle-aware Dog Profile with Overview, Pedigree, Work, and History views
- clickable parents, grandparents, litter siblings, offspring, and archived relatives
- season work summaries derived from work participation, plus effective-dated class,
  availability, lifecycle, and housing timelines
- reusable neutral dog media placeholder ready for P10 synthetic portraits
- semantic validation and checksum independent of database identities and timestamps
- reusable actual-work guardrail enforcing at most 30 km per dog per calendar date
- historical Kennel Map snapshots with A1/A2/B1/B2 rows, two puppy buildings,
  dated housing/state resolution, dog finding, and Default/Gender/Neutered/Class/
  Unavailable visual layers
- PostgreSQL-backed Daily Plans with ordered activities, dated manual participant pools,
  optimistic revisions, and the shared 30 km per-dog/day training guardrail
- linting, typing, build, and test infrastructure
- canonical product, data, domain, architecture, reference-audit, and roadmap docs

The next product package is P6 Team Builder. P5 deliberately stops at selected dog
pools: it adds no harness positions, pair optimization, auto-fill, actual confirmation,
or kennel analytics. See
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
docker compose exec backend uv run alembic upgrade head
docker compose exec backend uv run python -m app.demo.seed
```

Then open:

- frontend: <http://localhost:4300>
- API health: <http://localhost:8030/api/v1/health>
- dataset summary: <http://localhost:8030/api/v1/demo-dataset>
- dogs registry API: <http://localhost:8030/api/v1/dogs>
- archive API: <http://localhost:8030/api/v1/archive>
- Kennel Map: <http://localhost:4300/kennel>
- dated map API: <http://localhost:8030/api/v1/kennel-map?date=2026-03-31>
- Daily Plan: <http://localhost:4300/daily>
- Daily Plan API: <http://localhost:8030/api/v1/daily-plans/2026-03-31>
- API docs: <http://localhost:8030/api/docs>

Stop the stack with `docker compose down`. The PostgreSQL volume persists until it is
explicitly removed.

## Canonical demo data commands

The commands are deliberately scoped to the non-production database named
`husky_tracking` and require `DEMO_RESET_ENABLED=true`.

```bash
cd backend
uv run alembic upgrade head

# Initialize an empty domain database. Refuses if dogs already exist.
DEMO_RESET_ENABLED=true uv run python -m app.demo.seed

# Explicitly clear only Husky Tracking domain tables and restore canonical v1.
DEMO_RESET_ENABLED=true uv run python -m app.demo.reset

# Validate and print the currently seeded world without changing it.
uv run python -m app.demo.inspect
```

The reset report includes cohorts, litters/parents, class and archive distributions,
current statuses, housing-history coverage, seasonal workload range, maximum daily dog
workload, and the semantic checksum.
The checksum covers the immutable canonical world (including work sessions and starts)
after sorting and replacing database keys with stable names/codes. It excludes mutable
Daily Plan workspace rows, generated timestamps, and PostgreSQL metadata. Demo reset
clears those planning rows and restores the known zero-plan baseline while preserving
the same core checksum.

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

`pytest` includes PostgreSQL integration coverage and resets the local app-owned demo
database twice to prove checksum determinism. Run Alembic first and ensure PostgreSQL is
available through the configured `DATABASE_URL`.

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
