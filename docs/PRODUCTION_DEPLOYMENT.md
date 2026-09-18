# Production deployment runbook

This is the P12B operator runbook for the canonical public origin
`https://huskytracking.com`. P12A prepares repository controls only; it does not change
DNS, configure a VPS/firewall, issue certificates, or install real SMTP credentials.

## Architecture and trust boundary

```text
Internet → TLS/public reverse proxy → frontend Nginx :80
                                      ├─ static Angular/media
                                      └─ /api/* → FastAPI :8000 → PostgreSQL :5432
```

In `compose.production.yml`, only the frontend HTTP port is published. Backend and
PostgreSQL are reachable solely on the private Compose network. Frontend Nginx
overwrites `X-Real-IP`, `X-Forwarded-For`, and `X-Forwarded-Proto`; Uvicorn may trust
forwarded headers only because its port is not public. If a host proxy is placed before
frontend Nginx in P12B, configure its trusted source ranges and real-IP behavior
explicitly. Never trust arbitrary client-supplied forwarding headers.

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

Production startup rejects HTTP/localhost public URLs, a weak session secret, insecure
demo cookies, origin-check bypass, placeholder privacy values, local/test database
URLs, sink contact delivery, and incomplete or plaintext SMTP configuration. Do not
print or commit the completed file. Configure real controller identity, privacy email,
controller country, hosting region, and—when SMTP is enabled—the mail provider name and
processing region. `privacy@huskytracking.com` and `contact@huskytracking.com` are only
examples until the mailboxes actually exist.

SMTP mode needs sender, recipient, host, optional paired username/password, provider
metadata, and either STARTTLS or implicit TLS. Runtime transport failure returns a safe
Contact error without stopping the application; invalid startup configuration fails
fast. Keep `CONTACT_DELIVERY_MODE=disabled` until delivery is ready.
Keep `DEMO_SESSION_SECRET` stable across ordinary redeploys; rotating it deliberately
invalidates all existing anonymous workspace cookies without exposing their values.

## Compose and release commands

All examples run from the repository root:

```bash
export COMPOSE_FILE=compose.production.yml
docker compose --env-file .env.production config --quiet
docker compose --env-file .env.production build
docker compose --env-file .env.production up -d db
```

### First deployment only

```bash
# 1. Start PostgreSQL and wait for health.
docker compose --env-file .env.production up -d db

# 2. Apply migrations exactly once as a deployment job, never from every web worker.
docker compose --env-file .env.production run --rm backend \
  /opt/venv/bin/alembic upgrade head

# 3. Seed only an empty database. This refuses existing Dog rows and never truncates.
docker compose --env-file .env.production run --rm backend \
  /opt/venv/bin/python -m app.demo.initialize

# 4. Validate the canonical world and checksum.
docker compose --env-file .env.production run --rm backend \
  /opt/venv/bin/python -m app.demo.inspect

# 5. Start the private backend and public frontend.
docker compose --env-file .env.production up -d backend frontend
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

Set `UVICORN_WORKERS` conservatively from measured VPS CPU/RAM (start with 2) and keep
the configurable SQLAlchemy pool bounded (`DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=5` are
small-host defaults). PostgreSQL memory, worker count, and total possible connections
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
gzip, and cache policies. Hashed build files and versioned dog portraits are immutable;
HTML/runtime config and API responses are not shared-cacheable. HSTS and source-IP rate
limits belong at the final TLS/public reverse proxy.

The CSP keeps scripts, images, fonts, connections, and framing self-only. The sole
`'unsafe-inline'` allowance is `style-src`, required by the current Angular component
runtime and data-driven inline bar sizing; `script-src` does not allow inline or eval.
Re-test the browser console whenever Angular/build behavior changes.

Suggested initial per-source limits (tune after real testing): Contact 3/minute and
10/hour; demo session/reset 10/minute; Team Builder generation 10/minute; other API
mutations 60/minute. Permit ordinary navigation (for example 120 GETs/minute) and do
not aggressively limit static assets. Retain Contact honeypot and backend payload
bounds. A process-local limiter is intentionally not used.

## Cleanup, logs and monitoring

Run hourly for a 24-hour workspace TTL:

```bash
docker compose --env-file .env.production run --rm backend \
  /opt/venv/bin/python -m app.demo.cleanup
```

The command is idempotent, deletes only expired workspace graphs through database
cascades, reports a count/exit status, and never deletes baseline rows. Cleanup failure
must alert/log but must not run heavy cleanup inside public requests.

Container/application logs contain request ID, method, path, status, and duration—not
query strings, cookies, workspace tokens, Contact bodies, note text, or secrets. P12B
must configure actual journald/Docker rotation and retention; start with 14–30 days and
adjust to policy/capacity. Monitor HTTP liveness/readiness, Docker health, database,
cleanup exit status, certificate renewal, disk space, memory, and backup jobs. Database,
logs, and backups share finite VPS disk even though workspace expiry bounds app growth.

## Backup, restore and rollback

Take PostgreSQL backups with provider-appropriate `pg_dump`/`pg_restore` commands and
store them outside the live database volume. A modest configurable starting policy is
daily backups with 7–14 daily copies plus a few weekly copies. The public demo has low
business-critical data value; measure storage before increasing retention. Source and
the 60 portrait assets are reproducible deployment artifacts, but GitHub is not a
database backup.

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
- [ ] Public proxy rate limits and trusted forwarding headers verified.
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
