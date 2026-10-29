# Fair Measure

A platform for competitions nobody has written the rules for yet. You define the
scoring categories, the points policy, and the tie-breakers; the app generates a
schedule, tracks live scores, keeps a league table, and gives every competition
its own social feed.

Built as three services that share Postgres and Redis:

| Service    | Stack                        | Responsibility                                     |
| ---------- | ---------------------------- | -------------------------------------------------- |
| `backend`  | Django 5 + DRF               | REST API, auth, domain logic, OpenAPI schema        |
| `realtime` | Node + Socket.io + BullMQ    | WebSocket fan-out and background job workers        |
| `frontend` | Ionic 8 + Angular 20         | Mobile-first client (web, iOS, Android via Capacitor) |

## Why three services

The requested stack mixes Django with two tools that only exist in Node — BullMQ
and Socket.io. Rather than substitute Celery and Django Channels, the Node
service runs both natively and Django talks to it through Redis:

- **Events out.** Django publishes to a Redis Pub/Sub channel. The gateway
  relays each message to the Socket.io rooms that should see it.
- **Jobs out.** Django pushes onto a Redis list. A bridge in the Node service
  drains it into the right BullMQ queue.
- **Work back in.** Workers call a token-authenticated `/internal/` API on
  Django to recompute standings, send pushes, or finalise media.

Django never imports a queue client and Node never touches the ORM, so each side
stays idiomatic. The contract between them is the message envelope in
`backend/apps/core/bus.py` and `realtime/src/types.ts`.

## Quick start

Requires Python 3.11+, Node 20+, and Docker (or your own Postgres and Redis).

```bash
cp .env.example .env          # defaults work for local development as-is
docker compose up -d          # Postgres + Redis
```

**Backend**

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python manage.py migrate
python manage.py seed_demo    # a rugby league mid-season, with data
python manage.py runserver
```

**Realtime service**

```bash
cd realtime
npm install
npm run dev       # Socket.io gateway on :4000
npm run worker    # BullMQ workers, in a second terminal
```

**Frontend**

```bash
cd frontend
npm install
npm start         # http://localhost:8100
```

Sign in as `owner@example.com` / `fairmeasure`.

| URL                             | What                         |
| ------------------------------- | ---------------------------- |
| http://localhost:8100           | The app                      |
| http://localhost:8000/api/docs/ | Swagger UI                   |
| http://localhost:8000/api/schema/ | OpenAPI 3 document         |
| http://localhost:8000/admin/    | Django admin                 |
| http://localhost:8000/healthz   | Database and Redis liveness  |

Postgres is optional in development: leave `DATABASE_URL` unset and Django falls
back to SQLite. Redis being down degrades the health check but does not fail
writes — real-time delivery is best-effort by design.

## Reproducing "only happens on hosted" bugs

The fast loop above (`ng serve` + SQLite + `config.settings.dev`) is a
genuinely different stack from Render: Render runs the production Angular
build, `config.settings.prod` (`DEBUG=False`, strict CORS), and real Postgres
+ Redis, all served from one origin by Django/whitenoise. Bugs that only show
up once deployed are usually one of those differences, not the feature code.
Two ways to get parity locally, from closest to least setup:

**Docker — the literal image Render deploys**

```bash
docker compose --profile parity up --build
```

Builds the same `Dockerfile`, runs `config.settings.prod` against the
Postgres/Redis containers above, and serves on http://localhost:8000 (no
`:8100`). Requires Docker Desktop or Colima.

**No Docker — same settings module and production bundle, SQLite underneath**

```bash
docker compose up -d postgres redis   # optional: adds real Postgres too
export DATABASE_URL=postgres://fairmeasure:fairmeasure@localhost:5432/fairmeasure
export REDIS_URL=redis://localhost:6379/0
./scripts/dev-parity.sh
```

Builds the production frontend bundle and runs Django on
`config.settings.prod`, single-origin, on http://localhost:8000. Skip the
`export` lines to fall back to SQLite — still catches build/settings drift,
just not Postgres-only behavior (e.g. a delete that only fails under real FK
constraints).

Render runs **one** service: there is no Node worker or Socket.io gateway
there. With `RENDER` set, prod settings turn on `JOBS_INLINE` (Django runs
queued jobs such as standings, notifications and demo expiry on a small thread
pool) and `REALTIME_POLLING` (the app polls `GET /api/v1/realtime/events`
instead of opening a socket). `dev-parity.sh` and the compose `web` service
switch both on too. If you add a worker and gateway on Render later, set both
to `false` and give the build a `FRONTEND_REALTIME_URL`.

**Run the backend tests on Postgres before pushing**

```bash
brew install postgresql@16 && brew services start postgresql@16   # once
cd backend && TEST_DATABASE_URL=postgres://$USER@localhost:5432/fairmeasure pytest
```

SQLite ignores column lengths and runs one write at a time, so it hides errors
Postgres raises in production (text too long, deadlocks). Local SQLite does
sort blanks last like Postgres (`config/db/sqlite_pglike`).

## The domain

A **Competition** owns everything else and is the unit of permission. Membership
carries one of four roles: owner, admin, scorer, member.

**Scoring is data, not code.** A competition has `ScoringCategory` rows — a try
worth 5, a conversion worth 2, a yellow card worth 0 that doesn't affect the
score. Recording a `ScoreEvent` sums into `FixtureSide.score`, so the same engine
handles rugby, tennis, and a chore chart with no branching.

**Points are a policy.** `PointsPolicy` holds win/draw/loss points, optional
bonus thresholds (rugby's four-try and losing bonuses), whether draws are
allowed, and an ordered `tiebreakers` list. `apps/standings/services.py` reads
that policy to build the table, so changing the policy changes the league.

Presets in `apps/competitions/presets.py` fill this in for sports, KPIs, a
cleaning rota, or a blank custom contest. They are a starting point that writes
ordinary rows — nothing downstream knows a preset was used. A user can run
several competitions from My leagues, each with its own scoring.

**Fixtures** are generated by the circle method for round robins (with a bye slot
for odd entrant counts) or seeded brackets for knockouts, then spread across the
competition's match weekdays.

## Tests

```bash
cd backend && pytest
```

41 tests covering the parts most likely to be wrong: score summation and outcome
resolution, the standings engine (bonus points, each tie-breaker, form), role
permissions, and the Redis envelopes the Node service depends on.

Those run without Redis or the Node service. To check the wiring between all
three, with everything running and the demo data seeded:

```bash
cd realtime && npm run smoke
```

It signs in over REST, opens a socket, joins the competition and fixture rooms,
records a score through the API, and fails if the broadcast does not come back.

## Integrations

Each of these is behind an adapter and inert until configured, so a fresh clone
runs without any third-party accounts.

**Object storage** (`STORAGE_PROVIDER=r2|s3`) — clients ask for a presigned URL
and upload directly to Cloudflare R2 or S3. Large files never proxy through
Django. For local work, `docker compose --profile storage up -d` starts MinIO;
point `STORAGE_ENDPOINT_URL` at `http://localhost:9000`.

**Video** (`VIDEO_PROVIDER=cloudflare_stream|mux`) — creators upload straight to
the provider, which calls back to `/api/v1/media/webhook/<provider>` when
transcoding finishes. Assets sit in `processing` until then, and the feed shows a
placeholder.

**Push** — Django holds the FCM credentials and is the only thing that calls the
send API. Native clients register through Capacitor; browsers use the Firebase JS
SDK with `src/firebase-messaging-sw.js`. Fill in `environment.firebase` to enable
web push.

**Search** — `SEARCH_ENABLED=false` by default, in which case search falls back
to Postgres `ILIKE` queries. Set it true with Meilisearch running
(`docker compose --profile search up -d`) to use the index instead.

**Auth** — email/password and Google Sign-In, both issuing DRF SimpleJWT tokens.
Google ID tokens are verified against Google's JWKS. The realtime service
verifies the same access tokens with the shared `JWT_SIGNING_KEY`, so a socket
cannot outlive its session.

## Layout

```
backend/
  config/settings/     base, dev, prod, test
  apps/
    accounts/          custom user, JWT, Google OAuth
    competitions/      competitions, membership, scoring config, presets
    fixtures/          fixtures, sides, score events, schedule generation
    standings/         the league table engine
    social/            posts, comments, reactions
    media_assets/      storage and video adapters
    notifications/     FCM devices, preferences, in-app records
    search/            Meilisearch with a Postgres fallback
    core/              base models, Redis bus, permissions, internal API
  tests/
realtime/src/
  index.ts             Socket.io gateway, auth, room subscriptions
  bridge.ts            drains Django's Redis job inbox into BullMQ
  worker.ts            queue consumers
  handlers.ts          each job's call back into Django
frontend/src/app/
  core/                auth, API client, realtime, uploads, push
  pages/               login, competitions, fixtures, discover, profile
  shared/              post card, composer, competition card
```

## Notes for production

- Set `DJANGO_SETTINGS_MODULE=config.settings.prod`, and give
  `DJANGO_SECRET_KEY`, `JWT_SIGNING_KEY`, and `INTERNAL_API_TOKEN` distinct long
  random values.
- `/internal/` must not be reachable from the internet. It trusts a bearer token
  and is meant for the worker process only.
- Serve Django under ASGI (`config.asgi`) if you add streaming endpoints;
  the WSGI entry point is fine for the current REST surface.
- Standings are recomputed by a worker rather than on the request path, so the
  table can trail a final whistle by a moment. Clients listen for
  `standings.updated` and refetch.
