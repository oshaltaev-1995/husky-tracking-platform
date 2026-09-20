# Anonymous demo privacy and threat review

## Implemented boundary

The canonical dataset is a shared read-only baseline. A visitor receives a 256-bit
random opaque token; only its HMAC-SHA256 digest under a runtime secret is stored. On the first mutation of a
calendar date, the workspace row is locked and the baseline plan/team and actual-work
graph for that date is cloned in one transaction. The workspace-day marker then makes
the copy replace—not supplement—the baseline for all reads. Untouched dates continue
to read baseline rows.

| Risk | Implemented mitigation | Remaining P12B work |
|---|---|---|
| Cross-workspace leakage/double counting | Every mutable read uses the effective baseline/workspace overlay; mutations materialize and target the resolved workspace; two-client tests cover plans, actuals, analytics, reset, and baseline fallback | Production concurrency/load test and penetration review |
| Token guessing | 256-bit random opaque token, HMAC-SHA256 digest-only storage under a strong production secret, no sequential/public database identity | TLS and deployed secret rotation/handling acceptance |
| Workspace fixation/tampering | Unknown, malformed, expired, or schema-incompatible tokens resolve to a fresh workspace; token is backend-issued only; unsafe cookie-authenticated production mutations require the canonical Origin | Real-domain browser/proxy acceptance |
| Expired-state recovery | Resolver rejects expired records; explicit idempotent cleanup cascades workspace rows | P12B schedules hourly `python -m app.demo.cleanup` and alerts on failures |
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

Application logs include generated correlation IDs, method, path, status, and duration.
They must not include query strings, contact message bodies, demo notes, session tokens,
Cookie/Authorization headers, SMTP credentials, or database URLs. A short operational
and security retention period is intended, but this repository does not configure the
host log collector; P12B must set and verify the actual rotation/retention policy.

## P12B-2.5 ingress boundary

The confirmed public controller is Oleg Shaltaev in Finland; the privacy address is
`privacy@huskytracking.com` and the VPS hosting region is Netherlands (EEA). The
private Cloudflare Email Routing forwarding destination is never recorded. Outbound
Contact now uses Brevo SMTP with certificate-verified STARTTLS on port 2525; the SMTP
secret and private recipient remain server-only. Contact content is not stored in the
application database or emitted in application logs.

The final Caddy-facing Docker network is dedicated to Husky frontend ingress. Only
that reviewed subnet can supply `X-Forwarded-For` to inner Nginx. Nginx uses the
resulting client IP for transient shared-memory Contact/demo/Team Builder/mutation
limits; it does not key on session cookies or contact addresses. The backend remains
private and receives overwritten forwarding headers. Cloudflare DNS ownership does
not imply its proxy is enabled; if enabled later, the Caddy/Cloudflare trust chain
needs a separate anti-spoof review. Whole-site Caddy Basic Auth and noindex are
temporary pre-launch controls, not yet live. No rate-limiting state is persisted or
shared with Kennel Operations. The Nginx access log records method/path/status without
query strings; site error logging is critical-only because ordinary Nginx rate-limit
and body-size diagnostics can echo full visitor-supplied request URIs.

## P12A security decision

Production uses one HTTPS origin. The host-only `SameSite=Lax` cookie is reinforced by
exact Origin validation on unsafe requests that carry the demo cookie. No complex auth
CSRF framework is needed for an anonymous, non-privileged workspace. Contact does not
act on cookie-owned state; honeypot, payload bounds, validation, and P12B proxy rate
limits address its spam/resource-abuse boundary. All API responses are `no-store`, so a
shared proxy cannot replay one visitor's workspace projection to another.
