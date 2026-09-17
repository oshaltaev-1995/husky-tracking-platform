# Reference audit

Audit date: 2026-09-17. Both repositories were inspected read-only. No production data,
media, topology, or implementation file was copied into this project.

## Reference roles

- `../husky-tracking`: an original Streamlit demonstration and the only reference
  whose dog/workload fixtures may be treated as synthetic.
- `../kenneloperations`: a mature real-world pilot used only to understand proven
  concepts and boundaries. Its records and kennel-specific configuration are private.

## Streamlit repository findings

### Dataset and demographics

The Excel workbook `data/demo/husky_kennel.xlsx` has one sheet,
`tracking_2025-12`, with 30 dogs and one value for every dog on every day from
2025-12-01 through 2025-12-31.

Synthetic names, integer ages, and explicit capabilities from
`scripts/seed_constraints.py` are:

| Dogs | Age | Lead | Team | Wheel |
| --- | ---: | :---: | :---: | :---: |
| Irbis, Taiga | 2 | yes | yes | no |
| Rikki, Joha | 7 | no | yes | no |
| Lennon, Blix | 7 | no | yes | yes |
| Talvi, Lumi | 10 | no | yes | no |
| Tesla, Lara | 3 | yes | yes | yes |
| Jukki, Vita | 11 | no | yes | no |
| Efir, Sparki | 8 | no | no | yes |
| Vesta, Lisa | 7 | yes | no | no |
| Prince, Rover | 6 | no | yes | yes |
| Landa, Koni | 6 | yes | no | no |
| Monti, Python | 6 | yes | yes | yes |
| Misha, Graph | 3 | no | no | yes |
| Ilon, Knox | 3 | no | yes | yes |
| Kurt, Marfa | 9 | no | yes | no |
| Whisky, Ray | 7 | no | yes | yes |

The workbook lists the same names, although its row order places Misha before Monti
and Python. Age is a static integer, not a date-derived value. There is no sex,
neuter state, exact/year-only birth field, mother, father, offspring, sibling, litter,
or pedigree structure anywhere in the inspected model, fixture script, or workbook.

### Pair and conflict fixtures

The 15 declared kennel pairs are the two dogs shown together in each table row above.
Pairs are stored twice (both directions) in a generic `dog_relations` table. Explicit
bidirectional conflicts are defined between:

- Vesta or Lisa and Jukki or Vita;
- Misha and Prince or Rover;
- Rikki and Marfa;
- Koni or Landa and Vesta or Lisa.

These are synthetic rule examples, not pedigree links.

### Workload mechanism and provenance

The application does not generate workload at runtime. It imports a static wide Excel
matrix into SQLite as one `TrainingLog` per dog/date/source. The importer melts the
sheet, creates dogs by name, and skips duplicate source rows. UI edits are upserted and
exports reconstruct a wide workbook.

The sheet contains 930 populated cells (30 × 31) and only the values 3, 6, 9, 12, 13,
15, 16, 19, 20, 23, and 26 km. Every dog works every calendar day; totals are tightly
clustered between 473 and 491 km. The repository contains no generator, random call,
random seed, formula, or documented construction algorithm. Therefore the persisted
fixture is deterministic when imported, but its original construction cannot be
proven from source. It appears precomputed or manually assembled, not runtime-random.
It should not be preserved as canonical workload because it lacks rest days, uses
distances outside the new 5/10 km focus, and does not model session/team causality.

### Concepts worth preserving

- all 30 names are safe candidates for the expanded fictional name pool;
- explicit lead/team/wheel capability flags;
- explainable workload windows and a fatigue-style score;
- hard conflicts and soft pair preferences as different rule strengths;
- supported lineup geometries such as 1-2-2, 2-1-2, 2-2-2, and 2-2-2-2;
- role shortages and rule failures explained to the user;
- dog workload views, heatmaps, red flags, and selected-period summaries.

Do not preserve the Excel workbook as the primary datastore, static integer ages, the
fully occupied daily matrix, or its unexplained distances. P2 replaces it with a
deterministic programmatic generator.

## Kennel Operations findings

### Mature concepts relevant to this product

- **Dog profile:** lifecycle-aware detail combines identity, birth precision, sex,
  neuter state, work class, capabilities, current/last housing, co-residents, family
  context, effective status, workload/activity, and histories.
- **Class/lifecycle/availability:** work class (`puppy`, `junior`, `training`,
  `standard`) is distinct from lifecycle and operational availability. Eligibility is
  a projection, not a single overloaded status value.
- **Status history:** dated status periods carry start/end, reason, notes, and
  resolution data. Baseline restrictions and explicit builder exclusion are distinct.
- **Archive:** leaving/death date, normalized neutral fate, and optional details remain
  with the historical profile. Archive preserves work, family, housing, and status.
- **Housing:** authoritative assignments are effective intervals. Historical reads
  return no assignment for a gap rather than substituting today's housing. Physical
  layout and dog assignment history are distinct concepts.
- **Kennel Map:** a dated HTML/DOM map and responsive row projection share one state.
  Layers change presentation only. Dog links, search/focus, neutral occupancy, class,
  sex, neuter, workload/readiness, and an independent unavailable overlay are proven
  interaction patterns.
- **Daily Entry:** selected-date grouping resolves historical housing, persisted rows
  reopen for correction, and canonical work is protected from unrelated workflows.
- **Team Builder:** hard lifecycle, availability, class, temporal, and workload safety
  outrank soft pairing. Persisted lineup geometry is explicit. Suggestions explain
  exclusions and shortages.
- **Work and dog starts:** a session header plus per-dog participation record captures
  source, activity, date, distance, role, and start count. Planned work and actual work
  remain distinct.
- **Analytics:** totals use one meaningful-activity projection; compatibility data is
  not double-counted. Overview, weekly comparison, housing summary, dog summary, work/
  rest history, and exports demonstrate useful analytical slices.

### Design cautions discovered

The mature repository contains current-state cache fields alongside effective history,
legacy enums, family names stored as text, and a compatibility work ledger beside the
canonical activity ledger. Those are migration realities, not patterns to reproduce
in a greenfield demo. The new model should use foreign keys for pedigree, one canonical
actual-work ledger, canonical enums from the first migration, and derived current state
unless profiling proves a cache necessary.

### Explicit non-transfer boundary

Do not carry over real dog/person names, IDs, birth/family records, notes, statuses,
housing assignments, photos, kennel sides/rows/slots, map geometry, guide/customer/PAX
data, printable templates, exports, source fixtures, credentials, operational rules
tied to named real dogs, or production integrations. Also excluded are the full
Operations Plans workflow, carousel, photo editor/background tooling, account/admin
complexity, and production completion machinery.

## Audit conclusion

The Streamlit project contributes a small safe name/rule vocabulary and demonstrates
explainable workload/team ideas. Kennel Operations validates historical-state and
workflow concepts. Neither is the codebase or schema to migrate. The new platform uses
a smaller normalized domain, a fixed demo clock, fictional topology, deterministic
session-based work, and newly written Angular/FastAPI code.
