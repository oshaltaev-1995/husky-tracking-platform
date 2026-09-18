# Anonymous demo privacy and threat review

## Implemented boundary

The canonical dataset is a shared read-only baseline. A visitor receives a 256-bit
random opaque token; only its SHA-256 digest is stored. On the first mutation of a
calendar date, the workspace row is locked and the baseline plan/team and actual-work
graph for that date is cloned in one transaction. The workspace-day marker then makes
the copy replace—not supplement—the baseline for all reads. Untouched dates continue
to read baseline rows.

| Risk | Implemented mitigation | Remaining P12 work |
|---|---|---|
| Cross-workspace leakage/double counting | Every mutable read uses the effective baseline/workspace overlay; mutations materialize and target the resolved workspace; two-client tests cover plans, actuals, analytics, reset, and baseline fallback | Production concurrency/load test and penetration review |
| Token guessing | 256-bit random opaque token, digest-only storage, no sequential/public database identity | TLS, proxy/header validation, and secret scanning in deployed environment |
| Workspace fixation/tampering | Unknown, malformed, expired, or schema-incompatible tokens resolve to a fresh workspace; token is backend-issued only | Browser/security-header acceptance |
| Expired-state recovery | Resolver rejects expired records; explicit idempotent cleanup cascades workspace rows | Schedule `python -m app.demo.cleanup` and alert on failures |
| Accidental baseline mutation | Copy-on-write precedes every Daily Plan, Team Builder, and Daily Entry mutation; checksum and validation select only baseline actual rows | Restrict production database privileges and rehearse restore |
| Contact/log leakage | Contact is non-persistent; sink logs length/transport metadata only; no cookie/token/note content is logged by application code | Configure provider retention, reverse-proxy redaction, log rotation, and incident procedure |
| Visitor enters real data | Concise warning in the demo shell and privacy notice; short TTL and per-workspace reset | Review production copy and abuse/reporting channel |
| Stale browser state | Server expiry is authoritative; session initialization reports replacement and UI displays expiry/reset state | Full cross-browser expiry acceptance |

## Deletion and foreign keys

Deleting a workspace cascades its day markers, Daily Plans, activities, participants,
teams, slots, WorkSessions, and participations. Dog and all shared historical rows use
restrictive/non-workspace ownership and cannot be cascaded from a workspace. The public
reset deletes only one workspace's mutable rows and keeps its session alive; the guarded
administrator reset truncates all workspaces and reconstructs the canonical baseline.

## Logging policy

Application logs must not include contact message bodies, demo notes, session tokens,
Cookie/Authorization headers, SMTP credentials, or database URLs. A short operational
and security retention period is intended, but this repository does not configure the
host log collector; P12 must set and verify the actual rotation/retention policy.
