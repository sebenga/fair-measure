# Single image: Angular app + Django API on one origin.
# Render: Web Service → Docker → this file.

FROM node:22-bookworm-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ENV FRONTEND_API_BASE_URL=/api/v1
ENV FRONTEND_REALTIME_URL=
RUN node scripts/write-render-env.mjs && npm run build:prod

FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    SPA_DIR=/app/spa
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY backend/ /app/
COPY --from=frontend /frontend/www/browser /app/spa

# collectstatic needs a throwaway secret; Render overrides it at runtime.
ENV DJANGO_SECRET_KEY=collectstatic-build-only \
    SECURE_SSL_REDIRECT=false \
    SEARCH_ENABLED=false
RUN python manage.py collectstatic --noinput

COPY scripts/render-docker-start.sh /render-docker-start.sh
RUN chmod +x /render-docker-start.sh

EXPOSE 8000
CMD ["/render-docker-start.sh"]
