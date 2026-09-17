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

**Objective:** make the six-feature loop feel like one coherent operational product.

**Required behavior:** operational overview for the demo reference/selected date,
consistent navigation/date context, attention summaries, recent plans/work, and useful
deep links.

**Backend:** lean dashboard projection composed from existing services; no duplicate
business rules.

**Frontend:** final app shell/navigation, dashboard cards, shared date/season context,
cross-feature breadcrumbs/links, polished responsive and empty/error states.

**Data/migrations:** none expected.

**Tests:** date consistency across features, deep links, navigation accessibility,
responsive workflow smoke tests, end-to-end core loop.

**Acceptance:** a new visitor can traverse Map → Profile → Plan → Builder → Entry →
Analytics without losing date or conceptual context.

**Exclusions:** no unrelated admin portal.

## P10 — Synthetic dog media

**Objective:** add one safe, consistent snowy portrait for every canonical dog.

**Required behavior:** one canonical generated image per dog, deterministic manifest/
ownership mapping, responsive display and fallback, alt text based on dog identity.

**Backend:** media URL/storage-key projection and integrity audit; storage adapter if
deployment requires object storage.

**Frontend:** integrate the single image in registry/profile/map as appropriate without
layout shift; retain neutral fallback.

**Data/migrations:** populate `photo_storage_key`; generated media and manifest; no real
reference photos.

**Tests:** every dog has exactly one valid asset, no orphan/collision, media path safety,
fallback and responsive image behavior.

**Acceptance:** 60-ish portraits are visibly fictional/synthetic, publishable, correctly
owned, and optimized.

**Exclusions:** no carousel, gallery, upload/editor, or background-processing product.

## P11 — Public SaaS/demo shell

**Objective:** present the application credibly at the future public hostname.

**Required behavior:** Landing, Features, About, Contact, and Demo routing; clear
synthetic/demo disclosure; calls to action; metadata/share previews; contact mechanism
chosen with anti-abuse protection.

**Backend:** minimal contact endpoint/integration only if selected; validation, rate
limit, and secret-backed delivery. Keep app API unchanged.

**Frontend:** public route shell, brand system, marketing copy/assets, basic SEO,
structured navigation and 404, responsive/accessibility polish.

**Data/migrations:** none unless contact persistence is explicitly chosen; prefer no
unnecessary personal-data storage.

**Tests:** route metadata, forms/validation/abuse controls, keyboard/screen-reader basics,
social/SEO tags, performance budget.

**Acceptance:** public visitors understand the value, synthetic boundary, and how to
enter the demo; no domain/DNS assumption is hardcoded.

**Exclusions:** no billing, tenancy, customer onboarding, or CRM.

## P12 — Production-demo hardening

**Objective:** make deployment repeatable, safe, observable, resettable, and acceptance
tested.

**Required behavior:** controlled deterministic reset, immutable builds, HTTPS/reverse
proxy readiness, database migrations, backups/restore, health/readiness, logs/metrics,
security baseline, responsive/accessibility/SEO acceptance, rollback runbook.

**Backend:** production settings validation, restricted reset command, readiness,
structured logging, error policy, request limits/security review, migration release step.

**Frontend:** production config, caching/security headers, final performance and browser
QA, error/recovery experience.

**Data/migrations:** production migration rehearsal, seed/reset preservation policy,
backup/restore verification, media backup strategy.

**Tests:** clean deploy, upgrade, rollback, reset checksum, backup restore, container
smoke, dependency/image scan, OWASP-oriented checks, accessibility audit, Core Web
Vitals/performance budget, full acceptance suite.

**Acceptance:** documented one-command/release-pipeline deployment can be reproduced;
reset cannot leak or destroy out-of-scope data; all product and privacy requirements
pass; the repository is safe to publish.

**Exclusions:** no scale infrastructure unsupported by measured demo needs.

## Completion discipline

Each package updates this roadmap only when evidence changes scope. It must include a
migration review, test evidence, privacy boundary review, documentation updates, clean
Git diff, and one coherent commit. Scope additions require an explicit product reason;
the default is to keep the public demo focused.
