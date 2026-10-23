#!/usr/bin/env bash
# Render Start Command: bash start.sh
set -euo pipefail
cd "$(dirname "$0")/backend"
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers 1 \
  --threads 4 \
  --timeout 120
