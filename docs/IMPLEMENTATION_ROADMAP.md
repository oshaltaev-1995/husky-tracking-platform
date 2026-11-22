# Authoritative implementation roadmap

Packages are completion gates, not loose phases. A package is complete only when its
required behavior, migrations, tests, docs, and acceptance checks pass. Do not begin
the next package to disguise incomplete current work.

## P1 — Audit, specification, and foundation

**Objective:** establish the independent product contract and a verified full-stack
skeleton.

**Required behavior:** explicit fixed demo clock; backend health contract; frontend
shell visibly identifies the synthetic Winter 2025–2026 demo and verifies API
connectivity.

**Backend:** FastAPI app, environment settings, DemoClock, SQLAlchemy base/session,
Alembic environment, health route, lint/type/test configuration.

**Frontend:** Angular standalone shell, responsive styling, typed health client,
loading/connected/unavailable states, lint/test/build configuration.

**Data/migrations:** PostgreSQL Compose service and empty migration environment; no
domain schema or seed data yet.

**Tests:** settings/date validation, health contract, shell health rendering, static
checks and production build.

**Acceptance:** all canonical docs exist; references remain unchanged; Compose config is
valid; service smoke test succeeds where Docker is available; one coherent commit.

**Exclusions:** no dogs, seed generator, profiles, map, plans, teams, work, analytics, or
generated photos.

## P2 — Synthetic demo world and domain persistence

**Status:** completed. P2 delivered the baseline migration, curated
`winter-2025-2026-v1` catalog, guarded seed/reset/inspect CLIs, PostgreSQL semantic
validator, deterministic checksum, and narrow dataset-summary endpoint. No P3 UI was
started.

**Objective:** implement the normalized domain core and deterministic canonical world.

**Required behavior:** reset/reseed produces 50 active + 10 archived fictional dogs,
valid three-generation pedigree, dated state/housing, fictional topology, roles/rules,
and complete season work with a stable checksum.

**Backend:** implemented Dog, first-class Litter parentage,
class/lifecycle/availability periods, archive, locations/housing,
capabilities/constraints, WorkSession/WorkParticipation, semantic validation/checksum,
DemoClock-based effective-state policies, and guarded seed/reset/inspect CLIs.

**Frontend:** no major feature UI; add a developer/demo dataset status surface only if
needed to verify seed version/counts.

**Data/migrations:** delivered baseline domain migration with PostgreSQL checks, foreign
keys, `btree_gist`, exclusion constraints, indexes, and seed-version metadata.

**Tests:** delivered migration up/down/smoke; population and cohort invariants; pedigree
chronology, ages, and cycle rejection; interval overlap rejection; occupancy/capacity;
deterministic checksum; full-season workload eligibility and distribution.

**Acceptance:** every invariant in `DEMO_DATA_SPEC.md` passes; two resets are identical;
no real/reference production record is present; generator report is documented.

**Exclusions:** no complete Dog Profile or map UI; do not generate photos.

## P3 — Dogs, Dog Profile, and Archive

**Status:** completed. P3 delivered the responsive active registry, preserved-record
archive, shared active/archived Dog Profile, focused read APIs, clickable three-
generation pedigree, canonical dog-level work ledger, effective-dated history views,
typed Angular API services, and neutral P10-ready media placeholder. The P2 schema and
semantic checksum remain unchanged.

**Objective:** make each fictional dog's identity and history a showcase feature.

**Required behavior:** searchable active registry and archive; Profile/Bio, Pedigree,
Work, and Status History tabs; archived relatives remain navigable; demo-relative age;
last-known housing for archived dogs.

**Backend:** delivered dog list/detail filters, effective summaries, pedigree/offspring/
sibling queries, demo-season work summaries/history, and archive reads. Editing and
lifecycle writes were intentionally excluded.

**Frontend:** delivered responsive registry/archive, tabbed detail, neutral photo
placeholder, status/class/lifecycle badges, linked pedigree, work trend/table,
chronological status and housing histories, empty/error/loading states.

**Data/migrations:** no change was required; P3 uses P2 normalized persistence and adds
no duplicated summary columns.

**Tests:** delivered API coverage for active/archive filtering, current projection,
archived pedigree links, work totals/interruptions, chronological histories, and 404s;
Angular coverage for registry/search/navigation, stable tab state, relation links,
archive indication, zero work, and API error states; desktop/narrow visual QA.

**Acceptance:** complete; a visitor can understand an active or archived dog without
ambiguous state; all values use the fixed reference/selected date.

**Exclusions:** no gallery/editor, no generated portraits, no permanent delete workflow.

**P4 handoff:** the map can consume stable dog UUID/profile links plus the existing
effective current-state projection shape (`lifecycle`, `dog_class`, `availability`, and
`housing`). P4 should add only its dated location-layout projection and layer semantics;
it should reuse P3 Dog Profile deep links and must not duplicate the effective-period
resolver.

## P3.5 — Application Shell, Sass Design System, UX Refinement, and Workload Guardrails

**Status:** completed. P3.5 establishes the long-term operational shell without
starting P4: persistent compact desktop sidebar, accessible mobile drawer, standard and
wide content modes, centralized Sass/CSS tokens and breakpoints, compact Dogs filters
with active chips, stronger dog cards, refined profile/archive presentation, and the
shared daily workload rule.

**Domain:** `MAX_DAILY_DOG_DISTANCE_KM = 30` is a hard limit per dog/calendar date.
Canonical 5 km and 10 km sessions may combine up to 30 km. The seed scheduler and
semantic validator share one rule implementation; tests cover valid 5/10 combinations,
35 km rejection, and the complete PostgreSQL dataset. The audited v1 maximum was 10 km,
so seed rows and checksum remain unchanged.

**Frontend:** Dogs retains all P3 server filters/sorts behind a compact expandable
workflow. Dog Profile keeps its query-compatible `profile` tab while displaying the
clearer label “Overview”; Pedigree relationship cards and active/archived navigation are
preserved. Archive remains the same historical registry in a quieter visual treatment.

**P4 handoff:** use the existing sidebar, `.content-wide` workspace mode, semantic
status tokens, shared controls, and 900 px drawer breakpoint. P4 adds only its map route,
toolbar, dated projection, and responsive kennel canvas.

## P4 — Kennel Map

**Status:** completed. P4 delivers the read-only historical `/kennel` wide workspace,
one bounded-query dated snapshot API, canonical A1/A2/B1/B2 and puppy-area topology,
resident search/highlight, stable Dog Profile links, and Default, Gender, Neutered,
Class, and Unavailable layers with responsive legends. It reuses the central effective
state resolver and does not change the P2 schema, seed rows, or checksum.

**Objective:** provide the primary dated spatial entry point into the product loop.

**Required behavior:** neutral map plus Gender, Neutered, Class, and Unavailable layers;
fictional 20-enclosure topology and puppy areas; date selector; search/highlight; dog
links; responsive row fallback.

**Backend:** `KennelMapState(as_of)` endpoint combining effective housing/state with
location layout; layer-neutral payload; historical gap semantics.

**Frontend:** accessible DOM/CSS map, paired horizontal enclosure blocks, legend per
layer, unavailable explanations, historical read-only indicator, row/table projection.

**Data/migrations:** layout metadata refinements only if static seeded location fields are
insufficient.

**Tests:** assignment boundary dates, no current-state leakage, all layers/classes,
retired/injured/rest/restricted display, search/navigation, keyboard and narrow-screen QA.

**Acceptance:** the map accurately answers where each dog lived on any seeded season
date and opens its profile.

**Exclusions:** no real kennel geometry; no complex drag/pan editor unless later evidence
justifies it; map layer changes never write data.

**P5 handoff:** Daily Plan can reuse the demo-season date bounds, shared
`EffectiveDogState` policy, stable dog/profile identities, layer/status visual tokens,
wide-workspace toolbar patterns, and the dated location/resident snapshot shape for
context links. P5 adds plan persistence and activity editing separately; it must not
turn the P4 map into a housing or planning editor.

## P4.1 — Kennel Ground Layout Refinement

**Status:** completed. P4.1 keeps the accepted P4 API, layers, date projection, URL
state, finder, and navigation unchanged while replacing desktop floating enclosure
cards with continuous physical row blocks. Adult cells share walls, A1/A2 and B1/B2
are paired around stable service aisles, resident and empty slots stay inside fixed
cells, and the two puppy areas read as separate buildings on the same ground system.

**Responsive contract:** wide and tablet workspaces preserve the five-cell ground rows
when readable; narrow layouts keep logical row grouping and stack cells without page
overflow. Layer and date changes alter cell semantics and occupancy only—never the
canonical location order or geometry.

**P5 handoff:** unchanged from P4. Daily Plan may reuse the wide workspace and dated
resident projection, but does not own or edit housing geometry.

## P5 — Daily Plan

**Status:** completed. P5 delivers the mutable `/daily` workspace, one lazy plan per
season date, four ordered activity types, revision-safe editing, a dated participant
picker, and server-authoritative eligibility/daily-distance validation. It adds no
seeded plans, teams, or actual work mutations; reset returns to zero plans and the core
synthetic checksum remains unchanged.

**Objective:** create the simplified universal plan that feeds Team Builder.

**Required behavior:** create/reopen a dated plan; add ordered training, open-space walk,
individual exercise, or rest activities; specify route/distance for training; select a
manual dog pool. Planned teams are deferred to P6.

**Backend:** DailyPlan, PlannedActivity, and normalized participant models; focused CRUD,
move, and eligibility APIs; optimistic revisions; centralized dated state; shared 30 km
guardrail. Team/TeamPosition models are deliberately not introduced early.

**Frontend:** season-date editor, explicit note save, ordered activity cards, accessible
add/edit participant dialog, disabled candidates with reasons, responsive empty/error/
confirmation states, and neutral “Teams not arranged” context for Training.

**Data/migrations:** three planning tables with unique plan date, deferred unique
activity order, unique participants, activity/distance checks, stable UUIDs, deliberate
cascades, restrictive Dog references, and indexes.

**Tests:** activity policy and historical eligibility, date bounds, ordering, full CRUD,
30/35 km boundaries and freed capacity, duplicate rejection, revisions, reset/checksum,
accessible forms, participant context, errors, navigation, and responsive live QA.

**Acceptance:** a valid Training activity retains date, 5/10 km distance, and selected
dog pool for P6; non-training activities never create sled kilometres or demand teams.

**Exclusions:** no production Operations Plans, PAX, customer, guide, or manager-heavy
completion system.

**P6 handoff:** Team Builder opens one Training activity by public UUID and consumes its
plan date, canonical distance, selected dog IDs, effective-date eligibility projection,
and per-dog already-planned km. P6 adds lineups/positions and conflict/role/workload
reasoning without replacing P5 persistence or converting plans into actual work.

## P6 — Team Builder

**Status:** completed. P6 delivers the deep-linked Training Team Builder, deterministic
workload/role/relationship solver, unsaved preview, accessible manual refinement,
revision-safe saved Lead/Team/Wheel geometry, Daily Plan summary, and explicit stale-
lineup clearing. It creates no actual work and leaves the immutable checksum unchanged.

**Objective:** propose safe, balanced, explainable lineups for planned training.

**Required behavior:** implemented effective state/class revalidation, 7/14-day and
season-before-date workload, explicit capabilities, same-pair hard conflicts, preferred
and dated home pairs, team balance, deterministic tie-breaking, supported 4/6/8/10/12
geometries, reviewed manual edits, and explicit Daily Plan save.

**Backend:** delivered bounded candidate/workload/relationship projection, pure
pair-oriented deterministic beam search, structured failure/explanation codes, complete
lineup revalidation, composite persistence constraints, and revision transactions.

**Frontend:** delivered context/capability summary, generated harness rows, meaningful
workload labels, unassigned explanations, shortage guidance, click-based swap/replace/
clear/fill, save/reopen/rebuild, profile links, and responsive layouts.

**Data/migrations:** `planned_teams` and `planned_team_slots` persist accepted geometry;
solver scores/traces are deliberately not persisted.

**Tests:** hard blockers, all role capabilities, preferred/home softness, shortages,
all supported representative layouts, deterministic repeats, workload bias, no future
actual leakage, uniqueness/cascades, reset, roundtrip, manual editor, and rebuild/clear
confirmation are covered.

**Acceptance:** seeded scenarios yield valid reproducible teams and intelligible reasons
for selection/unassignment; saved rows are the planned source for P7.

**Exclusions:** no opaque ML selection, named production-dog rules, or autumn/carousel
workflow.

**P7 handoff:** Daily Entry can read one Training activity's date/distance and selected
pool, its ordered saved teams, and each persisted pair/side/role/dog. Unassigned selected
dogs remain derivable by pool minus saved slots. P7 must create actual WorkSession/
WorkParticipation rows explicitly and must not treat a saved plan as completed work.

## P7 — Daily Entry

**Status:** completed. P7 delivers the `/daily-entry` historical actual-work workspace,
one canonical ledger, idempotent plan confirmation, editable saved harness geometry,
manual/unplanned sessions, plan divergence, not-run decisions, dated housing overview,
dog finding, and deterministic reset restoration.

**Objective:** capture actual work efficiently and correctly for historical demo dates.

**Required behavior:** date selection, historical housing grouping, search/find dog,
worked/not worked, 5/10 km or supported activity, status context, notes, save/reopen/
correct, and optional plan confirmation without double counting.

**Backend:** delivered a grouped entry read model, bounded dated eligibility/housing,
idempotent plan-to-actual confirmation, actual revision protection, safe create/edit/
delete, exact role/pair validation, and shared 30 km actual enforcement.

**Frontend:** delivered compact plan/actual cards, derived day metrics, focus-managed
participant/lineup editor, daily Find Dog, historical housing groups, persisted reopen,
and clear matches/modified/not-recorded/not-run language across desktop and mobile.

**Data/migrations:** `c4e87a1b92f0` adds WorkSession public/revision/start/provenance
metadata, actual participation geometry, session-owned cascade, and plan not-run state.

**Tests:** historical housing/map consistency, all effective-state rejections, idempotent
confirmation, saved-team and no-team copy, reopen/edit/delete, 30 km boundary, role and
pair rules, plan separation, not-run, reset/checksum, frontend interactions, and errors.

**Acceptance:** saved work appears exactly once in Dog Profile and downstream analytics;
historical entries never regroup by current housing.

**Exclusions:** no production printable sheets or unrelated-work deletion.

**P8 handoff:** analytics can query canonical WorkSession/WorkParticipation directly for
session count, distinct dogs, starts, dog-km, distance breakdown, roles, dates, and dog
drill-down. Plan and team tables are optional comparison context, never workload truth.

## P8 — Analytics and workload intelligence

**Status:** completed. P8 delivers `/analytics` with effective-dated Population and
actual-ledger Workload areas, reload-safe ranges/snapshot dates, compact KPI and
distribution views, Monday–Sunday trends, class-aware attention, streaks, role/distance
mix, and Dog Profile drill-down. It adds no schema or competing workload truth.

**Objective:** turn canonical actual work into clear kennel and individual insights.

**Required behavior:** dogs worked, starts, total km, average km per working dog, per-dog
distribution, weekly comparison, underused/high-use dogs, work/rest streaks, and
individual history for selected periods.

**Backend:** bounded projections over WorkSession/WorkParticipation, shared profile
distance summarization, explicit metric/streak semantics, stable eligible-day/class-peer
attention thresholds, and an EffectiveDogState-based population snapshot.

**Frontend:** Population/Workload navigation, snapshot/range controls, accessible compact
charts and exact values, responsive dog workload rows/cards, query-state restoration,
drill-down, and honest empty/partial-period handling.

**Data/migrations:** none. Existing indexes and the small deterministic world support
bounded live derivation; materialization was neither needed nor introduced.

**Tests:** hand-calculated starts/dog-km, multiple starts per worked day, week boundaries
and zero weeks, actual-only/edit/delete behavior, future exclusion, profile agreement,
effective eligibility/streaks, Population sums/ages/birth/class/lifecycle boundaries,
Map/registry consistency, bounded queries, UI ranges/tabs/filtering/empty/error states.

**Acceptance:** every displayed aggregate traces to canonical work and agrees across
profile, entry, and analytics views.

**Exclusions:** no predictive ML or production-specific export pack.

**P9 handoff:** Dashboard may compose current population counts, actual workload KPIs,
weekly trend, attention signals, Daily Plan context, and dated Map/housing context from
existing read services. It must not duplicate any metric or effective-state rule.

## P9 — Dashboard and integrated UX

**Status:** completed. P9 delivers `/dashboard` as the application landing route and a
single read-only dashboard projection composed from the established Population, Kennel
Map, Daily Plan, Team Builder, Daily Entry, and Analytics services. It adds no schema,
stored aggregates, seed changes, or competing metric semantics.

**Objective:** make the six-feature loop feel like one coherent operational product.

**Required behavior:** operational overview for the demo reference/selected date,
consistent navigation/date context, attention summaries, recent plans/work, and useful
deep links.

**Backend:** `GET /api/v1/dashboard?date=...` composes effective-dated population and
housing, unavailable resident details, persisted plan/team state, P7 actual-day totals,
P8's inclusive 14-day attention rules, and the latest six Monday-based workload weeks.
The selected date is demo-season validated and all values remain live projections.

**Frontend:** Dashboard is first in the operational sidebar. P11 moved its canonical
route to `/demo/dashboard` and made `/` the public product home. The
operational page provides a compact class/availability strip, purposeful zero-plan CTA,
plan/team and actual-work summaries, dated housing/unavailable residents, representative
attention dogs, six-week dog-km trend, and direct links into every owning module. Loading,
error, desktop/tablet/mobile, keyboard, and zero-plan states are explicit.

**Data/migrations:** none expected.

**Tests:** canonical baseline and date bounds; bounded composition; plan/team-present
state; cross-module Population, Map, Entry, and Analytics agreement; navigation/deep
links; no-plan/error states; frontend actions and responsive live inspection.

**Acceptance:** a new visitor can traverse Map → Profile → Plan → Builder → Entry →
Analytics without losing date or conceptual context.

**Exclusions:** no unrelated admin portal.

**P10 handoff:** dog identity links already use stable UUID routes and the existing
P10-ready media contract remains unchanged. Synthetic portraits can be introduced in
shared dog-media presentation (and optionally small Dashboard dog rows) without changing
Dashboard persistence, metric services, or projection semantics.

## P10A — Synthetic dog media system and generation manifest

**Status:** completed. P10A establishes the `dog-media-v1` contract without inventing
placeholder photographs: a curated 60-dog pedigree-aware identity catalog, complete
machine-readable generation manifest, shared photographic/anatomy/privacy guide, exact
P10B inventory, structural WebP validator, and one reusable frontend media component.

**Media contract:** one UUID-named `1086×1448` WebP per Dog under
`frontend/public/media/dogs/`, exposed by the existing nullable `photo_key`. A missing,
unsafe, or failed key uses the fixed 3:4 placeholder without a broken icon. Lists load
media lazily and Profile loads its hero eagerly. `dog-media-v1` is both manifest and
cache version and remains independent of `winter-2025-2026-v1`.

**Validation:** the CLI proves exact catalog/UUID/name/parent/litter/lifecycle mapping,
required unique briefs and traits, safe unique filenames, forbidden-name exclusion,
and—when P10B assets exist—exact file count, WebP structure, dimensions, integrity, and
size distribution. Human review remains mandatory for anatomy, age, snow, source safety,
family resemblance, and generation artifacts.

**Data/migrations:** none. All canonical seed `photo_key` values stay null in P10A, no
image bytes enter PostgreSQL, and the semantic checksum remains unchanged.

**Exclusions:** no generated, real, stock, scraped, or reference photographs; no SVG or
procedural fake photos; no carousel, upload, editor, gallery, or P11 work.

## P10B — Generated portrait ingestion and visual acceptance

**Status:** completed. Exactly 60 generated WebP portraits were structurally validated,
individually reviewed, activated, and integrated without re-encoding or non-media
domain changes.

**Objective:** generate, review, optimize, and integrate exactly one coherent synthetic
snow portrait for every one of the 60 manifest identities.

**Required behavior:** all exact filenames pass the strict validator and per-image human
QA; `photo_key` activation makes the same portrait appear in Registry, Profile, and
Archive; desktop/tablet/mobile layouts and bandwidth meet the documented budget.

**Acceptance:** 50 active and 10 archived dogs each have one publishable synthetic
portrait with credible age/anatomy/family resemblance, no source/privacy issue, and no
fallback or failed asset. Follow `docs/P10B_MEDIA_HANDOFF.md`; do not mark full P10
complete earlier.

**Data/migrations:** no migration. Seeded `photo_key` values are deterministic UUID
filenames; media activation is separately versioned and excluded from the immutable
domain checksum, which remains the canonical P2–P9 value.

**Exclusions:** no carousel, gallery, user upload/editor, regeneration UI, real media,
or P11 marketing work.

## P11 — Public SaaS/demo shell

**Status:** completed. P11 adds a responsive public product site and cleanly namespaces
the complete operational application under `/demo` without changing backend domain APIs
or canonical data.

**Objective:** present the application credibly at the future public hostname.

**Required behavior:** Landing, Features, About, Contact, and Demo routing; clear
synthetic/demo disclosure; calls to action; metadata/share previews; contact mechanism
chosen with anti-abuse protection.

**Backend:** `POST /api/v1/contact` validates bounded plain-text input and a honeypot,
then delegates to environment-selected sink, disabled, or SMTP delivery. Contact
messages are not persisted. The local sink logs length metadata only; P12 owns rate
limiting and production SMTP/secrets.

**Frontend:** `/`, `/features`, `/about`, and `/contact` use a focused public shell;
`/demo/...` uses the existing operational shell. Public copy accurately presents the
implemented workflow and makes fictional data, synthetic work, AI-generated portraits,
and resettable changes explicit. Legacy application URLs redirect to the canonical demo
tree with path/query state. Distinct route metadata, canonical/Open Graph/Twitter tags,
robots, sitemap, structured data, responsive navigation, and an intentional 404 are
included without SSR or tracking scripts.

**Data/migrations:** none unless contact persistence is explicitly chosen; prefer no
unnecessary personal-data storage.

**Tests:** public/demo/legacy routing, form success/failure/validation/honeypot and
transport failure, mobile navigation, 404, existing operational suites, production
build/static output, deep-link refresh, and responsive live inspection.

**Acceptance:** public visitors understand the value, synthetic boundary, and how to
enter the demo; no domain/DNS assumption is hardcoded.

**Exclusions:** no billing, tenancy, customer onboarding, or CRM.

**P12 handoff:** finalize the real hostname/DNS/TLS and canonical host configuration,
SMTP recipient and credentials, request/rate limits, workspace cleanup scheduling,
reverse-proxy headers, CORS, secrets, monitoring/logging, and production
accessibility/performance/security acceptance.

## P11.5 — Privacy and anonymous demo workspaces

**Status:** completed. P11.5 adds the public `/privacy` notice and safe public metadata,
then isolates each anonymous visitor's mutable Plan/Team/Actual state with a 24-hour
opaque HttpOnly session and date-level copy-on-write overlay. Shared Dogs, pedigree,
housing, state histories, media, and baseline work remain read-only.

The backend resolves the effective baseline/workspace view for Daily Plan, Team Builder,
Daily Entry, Dog Work, Analytics, and Dashboard. Per-workspace reset and expiry cleanup
cannot alter another workspace or the canonical baseline. Global reset removes all
workspaces and returns the baseline checksum. The frontend initializes a session only
on `/demo`, reports expiry/replacement, warns against real data, and provides a confirmed
Reset action. Privacy data mapping and the focused threat review record current facts
and remaining production controls.

**P12 handoff:** schedule workspace cleanup; finalize controller, hosting, mail-provider,
transfer, mailbox-retention, and log-retention configuration; validate TLS, headers,
proxy redaction, CSRF/origin policy, rate limits, and cross-browser expiry in deployment.

## P12A — Production readiness and repository security baseline

**Status:** completed. The canonical production origin is
`https://huskytracking.com`; live infrastructure remains intentionally unconfigured.

**Repository controls:** explicit development/test/production settings, fail-fast
production URL/session/cookie/privacy/SMTP/database validation, allowed hosts,
canonical-origin CORS and cookie-mutation Origin checks, HMAC session digests, safe
request IDs/log fields, no-store APIs, production-disabled interactive OpenAPI, and
database-backed multi-worker correctness.

**Delivery shape at P12A:** `compose.production.yml` published only frontend/Nginx; FastAPI and
PostgreSQL remain on the private network. Nginx owns same-origin `/api`, SPA/media
serving, restrictive CSP/security headers, body bounds, compression, and separate
immutable/static versus no-store cache policy. Production Angular source maps are off
and runtime `PUBLIC_BASE_URL` drives canonical metadata without breaking localhost.

**Operations:** liveness/readiness are distinct; Alembic and non-destructive first-time
initialization are explicit jobs; web startup never seeds/resets. The P12B runbook
documents hourly cleanup, trusted forwarding, proxy rate-limit defaults, resources,
logs/retention, backup/restore rehearsal, rollback, monitoring, DNS/TLS/HSTS gates, and
first/repeat deployment sequences.

**Data/migrations:** no domain migration and no seed/media mutation. Baseline checksum,
workspace-reset semantics, and 60 portraits remain unchanged.

## P12B — Live infrastructure deployment

**Status:** the application is publicly live at `https://huskytracking.com`.
P12B-4B adds the final shared-host firewall, Husky-only internal monitoring and
alerts, verified log/backup bounds, and a conservative one-day HSTS observation
period. External UptimeRobot setup remains an owner-account action until verified.
See `PRODUCTION_DEPLOYMENT.md` for the exact live controls and remaining gates.

**Staging evidence:** isolated PostgreSQL 18.6 and backend/frontend are healthy on the
shared VPS with frontend bound only to `127.0.0.1:8081`; Alembic `5c82f32e5d8a`,
canonical checksum, 60/60 media, two-workspace isolation/reset, Husky-only backup and
cleanup, and Kennel Operations HTTP 200 were verified. The server-installed cleanup
script needed `--no-deps` to prevent recreating its own database; this is now the
version-controlled maintenance contract to install at P12B-3.

**Ingress preparation:** final Compose has no host ports, only the uniquely named
`huskytracking-frontend` service joins `huskytracking_proxy`; this avoids a collision
with Kennel Operations' `frontend` DNS name on the shared Caddy container. Inner Nginx
trusts one reviewed Caddy subnet and applies
targeted transient 429 rate limits. Staging retains an explicit loopback override.
No Caddy, DNS, SMTP, TLS, or live VPS change occurs in P12B-2.5.

**Remaining external work:** update the staged VPS checkout and reinstall maintenance
units from this commit; replace the loopback override with a no-port runtime override;
create/connect the dedicated proxy network; add protected Caddy ingress; configure
DNS A/AAAA and optional `www`, certificate/renewal, HTTP→HTTPS and optional `www`
redirects; configure/test SMTP; review firewall and external monitoring; and complete
real-domain security/rate-limit/performance/accessibility QA. HSTS and Basic Auth
removal wait for explicit HTTPS and launch acceptance. Existing Husky backup/cleanup
schedulers and restore rehearsal were already exercised in staging.

**Exclusions:** no unsupported scale infrastructure and no claim of a live public
deployment until every go-live gate passes.

### Post-launch Package C — routing and deployment hardening

**Status:** repository changes completed; live deployment intentionally separate.

The production frontend now keeps direct refreshes for the finite Angular public/demo
route contract at `200`, while unknown non-file paths serve the branded, noindex Angular
Not Found view with an HTTP `404`. The Docker development proxy retains Docker DNS for
its upstream connection but preserves the browser `Host`, so FastAPI trusted-host
validation no longer rejects normal `localhost:4300` API requests and is not weakened.

The intended Caddy HSTS policy advances from the completed one-day observation value to
`max-age=31536000`, apex-only and without preload. Caddy remains the only HSTS owner;
the checked-in example and operations runbook do not themselves modify the shared live
proxy. No product workflow, domain data, migration, image, or live infrastructure is
changed by this package.

### Post-launch Package D — safe actual-work confirmation and correction

**Status:** completed locally; not pushed or deployed.

Planned Training confirmation now opens a concise, focus-managed review of date,
distance, exact recording participants, and lineup context before any write. Successful
confirmation provides immediate Undo, and linked sessions retain an explicit Revert
actual action after reload. Both correction paths delete the revision-checked canonical
`WorkSession`, preserve the plan and lineup, return the plan to `not_recorded`, and let
Dog Profile, Dashboard, and Analytics recalculate from `WorkParticipation` truth.

No migration or parallel correction ledger is introduced. One active actual per planned
activity remains enforced by the existing service idempotency and database unique
constraint; manual actual entry remains an intentional editable form submission.

## P13A — Read-only Ground view

**Status:** accepted for local continuation after independent P13A-R1/P13B review;
production deployment remains separate. Overview remains the default for existing links;
`/demo/kennel?view=ground` opens the spatial view. The two views reuse a single dated
snapshot and the existing layers, legends, finder, and Dog Profile links. View and
layer switches do not request a new snapshot for the same date.

**Geometry and occupancy:** Ground keeps the fictional A1/A2 and B1/B2 enclosure order,
aisles, and separate Puppy A/B buildings even on phones. It contains zoom, Fit, and
pointer, touch, and keyboard movement within the map viewport. Layout responds to
viewport and content bounds without creating page-wide horizontal scrolling. Both
views render the whole resident list independently of nominal capacity; Ground allows
rows to grow without hiding names or moving enclosures to different rows.

**Acceptance:** retain Overview and historical rendering; verify date/layer/view URL
state, only one active view, no redundant snapshot requests, navigation and search,
viewport controls and cleanup, and complete resident rendering with variable occupancy.
Use frontend fixtures for over-capacity examples, never a changed seed. Check desktop,
tablet, and mobile with real browser evidence.

**Scope boundary:** no API, database, seed, demo clock, or checksum changes. No housing
editing, print workflows, Training changes, or Operations Agent capabilities in P13A.

**P13A-R1:** search reveal/focus runs after Angular renders the result announcement.
Pending work is cancelled on a newer/cleared search, date/view changes, navigation,
and destruction. Reveal uses the dog link and immediate scrolling, so both the map
client area and browser window contain the result without a lingering smooth scroll.
Local production-build regression evidence covers the last Puppy A/B resident at
initial Fit and manual zoom, plus Overview at desktop, tablet, and mobile widths.
Technical validation is separate from the owner's independent acceptance.

**P13A-R1 technical gate:** completed locally before starting P13B under the owner's
explicit sequential authorization. The owner subsequently accepted the independent
review for continuation to P13C, without authorizing production deployment.

## P13B — Workspace housing backend and consistent reads

**Status:** accepted for local continuation to P13C after independent patch/source/QA
review. Migration, concurrency, and browser evidence belong in the P13B package report.
Production deployment has not been authorized by that acceptance.

**Persistence:** additive migration `b7e13a9d4c20` adds reference-date overrides unique
by workspace/dog/date, restrictive Dog/Location references, cascading workspace
ownership, and monotonic workspace `housing_revision`. Canonical housing intervals,
capacity metadata, baseline validation, seed, and checksum remain unchanged.

**API and transactions:** baseline GET without a valid cookie does not issue a session.
A current workspace/reference-date snapshot exposes a housing revision and HMAC
precondition bound to workspace, date, and revision. A cookie-authorized batch move
validates all unique dogs/destinations before writes and commits atomically. Occupied
destinations and occupancy above nominal capacity are supported. Same-origin checks
remain in place. Snapshot, moves, and Reset share the workspace row lock; Reset always
advances housing revision, and expiration cascades overrides. No plan/work day is
materialized by housing changes.

**Consumers:** one request-scoped `HousingContext` feeds Map, Registry/profile,
planning eligibility/participants, Team Builder soft home pairing, Entry housing
groups, Analytics housing projections, and nested Dashboard services. History labels
the temporary placement separately from canonical episodes. Earlier dates, historical
gaps, saved teams, actual work, workload totals, and eligibility policies retain their
existing semantics.

**Acceptance:** immutable checksum and strict baseline validation; two-workspace
isolation; reference-date-only overrides; over-capacity/mixed occupancy; all-or-nothing
validation; stale/cross-workspace preconditions; real PostgreSQL move/reset/cleanup
races; existing populated-workspace migration; bounded reads; every consumer; and
two-browser-context Map/Profile/reset checks. Destructive tests and migration rehearsal
must use only a dedicated disposable PostgreSQL instance.

**Handoff:** `P13C_HOUSING_HANDOFF.md` defines payloads, response metadata, and recovery
from stale or expired requests. Older binaries do not clear the new rows on Reset:
document and rehearse invalidating temporary data with compatible code before rollback.

## P13C — Move Together UI

**Status:** P13C and its R1 corrections accepted for local continuation to P13D.
Production acceptance and rollout remain separate. The work starts from accepted P13B and preserves its API and
schema head `b7e13a9d4c20`.

**Behavior:** View is the default. Overview and Ground share one committed snapshot,
one normalized draft, and action history. Select/touch/keyboard assignment and desktop
dragging stage a move into an occupied or empty active destination. No availability,
class, type, or nominal-capacity prohibition is introduced. Undo restores an action;
Discard clears the draft; Cancel review retains it. One reviewed confirmation sends one
atomic POST and accepts the server's complete committed snapshot on success.

**Recovery and navigation:** duplicate confirmation is blocked. A stale token requires
reload; session loss requires explicit reinitialization and a fresh snapshot; uncertain
save outcomes require reconciliation before another confirmation. There is no automatic
mutation retry or replay. Dirty date/route/Move-exit navigation is guarded, and shell
reset/replacement invalidates pending state. View/layer changes retain the draft.
Ground pan, zoom, search visibility, and all resident names remain available.

**Acceptance:** pure normalization/preview and DOM interaction tests, API-client request
shape, confirmation/cancel/undo/dirty guards, controlled error/recovery cases, and real
production-build browser flows against disposable PostgreSQL. Verify desktop/tablet/
mobile, actual dragging and touch/select, two workspaces and conflicting tabs, reset,
lost response, R1 visibility measurements, high occupancy, and unchanged plans/actuals/
checksum. Mark unavailable hardware/browser engines or other missing evidence NOT RUN.

**Scope:** feature UI and narrow session/reset/navigation hooks only. No new backend
contract, migration, seed, workload rule, or production change. No Swap, multi-select,
automatic moves, print/PDF, or Agent. See `P13C_MOVE_TOGETHER.md`.

**Later packages:** P13D was authorized separately below. Dog Summary, an opt-in demo
Training Day, and P14 Operations Agent remain outside P13C.

**P13C-R1:** accepted for local continuation. Corrections address consistent save-result
announcements, keyboard access to the entire scrollable Review, and Discard focus
ownership during delayed save failures. Before/after evidence and fresh regression
results belong to the R1 review bundle. No backend/schema, occupancy rule, workspace
authorization, or deployment change. This acceptance authorizes local P13D only.

## P13D — Kennel Map print

**Status:** spatial/color refinement and the keyboard lifecycle code on `efc710b`
are accepted for local continuation. P13E separately authorizes Dog Summary and the small
continuation-code wrapping polish. This is not deployment authorization.

One Print map action in either map view opens the same frozen committed snapshot/layer
projection. The read-only output preserves all locations, complete resident lists,
paired rows/aisles and separate puppy buildings. Pending moves and unresolved housing
operations block printing without saving/discarding anything. Historical snapshots are
printable. Date/reset/session invalidation closes the print context.

The feature uses ordinary HTML/CSS browser printing, A4 landscape at 100% with 10mm
margins, readable text and the same spatial composition as HT Ground. Zone A/B sit
beside each other with a main path, paired rows/service aisles and separate puppy
buildings below. Cards/legend reuse the five existing layer palettes; text and borders
remain readable without background printing. Conservative text budgets move remaining
names into explicit coded continuations, without omission or duplication and without
using nominal capacity as a limit. Preview and print share the same
document; no backend PDF API, new persistence or heavy dependency is introduced. Tokens,
revisions, IDs and API URLs never appear in the printed document. Browser afterprint
does not mean the user saved a PDF. Preview-local print-media changes re-evaluate the
existing observed-blur/return-focus recovery guard; no timeout unlock or global shortcut
interception is added. Native acceptance is reported separately from synthetic event
tests and headless PDF output, including any NOT VERIFIED sequence.

Acceptance includes per-location text/roster checks in real PDFs, page size/count,
every-page visual review, keyboard preview, workspace and historical contexts, five
layers, high occupancy, and compact Move/R1 visibility regression. Physical print-dialog
checks are distinguished from headless rendering; unavailable hardware/engines are
reported explicitly.

Small directly related non-blocking corrections are included and reported within the
authorized stage. Mandatory gates remain unchanged and are consolidated at the end;
data/isolation/persistence/core-flow or required-output blockers stop progression.
P13F and P13G are authorized separately below; P14 remains unauthorized and unstarted.

## P13E — One-page Dog Summary

**Status:** accepted for local continuation by independent review on 21 November 2026,
at `76c74abeba7b0c36f030577ffcb82e74c3005fe7`. No push, merge, tag or production deployment.
The small E-UUID-01 follow-up is included with the separately authorized P13F below.

Print summary is available from the shared header of every successfully loaded Dog
Profile tab. A detached immutable projection uses the existing four-GET bundle, checks
identity/reference-date coherence, and preserves backend-derived state and actual Work
metrics. Opening, closing and repeated printing require no additional bundle request
or mutation. Route/reset/session invalidation cannot reuse a stale dog's document.

The preview and one-page A4 portrait document share HTML, with 10mm margins and minimum
9pt type. Full identity, portrait/fallback, separate state fields, current/last housing,
archive date/reason, parents and four grandparents, and actual season metrics remain
readable. History is limited to three dated starts (not future events); temporary
workspace housing is explicitly separate. Notes use a documented 260-character excerpt
with a visible shortening notice. Null and zero work remain distinct.

The accepted Map lifecycle is shared narrowly, including title/focus/media-change
recovery and late-callback guards. Portrait load/decode/failure is bounded before normal
Print readiness. Map landscape → Summary portrait → Map landscape stays isolated.
Only the location code in Map continuation notices is kept together.

Acceptance evidence includes all 60 canonical profile PDFs with independent API-to-PDF
checks, representative/fallback/long-name fixtures, housing/actual UI workspace tests,
no print requests, keyboard and 1440/768/390 responsive checks, final gates and checksum.
In P13E, native Save → Cmd+P → Cancel was NOT VERIFIED: one bounded native-tool attempt
found a locked Mac. P13F's later bounded native Map result is recorded below; native Dog
Summary was not retested. Physical phone and additional browser engine are NOT RUN.
Unit/synthetic and headless-PDF evidence do not replace native checks.

### E-UUID-01 — Direct-link identity normalization

Implemented locally in P13F: validated canonical, uppercase and hyphenless spellings
of the same UUID load the same profile and Dog Summary. Invalid/different identities,
mixed bundles and late responses for an earlier route remain rejected. Backend UUID
handling, generated links, routing and shared print lifecycle are unchanged. Focused
profile regressions precede the Training Day implementation.

## P13F — Opt-in Training Day

**Status:** accepted for local continuation on
`0b3ef9faccd990a858fa9ad9b20888bd5b544750`. No push, merge, tagging or deployment;
`main` and `public-v1.2` remain protected. P13G is separately authorized below; P14 is not started.

Daily Plan offers one explicitly reviewed example for 29 March 2026: four ordinary
5 km Training activities at suggested windows 09:00–10:00, 10:30–11:30, 12:30–13:30 and
14:00–15:00. The same deterministic, date-eligible 16-dog pool repeats in all four groups:
64 planned participations, 20 planned km per dog, 320 planned dog-km. Review and Cancel
create no day or activity. A single explicit Apply is atomic and refuses any existing
plan (including notes-only) or effective actual work; it never clears or merges a day.
The normal editor retains 5/10 km, with no laps, PAX, end-time schema or new ledger.

Proposal selection reuses P6 workload/role/pair solving and shared date-effective
eligibility/housing. It proves two 8-dog teams are feasible without saving them. Pool,
generated preview, saved teams and actual work remain distinct. Each activity still
requires ordinary Generate/Save and separate reviewed Daily Entry confirmation.
Actual workload uses dates strictly before 29 March; 31 March workspace housing moves
do not leak into the historical proposal.

The existing cookie authorizes Apply; a purpose-specific HMAC binds the reviewed
date/version/participants to workspace public identity and reset generation. Reset of
an empty workspace also stales a review. Shared workspace-row locking precedes ordinary
materialization and plan/actual locks, with expiry rechecked after waiting. A queued
manual Actual detects changed plan public identity/revision and returns conflict;
recording begun after the committed plan is visible remains supported.

Pending/double-click guards, dirty note/activity protection and context generations
cover route/date, Reset, replacement, expiry and late callbacks. Lost-response outcomes
require explicit GET reconciliation, never automatic Apply replay; an empty GET is not
proof of rollback. Workspace Reset restores effective baseline state. Schema and
canonical seed are unchanged.

Review evidence distinguishes real PostgreSQL concurrency, source/UI checks, real
browser actions and headless PDF output. The single bounded P13F native Chrome Map check
passed real Save PDF → Cmd+P → Cancel, preserved usable preview controls and restored the
application title (`pdfs/native-map-save.pdf` in the review bundle). This does not extend
to native Dog Summary, a physical phone or an additional browser engine; those were not
retested. Final logs, UI flow, checksum/media/schema evidence and reproducible scripts
belong to the P13F review bundle.

## P13G — Regression and release gate

**Status:** local candidate preparation, pending independent release review. This is
not a production deployment or an assertion that all acceptance checks have passed;
the final report records READY FOR RELEASE REVIEW or a concrete NO GO.

The two accepted follow-ups are narrow: F-INGRESS-01 adds Training Day proposal GET and
Apply POST to the existing 10/minute, burst-6 solver zone, retaining mutation limits,
trusted-IP boundaries and unaffected ordinary GET navigation. F-STATUS-01 makes applying,
reconciling, conflict, unknown and error feedback visible alongside review controls,
independent of roster scroll position. Unknown/empty-read semantics and explicit new
Review/Apply remain intact.

The gate uses a production Angular/Nginx same-origin stack and positively identified
disposable PostgreSQL. One integrated P13A–F UI flow plus targeted isolation/context/error
checks accompanies the mandatory full source/config gates, bounded real-Nginx rate-limit
checks, representative PDFs and precisely scoped native evidence. Prior accepted PDF
corpora and the F native Map result are labelled prior evidence, not new G execution.
One bounded G native Dog Summary Save → immediate Cmd+P → Cancel check passed in real
Chrome/macOS, retaining usable preview controls, restoring the title and returning focus
to Print summary after Close. Its saved baseline PDF is separate from headless actual-work
Summary evidence. Physical-device coverage is not claimed.

Release rehearsal starts from exact `public-v1.2` code/schema `5c82f32e5d8a`, preserves
representative existing workspace state through upgrade to `b7e13a9d4c20`, restores a
real custom-format backup into a separate database, and exercises compatible rollback
and re-upgrade. New compatible code drains temporary workspace graphs while writers are
fenced before old binaries run; there is no routine schema downgrade, reseed or image-only
rollback claim. Old cookies may initialize fresh anonymous state but cannot restore their
deleted graphs or old housing/Training Day preconditions.

`P13_RELEASE_RUNBOOK.md` binds the future release to the accepted final commit, retained
actual image identities and verified project/volume/schema, with concrete stop conditions
and current public ingress paths. P12B staging/Basic Auth/first initialization are marked
historical. The canonical checksum, season, 60 portraits and plan/actual separation remain
unchanged. Main/public-v1.2, push, tagging, deployment and production infrastructure are
outside this local package; P14 is not started.

## P14A — Read-only Operations Agent foundation

**Status:** accepted local foundation at `5489869ec589461983cc16bf3c8c4e5bcca0a4d7`.
P14A itself performed no push, merge, tag, deployment, live inference or public agent UI/endpoint.
The source base is accepted P13G `bdffe6f`; main/public-v1.2 remain protected.

Includes strict immutable snapshot/tool/evidence/error DTOs; cookie-authorized dated
snapshot under the shared workspace lock/HousingContext, with transaction/session
closed before provider work; six closed read tools and existing-domain validation;
trusted evidence/deep-link checks; provider-specific injected HTTP adapters and bounded
single Groq Free → exact OpenRouter :free restart contracts. Default disabled, no
live transport, no new dependencies/models/infrastructure/schema/seed. Tests use only
fake HTTP, deterministic offline fixtures and a positively identified disposable PG.

G-DOC-01: P13G demonstrated unchanged **Work.summary / actual-work metrics for all16
dogs** after Apply, not equality of whole Work DTO histories/weekly arrays; historical
archives are unchanged. G-PRIVACY-01 names ht_demo_session, notes/housing moves and the
runtime lifetime; Reset clears mutable workspace data without deleting cookie or
extending expiry. Public Privacy never creates a workspace and makes no premature
AI-provider processing claim. Actual tests/limits and results belong to the P14A report.

See `OPERATIONS_AGENT_FOUNDATION.md` for architecture, official sources, byte/time/tool
budgets, refusal contracts, data minimization and Free-only future setup prerequisites.

## P14B — Limited live agent and UI

**Status:** **LIVE QA INCOMPLETE / BLOCKED on the reserve**. The context follow-up
restores selected participants/eligibility/states to mandatory `validate_day`, with
bounded issued evidence, explicit finding scope, independent pool/teams/actual facts
and truthful omissions. The four-working-dog Groq UI case now passes protocol/reference
checks and its stated core facts; exact zero-team and unrelated-archive wording is
not explicitly covered by the prose. Authenticated `/models/user` is HTTP 200 but
exact `particle-ai/particle-1:free` is ABSENT despite public presence, so no reserve
inference was attempted. Historical 11/12 ledger/closure are byte-identical; the new
explicitly authorized campaign closed at 2/6, combined 13/17 actual attempts, without
transferring unused slots. Prior fake primary 429 events remain separate; none were
added. QA-only fragmented error diagnostics and counter regressions pass. No
push/merge/tag/deploy, public enablement or P14C.

Carries four accepted-A follow-ups: Groq GPT-OSS `include_reasoning:false`, deadline
checks before construction/dispatch, strict finish-reason/tool consistency, and
tool-specific argument schemas. Adds bounded TLS transport, one serial model→read-tool
loop with required `validate_day` each provider attempt, exact default-disabled review
API, current-context/disconnect/deadline protection, summed known/incomplete usage,
and plain-text Operations review UI with facts, evidence, links and safe tool trace.
No materialization, new tables, migration, seed edits, local model or paid route.

The exact review POST is protected by the existing Nginx ingress with independent
per-IP 2/minute, burst-1, one-concurrent-review limits; backend one-per-worker admission
is explicitly not cross-worker/account quota accounting. Cancel/date/session/Reset/
navigation/expiry discard late UI results. No automatic browser/proxy/client retry.
Privacy describes external synthetic-data processing only when this environment's
feature is enabled, with excluded notes/Contact/cookies and no zero-retention or
EEA-only guarantee. Explicit private native/Compose configuration remains opt-in.

The continuation made one justified development-time replacement of the vanished
GPT-OSS20B free route with `particle-ai/particle-1:free`, plus narrow Groq output-mode,
reference/entity binding and optional OR parameter corrections. Strict evidence,
single-call parsing, zero prices, data_collection deny and require_parameters remain
unchanged. Removing the unadvertised optional parallel-call hint did not resolve 404;
its exact cause is not established. Known OpenRouter key metadata before/after showed
is_free_tier=true and usage 0; Groq billing measurement remains unknown beyond the
owner's Free attestation. This is not a universal measured-€0 claim.

Remaining live gate: a completed genuine free-reserve tool→result→final run with the
full required filters. Both campaigns are closed; their counters must not reset
or silently gain a new budget. Missing keys are not the blocker. No upgrade, privacy
relaxation, paid route or full-PASS claim is allowed to bypass unavailable routing.
See `OPERATIONS_AGENT_FOUNDATION.md` and the incremental live review evidence.

## P14C — Quality and adversarial evaluation (not started)

Approximately20–30 scenarios assessing model correctness, evidence, malicious inputs,
fallback/quotas, accessibility and regressions. Fake HTTP contract tests in A do not
establish model quality or live end-to-end success.

## P14D — Presentation and final candidate acceptance (not started)

Present the evaluated result and independent release candidate. Publication remains a
separate final owner-authorized action; no automatic push/deploy/tag from these stages.

## Completion discipline

Each package updates this roadmap only when evidence changes scope. It must include a
migration review, test evidence, privacy boundary review, documentation updates, clean
Git diff, and one coherent commit. Scope additions require an explicit product reason;
the default is to keep the public demo focused.
