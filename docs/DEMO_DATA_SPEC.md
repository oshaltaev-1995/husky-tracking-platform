# Deterministic demo data specification

This is the canonical contract implemented by P2. The world is entirely fictional and
is restored by application code, not an imported spreadsheet.

## Identity, time, and reset

- Dataset identifier: `winter-2025-2026-v1`.
- Scheduling seed: `20260331`.
- Season: `2025-12-01` through `2026-03-31`, inclusive.
- Reference date: `2026-03-31`.
- Expected semantic checksum:
  `2ad3418ecb5edad1d4676a9a6e0cf43b2cfbfa167c0218e96d9749fd12e24af2`.
- Stable dog public IDs are UUIDv5 values derived from dataset version and curated name.
- All domain decisions receive the centralized `DemoClock`; the generator never uses
  the machine date.

`python -m app.demo.seed` initializes an empty domain database and refuses an existing
dog population. `python -m app.demo.reset` truncates only the explicit Husky Tracking
domain-table allowlist and reseeds it. Reset is disabled in production, requires
`DEMO_RESET_ENABLED=true`, and only accepts the app-owned database name
`husky_tracking`. `python -m app.demo.inspect` validates and reports without mutation.

The semantic checksum normalizes and sorts datasets, dogs, litters/parentage,
class/lifecycle/availability periods, archive metadata, role capabilities, locations,
housing history, symmetric relationships, work sessions, and participations. Database
primary keys, sequences, generated ranges, seed timestamps, and other metadata are
excluded.

## Owner provenance correction and name boundary

The old Streamlit workload/data structure remains useful for study, but its 30 dog
names came from a real kennel and are not reusable. The generator and tests reject:

Irbis, Taiga, Rikki, Joha, Lennon, Blix, Talvi, Lumi, Tesla, Lara, Jukki, Vita, Efir,
Sparki, Vesta, Lisa, Prince, Rover, Landa, Koni, Monti, Python, Misha, Graph, Ilon,
Knox, Kurt, Marfa, Whisky, and Ray.

All canonical names below are manually curated fictional names. Faker and random name
generation are prohibited.

## Canonical population and cohorts

| Birth year | Total | Active | Archived | Reference-date class for active dogs |
| ---: | ---: | ---: | ---: | --- |
| 2016 | 4 | 4 | 0 | 4 standard |
| 2017 | 0 | 0 | 0 | — |
| 2018 | 5 | 3 | 2 | 3 standard |
| 2019 | 5 | 4 | 1 | 4 standard |
| 2020 | 5 | 4 | 1 | 4 standard |
| 2021 | 6 | 5 | 1 | 5 standard |
| 2022 | 5 | 4 | 1 | 4 standard |
| 2023 | 6 | 5 | 1 | 3 training, 2 standard |
| 2024 | 6 | 5 | 1 | 5 training |
| 2025 | 8 | 6 | 2 | 6 junior |
| 2026 | 10 | 10 | 0 | 10 puppy |
| **Total** | **60** | **50** | **10** | **10 puppy, 6 junior, 8 training, 26 standard** |

The four active 2016 foundation dogs have no litter or represented parents:

| Name | Birth date | Sex | Family role |
| --- | --- | --- | --- |
| Aurora | 2016-01-10 | female | C- and H-litter mother |
| Atlas | 2016-02-20 | male | D-litter father |
| Freya | 2016-04-18 | female | D-litter mother |
| Fjord | 2016-05-12 | male | H-litter father |

## Litters and pedigree

One letter identifies exactly one litter. Every member shares the litter birth date and
starts with its letter. “External” means that one parent is intentionally unknown and
not represented; parentage otherwise remains queryable regardless of lifecycle.

| Year / litter | Birth date | Mother | Father | Active members | Archived members |
| --- | --- | --- | --- | --- | --- |
| 2018 / C | 2018-06-15 | Aurora | external | Cedar, Cosmo, Clover | Cinder, Coast |
| 2019 / D | 2019-01-02 | Freya | Atlas | Dune, Delta, Daisy, Drift | Django |
| 2020 / H | 2020-05-20 | Aurora | Fjord | Harbor, Hazel, Hugo, Halo | Hilda |
| 2021 / K | 2021-02-15 | Clover | Django | Koda, Kira, Kenzo, Kaia, Kepler | Kismet |
| 2022 / M | 2022-04-14 | Delta | Coast | Maple, Magnus, Milo, Mistral | Mabel |
| 2023 / N | 2023-03-01 | Hazel | Koda | Nova, Niko, Nala, Nora, North | Nimbus |
| 2024 / O | 2024-06-20 | Kira | Magnus | Orion, Olive, Otis, Opal, Onyx | Oona |
| 2025 / S | 2025-03-10 | Maple | Nimbus | Sanchez, Sampo, Sancho, Siri, Sophie, Storm | Sergio, Sage |
| 2026 / T | 2026-01-12 | Nova | Milo | Taro, Tessa, Theo, Tindra, Toast | — |
| 2026 / V | 2026-02-18 | Nora | Kenzo | Vega, Valor, Violet, Viggo, Viva | — |

This graph contains independent foundation branches and more than three represented
generations. Examples include Atlas → Django (archived) → Kira → Orion, and Aurora →
Hazel → Nova → the T-litter. Archived Coast parents active M-litter dogs; archived
Nimbus parents active S-litter dogs. Parent roles require female mother/male father in
v1, parents are at least 730 days old at litter birth, archive follows offspring birth,
and cycles/self-parenting are rejected.

## Effective class, lifecycle, and availability

Class, lifecycle, and availability are separate `[valid_from, valid_to)` histories.
Current values are derived at the DemoClock reference date; PostgreSQL GiST exclusion
constraints reject overlap. Older dogs demonstrate normal puppy → junior → training →
standard progressions, while curated early/extended training transitions produce the
exact current distribution above.

Lifecycle contains only `active` and `archived`. Operational retirement is availability,
not lifecycle. Current availability is:

| State | Count | Canonical current example |
| --- | ---: | --- |
| available | 46 | broadly distributed working and non-working dogs |
| injured | 1 | Hazel, from 2026-03-15 |
| rest | 1 | Orion, from 2026-03-25 |
| restricted | 1 | Cedar, from 2026-03-20 |
| retired | 1 | Fjord, from 2026-02-15; still active and housed |

Historical interruptions include Maple injured from 2025-12-20 to 2026-01-10, Koda
resting from 2026-01-18 to 2026-01-25, Delta restricted from 2026-02-01 to
2026-02-12, and Aurora resting from 2026-03-05 to 2026-03-10. In v1, every
non-available state blocks sled work.

## Archive metadata

| Reason | Count | Dogs |
| --- | ---: | --- |
| `euthanized` | 3 | Django, Nimbus, Sergio |
| `deceased` | 3 | Coast, Kismet, Oona |
| `rehomed_to_guide` | 4 | Cinder, Hilda, Mabel, Sage |

Every archive record has a plausible date and a neutral fictional note. Archive closes
the active lifecycle, opens archived lifecycle, and never deletes pedigree, class,
availability, housing, role, relationship, or historical work references.

## Roles and symmetric relationships

Capabilities use normalized `lead`, `team`, and `wheel` rows. Standard dogs are
team-capable with a deterministic mixture of lead/wheel and multi-role approval;
training dogs have narrower capability. Juniors and puppies have no working-role rows.

Symmetric relationship rows are stored once with `dog_a_id < dog_b_id`:

- 10 preferred pairs: Aurora–Atlas, Freya–Fjord, Cedar–Clover, Delta–Dune,
  Harbor–Hazel, Koda–Kira, Maple–Magnus, Nova–Niko, Orion–Olive, Sanchez–Sophie;
- 6 hard conflicts: Atlas–Fjord, Cedar–Dune, Hazel–Koda, Maple–Nimbus,
  Nova–North, Orion–Onyx.

Self-relations and duplicate inverse rows are rejected. These relationships are
synthetic and do not copy named rules from either reference repository.

## Housing topology and history

There are exactly 20 active adult enclosures, capacity two each:

- A1: `A1-01` through `A1-05`;
- A2: `A2-01` through `A2-05`;
- B1: `B1-01` through `B1-05`;
- B2: `B2-01` through `B2-05`.

Zone, row, numeric position, display order, type, capacity, and active flag are stored
separately so P4 can render horizontal rows without parsing codes. At the reference
date every enclosure has exactly two active non-puppy residents: all 40 such dogs are
housed once.

Reference-date adult occupancy is fixed:

- A1: `01` Atlas/Aurora; `02` Fjord/Freya; `03` Cedar/Clover; `04` Cosmo/Daisy;
  `05` Delta/Drift;
- A2: `01` Dune/Halo; `02` Harbor/Hazel; `03` Hugo/Kaia; `04` Kenzo/Kepler;
  `05` Kira/Koda;
- B1: `01` Magnus/Maple; `02` Milo/Mistral; `03` Nala/Niko; `04` Nora/North;
  `05` Nova/Olive;
- B2: `01` Onyx/Opal; `02` Orion/Otis; `03` Sampo/Sanchez; `04` Sancho/Siri;
  `05` Sophie/Storm.

`PUPPY-A` houses the complete five-dog T-litter and `PUPPY-B` the complete five-dog
V-litter; each area has capacity five and occupancy five. Eight active dogs participate
in four paired historical swaps on 2026-01-15 or 2026-02-10. Every archived dog retains
a closed historical housing assignment. Capacity is validated over all effective
intervals, not only at the reference date.

## Canonical workload ledger and generator

`WorkSession` is the actual-work header; `WorkParticipation` is one dog start and gets
distance from its session. There is no authoritative aggregate on Dog.

The v1 schedule is deterministic:

- training days are Monday, Tuesday, Thursday, and Saturday during the season;
- every training day has one 10 km and one 5 km sled session, each with eight starts;
- output is 140 sessions: 70 × 5 km and 70 × 10 km, with 1,120 starts;
- 10 km selection requires effective Standard class;
- 5 km selection admits Standard plus at most two Training dogs;
- Puppy and Junior dogs receive zero sessions, starts, and km;
- archived/injured/rest/restricted/retired dogs cannot work on blocked dates;
- assigned roles must exist in the dog's capability rows;
- previous-day spacing is preferred when the eligible pool can support it;
- cumulative km divided by a stable persona weight drives balancing, then starts and a
  SHA-256 tie-break based on seed/date/distance/name complete deterministic ordering.

Aurora, Atlas, and Freya are mild high-workload examples; Cedar, Delta, and Harbor are
mildly underused relative to comparable Standard dogs. Status interruptions explain
additional variance. At v1 the active eligible-dog workload range is 70–350 km with a
300 km median; Training dogs are deliberately 5 km-only.

## Automated acceptance invariants

Tests and the seed validator enforce:

- exact population, cohort, class, archive-reason, location, relationship, session, and
  participation counts;
- unique names and complete rejection of the owner-forbidden Streamlit names;
- litter prefix/date coherence, correct parent roles, minimum age, archive chronology,
  no self-parenting/cycles, archived parents, and represented grandparents;
- non-overlapping class/lifecycle/availability/housing periods;
- effective housing uniqueness and historical capacity at every boundary;
- only season-bound 5/10 km work, effective lifecycle/class/status eligibility,
  capability-compatible role, eight unique starts per session, Training at 5 km only,
  and zero Puppy/Junior workload;
- two PostgreSQL resets yielding the expected identical semantic checksum.

P10, not P2, generates dog images. `photo_key` remains null and the frontend retains
the neutral placeholder strategy.
