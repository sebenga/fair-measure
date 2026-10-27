# Hosting

Fair Measure is one Docker image (Angular SPA + Django) on Render, same origin.

## Cold start (P0)

**Recommendation: keep the Render free web service and add a keep-alive ping.**

Render free spins the process down after idle. The next request waits ~30s on a
holding page. Two ways out:

| Option | Cost | Effort | Effect |
| --- | --- | --- | --- |
| UptimeRobot (or similar) GET `/healthz` every 5–10 min | $0 | 5 min in their UI | Stops most spin-downs. Still one cold start after deploys. |
| Render Starter | ~$7/mo | Change plan in the dashboard | No spin-down. Needed once traffic is real. |

Do **not** upgrade from this repo — Render plans are billed in the dashboard.
Point a free monitor at `https://<host>/healthz`. The public body is only
`{"status":"ok"|"degraded"|"error"}` so it is safe to poll.

When Redis is down but Postgres is up, public `/healthz` stays **HTTP 200** with
`status: "degraded"` so Render does not kill the web process. Use `X-Health-Key`
for the real checks (see RUNBOOK.md).

## Redis

The Blueprint provisions Render Key Value and sets `REDIS_URL` (`rediss://`).
Django uses it for pub/sub (`fm:events`) and the job inbox (`fm:jobs:inbox`).
The Node Socket.IO / BullMQ consumer is **not** on this Blueprint. Live sockets
need that service (or leave `FRONTEND_REALTIME_URL` empty so the SPA polls).

Connection errors on Render were localhost defaults or TLS. The client now:

- treats empty / localhost `REDIS_URL` on Render as **unconfigured** (health: `skipped`)
- uses `ssl_cert_reqs=CERT_NONE` for `rediss://`
- reconnects once after a `RedisError`

## Staging → production

Render free allows **one** web service. Recommended path when you pay:

1. Add a second Docker web service `fairmeasure-v2-staging` on the same Blueprint
   (Starter or a second paid instance). Auto-deploy `main` there.
2. Keep `fairmeasure-v2` as production. Promote by deploying the same image/SHA
   (Render “Manual Deploy” of the commit that passed staging smoke).
3. On smoke failure, redeploy the previous successful deploy from the Render
   dashboard (no `git push --force`).

Until then, `main` deploys straight to the single production service.

## Environment

| Variable | Purpose |
| --- | --- |
| `HEALTH_KEY` | Shared secret for `/healthz` details (`X-Health-Key`) |
| `REDIS_URL` | Render Key Value connection string |
| `FRONTEND_HORSES` | `true` to show `/tabs/horses` (off in production) |
| `FRONTEND_REALTIME_URL` | Socket.IO origin. Empty = no live socket (HTTP only) |
| `SENTRY_DSN` | Optional; not wired yet |

## Socket.IO

Path: `/socket.io` on the **realtime** host (`environment.realtimeUrl`), not
under `/api/v1`. Handshake requires a JWT in `auth.token`. The client falls
back to HTTP polling and reconnects with exponential backoff (max 15s).
Without a realtime service the app stays usable over REST.
