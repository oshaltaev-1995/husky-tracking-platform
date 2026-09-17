# Deterministic demo data specification

This document is the canonical contract for P2's generator. P1 does not seed domain
records.

## Time and identity

- Dataset identifier: `winter-2025-2026-v1`.
- Season bounds: `2025-12-01` through `2026-03-31`, inclusive.
- Reference date: `2026-03-31`.
- Human label: **Demo season — Winter 2025–2026**.
- The generator uses a named, fixed seed stored beside the generator version.
- Reset is idempotent: the same application revision, dataset version, and seed produce
  identical business records and stable public identifiers.

The generator must receive a `DemoClock`; it must never call `date.today()` for domain
decisions. Tests run with a different host date and prove identical output.

## Population

Generate exactly **50 active dogs** plus approximately **10 archived dogs** (the v1
target is 10). All identities, bios, notes, and relationships are fictional.

### Active dogs

- Exactly four oldest active dogs have 2016 births.
- No active 2017 cohort is required; v1 should have none so the intentional gap is
  visible.
- The remaining older cohorts begin in 2018 and form believable litter/cohort groups.
- Exactly 10 active dogs are puppies born in 2026.
- Exactly 40 active non-puppies occupy the adult topology at the reference date.
- Sex distribution should be broadly balanced without forcing exact parity.
- Neuter state, class, roles, and availability should be varied and explainable.

The precise year-by-year counts and names are frozen in generator fixtures during P2,
after validation shows they satisfy every invariant. A cohort is not automatically a
single litter; litter sizes can commonly be 5–8 while unrelated dogs may share a birth
year.

The 30 safe reference names may be reused as candidates: Irbis, Taiga, Rikki, Joha,
Lennon, Blix, Talvi, Lumi, Tesla, Lara, Jukki, Vita, Efir, Sparki, Vesta, Lisa, Prince,
Rover, Landa, Koni, Monti, Python, Misha, Graph, Ilon, Knox, Kurt, Marfa, Whisky, and
Ray. P2 must add enough new fictional names to reach the full population and must make
all canonical names unique case-insensitively.

### Classes

Every effective class is one of `puppy`, `junior`, `training`, or `standard`. Class is
explicit domain data; age may validate or suggest a class but does not silently mutate
it. The ten 2026 dogs are Puppy at the reference date. Older cohorts should include
credible Junior and Training examples so the Class map layer and Team Builder
exclusions are demonstrable.

### Archive

Target 10 archived dogs. Use neutral normalized reasons such as:

- `euthanized`;
- `natural_death`;
- `rehomed` (UI wording may say adopted by a guide/private home);
- `transferred`;
- `other`.

Every archived dog has an archive date within a chronologically valid lifetime and an
optional short synthetic note. Some archived dogs should parent active older dogs.
Archived records keep pedigree links, historical housing/status, and meaningful work.
They have no open current housing assignment and are never eligible for new work.

## Pedigree

The combined active/archive population should demonstrate approximately three
generations. Not every dog needs known parents and not all dogs are related.

Generator validation must reject:

- self-parenthood;
- duplicate mother/father edges;
- a child born before a parent;
- a parent below the configured plausible minimum age at the child's birth;
- a parent implausibly old at the child's birth;
- any dog appearing in its own ancestor chain;
- any directed pedigree cycle.

The plausible parent-age bounds are generator policy, documented with tests rather
than hidden constants. Siblings are derived from shared parent edges; they are not
stored as independent relationships.

## Housing and topology

Create 20 adult enclosures:

- `A1-01` through `A1-05`;
- `A2-01` through `A2-05`;
- `B1-01` through `B1-05`;
- `B2-01` through `B2-05`.

At the reference date each adult enclosure has exactly two of the 40 active non-puppy
dogs. The map configuration places A1 opposite A2 and B1 opposite B2 as horizontal
blocks; geometry is fictional configuration, not encoded in location names.

Create simple separate puppy areas, for example `PUP-01` and `PUP-02`, with capacity
for five puppies each. P2 freezes final labels. Puppy group housing must not be forced
into the adult two-dog capacity rule.

Housing assignments are effective `[valid_from, valid_to)` intervals. Include a small
number of earlier-season moves so historical map and Daily Entry tests can answer,
“Where did this dog live on this date?” No dog has overlapping assignments; archived
dogs have no assignment open beyond their archive date.

## Operational state and scenarios

Lifecycle and availability are independent. Active/archived lifecycle records and
availability values (`available`, `injured`, `rest`, `restricted`, and where justified
`retired`) must produce visible scenarios at the reference date. Retirement is treated
as operationally unavailable and blocks normal working selection even if represented
as a lifecycle state in the final schema.

Seed short, professional synthetic status histories that demonstrate:

- an injury spanning part of the season;
- a rest/recovery interval;
- a restriction;
- a dog returned to available;
- at least one retired/unavailable active-profile example if allowed by final lifecycle
  semantics.

Never use private notes or simulate sensitive medical detail. Status periods and
housing histories should include boundary-day test cases.

## Roles and relationship constraints

Role capability is many-to-many at the domain level: a dog can be suitable for Lead,
Team, Wheel, or multiple roles. Ensure enough Standard, available dogs exist in each
role to build 5-, 6-, and 8-dog teams.

Seed explainable rules:

- soft preferred pairs, some based on shared housing and some explicitly configured;
- hard conflicts that prevent one team;
- explicit per-dog planning exclusions with public-safe reasons;
- a few role-specialist and multi-role dogs;
- underused dogs who become sensible tie-break candidates.

Rules use dog identifiers, not names as foreign keys. Store each unordered pair once in
canonical ID order and prohibit self-relations.

## Workload generation

Generate canonical work from **sessions and team participation**, not independent
per-dog random totals.

1. Build a deterministic calendar of training sessions from 2025-12-01 through
   2026-03-31 with realistic rest days and modest weekly variation.
2. Choose primarily 5 km and 10 km sessions/routes.
3. For each session, choose eligible dogs under effective class, lifecycle,
   availability, rest, role, and relationship constraints.
4. Persist a lineup with roles and one per-dog work record. One participation is one dog
   start; distance comes from the session unless a deliberate per-dog override exists.
5. Balance assignment by recent starts/km with deterministic seeded tie-breaking.
6. Apply stable workload personas or weights so totals are varied: a few high-use dogs,
   a few mild underuse examples, more 10 km work for some, more 5 km work for others.
7. Never assign adult workload to puppies; retired, archived, injured, resting, or
   restricted dogs are excluded on effective dates according to policy.

The output should be broadly balanced, not identical. Every unusual total must be
explainable through the schedule, eligibility, and deterministic selection trace. The
generator emits a validation report with counts, cohorts, housing occupancy, workload
distribution, invalid assignments, and a stable dataset checksum.

## Media

P10 will create one snowy outdoor portrait per dog. Do not import reference photos.
Store only a stable relative storage key on Dog, using a convention such as:

`dogs/{public_id}/profile.webp`

Generated files live under a configurable media root or object store in production.
The UI uses one neutral local placeholder while `photo_storage_key` is absent. No
gallery, carousel, upload editor, or background-processing workflow is planned.

## P2 acceptance invariants

- repeated reset yields the same checksum;
- 50 active and 10 archived records;
- 10 active 2026 puppies, four active 2016 dogs, and no active 2017 dogs;
- 40 active non-puppies occupy 20 adult enclosures exactly two each;
- all pedigree chronology and acyclicity checks pass;
- no overlapping status/class/lifecycle/housing periods;
- complete season workload uses valid eligible dogs and primarily 5/10 km distances;
- puppies and unavailable/archived dogs have no forbidden work;
- no fixture contains a real-world reference record or secret.
