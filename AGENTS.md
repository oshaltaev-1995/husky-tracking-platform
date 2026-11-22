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
- Kennel Map is the `/demo/kennel` wide workspace, initially in View mode. Overview and
  Ground share one committed snapshot and one feature-local Move draft. Preserve its
  season-bounded `date` and its `layer` and `view` URL state. Both render all residents
  regardless of nominal capacity. Ground preserves the fictional
  enclosure order and adjacency at every viewport size; contain map scrolling without
  horizontal page overflow.
- Canonical housing remains immutable. P13B allows only temporary workspace overrides
  on `DemoClock.reference_date`, through the cookie-authorized atomic housing batch API.
  Use the shared `HousingContext` and `EffectiveDogState` for every consumer; never apply
  a reference-date override to past dates. Nominal capacity is not a workspace move
  limit. Moves do not alter work eligibility, plans, teams, actual records, or status.
  P13C stages Move Together changes locally in either view. Drop/select/Undo/Discard
  never write; one explicit review confirmation sends one existing atomic batch. Keep
  committed state separate from preview and do not persist or log draft/preconditions.
  Stale, expired, and unconfirmed request outcomes require reload/reconciliation,
  never automatic replay. Reset/session replacement invalidates old drafts. Dirty
  navigation must be confirmed, and an in-flight unsubscribe is not a server rollback.
- Kennel Map printing uses one frozen projection of the loaded committed snapshot and
  selected layer, never a pending preview. Dirty or unresolved housing states block
  application printing. The feature-local print preview uses browser HTML/CSS printing,
  excludes technical identifiers/tokens, and closes on date/session/reset invalidation.
- Dog Summary printing uses one completed Profile/Pedigree/Work/History bundle,
  detached and checked for matching dog identity/reference dates. Preview and print
  share one read-only A4 portrait document; opening/repeating/closing never refetches
  the bundle or creates workspace state. Reset/session/route invalidation closes it.
  Preserve full core fields, actual-work truth, temporary housing provenance, and the
  bounded three-event/260-character summary policy; full records stay in the profile.
- Daily Plan is the mutable `/demo/daily` wide workspace. Keep plans separate from actual
  `WorkSession` records, resolve participant eligibility and housing on the plan date,
  and use optimistic plan revisions for every activity/note mutation.
- Training Day is an opt-in example for 29 March 2026, not seed data or a competing
  scheduler. Review is read-only; one explicit atomic apply creates four ordinary
  5 km activities with the reviewed 16-dog pool only on an empty plan/actual day.
  Reuse dated eligibility, housing, workload and the existing Team Builder solver.
  Keep pool, generated preview, saved teams and actual confirmation distinct.
  Apply uses the existing workspace cookie, a purpose-specific generation-bound HMAC
  and the shared workspace lock before materialization. Reset, expiry and unknown
  outcomes require fresh review/reconciliation, never automatic mutation replay.
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
- Operations Agent P14A established the disabled read-only foundation. P14B adds one
  explicitly triggered, default-disabled selected-day review, not a chat or writer.
  Capture one bounded frozen snapshot
  under the existing cookie-authorized workspace lock and shared HousingContext; close
  the transaction/Session before any provider wait. Tools never materialize or write.
  Recheck session/expiry/Reset/cancellation before fallback and final output. Keep private
  context, notes, cookies, preconditions and keys out of provider data/logs. Reuse existing
  eligibility, actual-work and lineup rules; evidence is server-created. Groq Free and
  exact OpenRouter `:free` contracts permit one bounded switch, zero-price/privacy filters
  and no paid bypass. P14A tests use fake HTTP only, even if keys exist in the environment.
  Live QA requires explicit owner authorization, project-only keys, Groq Free
  confirmation and OpenRouter free-route/account privacy checks. The original campaign
  is closed at 11/12; the separately authorized context follow-up is closed at 2/6
  (13 combined), with no unused-slot transfer or automatic new budget. Exact reserve
  absence from validated account metadata blocks blind reserve dispatch, even when
  the public catalog lists it. Missing live proof is not full PASS; P14C remains gated.
  Force a model-requested `validate_day`
  on each provider attempt before accepting a final result. Its bounded projection
  must preserve successful selected-pool/eligibility/state facts, distinguish unique
  dogs from participations, separate saved teams/actuals, scope unrelated findings,
  and report omitted details honestly without changing canonical checks. The production
  Nginx
  exact review POST owns per-IP admission (2/minute, burst 1, one concurrent review);
  the backend's one-slot-per-worker guard is concurrency control, not global rate or
  account-quota accounting. Preserve the private backend boundary and no automatic
  POST replay. Date/session/Reset/navigation/expiry/Cancel invalidate client results.
  An already dispatched provider request may finish and use quota after cancellation.
  Provider explanations are plain text, distinct from server-created facts/evidence.
  Public Privacy names external AI only when this environment enables the feature;
  never claim universal zero retention, EEA-only processing or unverified account controls.
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
- Housing reads use explicitly scoped overrides without materializing a plan/work day.
  Snapshot GET without a valid cookie returns a non-editable baseline without issuing
  a cookie. Housing writes require an existing workspace and a server HMAC precondition
  bound to workspace, reference date, and housing revision; never accept a payload
  workspace ID as authorization. Do not log preconditions, cookies, or move bodies.
- Per-workspace reset deletes only that workspace's mutable rows. The global guarded
  reset clears every workspace and restores the canonical baseline. Semantic checksum
  and canonical validation always exclude workspace-owned actual rows.
  Moves, consistent housing reads, and Reset share a database workspace-row lock;
  Reset always advances housing revision, including when already empty. Expiration
  cascades temporary housing overrides with the workspace.
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

## Package review discipline

Within an already authorized package, include small non-blocking fixes directly related
to its result and list their reason and verification in the report. Do not open a
separate revision package solely for that polish. Stop before the next stage when data,
isolation, persistence, a core workflow, or a required result is broken or incomplete;
authorization for later packages is still required. Consolidate the mandatory quality
gates into one final run; repeat affected checks only after concrete changes or failures.
This scheduling rule does not remove or weaken any gate above.
