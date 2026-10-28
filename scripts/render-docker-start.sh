#!/usr/bin/env bash
set -euo pipefail
cd /app
python manage.py migrate --noinput
# Demo data only when the database has no users. Never reset existing accounts.
if [ "${SEED_ON_BOOT:-}" = "true" ]; then
  python manage.py seed_demo || true
fi
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers 1 \
  --threads 4 \
  --timeout 120
