#!/usr/bin/env bash
set -euo pipefail
cd /app
python manage.py migrate --noinput
python manage.py seed_demo || true
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers 1 \
  --threads 4 \
  --timeout 120
