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

## P5 — Daily Plan

**Objective:** create the simplified universal plan that feeds Team Builder.

**Required behavior:** create/reopen a dated plan; add ordered training, open-space walk,
individual exercise, or rest activities; specify route/distance for training; attach
planned teams.

**Backend:** DailyPlan/PlannedActivity/Team/TeamPosition models and CRUD services with
revision/idempotency rules and validation.

**Frontend:** season-date plan editor, activity cards/forms, status and unsaved-state
handling, clear path into Team Builder.

**Data/migrations:** planning tables, unique plan date, ordered activities/teams, lineup
constraints and indexes.

**Tests:** activity-specific validation, date bounds, ordering, reopen/update, concurrency
revision behavior, accessible forms.

**Acceptance:** a valid training activity can launch Team Builder context and retain an
accepted lineup; non-training activities do not demand teams.

**Exclusions:** no production Operations Plans, PAX, customer, guide, or manager-heavy
completion system.

## P6 — Team Builder

**Objective:** propose safe, balanced, explainable lineups for planned training.

**Required behavior:** filter by effective state/class/exclusion; use recent km/starts,
roles, hard conflicts, soft preferred pairs, double-booking, and optional underuse bias;
support approved 5/6/8-dog geometries; allow reviewed manual edits; save to Daily Plan.

**Backend:** eligibility policy, workload projection, deterministic scoring/solver,
structured explanation codes, lineup validation and persistence transaction.

**Frontend:** candidate pool, exclusions/reasons, proposed harness rows, workload context,
warnings, manual swap/edit, accept/save, shortage guidance.

**Data/migrations:** relationship/exclusion refinements only if P2 schema lacks an
accepted rule; optional suggestion audit metadata, not full solver traces in core rows.

**Tests:** hard blockers always win; pair preference never overrides safety; role and
geometry shortages; deterministic ties; no dog reuse/overlap; accepted lineup roundtrip.

**Acceptance:** seeded scenarios yield valid reproducible teams and intelligible reasons
for selection/exclusion.

**Exclusions:** no opaque ML selection, named production-dog rules, or autumn/carousel
workflow.

## P7 — Daily Entry

**Objective:** capture actual work efficiently and correctly for historical demo dates.

**Required behavior:** date selection, historical housing grouping, search/find dog,
worked/not worked, 5/10 km or supported activity, status context, notes, save/reopen/
correct, and optional plan confirmation without double counting.

**Backend:** grouped entry read model, idempotent WorkSession/WorkParticipation upsert,
plan-to-actual confirmation, revisions and safe correction semantics.

**Frontend:** compact desktop/mobile entry grid, filters/search, batch controls where
safe, validation summaries, persisted/reopened state, clear actual-versus-plan language.

**Data/migrations:** source references/revisions and audit fields if not already present;
indexes for date/dog/session queries.

**Tests:** historical housing, boundary dates, idempotent saves, reopen/edit, zero/not-worked
semantics, plan confirmation, duplicate prevention, mobile interaction.

**Acceptance:** saved work appears exactly once in Dog Profile and downstream analytics;
historical entries never regroup by current housing.

**Exclusions:** no production printable sheets or unrelated-work deletion.

## P8 — Analytics and workload intelligence

**Objective:** turn canonical actual work into clear kennel and individual insights.

**Required behavior:** dogs worked, starts, total km, average km per working dog, per-dog
distribution, weekly comparison, underused/high-use dogs, work/rest streaks, and
individual history for selected periods.

**Backend:** aggregate query services over WorkParticipation, explicit meaningful-work rules,
period comparison, stable thresholds/configuration, optional export endpoints only when
they strengthen the demo.

**Frontend:** overview metrics, accessible tables/charts, period controls, definitions,
drill-down to dogs, honest empty/partial-period handling.

**Data/migrations:** query indexes; materialization only after profiling. Never add a
competing work ledger.

**Tests:** hand-calculated fixtures, week boundaries, starts versus dogs-worked semantics,
zero/rest rows, no double counting, chart/table equivalence, accessibility.

**Acceptance:** every displayed aggregate traces to canonical work and agrees across
profile, entry, and analytics views.

**Exclusions:** no predictive ML or production-specific export pack.

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
