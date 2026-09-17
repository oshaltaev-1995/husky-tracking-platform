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
- Backend: FastAPI, SQLAlchemy 2 typed mappings, Alembic, PostgreSQL; thin routes,
  explicit services, relational constraints for core data.
- API routes live under `/api/v1`. Persist dates as calendar dates and timestamps in
  UTC where time-of-day is required.
- Product read APIs use explicit response schemas and feature read services. Resolve
  effective class, lifecycle, availability, and housing centrally against `DemoClock`;
  do not duplicate current-state logic in routes or Angular.
- Dog identity routes use stable `public_id` UUIDs. Archived dogs use the same profile
  and pedigree system as active dogs and must remain navigable.
- Add migrations for every schema change; never use `Base.metadata.create_all()` as a
  production migration mechanism.
- Use `.env.example` for public configuration; never commit secrets.

## Quality gates

Before completing a package, run backend lint/format/type/tests, frontend lint/tests/
build, and `docker compose config --quiet`. Add focused tests for demo-clock behavior,
date boundaries, relational invariants, and eligibility rules.

The authoritative work sequence and acceptance criteria are in
`docs/IMPLEMENTATION_ROADMAP.md`. Do not begin a later package casually when completing
an earlier one.
