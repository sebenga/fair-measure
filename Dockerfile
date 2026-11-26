# Minimal free-tier redirect for the leftover Render service.
# This file belongs on the render-redirect branch only. Coolify builds from main.
FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
EXPOSE 10000
