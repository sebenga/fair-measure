# Matchday flows (Soccer & Rugby)

Fair Measure runs locked **Football (Soccer)** and **Rugby union** end to end without manual DB edits. Scores are always derived from events (`ScoreEvent` / `MatchEvent` alias). Full-time auto-confirms in Phase 1; Phase 2 adds explicit referee match-card sign-off to `confirmed`.

## Create → table

1. **Create** competition from the soccer or rugby_union preset (locked scoring, halves, league points, rugby bonus points).
2. **Teams & squads** — team sheet minima from the preset (soccer 11+bench / min 14; rugby 1–15 + 16–23 / min 17). Custom boards no longer invent a “14 players” minimum.
3. **Fixtures** — generate round robin / knockout. Results sports cannot invent a fixture via score-assist.
4. **Appoint referee** — admin invites a user with a Referee profile path; official **accepts**. Kickoff blocked until an **accepted** referee exists (or admin stand-in, audited).
5. **Line-ups** — submit team sheets; then kick off.
6. **Live** — only the accepted referee (or delegated AR/4th/TMO) records events / clock. Admins get **403** live. Watch PWA: `/ref/watch/:matchId` with pair code + offline IndexedDB sync (`source=watch`).
7. **Full time** — status `completed` with `confirmed_at` (auto) or `POST …/confirm` → `confirmed`. Standings update for counted fixtures.
8. **Dispute** — members may dispute within `dispute_window_hours` (default 24); admin resolves with audit trail.
9. **Season finish** — when every scheduled fixture is signed off (or admin closes early with reason). Synthetic score-assist rows alone never finish a results season.
10. **Scouting / AI** — optional AI suggestions (`source=ai_camera`) after human accept; cards never auto-apply. See `docs/AI_CAMERA.md`.

## How points work

- **Match score** — goals / tries / kicks from events.
- **League points** — win/draw/loss from the preset (soccer 3/1/0; rugby union 4/2/0) plus configurable `table_bonus` (e.g. 4+ tries, lose by ≤7).
- UI notes on standings and the match centre separate the two.

## Realtime

Match channel `match:{id}` / competition rooms carry score and fixture updates. Enrich with `event_added`, `period_change`, `sin_bin_tick` as the Node service evolves. Push for goals/tries/FT remains opt-in.

## Docs

| Doc | Purpose |
| --- | --- |
| `docs/AUDIT_MATCHDAY.md` | Phase 0 gaps checklist |
| `docs/AI_CAMERA.md` | Vision pipeline & privacy |
| `watch/README.md` | Watch PWA + native plan |
