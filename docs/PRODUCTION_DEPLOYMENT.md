# Production deployment runbook

This is the P12B operator runbook for `https://huskytracking.com`. P12B-2 staged the
exact `bc6d248` release on the shared VPS behind `127.0.0.1:8081`; it did **not**
connect Caddy or DNS. P12B-2.5 codifies the ingress and maintenance configuration in
Git only. Do not confuse repository preparation with a live public launch.

## Architecture and trust boundary

```text
Internet → existing Caddy :80/:443 → huskytracking_proxy
                                      └─ huskytracking-frontend :80
                                         ├─ static Angular/media
                                         └─ /api/* → private FastAPI :8000
                                                      └─ private PostgreSQL :5432
```

`compose.production.yml` publishes **zero** host ports. Its production frontend
service key is deliberately `huskytracking-frontend`, not `frontend`:
the existing Kennel Operations Caddy already resolves `frontend` on its own network.
`compose.ingress.yml` joins only this uniquely named service to the external
`huskytracking_proxy` network. Backend and PostgreSQL stay on the separate
project-private network. The staging-only `compose.staging.yml` publishes only
`127.0.0.1:8081:80` and must not be included in the public invocation. The existing
Kennel Operations network, volume, services, and Caddy configuration remain separate.

Before ingress, create and verify the dedicated network with the reviewed subnet
`172.30.50.0/24`; set `TRUSTED_PROXY_CIDR` to that **actual** subnet. Only Caddy and
the Husky frontend should join it. Nginx trusts `X-Forwarded-For` only from this
subnet; direct loopback/Docker-bridge callers cannot choose a rate-limit identity by
sending that header. Caddy's default reverse proxy ignores untrusted incoming
`X-Forwarded-*` values. Nginx then overwrites IP forwarding headers sent to the
private backend. The backend's internal hop is HTTP; canonical public URLs come from
`PUBLIC_BASE_URL`, not that hop's scheme. Keep Cloudflare DNS-only initially unless
the Caddy/Cloudflare trust chain is reviewed; enabling Cloudflare proxying later may
otherwise group visitors by Cloudflare egress IP. Never trust arbitrary
`CF-Connecting-IP` or `0.0.0.0/0`.

The production browser uses one origin and relative `/api/v1/...` URLs. The configured
`PUBLIC_BASE_URL=https://huskytracking.com` drives runtime canonical/Open Graph URLs.
Interactive API docs are disabled in production. `/api/v1/health` is process liveness;
`/api/v1/ready` includes a local database query and reveals no topology or credentials.

## Required environment

Copy `.env.production.example` to an untracked `.env.production` on the server and
replace every placeholder. Generate secrets privately, for example:

```bash
openssl rand -hex 32  # DEMO_SESSION_SECRET
openssl rand -base64 36  # database password; URL-encode it in DATABASE_URL
```

The controller is Oleg Shaltaev (Finland), the confirmed public privacy address is
`privacy@huskytracking.com`, and the hosting region is Netherlands (EEA). The private
Cloudflare Email Routing destination is not a deployment/documentation value.
`contact@huskytracking.com` also receives mail. Production Contact delivery is now
enabled through Brevo SMTP with STARTTLS on port 2525; SMTP credentials and the private
Contact recipient remain only in the server environment. The initial public form test
was accepted by SMTP and received by the owner. Do not print or document the forwarding
destination. The received test message passed SPF, domain-aligned DKIM, and DMARC.

Production startup rejects HTTP/localhost public URLs, a weak session secret, insecure
demo cookies, origin-check bypass, placeholder privacy values, local/test database
URLs, sink contact delivery, and incomplete or plaintext SMTP configuration. Do not
print or commit the completed file. Configure real controller identity, privacy email,
controller country, hosting region, and—when SMTP is enabled—the mail provider name and
processing region. Both public addresses are confirmed active; that does **not** imply
SMTP delivery is configured.

SMTP mode needs sender, recipient, host, optional paired username/password, provider
metadata, and either STARTTLS or implicit TLS. Runtime transport failure returns a safe
Contact error without stopping the application; invalid startup configuration fails
fast. Port 587 was unreachable from this VPS, so the validated production transport
uses port 2525 with certificate-verified STARTTLS. Do not change this to plaintext to
work around network failures.
Keep `DEMO_SESSION_SECRET` stable across ordinary redeploys; rotating it deliberately
invalidates all existing anonymous workspace cookies without exposing their values.

## Compose and release commands

On the VPS, run from `/opt/huskytracking`. Every command must use the explicit project
and private environment file. Never use a directory-derived Compose project name.
The currently installed P12B-2 VPS override is staging-only and must not be used for
final public ingress: first carry its resource/log/PostgreSQL tuning into a reviewed
host-specific override **without ports**, such as
`/etc/huskytracking/compose.vps-runtime.yml`.

```bash
# Validate final public mode before changing containers. This must list zero ports.
docker compose --project-name husky-tracking-production \
  --env-file /etc/huskytracking/.env.production \
  -f compose.production.yml -f compose.ingress.yml \
  -f /etc/huskytracking/compose.vps-runtime.yml config

# Validate the explicit staging alternative separately; only 127.0.0.1:8081 is allowed.
docker compose --project-name husky-tracking-production \
  --env-file /etc/huskytracking/.env.production \
  -f compose.production.yml -f compose.staging.yml config
```

Do not include `compose.staging.yml` alongside `compose.ingress.yml`. Caddy owns
public TCP 80/443; no Husky service publishes a host port in final mode. The
production image can validate Nginx with `nginx -t` once `backend` resolves on its
private network; its entrypoint also validates the trusted CIDR before Nginx starts.

### First deployment only

```bash
# 1. Start only the dedicated PostgreSQL service and wait for health.
docker compose --project-name husky-tracking-production \
  --env-file /etc/huskytracking/.env.production \
  -f compose.production.yml up -d db

# 2. Apply migrations exactly once as a deployment job, never from every web worker.
docker compose --project-name husky-tracking-production \
  --env-file /etc/huskytracking/.env.production \
  -f compose.production.yml run --rm --no-deps backend \
  /opt/venv/bin/alembic upgrade head

# 3. Seed only an empty database. This refuses existing Dog rows and never truncates.
docker compose --project-name husky-tracking-production \
  --env-file /etc/huskytracking/.env.production \
  -f compose.production.yml run --rm --no-deps backend \
  /opt/venv/bin/python -m app.demo.initialize

# 4. Validate the canonical world and checksum.
docker compose --project-name husky-tracking-production \
  --env-file /etc/huskytracking/.env.production \
  -f compose.production.yml run --rm --no-deps backend \
  /opt/venv/bin/python -m app.demo.inspect

# 5. Start the private backend and frontend using the reviewed final overlays.
docker compose --project-name husky-tracking-production \
  --env-file /etc/huskytracking/.env.production \
  -f compose.production.yml -f compose.ingress.yml \
  -f /etc/huskytracking/compose.vps-runtime.yml up -d backend huskytracking-frontend
```

The inspection must report
`2ad3418ecb5edad1d4676a9a6e0cf43b2cfbfa167c0218e96d9749fd12e24af2`.
Do not use `app.demo.reset` in production; it is deliberately refused. `initialize`
does not replace existing data.

### Normal redeploy

1. Build/pull the intended immutable revision and retain the previous image/revision.
2. Take a database backup when migration risk warrants it.
3. Run `alembic upgrade head` as one explicit job.
4. Restart backend/frontend, then wait for health and run smoke tests.
5. Never reseed or reset during a normal redeploy.

### P12B-3 transition from the current loopback staging stack

This is a future live operation, **not** performed by P12B-2.5:

1. Update `/opt/huskytracking` to the reviewed new Git commit; verify its SHA and
   preserve the private environment and separate PostgreSQL volume.
   For the P12B-3R corrective release, rename the frontend key in both VPS-only
   resource overlays to `huskytracking-frontend` before rendering Compose. Stop and
   remove only the old Husky project `frontend` container before starting the renamed
   staging service on 8081; never use `--remove-orphans` against an unreviewed project.
2. Reinstall the version-controlled Husky maintenance units from
   `ops/production/systemd/`. Test cleanup and backup manually, verify checksum and
   backup, then resume timers. This removes the P12B-2 server-script drift.
3. Carry current VPS resource/log/PostgreSQL settings into a host-only runtime
   override with **no published ports**; remove `127.0.0.1:8081` from the active
   Compose invocation. Render and inspect final Compose before starting containers.
4. Create `huskytracking_proxy` with the reviewed `172.30.50.0/24` subnet. Join only
   Husky's uniquely named `huskytracking-frontend` service and existing Caddy.
   Before editing Caddy, confirm from inside that container that `frontend` resolves
   **only** to the Kennel Operations frontend and `huskytracking-frontend` resolves
   **only** to Husky. If either assertion fails, detach Caddy immediately and return
   Husky to loopback staging. Do not join Husky backend/database or Kennel Operations
   app services.
   This check is mandatory: the first attempted attachment of the generic Husky
   `frontend` service made the existing Caddy resolve its Kennel Operations upstream
   to Husky and briefly returned 502. Detachment restored the old site without a
   restart; a mere additional alias does not fix the generic service-name collision.
5. Add a Caddy site for `huskytracking.com` routing to that alias, with whole-site
   Basic Auth and temporary global noindex. Validate Caddy config before a controlled
   reload; preserve the existing `app.kennelops.fi` site and health.
6. Configure Cloudflare DNS A (and optional AAAA/`www`) only after ingress is ready;
   obtain/verify TLS and HTTP→HTTPS. Keep Cloudflare DNS-only until client-IP trust is
   reviewed for any proxy mode.
7. Configure/test outbound Contact SMTP, firewall, external monitoring and alerting,
   and final real-domain security, rate-limit, privacy, accessibility, performance,
   workspace-isolation, and backup checks. Consider HSTS only after HTTPS/renewal is
   accepted; remove Basic Auth only for the deliberate public launch.

P12B-2 verified one Uvicorn worker and a bounded pool of 3 + 2 overflow connections
beside the warm Snow worker; retain those conservative initial values until measured
load justifies change. PostgreSQL memory, worker count, and total possible connections
must be reviewed together. Correctness does not rely on process memory: workspace
tokens, date locks, copied rows, and cleanup state are PostgreSQL-backed.

## HTTPS, hostname and public proxy (P12B)

P12B must configure DNS and certificates, then preserve path/query for:

- `http://huskytracking.com/*` → `https://huskytracking.com/*`;
- optionally `https://www.huskytracking.com/*` → `https://huskytracking.com/*`.

Do not enable HSTS until certificate issuance and renewal, HTTP redirect, canonical
HTTPS, and all chosen subdomains have passed acceptance. Do not add
`includeSubDomains` or preload without a separate deliberate decision. Public firewall
rules should expose only required web/administration ports—not 5432 or 8000.

Repository Nginx sets CSP, anti-sniffing, referrer, permissions, clickjacking, body-size,
gzip, cache policy, and Husky-specific source-IP rate limits. Hashed build files and
versioned dog portraits are immutable; HTML/runtime config and API responses are not
shared-cacheable. Existing Caddy 2.8.4 has no rate-limit module; do not install a plugin
or a second public listener. Caddy owns TLS, HTTP→HTTPS, optional `www` redirect, and
eventual HSTS. During private pre-launch, protect the **entire** site including `/api`
with Caddy `basic_auth` and temporary global
`X-Robots-Tag: noindex, nofollow, noarchive`. Do not add a second application auth
layer or commit preview credentials. Do not alter the app's long-term SEO metadata for
this temporary gate.

The CSP keeps scripts, images, fonts, connections, and framing self-only. The sole
`'unsafe-inline'` allowance is `style-src`, required by the current Angular component
runtime and data-driven inline bar sizing; `script-src` does not allow inline or eval.
Re-test the browser console whenever Angular/build behavior changes.

Nginx transient shared-memory zones use the trusted client IP, never a cookie, email,
or fingerprint. Initial limits are Contact POST 3/minute with burst 2; demo session
GET/reset POST 10/minute with burst 6; Team Builder generate POST 10/minute with burst
6; and a broad API POST/PUT/PATCH/DELETE limit of 1/second with burst 30. The general
mutation limit also applies to those special endpoints. Excess requests return a small
JSON `429`; limits are operational starting points to tune after real traffic tests.
Ordinary GET navigation, public pages, and static assets are not rate-limited. The
256 KiB body ceiling, Contact honeypot, and backend field validation remain in place.
No process-local FastAPI limiter is used.

## Cleanup, logs and monitoring

The repository-owned maintenance entrypoints are
`ops/production/cleanup.sh` and `ops/production/backup.sh`, with dedicated systemd
units/timers under `ops/production/systemd/`. They hard-code only the Husky project,
deployment path, and private environment path; no Kennel Operations resource is a
dependency. Cleanup uses `run --rm --no-deps backend` so Compose cannot recreate its
database dependency. Backup uses `compose exec -T db`, targeting the already-running
Husky database; it cannot start a second database container. Both propagate failures.

Run cleanup hourly for the 24-hour workspace TTL. The canonical manual command is:

```bash
/opt/huskytracking/ops/production/cleanup.sh
```

The command is idempotent, deletes only expired workspace graphs through database
cascades, reports a count/exit status, and never deletes baseline rows. Cleanup failure
must alert/log but must not run heavy cleanup inside public requests.

P12B-2 corrected the installed cleanup script on the VPS after a one-off run recreated
**only the new Husky** PostgreSQL container. That server-only correction is now in Git.
At P12B-3, update `/opt/huskytracking` to this commit, install the version-controlled
systemd units, `systemctl daemon-reload`, manually test both services, and only then
resume their timers. Do not preserve the old `/usr/local/sbin` variants as undocumented
drift. The new scripts intentionally use the base production Compose file alone for
maintenance: `--no-deps`/`exec` prevent dependency orchestration, regardless of the
active staging or ingress overlay.

Container/application logs contain request ID, method, path, status, and duration—not
query strings, cookies, workspace tokens, Contact bodies, note text, or secrets. P12B
must configure actual journald/Docker rotation and retention; start with 14–30 days and
adjust to policy/capacity. Monitor HTTP liveness/readiness, Docker health, database,
cleanup exit status, certificate renewal, disk space, memory, and backup jobs. Database,
logs, and backups share finite VPS disk even though workspace expiry bounds app growth.

## Backup, restore and rollback

The Husky-only backup unit runs daily at 04:40 Europe/Helsinki, separately from the
Kennel Operations backup window. It writes a validated PostgreSQL custom-format dump,
SHA-256, and non-secret commit/Alembic/checksum manifest atomically under
`/var/backups/huskytracking`; it retains timestamp-named local backups for about 14
days. Check permissions and free space. Source and the 60 portrait assets are
reproducible deployment artifacts, but GitHub is not a database backup.

Rehearse restoration without touching production:

1. create a backup;
2. restore it into a temporary isolated database;
3. run `alembic upgrade head` and `alembic check`;
4. run `python -m app.demo.inspect` and verify the baseline checksum;
5. start an application pointed only at the restored database and smoke-test it.

For rollback, retain the previous build/image and assess schema compatibility before
deploying it. Back up before risky migrations. Alembic downgrade is not an automatic
production rollback: downgrades can discard data, and forward-fix plus restore is often
safer. Document the decision per release; do not promise zero-downtime rollback.

## Go-live checklist (P12B)

- [ ] VPS capacity and supported OS reviewed; Docker/Compose patched.
- [ ] Private `.env.production` populated with generated secrets and real privacy data.
- [ ] Strong database password and least-privilege networking configured.
- [ ] SMTP provider, addresses, TLS mode, region, and delivery tested.
- [ ] DNS A/AAAA records and optional `www` record configured.
- [ ] TLS certificate issuance and automated renewal verified.
- [ ] HTTP→HTTPS and optional `www` redirects preserve path/query.
- [ ] Only public web/administration ports exposed; firewall reviewed.
- [ ] Migrations, first initialization, checksum, and 60/60 media validation pass.
- [ ] `/healthz`, `/api/v1/health`, and `/api/v1/ready` monitored.
- [ ] Inner-Nginx rate limits and Caddy→Nginx trusted forwarding verified on the real domain.
- [ ] HSTS enabled only after HTTPS/renewal/subdomain acceptance.
- [ ] Hourly cleanup and failure reporting installed.
- [ ] Log rotation/14–30 day retention configured and secret redaction inspected.
- [ ] Backup schedule and isolated restore rehearsal pass.
- [ ] Disk/database/certificate/uptime monitoring active.
- [ ] Real-domain security headers, CSP console, same-origin network, performance,
      responsive accessibility, Contact failure, and workspace isolation tested.
- [ ] Rollback owner, prior image, backup, and migration compatibility recorded.

There is no public admin surface. Global initialization, inspection, cleanup, migration,
and guarded development reset are CLI/operator operations. **Never run the destructive
development reset against production.**
