#!/usr/bin/env bash
set -euo pipefail

cd /opt/huskytracking
exec docker compose \
  --project-name husky-tracking-production \
  --env-file /etc/huskytracking/.env.production \
  -f /opt/huskytracking/compose.production.yml \
  run --rm --no-deps backend /opt/venv/bin/python -m app.demo.cleanup
