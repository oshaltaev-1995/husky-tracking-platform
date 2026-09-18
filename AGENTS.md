# Repository instructions

These instructions apply to the entire repository.

## Identity and boundaries

- Product: **Husky Tracking**; repository: `husky-tracking-platform`.
- This is an independent implementation for a public synthetic demo.
- Write only in this repository. The sibling repositories `../husky-tracking` and
  `../kenneloperations` are read-only references.
- Never copy or expose real kennel dogs, people, photos, topology, notes, customers,
  exports, credentials, or other production data.
- The 30 dog names recorded in `docs/REFERENCE_AUDIT.md` came from a real kennel and
  are forbidden in seeded/public demo populations. The Streamlit data shape may be
  studied, but its names may not be reused.
- Concepts may be reimplemented and generalized; implementation files must not be
  mechanically copied from the references.

## Canonical product decisions

- Keep the loop **Kennel Map → Dog Profile → Daily Plan → Team Builder → Daily Entry →
  Analytics** visible in product and architectural choices.
- Use the central application demo clock for domain calculations. The fixed season is
  `2025-12-01` through `2026-03-31`; the reference date is `2026-03-31`.
- Keep operational class, lifecycle, and availability separate.
- Housing and operational status are date-effective histories.
- Derive analytics from canonical per-dog work records; do not maintain competing
  summary ledgers.
- The seed/reset path must be deterministic and validated.
- Canonical demo dataset version: `winter-2025-2026-v1`; scheduling seed: `20260331`.

## Technical conventions

- Frontend: Angular, TypeScript, SCSS; feature-oriented folders and standalone
  components; strict TypeScript and accessibility tests where applicable.
- Shared visual decisions belong in `frontend/src/styles/`: use semantic CSS custom
  properties, the common spacing/radius/type scale, and shared breakpoint mixins before
  introducing feature-local hard-coded design values.
- Backend: FastAPI, SQLAlchemy 2 typed mappings, Alembic, PostgreSQL; thin routes,
  explicit services, relational constraints for core data.
- Reusable business constraints belong in `backend/app/domain/`; demo generation and
  validation must invoke the same rule that later application services will use.
- API routes live under `/api/v1`. Persist dates as calendar dates and timestamps in
  UTC where time-of-day is required.
- Product read APIs use explicit response schemas and feature read services. Resolve
  effective class, lifecycle, availability, and housing centrally against `DemoClock`;
  do not duplicate current-state logic in routes or Angular.
- Public pages use the marketing shell at `/`, `/features`, `/about`, and `/contact`.
  The operational application has one canonical route tree under `/demo`; legacy
  pre-P11 routes redirect into it while retaining path and query state.
- Kennel Map is the read-only `/demo/kennel` wide workspace. Its `date` and `layer` URL
  state must remain demo-season bounded, and its DOM/CSS layout must preserve the
  A1/A2/B1/B2 grouping without horizontal page overflow on narrow screens.
- Daily Plan is the mutable `/demo/daily` wide workspace. Keep plans separate from actual
  `WorkSession` records, resolve participant eligibility and housing on the plan date,
  and use optimistic plan revisions for every activity/note mutation.
- Planned sled distance uses the shared workload rule: only 5/10 km Training activities
  count, and their per-dog daily sum may not exceed 30 km. P6 may extend a Training
  activity with lineups but must not replace its selected participant pool.
- Team Builder is planning-only. Candidate workload queries must use actual work strictly
  before the plan date; saved slots must stay within the selected pool, match explicit
  Lead/Team/Wheel capability, and interpret `hard_conflict` as must-not-share one harness
  pair. Team mutations participate in the Daily Plan optimistic revision.
- Daily Entry is the mutable `/demo/daily-entry` actual-work workspace. Extend the canonical
  `WorkSession`/`WorkParticipation` ledger rather than creating another ledger; resolve
  eligibility and housing on the selected historical date, preserve plan/actual
  independence, and enforce the shared 30 km actual limit on every mutation. Runtime
  actual edits may change the live checksum; full reset must restore the baseline hash.
- Analytics is the read-only `/demo/analytics` wide workspace. Population snapshots reuse
  effective lifecycle/class/availability/housing on the selected date; workload totals
  use actual `WorkSession`/`WorkParticipation` rows only. Planned/not-run work is never
  counted, weeks run Monday–Sunday, and attention rules normalize by eligible days and
  class peers rather than comparing Puppy/Junior dogs with working adults.
- Dashboard is the fixed-reference `/demo/dashboard` operational home. Its projection must
  compose the existing Population, Kennel Map, Daily Plan, Daily Entry, and Analytics
  services; do not persist dashboard totals or create alternate KPI/attention rules.
- Dog media uses one optional canonical `photo_key` per Dog. Keys are UUID-based WebP
  filenames served from `/media/dogs/`; absent or failed assets use the shared local
  placeholder. The `dog-media-v1` manifest is separate from the domain dataset, and
  real, stock, scraped, or reference-repository dog photographs are prohibited. The
  canonical seed activates all 60 validated portraits; media keys remain outside the
  domain semantic checksum.
- Dog identity routes use stable `public_id` UUIDs. Archived dogs use the same profile
  and pedigree system as active dogs and must remain navigable.
- Contact delivery is non-persistent and plain-text. Local `sink` mode logs only
  metadata; production SMTP is environment-configured. Never commit recipients or
  credentials, and never echo or render contact values as trusted HTML.
- Anonymous `/demo` state is isolated by the backend-issued `ht_demo_session` cookie.
  Mutable Daily Plan/Team and actual-work reads use the baseline plus date-materialized
  workspace overlay; never query all workspace rows or mutate baseline rows from public
  endpoints. Public pages, Contact, and Privacy must not create a workspace cookie.
- Per-workspace reset deletes only that workspace's mutable rows. The global guarded
  reset clears every workspace and restores the canonical baseline. Semantic checksum
  and canonical validation always exclude workspace-owned actual rows.
- Add migrations for every schema change; never use `Base.metadata.create_all()` as a
  production migration mechanism.
- Use `.env.example` for public configuration; never commit secrets.
- Production uses `https://huskytracking.com`, a same-origin `/api` proxy, host-only
  Secure demo cookies, origin-checked cookie mutations, private backend/database
  networking, and explicit migration/initialization jobs. Never migrate, seed, or reset
  automatically in application startup. Follow `docs/PRODUCTION_DEPLOYMENT.md`.
- Production API responses are `no-store`; static hashed/media assets may be cached.
  Logs may include generated request IDs and request metadata, but never query strings,
  cookies/tokens, Contact bodies, demo notes, database URLs, or credentials.

## Quality gates

Before completing a package, run backend lint/format/type/tests, frontend lint/tests/
build, and `docker compose config --quiet`. Add focused tests for demo-clock behavior,
date boundaries, relational invariants, and eligibility rules.

The authoritative work sequence and acceptance criteria are in
`docs/IMPLEMENTATION_ROADMAP.md`. Do not begin a later package casually when completing
an earlier one.
