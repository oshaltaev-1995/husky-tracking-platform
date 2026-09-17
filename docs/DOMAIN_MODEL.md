# Canonical domain model

This is the greenfield target model for P2–P8. Names may receive small implementation
refinements in migrations, but the separation and invariants are authoritative.

## Modeling rules

- PostgreSQL is authoritative; core relationships are relational, not JSON blobs.
- UUID public identifiers are exposed through APIs; integer or UUID primary-key choice
  is finalized in P2 and remains opaque to clients.
- Calendar-domain fields use `date`. Event timestamps use timezone-aware UTC.
- Effective intervals are half-open: `[valid_from, valid_to)`, with null `valid_to`
  meaning open-ended.
- Current state is derived from the interval covering the requested reference date.
  Do not add current-state cache columns until measurement justifies them.
- Plans are intentions. Confirmed work is the single analytics source of truth.

## Dog aggregate

### Dog

Identity and stable profile data:

- `id`, `public_id`, unique canonical `name`, optional `slug`;
- `sex` (`female`, `male`, `unknown`) and neuter/spay boolean or explicit unknown;
- `birth_date` plus `birth_date_precision` (`day`, `month`, `year`);
- fictional bio/notes;
- optional `photo_storage_key`;
- created/updated timestamps.

When only a year is known, store a normalized comparison date plus precision, or store
year separately; P2 must choose one consistent API. Age presentation always uses the
DemoClock reference date and respects precision.

Constraints: name unique case-insensitively; birth not after demo reference date;
storage key relative and unique when present.

### DogParent

Normalized pedigree edge:

- `child_id` → Dog;
- `parent_id` → Dog;
- `parent_role` (`mother`, `father`), when known.

Constraints: unique `(child_id, parent_role)`; unique `(child_id, parent_id)`;
`child_id <> parent_id`; restrictive deletion so pedigree identity is not silently
lost. Parent sex is not inferred when unknown. Offspring is the reverse relation and
siblings are derived through shared parent IDs.

Birth chronology, plausible parent ages, ancestry cycles, and transitive
self-ancestry require a transaction-level domain validator. PostgreSQL constraints
cover local edges; P2 adds a recursive-CTE validation and generator tests.

### DogRoleCapability

- `dog_id`;
- `role` (`lead`, `team`, `wheel`);
- optional proficiency/preference rank.

Primary key `(dog_id, role)`. Absence means not approved for that role.

### DogClassPeriod

- `dog_id`, `dog_class` (`puppy`, `junior`, `training`, `standard`);
- `valid_from`, nullable `valid_to`;
- optional public-safe note.

Exactly one effective class is expected for every active dog. Exclude overlapping
periods per dog with a PostgreSQL GiST exclusion constraint over a `daterange`.

### DogLifecyclePeriod

- `dog_id`, `lifecycle` (`active`, `retired`, `archived`);
- `valid_from`, nullable `valid_to`;
- optional reason/note.

Lifecycle is independent from class and availability. `retired` is operationally
unavailable. Archive transitions preserve identity and all referenced histories.
Periods may not overlap.

### DogArchive

One-to-zero/one metadata record for the current archive transition:

- `dog_id` unique;
- `archived_on`;
- `reason` (`euthanized`, `natural_death`, `rehomed`, `transferred`, `other`);
- optional explanatory note.

The corresponding lifecycle period must be Archived from `archived_on`. A database
constraint cannot enforce the cross-table temporal rule alone; the archive service
performs one locked transaction. Permanent deletion is not a public-demo workflow.

### DogStatusPeriod

Operational availability history:

- `dog_id`;
- `availability` (`available`, `injured`, `rest`, `restricted` initially);
- `valid_from`, nullable `valid_to`;
- reason and optional note;
- created/updated timestamps.

Periods may not overlap for one dog. Availability does not encode class, lifecycle, or
manual Team Builder exclusion. Status History displays these rows chronologically.

## Housing aggregate

### KennelLocation

- `id`, unique `code`, public label;
- `location_type` (`adult_enclosure`, `puppy_area`);
- capacity;
- map group and deterministic display order;
- optional layout coordinates/size in configuration columns.

No real kennel naming or geometry is permitted. Location existence/layout history can
be added if the fictional layout evolves; it is distinct from occupancy history.

### DogHousingAssignment

- `dog_id`, `kennel_location_id`;
- `valid_from`, nullable `valid_to`;
- optional note.

Constraints: `valid_to > valid_from`; no overlapping assignments per dog; one open
assignment maximum. Capacity is validated transactionally because it spans rows and
dates. Historical queries use `valid_from <= as_of` and
`valid_to IS NULL OR as_of < valid_to` and never fall back to current housing.

## Planning aggregate

### DailyPlan

- unique `plan_date` for the demo's universal daily plan;
- status (`draft`, `ready`, `completed`, `cancelled`);
- optional public-safe note; revision and timestamps.

### PlannedActivity

- `daily_plan_id`;
- ordered activity type (`training`, `open_space_walk`, `individual_exercise`, `rest`);
- route/label, optional distance, optional start time;
- status and notes.

Constraints: distance non-negative; training requires an allowed route/distance;
rest has no team.

### Team and TeamPosition

`Team` belongs to one PlannedActivity and has an order/label. `TeamPosition` stores:

- `team_id`, `dog_id`;
- harness row/order and role (`lead`, `team`, `wheel`);
- optional side/order within a row.

Constraints: dog unique within a team; lineup slot unique; role must match approved
capability at plan time unless a deliberate, explained manual override exists. A dog
cannot be double-booked in temporally overlapping activities. Persisted lineup geometry
is authoritative.

### DogRelationshipConstraint

- canonical ordered pair `dog_a_id < dog_b_id`;
- `constraint_type` (`preferred_pair`, `conflict`);
- strength (`soft`, `hard`) where meaningful;
- optional effective dates and public-safe reason.

Unique pair/type; no self-pair. Hard conflict blocks a shared team. Preferred pairing
is a scoring input and never overrides eligibility.

### DogPlanningExclusion

An optional dated per-dog exclusion separate from availability:

- `dog_id`, effective interval, scope (`team_builder` initially), reason.

This preserves the distinction between “not operationally available” and “available
but deliberately excluded from automatic selection.”

## Actual-work aggregate

### WorkEntry

Canonical session/event header:

- `id`, `work_date`, activity type, source (`daily_entry`, `plan_confirmation`,
  `demo_seed`);
- optional `planned_activity_id`;
- route/label, canonical distance, notes;
- revision and created/updated timestamps.

A stable source reference supports idempotent seed/import and reopen/update behavior.

### DogWork

Per-dog participation/result:

- `work_entry_id`, `dog_id`;
- `worked` or an outcome enum when a not-worked chronology row is required;
- assigned role;
- distance km and `start_count`;
- optional note.

Unique `(work_entry_id, dog_id)`; non-negative distance/start count; `worked=false`
implies zero distance and starts. Meaningful work is `worked=true` with a positive
start or distance. Dogs worked, dog starts, total km, averages, streaks, and individual
history are all queries over this ledger. Do not create a second summary work table.

## Query projections and policies

These are services/read models, not independent sources of truth:

- `EffectiveDogState(as_of)` combines class, lifecycle, availability, exclusion, and
  housing without collapsing them.
- `DogEligibility(as_of, activity)` applies hard blockers first, then role/relationship
  rules, and emits machine codes plus human explanations.
- `DogWorkload(window)` aggregates DogWork by dates and returns km, starts, active days,
  streaks, and distribution context.
- `KennelMapState(as_of, layer)` combines effective housing/state with fictional layout.
- `TeamSuggestion` is ephemeral until accepted into Team/TeamPosition.

Analytics may use SQL views or materialized views later, but every value remains
traceable to WorkEntry/DogWork.

## PostgreSQL integrity strategy

P2 should enable `btree_gist` and use exclusion constraints for non-overlapping dated
rows. Use check constraints for interval order, non-negative metrics, distinct pair/
parent IDs, and enum-like values (native enum versus checked text is decided once in
the first migration). Use partial unique indexes for open intervals when helpful.

Deletion behavior defaults to `RESTRICT` for business history and pedigree. Child rows
that are purely owned implementation details may cascade. Archive is not deletion.
