# Runbook

Production: `https://fairmeasure-v2.onrender.com`

## Health

```bash
# Public — no internals
curl -sS https://fairmeasure-v2.onrender.com/healthz
# {"status":"ok"} | {"status":"degraded"} | {"status":"error"}

# Details (Render dashboard → Environment → HEALTH_KEY)
curl -sS -H "X-Health-Key: $HEALTH_KEY" \
  https://fairmeasure-v2.onrender.com/healthz
# {"status":"...","checks":{"database":"ok","redis":"ok|error|skipped"},"debug":false}

curl -sS https://fairmeasure-v2.onrender.com/api/v1/version
# {"commit":"<sha>","built_at":"<iso>"}
```

Alert when `status != "ok"` **or** TTFB > 3s. `degraded` usually means Redis.
`error` / HTTP 503 means Postgres is down.

## Common failures

### Cold start (~30s holding page)

Free web processes sleep. Confirm UptimeRobot (or equivalent) hits `/healthz`
every 5 minutes. If users still wait after idle, upgrade that service to
Render Starter (~$7/mo). See HOSTING.md.

### Redis `ConnectionError` / health `degraded`

1. Render → Key Value `fairmeasure-v2-kv` is running.
2. Web service `REDIS_URL` is the Key Value connection string (`rediss://`).
3. Do not point production at `localhost`.
4. Live scores still write through the API; only sockets and background jobs
   need Redis + the Node consumer.

### Blank white page

The SPA now shows a boot skeleton, a Retry button after 20s / bootstrap
failure, and a runtime banner. If it is still blank:

1. Browser console — look for `/api/...` returning HTML (fixed by SPA
   fallback: APIs now 404 JSON).
2. `GET /manifest.webmanifest` must be JSON, not HTML.
3. Hard-reload after a deploy (hashed bundles).

### Socket disconnects

Expected when `FRONTEND_REALTIME_URL` is empty (this Blueprint). The client
does not connect. REST still loads tables, fixtures and scores. To enable
live updates, deploy `realtime/` and set `FRONTEND_REALTIME_URL`.

Unauthenticated socket handshakes are rejected (`An access token is required`).

### Registered account disappeared

The user table lives in Postgres (`DATABASE_URL`). If that variable is missing,
Render used to fall back to SQLite **inside the container**. A deploy or sleep
wipes that file, so new accounts vanish. `collectstatic` can finish without it;
the web process still refuses to start without `DATABASE_URL`. After deploy, confirm:

```bash
curl -sS -H "X-Health-Key: $HEALTH_KEY" https://fairmeasure-v2.onrender.com/healthz
```

`checks.database` must be `ok`. Then sign in with the email you registered —
do not register again; a duplicate email is rejected on purpose.

### Auth 429

`/api/v1/auth/login`, `/register`, `/google` are limited to 5 attempts / minute
/ IP. Wait a minute; do not reset the database.

## Rollback

1. Render → `fairmeasure-v2` → Events → previous **successful** deploy →
   **Rollback**.
2. Do not force-push `main`.
3. Recheck `/healthz` and `/api/v1/version` after the rollback finishes.
4. If migrate-forward is unsafe, restore the Postgres backup from the
   Render dashboard before rolling the image back.

## Synthetic monitor

Create a check every 5 minutes:

- URL: `https://fairmeasure-v2.onrender.com/healthz`
- Header: `X-Health-Key: <HEALTH_KEY>` (optional; public body is enough for
  `status`)
- Alert if HTTP != 200, body `status` is not `ok`, or response time > 3s
