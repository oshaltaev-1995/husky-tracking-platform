# Canonical domain model

P2 establishes the implemented persistence model below. PostgreSQL is authoritative;
current values and analytics are projections over normalized history, not duplicated
columns on Dog.

## Common rules

- Integer primary keys are private persistence identities. `Dog.public_id` is a stable
  UUIDv5 identifier intended for later APIs.
- Calendar-domain fields use `date`; infrastructure timestamps use timezone-aware UTC.
- Effective intervals are half-open `[valid_from, valid_to)`, with null `valid_to`
  meaning open-ended.
- Date-effective tables expose a generated PostgreSQL `daterange` and a GiST exclusion
  constraint so one dog cannot have overlapping rows in that dimension.
- Checked text values are the canonical v1 enum representation. They avoid migration
  coupling while still rejecting unknown values in PostgreSQL.
- Age is derived from `birth_date` and `DemoClock.reference_date`; no static age is
  stored.
- Actual work is the only analytics source of truth. Plans introduced in P5 will be
  intentions until explicitly confirmed into this ledger.

## Dataset identity

### `demo_datasets`

Stores one canonical `version`, its scheduling `random_seed`, the computed
`semantic_checksum`, and an informational `seeded_at`. The timestamp and database ID do
not participate in the checksum. The v1 row is `winter-2025-2026-v1` / `20260331`.

## Dog, litter, and pedigree

### `dogs`

- `id`, unique `public_id`, unique case-insensitive `name`;
- exact `birth_date` and biological `sex` (`female`, `male`);
- `is_neutered` and optional `neutered_on`, constrained not to precede birth;
- nullable `litter_id`;
- nullable `photo_key` reserved for P10 and fictional notes.

All P2 dates are exact, so birth precision machinery is intentionally absent. The four
2016 foundation dogs have null litter; every later canonical dog belongs to one.

### `litters`

- unique single-letter `code` and shared `birth_date`;
- nullable `mother_id` and `father_id`, both restrictive Dog foreign keys;
- optional notes.

Litter is first-class and authoritative for both sibling membership and represented
parentage. A separate DogParent table would duplicate the same facts and is therefore
not present. A member's parents are its litter's mother/father; offspring are litters
that reference a dog; siblings are other members of the same litter. Nullable parent
columns permit an external/unknown parent without inventing a record.

The local distinct-parent check is backed by the domain validator, which enforces:

- member date equals litter date and member name starts with its litter code;
- child birth follows each parent's birth by at least 730 days;
- v1 mother is female and father male;
- no dog is its own parent and no ancestor cycle exists;
- an archived parent's archive date follows the represented offspring birth.

Parent/litter queries never filter on lifecycle, so archived parents remain navigable.

### `dog_role_capabilities`

One unique `(dog_id, role)` row for `lead`, `team`, or `wheel`. Absence means the dog is
not eligible for that role. Foreign-key deletion is restrictive.

## Independent effective histories

### `dog_class_periods`

Stores `puppy`, `junior`, `training`, or `standard` with an effective interval. Class is
an operational assignment, not an age cache, lifecycle, or availability value. Every
active canonical dog has exactly one effective class at the reference date.

### `dog_lifecycle_periods`

Stores `active` or `archived`. Archive closes Active and opens Archived on the same
boundary. Retirement is deliberately absent because it is an availability state; an
active retired dog remains a kennel resident.

### `dog_availability_periods`

Stores `available`, `injured`, `rest`, `restricted`, or `retired`, plus a public-safe
note. In v1 all four non-available values block sled work. This table never encodes
class or lifecycle.

### `dog_archives`

One-to-zero/one metadata row with `archive_date`, reason (`euthanized`, `deceased`, or
`rehomed_to_guide`), and an optional neutral fictional note. Cross-table validation
requires the lifecycle boundary and archive row to agree.

## Housing

### `kennel_locations`

- stable unique `code` and `display_name`;
- `location_type` (`adult_enclosure`, `puppy_area`);
- `zone`, `row_label`, and numeric `position` for P4 rendering;
- positive `capacity` and `is_active`.

The unique `(zone, row_label, position)` tuple prevents layout collisions. Location
metadata is sufficient to render A1/A2/B1/B2 rows and separate puppy buildings without
parsing the code or redesigning persistence.

### `housing_assignments`

Stores restrictive Dog/Location foreign keys, effective interval, and optional note.
A GiST exclusion constraint prevents one dog occupying two locations simultaneously;
an indexed location/date path supports capacity checks and dated maps. Capacity spans
multiple rows, so the application validator sweeps all interval boundaries and rejects
over-capacity worlds. Historical gaps remain gaps and are never replaced by current
housing.

## Team-builder relationship facts

### `dog_relationship_constraints`

Stores a canonical unordered pair as `dog_a_id < dog_b_id`, a kind
(`preferred_pair` or `hard_conflict`), and optional note. Unique pair/kind plus ordering
prevents self-relations and inverse duplicates. Semantics are symmetric: hard conflict
will be a future P6 blocker, while preferred pair will be a soft scoring input.

P5 plans reference these facts and the effective state tables rather than adding
competing dog-state columns. P6 Team lineups remain deliberately deferred.

## Mutable Daily Plan workspace

### `daily_plans`

One row per unique `plan_date`, plus optional general notes, optimistic `revision`,
stable public UUID, and UTC infrastructure timestamps. Browsing an empty date creates
no row; saving a note or first activity creates it lazily. Clearing the last meaningful
content removes the empty row.

### `planned_activities`

Ordered children of one Daily Plan with stable public UUID, optional local start time,
title, notes, and exactly one canonical type: `training`, `open_space_walk`,
`individual_exercise`, or `rest`. A deferred unique `(daily_plan_id, sequence)`
constraint supports transactional up/down reordering. Training alone has a checked 5
or 10 km distance; non-training activities store no sled distance.

### `planned_activity_participants`

Normalized unique `(planned_activity_id, dog_id)` membership. Plan/activity deletion
cascades only through workspace children; the Dog foreign key is restrictive. The
service resolves class, lifecycle, availability, birth, and housing on the plan date.
Training permits available Training-class dogs for 5 km and available Standard dogs
for 5/10 km; Puppy, Junior, unavailable, archived, and unborn dogs are rejected. Walk
and individual exercise use the same active/available rule without a sled distance.
Rest is an instruction for active, born dogs and never mutates availability history.

Planned Training participations reuse `app.domain.workload`: the sum across all of a
dog's Training activities on one plan date may be 30 km but never more. Plans remain
intentions; they do not create or modify actual work rows. Optimistic revision mismatch
is a conflict rather than a silent overwrite.

## Canonical actual-work ledger

### `work_sessions`

- unique stable `source_reference` for idempotent seeded identity;
- `work_date`, checked `distance_km` of 5 or 10;
- checked `activity_type` of `sled_training` in canonical v1;
- optional synthetic label/note.

### `work_participations`

- restrictive session and dog foreign keys;
- nullable checked `assigned_role` (`lead`, `team`, `wheel`);
- unique `(session_id, dog_id)`.

One participation is exactly one dog start and its km is the parent session distance.
There is no per-dog distance override, stored start count, or aggregate workload on Dog.
Totals, starts, work/rest streaks, and later Dog Profile/Analytics views query these two
tables.

The seed validator ensures the dog has the assigned capability and effective active,
available, eligible class on the work date. Training dogs receive only 5 km; Juniors
and Puppies receive no participations.

Actual-work services must also enforce `MAX_DAILY_DOG_DISTANCE_KM = 30` for each
`(dog, work_date)` pair. `app.domain.workload` is the shared policy boundary: it accepts
only canonical 5 km/10 km sled distances and rejects an addition that would take the
daily total above 30 km. The deterministic generator and semantic validator both use
this rule; P5/P7 must reuse it rather than copy a numeric limit into plan or entry code.
Season totals such as 70–350 km are independent cumulative measures.

## Deletion and archive policy

All core history, parent, housing, relationship, and work foreign keys use `RESTRICT`.
The cyclic Dog/Litter foreign keys are created deliberately by Alembic after both
tables exist. Application workflows archive dogs rather than deleting them. There is no
casual hard-delete API and deleting a dog cannot cascade away pedigree, housing,
availability, class, archive, relationship, or work history.

The reset CLI is the sole bulk-clearing mechanism. It is explicitly local/demo-only,
uses a fixed table allowlist, checks database name/environment, and reconstructs the
entire semantic world in one transaction. Mutable plan tables are cleared first and
remain empty after reset. They are intentionally outside the immutable-world semantic
checksum, whose scope and value remain unchanged.

## Migration integrity

Baseline migration `0cc49c993626_add_synthetic_kennel_domain`:

- enables `btree_gist` when absent;
- creates all 13 domain tables with deliberate checks, unique constraints, restrictive
  foreign keys, and query indexes;
- adds generated finite-backed date ranges and GiST overlap exclusions for class,
  lifecycle, availability, and per-dog housing;
- has a tested downgrade, including explicit removal of the cyclic Dog→Litter foreign
  key before table teardown.

Alembic remains the only production schema mechanism; application code never calls
`metadata.create_all()`.

Forward migration `83ee450cd525_add_daily_planning_workspace` creates the three P5
tables, stable UUIDs, date/order/participant uniqueness, type/distance/title checks,
indexes, plan-owned cascades, and restrictive Dog references.

## Read projections and later packages

P2 exposes only `GET /api/v1/demo-dataset`, a small read-only verification projection
with dataset version, reference date, active/archive counts, and checksum. P3 can build
Dog registry/profile/archive projections directly from the persisted identity,
pedigree, state, housing, and work histories. P4 can build a dated map from location and
housing metadata. P5 now persists selected dated activity pools. P6 can attach lineups
to a Training activity using its date, distance, participants, dated eligibility, and
already-planned kilometres without replacing this schema. P8 continues to read actual
work only.
