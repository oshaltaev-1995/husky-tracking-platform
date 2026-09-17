# Product scope

## Product statement

Husky Tracking is a generalized kennel-management concept presented as a safe public
demo. It makes the operational state of a fictional sled-dog kennel understandable
without exposing real kennel data. It is not described or implemented as a copy of
Kennel Operations.

Working public hostname: **huskytracking.com**. The domain, DNS, and production host
are not assumed to exist yet.

## Product loop

1. **Kennel Map** gives a dated spatial view of housing and operational state.
2. **Dog Profile** explains identity, pedigree, work, status, and housing history.
3. **Daily Plan** describes intended training, exercise, walking, or rest.
4. **Team Builder** proposes explainable, eligible lineups for planned training.
5. **Daily Entry** records what actually happened on a selected demo date.
6. **Analytics** derives kennel- and dog-level workload intelligence from actual work.

Navigation, APIs, and package sequencing should preserve this loop.

## Audience and goals

The first audience is a portfolio visitor evaluating product and engineering quality.
The demo should feel operationally credible, be quick to understand, respond well on
desktop and mobile, and make its synthetic nature explicit. A later public shell will
provide landing, features, about, contact, and demo routes with basic SEO and
accessibility.

## Canonical demo state

- Fixed season: `2025-12-01` through `2026-03-31`.
- Fixed reference date: `2026-03-31`.
- Display label: **Demo season — Winter 2025–2026**.
- Exactly 60 fictional dogs: 50 active and 10 archived.
- Exactly 10 active puppies born in 2026; 40 older active dogs.
- Four oldest active dogs born in 2016; no required active 2017 cohort.
- Internally coherent, approximately three-generation pedigree.
- Twenty fictional adult enclosures, two adult dogs per enclosure.
- Separate puppy areas.
- Work history covers the full season and primarily uses 5 km and 10 km sessions.

The demo clock is product behavior, not test-only configuration. Host `today()` must
not silently change age, class, housing, status, or workload context.

## In-scope capabilities

### Dog Profile

Tabbed presentation:

- **Profile / Bio:** canonical photo, name, sex, neuter state, date/year of birth,
  demo-relative age, class, lifecycle, availability, current housing, role
  capabilities, and fictional notes.
- **Pedigree:** mother, father, offspring, and derived siblings. Archived relations
  remain linked.
- **Work:** recent work, starts, total km, activity dates, selected-period workload,
  and trends.
- **Status History:** chronological operational status and housing history.

### Kennel Map

The map is a first-class HTML/DOM application view backed by dated housing. It needs a
neutral view plus Gender, Neutered, Class, and Unavailable layers. Class distinguishes
Puppy, Junior, Training, and Standard. The Unavailable projection explains injury,
rest, restriction, and retirement. Dog interactions open Dog Profile.

### Planning and work

- A simplified universal Daily Plan supports training, open-space walk, individual
  exercise, and rest. Training includes date, route/activity, distance, and teams.
- Team Builder considers class, availability, recent workload/work, lead/team/wheel
  capability, pair preferences, conflicts, exclusions, and optional underuse bias.
- Daily Entry supports a selected historical/demo date, meaningful grouping, worked
  versus not worked, 5/10 km or related activity, status, notes, search, and reopening
  saved entries. Its grouping uses housing effective on the selected date.
- Analytics includes dogs worked, dog starts, total and average km, per-dog workload,
  distribution, weekly comparisons, under/high workload, streaks, and individual
  history.

## Explicitly out of scope

- the production Operations Plans workflow;
- carousel workflows;
- guide, manager, PAX, or customer-management complexity;
- production completion/reconciliation machinery;
- private printable documents or customer workflows;
- real kennel topology, dogs, users, media, or notes;
- a photo editor, gallery, or background-generation workflow;
- microservices or speculative enterprise infrastructure.

Authentication and multi-tenant SaaS behavior are not required for the core demo. A
safe public reset/reseed mechanism and deployment hardening are required before public
release.

## Product principles

- **Explainable over clever:** a recommendation must state why a dog was selected or
  excluded.
- **Historical truth:** past views resolve past status and housing rather than leaking
  the current state.
- **One work ledger:** plans are intentions; confirmed work is the analytics source.
- **Synthetic by construction:** fixtures, names, images, and prose must be safe to
  publish.
- **Focused scope:** include a mature concept only when it strengthens the public loop.
