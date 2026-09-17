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
    domain/                reusable business rules independent of adapters
    models/                typed P2 SQLAlchemy domain persistence
    demo/                  curated catalog, generator, validation, checksum, CLIs
    schemas/               explicit product-facing response DTOs
    services/              P3 read projections and shared effective-state policy
  tests/
frontend/
  src/styles/              Sass tokens, mixins, type, forms, primitives, utilities
  src/app/
    core/                  singleton API/config/layout concerns
    shared/                reusable presentational pieces
    features/              map, dogs, plans, builder, entry, analytics
docs/                      canonical product and engineering decisions
media/                     ignored generated media root
```

Feature services/repositories are added with the package that needs them rather than as
empty architecture theater.

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

`GET /api/v1/health` proves frontend/backend connectivity and exposes the demo-season
contract. `GET /api/v1/demo-dataset` remains the narrow verification projection for
version, reference date, counts, and checksum. P3 adds focused read APIs:

- `GET /api/v1/dogs` — active registry summary, search, filters, and sorting;
- `GET /api/v1/archive` — archived registry, reason filter, and sorting;
- `GET /api/v1/dogs/{dog_id}` — lifecycle-aware identity/current-state profile;
- `GET /api/v1/dogs/{dog_id}/pedigree` — parents, grandparents, litter siblings, and
  offspring without lifecycle filtering;
- `GET /api/v1/dogs/{dog_id}/work` — dog-level season ledger and weekly summary;
- `GET /api/v1/dogs/{dog_id}/history` — dated class, availability, lifecycle, housing,
  and archive metadata.
- `GET /api/v1/kennel-map?date=YYYY-MM-DD` — one demo-season-bounded location snapshot
  with effective residents, lifecycle, class, availability, housing, and layer counts.
- `GET|PUT /api/v1/daily-plans/{date}` — lazy dated plan read and note mutation;
- `POST|PATCH|DELETE /api/v1/daily-plans/{date}/activities...` — revision-checked
  activity creation, editing, ordering, and removal;
- `GET /api/v1/daily-plans/{date}/eligible-dogs` — one bounded participant projection
  with dated housing, effective state, planned km, and human-facing exclusion reasons.

`EffectiveDogState` is the shared half-open-period resolver used by both
`DogReadService` and `KennelMapReadService`, so Profile and Map agree for the same dog
and date. Dog reads bulk-load related histories and derive work totals from
`WorkSession` plus `WorkParticipation`. The map read service bulk-loads all locations,
dogs, effective histories, litters, and housing in a bounded seven-query projection;
it never queries once per enclosure or resident. Routes validate query/path values,
invoke these services, and serialize explicit Pydantic DTOs. No current
class/status/housing fields or workload aggregates are duplicated on Dog.

`DailyPlanService` is the P5 mutation boundary. It validates season dates, resolves dog
state through the same `EffectiveDogState`, checks activity policy and the shared
workload guardrail, and returns a complete revisioned day after each transaction.
Public activity UUIDs appear in routes; integer keys remain internal. A stale revision
returns a stable `plan_changed` conflict. The eligibility projection loads dogs and
their histories in bounded select-in queries rather than per-profile calls.

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

SQLAlchemy 2 typed mappings implement the model in `DOMAIN_MODEL.md`. Alembic is
the only schema evolution path. Production startup runs `alembic upgrade head` as an
explicit release step; the application does not create tables opportunistically.

PostgreSQL provides foreign keys, check/unique/partial indexes, range types, GiST
exclusion constraints, and transactional enforcement primitives. The P2 semantic
validator performs pedigree traversal and interval-capacity checks in the seeding
transaction. P2 starts with one coherent baseline migration; subsequent changes are
forward migrations with tested downgrade policy where practical.

The deterministic generator is application code invoked by guarded CLI operations. It
uses a fixed curated catalog for identity/pedigree and deterministic scheduling for
work. `seed` refuses existing Dog rows; `reset` truncates only an explicit domain-table
allowlist after checking non-production mode, an enable flag, and the app-owned
database name. `inspect` is read-only. Every write is validated before commit and the
normalized semantic snapshot is SHA-256 hashed without generated IDs/timestamps. No
seed/reset operation runs on ordinary application startup.

## Frontend architecture

Angular uses standalone components, feature-route boundaries, strict templates, and
typed API models. The app shell owns navigation and the visible demo-season marker.
Each feature owns its pages, components, models, services, and focused utilities.

P3 route boundaries are `/dogs`, `/archive`, and `/dogs/:dogId`. Dog Profile section
state is a `tab` query parameter, so pedigree/work/history views are deep-linkable. A
single request bundle is retained while tabs change. Active and archived dogs render in
the same profile composition; lifecycle changes only the projected state and visual
context. Litter siblings come only from `Dog.litter_id`; parent sharing is not silently
presented as litter siblinghood. The neutral `DogMediaComponent` owns the stable media
aspect ratio and is the P10 image integration seam.

### Application shell and Sass system

P3.5 replaces the two-link top navigation with a compact 232 px desktop sidebar and a
focus-managed mobile drawer below 900 px. The sidebar renders only implemented routes
but groups them so Dashboard, Kennel Map, Daily Plan/Entry, and Analytics can be added
without changing shell structure. Navigation closes after mobile route changes, traps
keyboard focus while open, restores trigger focus, and locks document scrolling.

Shared Sass is organized as tokens, breakpoint/focus mixins, typography, forms,
components, and utilities. Sass-defined decisions are exposed as semantic CSS custom
properties for runtime state styling. Shared breakpoints are phone 480 px, tablet
900 px, desktop 1200 px, and wide 1440 px; feature layouts reflow rather than relying
on page-wide horizontal scrolling. `.content-standard` constrains registry/profile
content, while `.content-wide` is the P4 seam for a sidebar, toolbar, and wide map
canvas. Feature styles consume tokens and shared primitives before adding local values.

Remote data should use a consistent state/query approach introduced only when feature
complexity warrants it; no global state library is needed in P1. Accessibility basics
include semantic landmarks, keyboard-operable controls, visible focus, sufficient
contrast, meaningful empty/error/loading states, and automated checks plus manual QA.

The Kennel Map should be DOM/CSS based for accessible dog links and responsive layouts.
Its geometry is fictional configuration; visual layer changes are pure presentation
and cannot mutate housing or status.

### Historical Kennel Map

P4 adds `/kennel` as a `.content-wide` route. `date` and `layer` query parameters make
historical views reload-safe and shareable; invalid values normalize to the reference
date and Default layer. Public browsing is constrained to `2025-12-01` through
`2026-03-31`. Every snapshot resolves birth, lifecycle, class, availability, and
housing on that same calendar date. A historical housing gap stays empty rather than
falling back to a current assignment.

P4.1 renders each five-enclosure adult row as a continuous physical block with shared
walls and fixed resident slots. A1/A2 and B1/B2 remain paired around a narrow service
aisle, so layer or historical-state changes update the residents inside stable
geography rather than rearranging locations. Puppy areas use separate building
footprints on the same ground surface. At tablet widths the compact five-cell rows are
retained while readable; narrower layouts reflow within named rows, and phone widths
stack cells without page-wide horizontal scrolling. Default, Gender, Neutered, Class,
and Unavailable are single-select presentation layers over the same payload. Text
markers and compact legends accompany shared semantic colors. Search focuses a dated
resident and outlines its enclosure; every resident name is a normal
`/dogs/{public_id}` link.

The canonical archived dogs keep valid housing history, but their assignments all end
before the public demo season. P4 therefore truthfully shows no archived resident in a
December–March snapshot; lifecycle resolution remains historical and never substitutes
current lifecycle or last-known housing. Future datasets can show a currently archived
dog on an earlier map date without changing the API shape when its active lifecycle and
housing intervals overlap that date.

### Daily Plan workspace

P5 adds `/daily` as a wide operational route. The selected date is demo-season bounded,
defaults to `2026-03-31`, and is shareable through the `date` query parameter. The page
uses a compact day header, explicit note save, ordered activity cards with accessible
up/down controls, inline delete confirmation, and a focus-managed activity dialog.
The participant picker shows eligible and disabled dogs together with dated housing,
class, availability, already-planned Training km, and concise reasons. At phone widths
the dialog becomes a full-height one-column workspace with no page-level overflow.

P5 intentionally retains only a selected participant pool. No Team/position model,
solver, pair/conflict UI, or inert Team Builder button is introduced. P6 can attach
lineups to the stable Training activity UUID and reuse its date/distance/pool.

## Plans, actuals, and analytics

Daily Plan and accepted Team Builder output remain planned data. Daily Entry or explicit
confirmation creates/updates WorkSession and WorkParticipation actuals. Analytics reads
the actual ledger only. This avoids double counting and keeps every total traceable.

The immutable canonical checksum does not include mutable Daily Plan rows. Demo reset
explicitly truncates planning tables before reseeding and restores a zero-plan baseline;
the canonical dog/pedigree/state/housing/actual-work checksum therefore remains stable.

Eligibility order is:

1. effective lifecycle/class/availability and dated exclusion;
2. activity/date and role capability;
3. hard conflict/double-booking/workload limits;
4. soft pair, housing, underuse, and balance preferences;
5. deterministic tie-break.

Every exclusion and warning has a code and user-facing explanation.

Actual sled work has a hard reusable ceiling of 30 km per dog per calendar date.
`app.domain.workload` validates canonical 5/10 km additions; the seed scheduler and
semantic validator call it, and P5/P7 must call the same policy before saving planned or
actual participation.

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
static assets served by Nginx; FastAPI runs as a non-root user. The current development
Compose file is development-oriented. P12 adds production Compose/platform
configuration, health-gated release migrations, HTTPS/reverse-proxy config, resource
limits, backup/restore, observability, and rollback documentation.

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

- unit tests for DemoClock, curated catalog, eligibility, workload, generator, and
  frontend utilities;
- PostgreSQL integration tests for range exclusions, relationships, migrations, and
  transaction rules;
- API contract tests for registry filters, pedigree links, work derivation, effective
  histories, history boundary dates, and idempotent writes;
- Angular component tests for loading/error/data and accessibility behavior;
- end-to-end tests for the core loop once features exist;
- deterministic snapshot/checksum tests for the v1 demo world;
- production-image smoke tests and Compose validation.

SQLite is not a substitute for PostgreSQL constraint tests.

## Architecture decisions deferred deliberately

Authentication model, hosting vendor, object-storage vendor, analytics materialization,
and anonymous demo edit isolation are selected in the package that needs them. They do
not justify microservices or extra infrastructure.
