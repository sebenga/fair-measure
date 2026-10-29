#!/usr/bin/env bash
# Run the whole app the way Render runs it, on your own machine:
#
#   - the production Angular build (not `ng serve`), served by Django from
#     a single origin, exactly like the Dockerfile + whitenoise do on Render
#   - DJANGO_SETTINGS_MODULE=config.settings.prod (DEBUG=false, strict CORS,
#     the same exception handling and SPA fallback middleware hosted uses)
#   - whatever DATABASE_URL/REDIS_URL are already in your shell. Export the
#     ones from docker-compose.yml first for full Postgres+Redis parity:
#       export DATABASE_URL=postgres://fairmeasure:fairmeasure@localhost:5432/fairmeasure
#       export REDIS_URL=redis://localhost:6379/0
#     (requires `docker compose up -d postgres redis`, or a native install).
#     Leave them unset and it still runs — against SQLite, same as before —
#     which still catches every build/settings bug, just not DB-engine bugs.
#
# Usage: scripts/dev-parity.sh
# Then open http://localhost:8000 — there is no separate :8100 frontend.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Building the production frontend bundle (same as the Dockerfile)"
cd "$ROOT/frontend"
FRONTEND_API_BASE_URL="${FRONTEND_API_BASE_URL:-/api/v1}" \
FRONTEND_REALTIME_URL="${FRONTEND_REALTIME_URL:-http://localhost:4000}" \
  node scripts/write-render-env.mjs
npm run build:prod

echo "==> Starting Django on config.settings.prod, serving that bundle"
cd "$ROOT/backend"
export DJANGO_SETTINGS_MODULE=config.settings.prod
export DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY:-local-parity-secret-key-change-me}"
export JWT_SIGNING_KEY="${JWT_SIGNING_KEY:-local-parity-jwt-key-change-me}"
export DJANGO_DEBUG=false
export DJANGO_ALLOWED_HOSTS="${DJANGO_ALLOWED_HOSTS:-localhost,127.0.0.1}"
export CORS_ALLOWED_ORIGINS="${CORS_ALLOWED_ORIGINS:-http://localhost:8000}"
export PUBLIC_APP_ORIGIN="${PUBLIC_APP_ORIGIN:-http://localhost:8000}"
export PUBLIC_API_ORIGIN="${PUBLIC_API_ORIGIN:-http://localhost:8000}"
export SECURE_SSL_REDIRECT=false
export SEARCH_ENABLED="${SEARCH_ENABLED:-false}"
export SPA_DIR="$ROOT/frontend/www/browser"

python manage.py migrate --noinput
exec python manage.py runserver "0.0.0.0:${PORT:-8000}"
