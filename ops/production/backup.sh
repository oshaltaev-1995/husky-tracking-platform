#!/usr/bin/env bash
set -euo pipefail
umask 077

cd /opt/huskytracking
backup_root=/var/backups/huskytracking
state_root=/var/lib/huskytracking
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
tmp_dir=$(mktemp -d "$backup_root/.incomplete-$timestamp-XXXXXX")
final_dir="$backup_root/$timestamp"

cleanup_tmp() {
  if [ -d "$tmp_dir" ]; then
    find "$tmp_dir" -maxdepth 1 -type f -delete
    rmdir "$tmp_dir" 2>/dev/null || true
  fi
}
trap cleanup_tmp EXIT

exec 9>/run/lock/huskytracking-backup.lock
flock -n 9 || { echo 'Another Husky Tracking backup is running.' >&2; exit 1; }

compose() {
  docker compose \
    --project-name husky-tracking-production \
    --env-file /etc/huskytracking/.env.production \
    -f /opt/huskytracking/compose.production.yml \
    "$@"
}

# exec targets only the already-running, project-labelled DB container. Unlike
# compose run/up, it cannot create or restart dependencies.
[ "$(compose ps --status running -q db | wc -l)" -eq 1 ]
compose exec -T db sh -lc \
  'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl' \
  > "$tmp_dir/database.dump"
compose exec -T db sh -lc 'exec pg_restore --list' \
  < "$tmp_dir/database.dump" > /dev/null

dump_sha=$(sha256sum "$tmp_dir/database.dump" | awk '{print $1}')
alembic_revision=$(compose exec -T db sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "select version_num from alembic_version limit 1"')
canonical_checksum=$(compose exec -T db sh -lc \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "select semantic_checksum from demo_datasets order by id desc limit 1"')
deployed_commit=$(cat "$state_root/deployed-commit")

printf '%s  %s\n' "$dump_sha" database.dump > "$tmp_dir/database.dump.sha256"
cat > "$tmp_dir/manifest.txt" <<EOF
timestamp_utc=$timestamp
deployed_commit=$deployed_commit
alembic_revision=$alembic_revision
canonical_checksum=$canonical_checksum
dump_sha256=$dump_sha
EOF

if [ -e "$final_dir" ]; then
  echo 'A Husky Tracking backup already uses this UTC timestamp.' >&2
  exit 1
fi
mv -T "$tmp_dir" "$final_dir"
trap - EXIT
printf '%s\n' "$timestamp" > "$state_root/last-successful-backup"

# Retain only this job's timestamp-named backup directories, inside its own root.
while IFS= read -r candidate; do
  find "$candidate" -maxdepth 1 -type f -delete
  rmdir "$candidate"
done < <(find "$backup_root" -mindepth 1 -maxdepth 1 -type d \
  -name '20??????T??????Z' -mtime +14 -print)

echo "Created Husky Tracking PostgreSQL backup $timestamp"
