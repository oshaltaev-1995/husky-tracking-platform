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

Generated dog media → Angular static `/media/dogs/` assets (object storage can retain the same URL contract later)
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
    features/              dashboard, map, dogs, plans, builder, entry, analytics
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

`GET /api/v1/health` is inexpensive liveness and exposes the non-sensitive demo-season
contract. `GET /api/v1/ready` adds a database connectivity probe and returns only a
safe ready/unavailable state. `GET /api/v1/demo-dataset` remains the narrow verification projection for
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
- `GET /api/v1/daily-plans/{date}/activities/{activityId}/team-builder` — selected-pool
  context, dated workload/capability/relationship projection, and saved lineups;
- `POST .../teams/generate` — deterministic unsaved lineup preview with explanations;
- `PUT .../teams` — revision-checked complete-lineup validation and persistence.
- `GET /api/v1/daily-entry/{date}` — one dated plan/actual/summary/housing projection;
- `GET .../eligible-dogs` — bounded actual eligibility and existing daily-km context;
- `POST|PATCH|DELETE .../sessions` — manual create and revision-safe correction/removal;
- `POST .../planned-activities/{activityId}/confirm` — idempotent transactional
  plan/team-to-actual confirmation;
- `POST|DELETE .../{activityId}/not-run` — ledger-free not-run decision/restore.

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

## Kennel Map print projection

Map printing is a frontend-only read projection of the last coherent committed API
snapshot and selected visual layer. Opening the preview creates no request, workspace,
day or mutation. The projection is detached from both the API object and unsaved Move
draft and remains fixed for that preview. Housing operations with pending or uncertain
results must be resolved before opening it; historical read-only snapshots need no
editing precondition. Date/session/reset invalidation closes it.

A feature-local preview host is attached directly under body so scoped print media
rules can hide the application without clipping a descendant document or leaving its
screen layout as blank pages. The document itself is shared between preview and print,
uses named A4-landscape pages and the HT Ground composition: Zone A left, Zone B right,
main path between them, paired enclosure rows/service aisles, and puppy buildings below.
Resident cards and legend use the existing map tone tokens with text/markers. User
background/color print preferences remain authoritative; borders and words carry the
same information without color. Print styling
is active only while this context exists; ordinary browser printing outside it is not
globally intercepted or hidden. Lifecycle cleanup restores title, listeners, body
classes and appropriate focus. No event claims that a PDF was saved.
If afterprint is absent, a preview-local recovery guard requires an observed window
blur/return-focus sequence and explicitly inactive print media before restoring controls;
focus alone and the return value of print never remove the document or prove saving.
The preview owns a print-media change listener, so leaving print media re-evaluates that
same guard even if focus returned before media ended and afterprint never arrived. The
listener is removed on destruction; it does not intercept the browser Print shortcut.

The frozen display projection retains every resident and splits each location's ordered
roster into disjoint spatial/continuation slices. A conservative estimated text-line
budget (six for an adult cell, ten for a puppy building, at the fixed 9/10pt typography)
keeps the spatial sheet readable. This is a page-layout budget, independent of nominal
capacity and eligibility. Remaining/long names appear once in explicitly coded
continuation tables with repeating headers, never as hidden or abbreviated residents.
Only the short continuation location code is nowrap; continuation words and full names
retain their wrapping behavior.
Canonical 50-dog snapshots fit one spatial A4 landscape sheet at 100%; larger rosters
may use additional sheets. There is one automatic print flow, without a map/report mode.

Printed data includes names and dated housing/layer context, never preconditions,
revision values, cookie data, technical IDs or API URLs. There is no server-side PDF
generator, image capture pipeline or duplicate housing computation.

## Dog Summary print projection

P13E adds a frontend-only document from one completed `getProfileBundle()` subscription
(profile, pedigree, work, history). Those four existing GETs are not a transactional
snapshot. The display-only, deeply frozen projection checks dog identities, available
reference dates and known workspace-placement consistency before acceptance. It copies
no technical identity except the canonical portrait key. Domain dates come from the
backend; calendar formatting anchors them at UTC midnight, independent of host timezone
or today. Work values are copied from the same actual-ledger summary as the Work tab;
plans never contribute. No new API, schema, ledger or persisted summary exists.

A shared-profile-header action works from every tab without refetching the bundle.
Route changes cancel the old load; Reset/session replacement/known expiry close the
preview and invalidate printable state. Reset completion reloads the profile; an expired
session requires explicit recovery through the existing route guard. A late bundle or
portrait callback cannot replace a newer context. Print itself never creates a workspace,
materializes a day, calls Reset, writes state, logs notes, or stores its projection.

The document preserves full core identity, separate lifecycle/class/availability,
recorded capabilities, effective current or clearly labelled last housing, archive data,
parents and four grandparents, and per-dog actual season metrics. Temporary workspace
housing is a separate row, never a canonical history event. Up to three history starts
on/before the state date are sorted newest-first; equal dates use Availability, Class,
Lifecycle, Housing, then full value. Notes normalize whitespace and use at most 260
characters including an ellipsis, at a word boundary (an overlong single token is
bounded); shortened notes are explicitly labelled. Null work averages/dates and missing
relations remain “Not recorded”; zero starts/distance remain zero.

One document component supplies preview and selectable HTML/CSS print output. A named
A4 portrait page with 10mm margins and minimum 9pt type is body-scoped independently of
the Map's landscape page. The existing DogMedia portrait is awaited through load/decode
or fallback; an 8-second preparation bound renders the normal placeholder if necessary.
Regular registry media remains lazy. Preview initially focuses its scrollable paper,
contains keyboard focus, and has explicit Print / Save as PDF and Close actions.
The small shared `PrintPreviewLifecycle` retains P13D's observed-blur/focus/media recovery,
title ownership and destruction guards for both documents. Hosts remain feature-owned;
there is no universal export framework or browser shortcut interception. Browser-native
printing initiated before image preparation cannot be deferred by `beforeprint`; normal
Print is enabled only after preparation. No event asserts a file was saved.

P13D spatial/color work is accepted; P13E is local and pending independent review.
The exact native Save → Cmd+P → Cancel sequence remains NOT VERIFIED because the single
bounded P13E system-tool attempt found macOS locked. Headless PDF and synthetic lifecycle
checks are separate evidence. P13F and release/deployment work are outside this package.

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
typed API models. The root component owns only routing and metadata coordination.
`PublicShellComponent` owns the editorial header/footer, while `DemoShellComponent`
owns operational navigation and the visible demo-season marker. Each feature owns its
pages, components, models, services, and focused utilities.

Canonical P3 route boundaries are `/demo/dogs`, `/demo/archive`, and
`/demo/dogs/:dogId`. Dog Profile section
state is a `tab` query parameter, so pedigree/work/history views are deep-linkable. A
single request bundle is retained while tabs change. Active and archived dogs render in
the same profile composition; lifecycle changes only the projected state and visual
context. Litter siblings come only from `Dog.litter_id`; parent sharing is not silently
presented as litter siblinghood. The neutral `DogMediaComponent` owns the stable media
aspect ratio and is the P10 image integration seam.

### Public and demo route shells

P11 separates marketing content from the operational product without duplicating
either. Public routes are `/`, `/features`, `/about`, `/contact`, and `/privacy`; the application
is canonical under `/demo/...`, with `/demo` redirecting to `/demo/dashboard`.
Pre-P11 paths remain redirect-only aliases and preserve parameters and query state.
Unknown routes render the Public Shell's explicit 404 page rather than entering the
demo. Production Nginx recognizes the finite public, canonical demo, and legacy-alias
route shapes. Known deep-link refreshes receive `index.html` with `200`; an unknown
non-file path receives the same bundle with `404`, allowing Angular to retain the
branded, noindex Not Found view without a soft-404 response. This route contract must
stay aligned with `app.routes.ts`; record existence within parameterized routes remains
an API/application concern.

Public route data supplies distinct titles and descriptions. `SeoService` updates
canonical, robots, Open Graph, and Twitter metadata on navigation using
`https://huskytracking.com` as the intended base URL; P12 owns final host configuration.
Static `robots.txt` indexes public pages while excluding `/demo`, and the sitemap lists
the public routes. No tracking script or analytics cookie is included.

### Anonymous demo workspace overlay

P11.5 isolates mutable public-demo state without duplicating the 60-dog world. The
backend issues a random opaque HttpOnly `ht_demo_session` cookie; PostgreSQL stores only
its digest plus creation/expiry metadata. `DemoWorkspaceDay` is the date-level
copy-on-write marker. Before the first plan, team, or actual mutation on a date, the
service locks the workspace and clones that date's baseline mutable graph. From then on,
all mutable reads use workspace rows for that date and hide baseline rows; untouched
dates continue to resolve baseline data. Range analytics apply the same overlay and
therefore never double-count baseline plus clones.

`DailyPlan.demo_workspace_id` and `WorkSession.demo_workspace_id` own the cloned roots;
existing cascades own activities, teams, slots, and participations. Workspace deletion
cascades only those mutable graphs, never Dog or historical canonical data. The public
reset removes one workspace's materialized rows. The guarded global reset clears every
workspace before restoring the seed. `python -m app.demo.cleanup` removes expired
workspaces; the 24-hour default is configurable.

P13B adds a separate reference-date housing overlay without using the date-level
plan/work materialization path. `HousingContext` loads one explicitly scoped set of
overrides after locking the workspace row and rechecking expiry. `EffectiveDogState`
uses that context only at `DemoClock.reference_date`; historical reads retain the
canonical half-open assignment or a real gap. The location-shaped result supports
existing `location_id` and `location` consumers without inventing ORM history periods.
The context is cached only within one service request; Dashboard passes one context
to its nested Population, Map, Plan, and Entry services. Registry/profile, planning
candidates/participants, Team Builder candidate home pairing, Daily Entry groupings,
and Analytics housing buckets/range-end labels all consume the same policy.

`GET /api/v1/kennel-map?date=…` optionally resolves an existing cookie without issuing
or replacing a workspace. Missing, invalid, or expired cookies return baseline with
non-editable context. A valid reference-date workspace receives `housing_edit` with
the date, revision and an opaque HMAC precondition. `POST /api/v1/kennel-map/moves`
requires that existing cookie and a nonempty batch of at most 60 unique dogs. The
precondition binds workspace identity, reference date, and monotonic revision under
the existing session secret; it exposes neither the cookie nor secret. Origin checks
and the precondition are separate protections.

Snapshot projection, batch changes, and Reset serialize on the workspace row, using
freshly loaded state after any lock wait. The lock spans reading overrides/revision
and constructing the response; the route commits before returning the response.
Batch validation finishes before any write, and one changed batch increments revision
once. Stale confirmation returns a structured `409`; Reset increments even when empty
so an old confirmation cannot restore reset placements. Expiry cleanup deletes the
workspace and cascades its housing rows. Housing-only writes never create a
`DemoWorkspaceDay`, plan, or actual session. API responses stay `no-store`, and existing
request logs omit bodies, cookies, preconditions, and query strings. See
`P13C_HOUSING_HANDOFF.md` for the exact read/write and conflict contract.

The migration is additive, but an older application binary does not understand these
overrides or remove them on Reset. Before an application rollback to an older version,
use compatible code in a controlled maintenance step to drain/invalidate temporary
workspace data and pending housing confirmations, preserving the immutable baseline.
Otherwise an older binary can leave stale overlays that reappear after re-upgrade.
Do not assume compatibility from an additive schema alone; test the chosen rollback
sequence in a disposable database and do not routinely downgrade live schema.

The Angular demo-route guard initializes the session before operational components load.
The shell exposes expiry, a real-data warning, and an explicit scoped reset. Public
routes and Contact/Privacy endpoints have no workspace dependency. See
`PRIVACY_DATA_MAP.md` and `PRIVACY_SECURITY_REVIEW.md` for browser storage, logging,
retention, and P12 boundaries.

The public pages reuse the token system and synthetic dog assets but do not render the
operational sidebar. Their content explicitly identifies the project as an independent
portfolio demonstration and discloses fictional records, synthetic work, AI-generated
portraits, and resettable mutable state near demo entry.

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

`/demo/kennel` has Overview and Ground views in a `.content-wide` route. View mode is
the default; P13C adds a shared Move mode over P13B's accepted housing API.
`date`, `layer`, and `view` query parameters make a presentation reload-safe and
shareable. The reference date, Default
layer, and Overview are the fallbacks; `?view=ground` opens Ground directly. Public
browsing is constrained to `2025-12-01` through `2026-03-31`. The existing
`KennelMapSnapshot` API resolves birth, lifecycle, class, availability, and housing on
one calendar date. A historical housing gap stays empty rather than falling back to a
current assignment. Both views share the date-driven snapshot and mount only the active
view, so switching the view or layer does not refetch the same date or duplicate links.

- **Overview** retains P4.1's paired A1/A2 and B1/B2 rows, separate puppy areas, and
  responsive reflow within each named row.
- **Ground** depicts the same fictional zones, paired five-cell rows, aisles and
  separate puppy buildings as a DOM/CSS plan. The viewport contains zoom and pan
  instead of changing enclosure order or adjacency at mobile widths. The zoom range
  is 25–175%; Fit uses the viewport and board dimensions and never enlarges above
  100%. Additional residents can expand a row and change those bounds without
  changing the topology. Fit recalculates on resize until the user chooses a manual
  zoom. Users may zoom in to read names following a small-screen Fit; any overflow
  stays in the map viewport.

Both views render every resident in each location. Nominal capacity describes the
baseline and may guide empty-slot presentation; it does not truncate the rendered list.
Default, Gender, Neutered, Class, and Unavailable remain presentation-only layers with
text markers and legends. Search matches exact name, then prefix, then substring;
it highlights the dog and enclosure and reveals the active profile link. Every resident
name remains a regular `/demo/dogs/{public_id}` link. P13A's presentation adds no
housing writes, snapshot API changes, migrations, or seed changes. P13B adds only the
workspace exception described above; the canonical map projection remains read-only.

### Move Together editor

P13C keeps the committed `KennelMapSnapshot`, its server editing context, an in-memory
dog UUID → destination map, and an action history separate. Pure feature-local draft
functions derive preview housing and review changes without mutating API data. Repeated
assignments normalize to one final destination; returning to committed housing removes
the pending entry. Undo restores the previous intention, including a repeated move of
the same dog. Discard drops the draft, while cancelling review keeps it.

Both active map representations use the same draft and `KennelMapService.moveDogs`.
View/layer changes keep draft state and do not fetch a new snapshot. Desktop dragging
and keyboard/touch selectors stage the same operation; a dog drag does not start Ground
pan, and moving a dog does not automatically Fit or zoom the map. Review shows committed
source, proposed destination, and every affected location's resulting residents. Nominal
capacity remains informational. Server `housing_edit` controls editability, including a
valid zero revision; historical/no-workspace snapshots remain read-only.

An explicit confirmation freezes one batch and sends one POST. No interceptor or API
client retries it. A complete HTTP 200 response replaces committed state and clears the
confirmed draft/history. A 409 blocks stale confirmation until an explicit reload;
401 requires reinitializing the existing demo-session flow and loading a fresh snapshot
without replay. Narrow `DemoSessionService` reset/replacement notifications coordinate
the shell and editor. Network/timeout/uncertain 5xx outcomes remain unconfirmed until
GET reconciliation; unsubscribing or navigating cannot undo an accepted server write.
Responses from an old context cannot overwrite a newer date or session.

Date/route changes, leaving Move mode, and profile navigation protect dirty drafts;
view/layer changes remain presentation-only. Review/discard dialogs use the existing
focus-managed pattern, and beforeunload warns only while relevant unsaved work exists.
Reset invalidates the editor without a second stale-discard prompt. Drafts, preconditions,
and bodies stay out of URLs, browser storage, and logs. No backend, schema, seed, or
domain-policy changes are part of P13C. Detailed behavior and review boundaries are in
`P13C_MOVE_TOGETHER.md`; print, Training Day, and Agent work remain separate packages.

The canonical archived dogs keep valid housing history, but their assignments all end
before the public demo season. P4 therefore truthfully shows no archived resident in a
December–March snapshot; lifecycle resolution remains historical and never substitutes
current lifecycle or last-known housing. Future datasets can show a currently archived
dog on an earlier map date without changing the API shape when its active lifecycle and
housing intervals overlap that date.

### Daily Plan workspace

P5 adds `/demo/daily` as a wide operational route. The selected date is demo-season bounded,
defaults to `2026-03-31`, and is shareable through the `date` query parameter. The page
uses a compact day header, explicit note save, ordered activity cards with accessible
up/down controls, inline delete confirmation, and a focus-managed activity dialog.
The participant picker shows eligible and disabled dogs together with dated housing,
class, availability, already-planned Training km, and concise reasons. At phone widths
the dialog becomes a full-height one-column workspace with no page-level overflow.

P5 retains the selected participant pool as the builder boundary. P6 adds a functional
`Build teams`/`View teams` link to
`/demo/daily/{date}/activities/{activityId}/teams` without
changing participant ownership. Distance or pool edits that affect saved teams return a
stable conflict until the UI obtains explicit confirmation; the backend then applies
the edit and lineup deletion in one revision-checked transaction.
One-to-three-dog Training plans remain valid and can be recorded as unpositioned actual
work in Daily Entry. Daily Plan exposes Team Builder only when the selected pool meets
the minimum from `SUPPORTED_TEAM_SIZES`; the API projects that minimum so the UI does
not maintain a competing constant. A direct builder link with too few currently
eligible dogs explains the shortage and returns to Daily Plan.

### Team Builder

P6 separates candidate projection, pure deterministic solving, explanation, validation,
and persistence. The projection uses bounded aggregate queries for actual workload
strictly before the plan date: 7-day km, 14-day km/starts, season-to-date km, and days
since last work. It also returns total planned Training km on the selected date without
double-counting the activity. Effective lifecycle/class/availability/housing comes from
the same dated state policy used by P3–P5; later actual sessions never affect an earlier
generation.

The solver works in harness pairs and keeps a deterministic beam of the 240 strongest
partial arrangements. Hard rules are selected-pool membership, dated P5 eligibility,
unique dog use, explicit role capability, supported geometry, same-pair hard conflicts,
and the existing 30 km planning limit. Candidate scoring uses transparent weights:
`+1.3` per recovery day (capped at 14), `-1.8` per 7-day km, `-0.55` per 14-day km,
`-0.04` per season km, `-1.5` per 14-day start, and `-1.5` per planned km today.
Preferred pairs add `120`, exact dated home pairs add `28`, and team-to-team 7/14-day
workload spreads cost `0.8`/`0.2` per km. Name then stable dog UUID supplies the final
tie-break. Role correctness always outranks soft scoring.

Generated teams are client-visible previews only. Explicit Save persists complete
Lead/Team/Wheel, Left/Right slots and increments the owning Daily Plan revision. The
click-based editor supports replace, swap, move, clear, and fill without a drag-only
interaction. Server validation repeats every hard rule; preferred/home/workload choices
remain manually overridable. Reopening shows saved geometry rather than regenerating.

### Daily Entry

P7 adds `/demo/daily-entry` as a wide, date-query-driven operations route. One bounded read
returns Daily Plan context, canonical actual sessions, derived day totals, and every
active resident grouped by housing resolved on that date. Find Dog highlights/focuses
the dated resident; zero-work dogs stay visible. Seeded sessions reopen like any other
actual and are editable during a demo run.

`DailyEntryService` is the actual mutation boundary. It uses `EffectiveDogState`, the
shared workload rule, bounded daily aggregates, explicit role capabilities, and precise
same-pair conflict semantics. Confirm-from-plan copies a saved P6 lineup including team,
pair, side, role, and order; without teams it copies selected participants unpositioned.
The nullable unique plan link makes repeated confirmation idempotent. Manual create,
revision-checked edit, and explicit delete all return a fully rehydrated day. Actual
edits never mutate planned pools or saved teams, and plan deletion only nulls provenance.

Confirm-from-plan is deliberately two-step in the UI. A focus-managed review presents
the date, activity, distance, exact dogs that will be copied, and saved-lineup context;
no request is made until confirmation. Successful recording exposes immediate Undo,
while every reopened linked session exposes Revert actual. Both use the existing
revision-checked deletion boundary, so the plan returns to `not_recorded` and Dog Work,
Dashboard, and Analytics recalculate from the canonical ledger rather than client state.
Pending guards prevent duplicate UI submission; the service and database unique plan
link remain the authoritative duplicate protection.

The focus-managed actual editor supports unpositioned participant selection, positioned
replacement, compatible cross-position swaps, removal, and clearing all harness
geometry without drag-only interaction. Dated housing/class/availability and current
actual km are visible in candidate rows. At phone width the editor becomes a full-height
single-column workspace and the page uses stacked cards without horizontal overflow.

## Plans, actuals, and analytics

Daily Plan and accepted Team Builder output remain planned data. Daily Entry creates or
updates `WorkSession`/`WorkParticipation` actuals. Dog Profile and P8 Analytics read this
ledger only. This avoids double counting and keeps every total traceable.

The baseline checksum excludes mutable Daily Plan/Team rows but includes seeded actual
work. Runtime Daily Entry corrections therefore legitimately change the live semantic
checksum. Demo reset truncates planning and actual rows, regenerates canonical sessions,
and restores the exact zero-plan baseline checksum.

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

### Analytics workspace

P8 adds the read-only `/demo/analytics` wide workspace with Population and Workload areas.
The reload-safe Workload range uses `from`/`to` query parameters; Population uses a
dated `view=population&date=...` snapshot. Invalid values normalize inside the demo
season. Angular consumes explicit projections rather than recomputing domain state from
a raw dog list.

`AnalyticsService` performs two bounded actual-ledger projections plus bounded
select-in loading of all dog histories. It never queries per dog and never reads Daily
Plan or Planned Team rows. Shared participation-distance summarization keeps Dog Profile
and kennel analytics totals identical. No cache or materialized summary means P7
create/edit/delete mutations appear on the next read.

Workload overview returns semantic KPIs, zero-filled Monday–Sunday weeks, 5/10 km and
recorded-role breakdowns, and class/eligible-day-normalized attention lists. The dog
projection intentionally includes relevant zero-start and archived historical dogs,
then adds selected-range streaks and end-date state/housing context. Lightweight
DOM/CSS charts retain exact textual values and responsive dog cards replace the desktop
row layout below the tablet breakpoint.

Population uses the same `EffectiveDogState` resolver as Map/Profile/Plan for lifecycle,
class, availability, and housing. The API returns headline lifecycle counts plus
server-computed age bands, birth cohorts, sex, class, neuter, availability, capability,
and housing-area distributions. Cohorts show represented active and archived history;
the other distributions describe active dogs at the selected snapshot date.

### Operational Dashboard

P9's Dashboard now lives at `/demo/dashboard` as the operational landing route, while
P11 uses `/` for the public product site. The Dashboard is anchored to the DemoClock reference
date (`2026-03-31`) and uses a single `GET /api/v1/dashboard?date=...` projection so the
Angular shell does not fan out across many endpoints.

`DashboardService` is orchestration, not a second analytics implementation. It composes
the existing Population snapshot, dated Kennel Map, Daily Plan, Daily Entry, P8 attention,
and weekly workload services. Population and availability use effective state for the
same selected date; actual-day totals retain P7/P8 session/start/dog-km semantics; the
attention window is the inclusive previous 14 days ending on the dashboard date. The
recent trend is the latest six Monday-based demo weeks. No Dashboard table, cache, or
stored aggregate exists, so plan/team and actual-work mutations appear on the next read.

The response stays summary-sized: headline population/class/availability/housing counts,
current unavailable residents, concise plan/team/actual state, up to three representative
dogs in each attention category, and six weekly points. Every item links back to its
owning feature instead of duplicating editors, maps, profiles, or analytics. The wide
workspace uses a compact responsive section grid; at phone width it becomes a single
column with textual chart values and no page-level horizontal overflow.

### Synthetic dog media

P10 keeps one media identity per stable Dog UUID without adding a gallery or probing
the filesystem during API reads. `Dog.photo_key` is the nullable activation contract;
the existing read DTOs expose it unchanged. A null or unsafe key renders the polished
placeholder and makes no image request. An activated key must be exactly
`<public-uuid>.webp` and resolves in the shared Angular component to
`/media/dogs/<key>?v=dog-media-v1`. A load error removes the failed image element and
restores the same fixed-ratio fallback, so the browser never leaves a broken-image UI.

Canonical assets live once in `frontend/public/media/dogs/`, which Angular copies for
development and production builds. Registry/Archive instances load lazily; the Profile
hero loads eagerly. Every context keeps a `3:4` frame, `object-fit: cover`, and identity
alt text. The UUID filename is immutable identity while the separate media version query
is the simple cache-invalidation boundary for a curated replacement set.

`docs/dog-media-manifest.json` is a generated, reviewable projection of the curated
60-dog visual-identity catalog. Its version is independent of
`winter-2025-2026-v1`. The media CLI validates canonical ownership, filenames, required
traits, pedigree/litter mapping, WebP container structure, exact 1086×1448 dimensions,
and file-size distribution. It does not claim to automate subjective anatomy or source
review; those remain explicit human gates. P10B ships 60 reviewed synthetic portraits
and deterministically seeds all 60 UUID filenames. Media keys are deliberately excluded
from the domain semantic checksum, so the canonical world hash remains stable while
`dog-media-v1` versions the independent visual artifact set.

## Configuration and environments

Pydantic Settings reads environment values. `.env.example` documents safe local
defaults; `.env` is ignored. Browser configuration uses relative `/api` URLs so the same
bundle works behind a reverse proxy. CORS is restricted to configured origins and is
primarily needed for split local development.

The contact form posts plain text to `POST /api/v1/contact`. Pydantic validates bounded
name, email, subject, message, optional organization, and an invisible honeypot. The
delivery service has `sink`, `disabled`, and SMTP implementations selected by
environment configuration. Sink mode logs only field-length metadata; messages are
never persisted in PostgreSQL. SMTP credentials, sender, and recipient remain secrets
for P12 deployment. Delivery errors return a generic safe 503 and never expose
transport details.

Environment mode is explicit (`development`, `test`, or `production`) rather than
inferred from hostname. Production validation requires the canonical HTTPS public URL,
allowed host/origin, HMAC session secret, Secure cookie, origin guard, real privacy
metadata, a non-local PostgreSQL URL, and encrypted complete SMTP whenever SMTP is
enabled. Interactive OpenAPI is available in development/test and disabled in
production. SQLAlchemy pool size/overflow/timeouts and Uvicorn workers are bounded and
environment-configurable.

SEO reads `PUBLIC_BASE_URL` from a small runtime config file generated by the production
container; development defaults to the browser origin. Thus one relative-API Angular
bundle serves local and production environments without embedding localhost in public
metadata.

Environments:

- **local:** Compose database/backend/frontend with bind mounts and reload;
- **test/CI:** isolated dependency installs, unit/integration tests, build, migration
  checks, and ephemeral PostgreSQL for database constraints;
- **public demo:** immutable images, managed/persistent PostgreSQL, HTTPS reverse proxy,
  controlled seed/reset, backups, logs, and no development mounts/docs unless intended.

## Containers and deployment

Development uses three published services with bind mounts. Production images are
multi-stage: Angular builds without source maps to static assets served by Nginx;
FastAPI runs as a non-root user. `compose.production.yml` publishes no host ports;
`compose.ingress.yml` places only the uniquely named `huskytracking-frontend` service
on external `huskytracking_proxy`. The unique Compose service key prevents a Docker DNS
collision with Kennel Operations' existing `frontend` upstream when Caddy joins both
networks. Backend/database remain on the Husky-private network with
health-gated startup. `compose.staging.yml` is a separate loopback-only 8081 exception.
Nginx serves SPA deep links/media, proxies `/api`, overwrites backend forwarding
headers, and sets CSP/security/cache/compression/body-size policy. Its transient
source-IP rate-limit zones trust forwarded client IPs only from the reviewed ingress
CIDR; direct callers cannot supply a rate-limit identity. Caddy owns public TLS and
future HSTS, without needing a rate-limit plugin.

Alembic migration and the non-destructive `app.demo.initialize` command are explicit
deployment jobs. Application startup never resets or reseeds. The full first-deploy,
redeploy, cleanup, backup/restore, and rollback model is documented in
`PRODUCTION_DEPLOYMENT.md`.

Persistent runtime state is PostgreSQL. The 60 generated portraits are versioned source
artifacts copied into the image, while secrets stay in runtime environment files.
PostgreSQL backup/restore remains independent of source/artifact reproducibility.

## Security and privacy baseline

- synthetic-only repository and seed review;
- no credentials, `.env`, production exports, or reference media in Git;
- parameterized SQL through SQLAlchemy;
- canonical-origin CORS, allowed-host enforcement, mutation Origin checks, CSP,
  anti-sniffing, clickjacking, referrer, permissions, and no-store API policy;
- sanitized errors and structured logs without notes/personal data;
- dependency/image scanning and patch review in P12;
- transient source-IP rate limiting at Husky inner Nginx behind the trusted Caddy
  network; no misleading per-process limiter;
- reset endpoints disabled or strongly controlled in public production.

The public demo allows anonymous edits only through the isolated, expiring workspace
overlay described above. No workspace is associated with Contact data or an account.
Session tokens are HMAC-SHA256 digests under the production secret. The cookie is
host-only, HttpOnly, SameSite=Lax, Secure, and `/api/v1` scoped. Cookie-authenticated
unsafe methods require the canonical Origin in production; Contact remains an
unauthenticated spam/abuse boundary. P12B schedules cleanup and validates deployed
proxy/security controls.

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

## P12A production build baseline

The Node 24 production build measured on 2026-09-18 is 324.86 kB raw initial
JavaScript/CSS (87.93 kB estimated transfer): main JavaScript is 314.88 kB and CSS is
9.98 kB. Production emits no source maps. The public Home hero portrait is 219,892
bytes; the largest dog portrait in the complete media set is 286,672 bytes. P12B must
repeat measurements over the real HTTPS/network path rather than treating local bundle
sizes as a Core Web Vitals claim.

## Architecture decisions deferred deliberately

Authentication model, hosting vendor, object-storage vendor, analytics materialization,
and anonymous demo edit isolation are selected in the package that needs them. They do
not justify microservices or extra infrastructure.
