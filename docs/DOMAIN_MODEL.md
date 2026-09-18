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
- nullable `photo_key` containing only the canonical UUID-based WebP filename, plus
  fictional notes.

P10B activates every canonical dog with its deterministic `<public-id>.webp` key after
strict file and visual review. The key is never image bytes, base64, an absolute host,
or a gallery relation. Angular maps it to `/media/dogs/<key>?v=dog-media-v1`; missing or
failed assets still use the shared placeholder. Media-set versioning and activation are
separate from dataset versioning and the domain semantic checksum.

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
prevents self-relations and inverse duplicates. Semantics are symmetric. In P6,
`preferred_pair` is a soft preference for sharing one left/right harness pair.
`hard_conflict` is a hard must-not-share-pair rule, not a whole-team exclusion. Dated
co-residence supplies a smaller soft home-pair preference.

Plans reference these facts and the effective state tables rather than adding competing
dog-state columns.

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
or 10 km distance; non-training activities store no sled distance. `actual_not_run` is
the minimal plan-side Daily Entry decision for a Training activity that did not happen;
it never creates a zero-km session or workload.

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

## Mutable Team Builder workspace

### `planned_teams`

One or more ordered teams belong to exactly one Training activity. Each row has a
stable public UUID, contiguous sequence, optional label, supported even `team_size`
(`4`, `6`, `8`, `10`, or `12`), and UTC infrastructure timestamps. Deleting the owning
activity cascades through teams; no team operation can delete a Dog or actual work.

### `planned_team_slots`

Each saved slot stores the owning activity/team, restrictive Dog reference,
zero-based pair index, `left`/`right` side, canonical `lead`/`team`/`wheel` role, and
stable position order. A composite team/activity foreign key prevents cross-activity
attachment. Unique `(planned_activity_id, dog_id)` enforces one saved slot per dog for
the whole Training activity, while unique team/pair/side and team/order constraints
preserve unambiguous harness geometry.

For 4 dogs the pairs are Lead/Wheel; larger supported sizes insert Team pairs between
them. Server validation re-resolves dated eligibility, participant membership,
capabilities, 30 km planned capacity, and same-pair hard conflicts on every save.
Generated lineups remain transient until explicit Save. Soft preferences may be
overridden manually; hard rules may not. A distance or participant-set edit with saved
teams requires explicit confirmation and clears lineups in the same plan-revision
transaction.

## Canonical actual-work ledger

### `work_sessions`

- unique stable `source_reference` and public UUID;
- nullable unique `planned_activity_id` provenance link with `ON DELETE SET NULL`;
- `work_date`, checked `distance_km` of 5 or 10;
- checked `activity_type` of `sled_training` in canonical v1;
- optional local start time, label, and note;
- optimistic revision plus UTC infrastructure timestamps.

The nullable unique link makes confirm-from-plan idempotent at service and database
levels. Deleting or editing a plan never deletes or rewrites the more authoritative
actual session. Baseline and manual sessions need no plan link.

### `work_participations`

- session-owned cascade for correction/deletion and restrictive Dog foreign key;
- nullable checked `assigned_role` (`lead`, `team`, `wheel`);
- nullable actual team sequence, pair index, `left`/`right` side, and position order;
- unique `(session_id, dog_id)`.

Actual geometry is either wholly absent or complete with a role. A positioned dog must
have the stored capability and explicit same-pair geometry may not violate a canonical
hard conflict. Unordered manual participants do not assert a pair and therefore do not
trigger pair constraints.

One participation is exactly one dog start and its km is the parent session distance.
There is no per-dog distance override, stored start count, or aggregate workload on Dog.
Totals, starts, work/rest streaks, and later Dog Profile/Analytics views query these two
tables.

The seed validator and `DailyEntryService` ensure the dog has the assigned capability
when positioned and is effectively active, available, born, and class-eligible on the
work date. Training dogs receive only 5 km; Juniors and Puppies receive none. Daily
Entry totals (sessions, distinct dogs, starts, dog-km) are derived, never persisted.

Actual-work services must also enforce `MAX_DAILY_DOG_DISTANCE_KM = 30` for each
`(dog, work_date)` pair. `app.domain.workload` is the shared policy boundary: it accepts
only canonical 5 km/10 km sled distances and rejects an addition that would take the
daily total above 30 km. The deterministic generator and semantic validator use this
rule; P5/P6/P7 must reuse it rather than copy a numeric limit into plan or entry code.
Season totals such as 70–350 km are independent cumulative measures.

## Derived analytics semantics

P8 adds no analytics tables or stored aggregates. `WorkSession` and
`WorkParticipation` remain the only workload truth:

- **Sessions** is the number of actual session headers in the inclusive selected range.
- **Dogs worked** is the number of distinct participating dogs.
- **Dog starts** is the number of participation rows; multiple starts on one date remain
  multiple starts.
- **Dog-km** is the session distance summed once per participation.
- **Worked day** is one dog/calendar date with at least one participation, regardless of
  the number of starts that day.
- **Average km / worked dog** and **average km / start** divide dog-km by their named
  denominator and return zero when that denominator is empty.
- Actual role totals use `WorkParticipation.assigned_role`; a null role is reported as
  Not recorded and is never inferred from capability or a planned slot.

Weeks are Monday–Sunday and the API returns every week intersecting the requested
range, including zero-work and partial boundary weeks. Work streaks are consecutive
calendar dates with a start. An eligible rest streak counts consecutive dates ending
at the range end where the dog was born, active, available, and in Training or Standard
class but had no start; an ineligible date or worked date breaks that streak.

Workload attention is deterministic operational guidance, not a health diagnosis.
Only dogs active at the range end with at least one eligible day and a Training or
Standard class enter the attention population; retired and archived-at-end dogs are
historical context only. Dog-km is normalized to km per seven eligible days and compared
with the median for the same class. Below 95% is **Underused**, above 115% is **Higher
workload**, and the middle band is **Balanced**. Puppy and Junior dogs remain visible
with zero work but are never labelled underused.

Population analytics is a separate effective-dated projection. Dogs not yet born on the
snapshot date are absent. Headline represented counts split effective active/archived
lifecycle; sex, age, class, neuter, availability, capability, and housing distributions
use active dogs on that date. Age derives from date of birth and the snapshot date;
cohorts retain both active and archived represented dogs so historical generations stay
visible.

## Deletion and archive policy

All core history, parent, housing, relationship, and work foreign keys use `RESTRICT`.
The cyclic Dog/Litter foreign keys are created deliberately by Alembic after both
tables exist. Application workflows archive dogs rather than deleting them. There is no
casual hard-delete API and deleting a dog cannot cascade away pedigree, housing,
availability, class, archive, relationship, or work history.

The reset CLI is the sole bulk-clearing mechanism. It is explicitly local/demo-only,
uses a fixed table allowlist, checks database name/environment, and reconstructs the
entire semantic world in one transaction. Mutable plan/team tables are cleared first
and remain empty after reset. They are intentionally outside the semantic checksum.
Runtime edits to canonical actual work legitimately change the live checksum; reset
reconstructs the exact baseline ledger and original hash.

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

Forward migration `9fa6b3d1c204_add_planned_team_lineups` creates the P6 team and slot
tables, supported-size/role/side checks, composite ownership foreign key, one-dog-per-
activity uniqueness, plan-owned cascades, and restrictive Dog references.

Forward migration `c4e87a1b92f0_add_daily_entry_actual_metadata` extends the canonical
ledger with public/revision metadata, nullable plan provenance, start time, complete
actual harness geometry, session-owned participation cascade, and the minimal not-run
flag. One actual per planned activity and one dog/position per session are constrained.

## Read projections and later packages

P2 exposes only `GET /api/v1/demo-dataset`, a small read-only verification projection
with dataset version, reference date, active/archive counts, and checksum. P3 can build
Dog registry/profile/archive projections directly from the persisted identity,
pedigree, state, housing, and work histories. P4 can build a dated map from location and
housing metadata. P5 persists selected dated activity pools; P6 attaches explicit
lineups. P7 copies saved team sequence/pair/side/role into editable actual participation,
or copies only the selected pool when no lineup exists. P8 reads canonical
`WorkSession`/`WorkParticipation` actuals without depending on plans or teams.
