# P13/P14 release candidate: upgrade and rollback

This is a procedure for a **future, separately authorized deployment**. P13G prepared
and rehearsed the upgrade locally. P14D prepares a presentation candidate and retains
an offline synthetic UX/UI stand; it does not publish code or change production.
Independent acceptance of the final candidate report and an explicit owner deployment
instruction are required before running these commands on the VPS. No release tag is
created by these local stages.

The expected installed public release is `public-v1.2`, commit
`bc8c91098e156411f40b39112a9e930e3a65904b`, schema `5c82f32e5d8a`. The P13 candidate
schema is `b7e13a9d4c20`; it adds workspace housing overrides without changing the
canonical seed. P13A–F are accepted local work, not evidence of an existing deployment.
Use the exact final commit and image identities from the independently accepted report,
not a moving branch name or the first P14D handoff. P14C recovery is independently
accepted at `0b602970df7d2b0263b055abcf5b462626ba2f08` in Groq-only demo scope.
P14D is **READY FOR UX/UI REVIEW**, not finally accepted: after that review insert its
final accepted 40-character SHA at the prompt below and retain the matching source/build
bindings. P14 adds no migration; the existing P13 schema upgrade/rollback still applies.
A different installed commit/schema/topology is a stop condition.

## P14 default-off/privacy gate

Do not mount local QA keys or fixture harnesses into production. Keep
`AGENT_ENABLED=false` and `AGENT_OPENROUTER_RESERVE_ENABLED=false` in the real private
runtime environment for this future deployment. Existing non-AI features must work
with both disabled. A saved reserve key never activates the reserve. OpenRouter is
DEFERRED, not a passed fallback. Any later owner-authorized activation is Groq Free
`openai/gpt-oss-20b` only with confirmed account/privacy controls and existing secret
handling. D adds no inference authorization: all historical ledgers remain CLOSED
at 21/21, and no live smoke may reuse their budgets.

To disable a previously authorized agent, set the existing `AGENT_ENABLED=false`
privately and recreate only Husky backend via the documented explicit Compose
invocation; configuration changes take effect on restart. Leave reserve disabled.
Do this only as part of an authorized deployment/operation, never while following this
local review package. Do not print environment files, keys or recipient values.

Retain same-origin cookie/origin fences, private backend/DB, API no-store, admission
limits, deadline/cancellation guards and path-only logs. Check conditional Privacy with
the actual active provider list; a disabled agent must not promise ongoing AI processing.
Confirm `PRIVACY_EFFECTIVE_DATE` at the future substantive notice publication. The local
2026-11-22 template/default is not evidence that production already carries that date.
Preserve real controller/contact/hosting/mail/TTL configuration and account opt-outs.

## Delivery and GitHub-hosted compute (read-only check, 22 November 2026)

At the P14D source HEAD there is no `.github/workflows` directory. Existing delivery is
exact Git commit plus Docker Compose builds/artifacts, not a mandatory Actions/ghcr
pipeline. Read-only authenticated GitHub queries returned: repository public, default
branch main; repository rulesets empty; main branch protection 404 "Branch not protected";
Actions workflows total 0. Commands used (no settings or jobs changed):

```bash
gh api repos/oshaltaev-1995/husky-tracking-platform --jq '{full_name,visibility,default_branch,archived}'
gh api repos/oshaltaev-1995/husky-tracking-platform/rulesets --jq '[.[] | {name,enforcement,target}]'
gh api repos/oshaltaev-1995/husky-tracking-platform/branches/main/protection --jq '{required_status_checks: .required_status_checks, enforce_admins: .enforce_admins.enabled}'
gh api repos/oshaltaev-1995/husky-tracking-platform/actions/workflows --jq '{total_count,workflows:[.workflows[] | {name,path,state}]}'
```

These observations are not a guarantee that remote rules will remain unchanged.
Recheck before a future merge/release; if a required check appears, satisfy it rather
than bypassing/disabling it or calling a local test a GitHub check. Account balance,
budget and reset date were **NOT VERIFIED**. No workflow/rerun/runner/build was launched.
[GitHub's billing documentation](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
distinguishes standard public-repository runner compute from included private/internal
usage, larger runners and storage. Do not infer an account reset on 1 December.

The existing manual path below requires no GitHub-hosted compute: retain accepted local
quality logs/source bindings, deliver the exact accepted commit through separately
authorized Git/archive transfer, preserve actual old images/backup, then build backend
and frontend sequentially on an explicitly authorized VPS with measured headroom.
Alternatively use independently verified exact-commit linux/amd64 artifacts if already
available. No requirement to publish a private repository, buy compute, add a self-hosted
runner on the Mac/shared VPS, or use ghcr is introduced. Runtime/image acceptance,
backup and the compatible P13 workspace-draining rollback remain mandatory.

## Fixed boundaries

- Repository/runtime: `/opt/huskytracking`.
- Private environment: `/etc/huskytracking/.env.production`; do not print or copy it.
- Compose project: `husky-tracking-production`.
- Public invocation: `compose.production.yml`, `compose.ingress.yml`, and the existing
  `/etc/huskytracking/compose.vps-runtime.yml` resource override.
- Services: `db`, `backend`, `huskytracking-frontend`. The database remains running;
  only Husky application containers are replaced.
- The existing Caddy is the only public listener. Only `huskytracking-frontend` joins
  `huskytracking_proxy`; backend/database remain on the project-private network.
  Public Compose publishes **no host ports**. Never combine the staging overlay with ingress.
- Keep DNS, Caddy/TLS/HSTS, firewall, SMTP, and Kennel Operations unchanged. Do not
  reintroduce historical Basic Auth/global noindex or first-deploy initialization.

Use one Bash operator session after the accepted candidate has been made available
through the separately approved Git/image delivery process:

```bash
set -euo pipefail
cd /opt/huskytracking
ht() {
  docker compose --project-name husky-tracking-production \
    --env-file /etc/huskytracking/.env.production \
    -f /opt/huskytracking/compose.production.yml \
    -f /opt/huskytracking/compose.ingress.yml \
    -f /etc/huskytracking/compose.vps-runtime.yml "$@"
}
release_base=bc8c91098e156411f40b39112a9e930e3a65904b
read -r -p 'Exact independently accepted candidate commit from the final review report: ' release_candidate
[[ "$release_candidate" =~ ^[0-9a-f]{40}$ ]] || exit 1
test -z "$(git status --porcelain)" || exit 1
test "$(git rev-parse HEAD)" = "$release_base" || exit 1
test "$(cat /var/lib/huskytracking/deployed-commit)" = "$release_base" || exit 1
git cat-file -e "$release_candidate^{commit}" || exit 1
git merge-base --is-ancestor "$release_base" "$release_candidate" || exit 1
ht config --quiet
```

Confirm that `release_candidate` equals the independently accepted report's final
`git rev-parse HEAD` and its source bindings; merely existing on a P13/P14 branch is
insufficient. For P14D the first reviewable SHA may change after UX/UI corrections. Do not amend or move
the accepted commit. Record non-secret evidence under a root-only release directory:
commit, timestamp, schema, full container IDs, image IDs, project/network/volume labels,
and the prior states of Husky timers. Do not save rendered environment/Compose secrets.

## Preflight and retained rollback images

1. Verify HTTP 200 for Husky `/`, `/api/v1/health`, `/api/v1/ready` and the existing
   Kennel Operations site. Record existing container IDs/start times/restart counts.
2. Use `ht ps -a`, selected `docker inspect --format` fields and volume/network labels
   to prove the actual Husky project and dedicated PostgreSQL volume. Expected Compose
   volume key: `production-postgres-data`; its usual project-qualified name is
   `husky-tracking-production_production-postgres-data`. Verify the actual identity;
   never select a volume merely by a similar name. Backend DNS `db` must resolve only
   to that project's database, with no published backend/PostgreSQL ports.
3. Privately review the rendered public topology; every `ports` list must be empty and
   only the frontend may join ingress. Verify the existing unique upstream alias and
   trusted proxy CIDR without changing the shared Caddy network/configuration.
4. Confirm old schema using the running old binary and read-only SQL:

   ```bash
   ht exec -T backend /opt/venv/bin/alembic current
   ht exec -T db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT version_num FROM alembic_version"'
   ht exec -T backend /opt/venv/bin/python -m app.demo.inspect
   ```

   Both revisions must be `5c82f32e5d8a`; checksum must be
   `2ad3418ecb5edad1d4676a9a6e0cf43b2cfbfa167c0218e96d9749fd12e24af2`.
   Resolve any unexpected baseline/target before proceeding; do not repair it by reseeding.
5. Capture the actual running backend/frontend image IDs and tag those IDs with unique
   rollback names before building. Preserve the old checkout identity and the rendered
   image-reference names. A deployment-evidence SHA does not prove both running images
   were built together, so retain the actual IDs:

   ```bash
   release_stamp=$(date -u +%Y%m%dT%H%M%SZ)
   old_backend_id=$(docker inspect --format '{{.Image}}' "$(ht ps -q backend)")
   old_frontend_id=$(docker inspect --format '{{.Image}}' "$(ht ps -q huskytracking-frontend)")
   old_backend_ref=$(docker inspect --format '{{.Config.Image}}' "$(ht ps -q backend)")
   old_frontend_ref=$(docker inspect --format '{{.Config.Image}}' "$(ht ps -q huskytracking-frontend)")
   docker tag "$old_backend_id" "huskytracking-rollback-backend:$release_stamp"
   docker tag "$old_frontend_id" "huskytracking-rollback-frontend:$release_stamp"
   ht config --images
   ```

   Record these IDs/tags. Do not prune images, containers or volumes. Stop if a service
   resolves to an unexpected image or external resource.

## Build and controlled upgrade

Before checkout/build can change the image alias used by maintenance, record which
**Husky-only** timers are active and temporarily hold them:

```bash
systemctl is-active huskytracking-cleanup.timer huskytracking-backup.timer \
  huskytracking-monitor.timer huskytracking-ingress-network.timer || true
systemctl stop huskytracking-cleanup.timer huskytracking-backup.timer \
  huskytracking-monitor.timer huskytracking-ingress-network.timer
```

Verify corresponding oneshot services and prior maintenance containers have finished;
wait rather than killing an active backup. A missing/unexpected unit requires review.
Do not edit/disable units or affect another project's maintenance. The old application
can keep serving while images build; restore only timers that were active beforehand.

Prefer verified `linux/amd64` artifacts from the accepted commit. If building on the VPS,
approve capacity/headroom beside existing workloads first and build sequentially. Never
stop another application or its worker to make space. After preserving old identities:

```bash
git checkout --detach "$release_candidate"
test "$(git rev-parse HEAD)" = "$release_candidate" || exit 1
test -z "$(git status --porcelain)" || exit 1
ht config --quiet
ht build backend
ht build huskytracking-frontend
```

Record the resulting image IDs and add immutable candidate tags. Preserve the standard
Compose image references too: `ops/production/cleanup.sh` deliberately uses the base
production Compose file, so a release-only image override must not leave maintenance
running an older backend image. Verify its resolved backend image equals the candidate.
Do not mix staging ports into the host runtime override.

```bash
candidate_backend_id=$(docker image inspect --format '{{.Id}}' "$old_backend_ref")
candidate_frontend_id=$(docker image inspect --format '{{.Id}}' "$old_frontend_ref")
docker tag "$candidate_backend_id" "huskytracking-release-backend:$release_candidate"
docker tag "$candidate_frontend_id" "huskytracking-release-frontend:$release_candidate"
```

Require the rendered old/new and maintenance image references to agree before using
those aliases. If a host override changes them, stop for an explicit reviewed image
mapping instead of treating a different tag as proof of the candidate build.

Use an announced short maintenance window; this procedure does not promise zero downtime.
Keep maintenance held, then fence browser requests by stopping only Husky frontend and
gracefully drain its backend:

```bash
ht stop -t 30 huskytracking-frontend
ht stop -t 30 backend
/opt/huskytracking/ops/production/backup.sh
```

Validate the new Husky-only backup's SHA-256 and custom archive (`pg_restore --list`),
retain its non-secret manifest and exact directory, and confirm the rehearsed restore
procedure is available. PostgreSQL stays up; no backup or dump is copied into a public
review archive. There are now no app/maintenance writers against this database.

```bash
ht run --rm --no-deps backend /opt/venv/bin/alembic upgrade head
ht run --rm --no-deps backend /opt/venv/bin/alembic current
ht run --rm --no-deps backend /opt/venv/bin/alembic check
ht run --rm --no-deps backend /opt/venv/bin/python -m app.demo.inspect
```

Require `b7e13a9d4c20`, no unexpected schema operations, and the canonical checksum above.
There is **no initialize, seed or reset** in this upgrade. If a check fails, leave ingress
fenced and use the rollback decision below; do not start a partially verified release.

```bash
ht up --wait --wait-timeout 150 --no-deps --no-build backend
ht up --wait --wait-timeout 150 --no-deps --no-build huskytracking-frontend
ht ps
```

Verify actual running image IDs equal the recorded candidate IDs. The database container,
volume, public proxy and other project containers must retain their recorded identities.
Old open tabs may need a full reload for new Angular chunks and review context; never
automatically replay an old move, Training Day Apply or actual confirmation.

## Acceptance before evidence/tag update

- Public routes and demo deep links load; unknown routes keep HTTP 404 and branded noindex.
- Health/readiness, private topology, same-origin Secure cookie/origin checks, no-store API,
  CSP and path-only logs remain correct. No tokens, notes or request bodies enter logs.
- The one solver zone covers Training Day GET/Apply POST and Team Builder Generate with
  10/minute, burst 6. Apply also retains the mutation limit. Verify only a bounded test
  against the authorized target; ordinary GET navigation is unaffected and 429 is readable.
- In a temporary isolated workspace, check committed map/housing, Map/Summary printing,
  Training Day → 2×8 Generate/Save → reviewed Actual, then explicit workspace Reset.
  Never global-reset the production baseline or send a real Contact test email as smoke.
- Confirm 60 portraits, canonical checksum, expected analytics/actual semantics and clean
  error/restart observation. Kennel Operations must remain healthy with unchanged IDs/
  restart counts. Restore only previously active Husky timers and verify their status.

Only after those checks write the candidate SHA to `/var/lib/huskytracking/deployed-commit`
and retain timestamp/schema/image evidence. Do not overwrite prior rollback records.
Create a matching next `public-v1.x` annotated tag only after a separately authorized,
successfully verified deployment; P13G itself creates no tag or GitHub Release.

## Compatible rollback: drain with current code, retain additive schema

Rollback triggers include failed migration/inspect, unhealthy candidate, isolation/data
inconsistency, broken core workflow or persistent new server/proxy errors. Stop and assess
before acting on an unexplained discrepancy. Backup restore is a separate reviewed
recovery choice if the database itself is damaged; an old image alone is insufficient.

The selected application rollback intentionally discards **all temporary anonymous demo
workspaces**, while preserving canonical synthetic rows. Obtain the owner's maintenance
approval for that consequence. Keep Husky frontend/backend and maintenance fenced as above.
Run this only using the **new compatible candidate image**, before switching to old images:

```bash
ht run --rm --no-deps -T backend /opt/venv/bin/python - <<'PY'
from sqlalchemy import delete, func, select, text
from app.db.session import SessionLocal
from app.demo.semantic import semantic_checksum
from app.models import (
    DailyPlan, DemoWorkspace, DemoWorkspaceDay, DemoWorkspaceHousingOverride,
    PlannedActivity, PlannedActivityParticipant, PlannedTeam, PlannedTeamSlot, WorkSession,
)

expected = "2ad3418ecb5edad1d4676a9a6e0cf43b2cfbfa167c0218e96d9749fd12e24af2"
with SessionLocal.begin() as session:
    assert list(session.scalars(text("SELECT version_num FROM alembic_version"))) == ["b7e13a9d4c20"]
    assert semantic_checksum(session) == expected
    workspace_ids = list(session.scalars(select(DemoWorkspace.id).order_by(
        DemoWorkspace.id
    ).with_for_update()))
    removed = len(workspace_ids)
    session.execute(delete(DemoWorkspace))
    session.flush()
    for model in (DemoWorkspace, DemoWorkspaceDay, DemoWorkspaceHousingOverride):
        assert session.scalar(select(func.count()).select_from(model)) == 0
    for model in (DailyPlan, WorkSession):
        assert session.scalar(select(func.count()).select_from(model).where(
            model.demo_workspace_id.is_not(None)
        )) == 0
    for model in (PlannedActivity, PlannedActivityParticipant, PlannedTeam, PlannedTeamSlot):
        assert session.scalar(select(func.count()).select_from(model)) == 0
    assert semantic_checksum(session) == expected
print(f"Drained {removed} temporary workspaces; canonical checksum preserved.")
PY
```

Database cascades remove workspace housing, days, plans/teams and actual overlays. A
failure rolls the whole drain transaction back. This is not the development global reset,
and it must not run while app/maintenance writers are active. Retain only counts/checksum,
not workspace IDs, cookies or preconditions. Confirm the exact project/database identity
again immediately before this destructive temporary-data operation.

Restore the old checkout and retag the **retained actual image IDs** to their recorded
Compose image references; do not rebuild old images or run a downgrade. Verify image
resolution for both normal runtime and the base-file maintenance invocation before start:

```bash
git checkout --detach "$release_base"
docker tag "$old_backend_id" "$old_backend_ref"
docker tag "$old_frontend_id" "$old_frontend_ref"
ht up --wait --wait-timeout 150 --no-deps --no-build backend
ht up --wait --wait-timeout 150 --no-deps --no-build huskytracking-frontend
```

The old binary ignores the additive housing schema; draining first prevents ignored
overrides from surviving old Reset and reappearing after re-upgrade. Old cookies cannot
resolve their deleted workspace; the old anonymous-session policy may issue a **new**
workspace, so do not promise every old-cookie request returns 401. Deleted planned
confirmation IDs and old housing/Training Day preconditions cannot recover the old graph.
Verify that behavior, canonical reads and a later re-upgrade without stale resurrection.
Do not restore a backup containing those deleted graphs merely to make a count match.
Record the rollback identities/consequence, restore only previously active Husky timers,
and verify both sites. No Caddy/DNS/SMTP/firewall or Kennel Operations change is part of it.

If migration failed before reaching `b7e13a9d4c20`, do not run the new-model drain against
an old schema. Keep writers fenced and inspect the database directly. Returning the
retained old images without draining is valid only after proving transactional rollback
left head `5c82f32e5d8a`, no housing-override table, unchanged old data and the expected
checksum. Any partial/unexpected state requires the separately reviewed backup-restore
recovery decision; never guess or run a downgrade to make the revision match.

Local rehearsal results, backup/restore hashes and precise retained/deleted evidence are
in the P13G review bundle (`qa/MIGRATION_REHEARSAL.md`, `qa/migration-rehearsal.py`,
`evidence/migration-restore-rollback.json`). The local run preserved two existing
workspaces through old-schema upgrade and separate backup restore, added new housing/
Training Day state, drained three workspace graphs with compatible code, exercised old
binaries on the additive schema and re-upgraded without stale resurrection. Those
results are not evidence that this procedure ran live or that P13G has been accepted.
