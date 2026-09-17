# Architecture

## System shape

Husky Tracking is one modular web product, not a microservice system.

```text
Browser
  └─ Angular SPA
       └─ /api/v1 HTTP/JSON
            └─ FastAPI modular monolith
                 ├─ domain/application services
                 ├─ SQLAlchemy repositories and query projections
                 ├─ deterministic demo generator
                 └─ PostgreSQL

Generated dog media → local media volume in development / object storage later
```

The public reverse proxy serves the SPA, forwards `/api/`, terminates HTTPS, and applies
security headers. Marketing and app/demo routes can live in the same Angular deployment
while retaining separate route shells.

## Selected stack

P1 uses supported, non-preview release lines as of 2026-09-17:

- Angular 22 with strict TypeScript and SCSS;
- Node 24 LTS in Docker;
- Python 3.11+ (Python 3.13 production image);
- FastAPI 0.141, SQLAlchemy 2.0, Alembic 1.20, Pydantic Settings 2;
- PostgreSQL 18;
- Docker and Docker Compose.

Exact transitive versions are committed in `package-lock.json` and `uv.lock`.
Dependency updates should be reviewed and verified, not floated during deployment.

## Repository layout

```text
backend/
  alembic/                 schema migrations
  app/
    api/                   versioned HTTP adapters
    core/                  settings and demo clock
    db/                    SQLAlchemy base/session
    domain/                P2+ entities, value objects, policies
    services/              P2+ application orchestration
    repositories/          P2+ persistence/query adapters
  tests/
frontend/
  src/app/
    core/                  singleton API/config/layout concerns
    shared/                reusable presentational pieces
    features/              map, dogs, plans, builder, entry, analytics
docs/                      canonical product and engineering decisions
media/                     ignored generated media root
```

P1 creates only folders that contain working code; later folders are added with their
packages rather than as empty architecture theater.

## Backend boundaries

Routes parse/serialize and invoke application services. They do not contain eligibility,
history, pedigree, or workload logic. Services operate in explicit transactions and
call repositories. Domain policies accept a reference date or DemoClock rather than
reading wall-clock time.

API conventions:

- all application endpoints are under `/api/v1`;
- public IDs, not database implementation IDs, appear in URLs;
- `as_of` is explicit on historical state APIs;
- errors use stable machine codes plus safe human messages;
- collection APIs use deterministic ordering and pagination where needed;
- OpenAPI is available in non-hardened environments.

The initial `GET /api/v1/health` proves frontend/backend connectivity and exposes the
demo-season contract. A later readiness endpoint may additionally verify PostgreSQL;
health should not expose secrets or infrastructure details.

## Demo clock

`Settings` validates season start/end/reference values and `DemoClock` is the only
application source for the canonical domain date. The default environment values are:

```text
DEMO_SEASON_START=2025-12-01
DEMO_SEASON_END=2026-03-31
DEMO_REFERENCE_DATE=2026-03-31
```

Age, operational class presentation, effective status/housing defaults, seed generation,
and workload windows use this clock. An explicitly selected historical date overrides
the default for that query but remains bounded/validated by the use case. Infrastructure
timestamps may use real UTC time; domain-demo calculations may not use real `today()`.

## Persistence and migrations

SQLAlchemy 2 typed mappings will implement the model in `DOMAIN_MODEL.md`. Alembic is
the only schema evolution path. Production startup runs `alembic upgrade head` as an
explicit release step; the application does not create tables opportunistically.

PostgreSQL provides foreign keys, check/unique/partial indexes, range types, GiST
exclusion constraints, recursive pedigree validation queries, and transactional locks
for capacity-sensitive housing writes. P2 starts with one coherent baseline migration;
subsequent changes are forward migrations with tested downgrade policy where practical.

The deterministic generator is application code invoked by a guarded CLI/admin reset
operation. It writes through validated services, produces a checksum/report, and is
never triggered accidentally on ordinary production startup.

## Frontend architecture

Angular uses standalone components, feature-route boundaries, strict templates, and
typed API models. The app shell owns navigation and the visible demo-season marker.
Each feature owns its pages, components, models, services, and focused utilities.

Remote data should use a consistent state/query approach introduced only when feature
complexity warrants it; no global state library is needed in P1. Accessibility basics
include semantic landmarks, keyboard-operable controls, visible focus, sufficient
contrast, meaningful empty/error/loading states, and automated checks plus manual QA.

The Kennel Map should be DOM/CSS based for accessible dog links and responsive layouts.
Its geometry is fictional configuration; visual layer changes are pure presentation
and cannot mutate housing or status.

## Plans, actuals, and analytics

Daily Plan and accepted Team Builder output remain planned data. Daily Entry or explicit
confirmation creates/updates WorkEntry and DogWork actuals. Analytics reads the actual
ledger only. This avoids double counting and keeps every total traceable.

Eligibility order is:

1. effective lifecycle/class/availability and dated exclusion;
2. activity/date and role capability;
3. hard conflict/double-booking/workload limits;
4. soft pair, housing, underuse, and balance preferences;
5. deterministic tie-break.

Every exclusion and warning has a code and user-facing explanation.

## Configuration and environments

Pydantic Settings reads environment values. `.env.example` documents safe local
defaults; `.env` is ignored. Browser configuration uses relative `/api` URLs so the same
bundle works behind a reverse proxy. CORS is restricted to configured origins and is
primarily needed for split local development.

Environments:

- **local:** Compose database/backend/frontend with bind mounts and reload;
- **test/CI:** isolated dependency installs, unit/integration tests, build, migration
  checks, and ephemeral PostgreSQL for database constraints;
- **public demo:** immutable images, managed/persistent PostgreSQL, HTTPS reverse proxy,
  controlled seed/reset, backups, logs, and no development mounts/docs unless intended.

## Containers and deployment

Development uses three services. Production images are multi-stage: Angular builds to
static assets served by Nginx; FastAPI runs as a non-root user. The current P1 Compose
file is development-oriented. P12 adds production Compose/platform configuration,
health-gated release migrations, HTTPS/reverse-proxy config, resource limits, backup/
restore, observability, and rollback documentation.

Persistent data categories are PostgreSQL and generated media. They require independent
backup/restore plans. Images and secrets do not belong in Git or baked configuration.

## Security and privacy baseline

- synthetic-only repository and seed review;
- no credentials, `.env`, production exports, or reference media in Git;
- parameterized SQL through SQLAlchemy;
- restrictive CORS and future security headers;
- sanitized errors and structured logs without notes/personal data;
- dependency/image scanning and patch review in P12;
- rate limiting and CSRF/auth decisions before any state-changing public endpoint is
  exposed;
- reset endpoints disabled or strongly controlled in public production.

The public demo may initially be read-only with reset state managed out of band. If
anonymous edits are later allowed, sessions must be isolated or periodically reset so
one visitor cannot affect another's experience indefinitely.

## Testing strategy

- unit tests for DemoClock, age, eligibility, workload, generator, and frontend utilities;
- PostgreSQL integration tests for range exclusions, relationships, migrations, and
  transaction rules;
- API contract tests for history boundary dates and idempotent writes;
- Angular component tests for loading/error/data and accessibility behavior;
- end-to-end tests for the core loop once features exist;
- deterministic snapshot/checksum tests for the v1 demo world;
- production-image smoke tests and Compose validation.

SQLite is not a substitute for PostgreSQL constraint tests.

## Architecture decisions deferred deliberately

Authentication model, hosting vendor, object-storage vendor, analytics materialization,
and anonymous demo edit isolation are selected in the package that needs them. They do
not justify microservices or extra infrastructure in P1.
