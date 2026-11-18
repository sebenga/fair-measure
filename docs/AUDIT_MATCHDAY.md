# Matchday audit — Soccer & Rugby (Phase 0)

Audit of the Fair Measure v2 monorepo as of this document. No code was changed for Phase 0. Later phases should close every item below.

## Current stack (what exists today)

| Layer | Reality |
| --- | --- |
| Competition presets | `backend/apps/competitions/presets.py`, `catalog.py`, `soccer_presets.py`, `rugby_presets.py`. Soccer and Rugby Union (fifteens) are `locked=True` with IFAB / World Rugby-aligned scoring categories, half lengths, and league points. |
| “Match” model | There is **no** `Match` / `MatchEvent` model. Live games are `Fixture` + append-only `ScoreEvent` (category/quantity/minute/period/player). Score is recalculated from events via `Fixture.recalculate_scores()`. |
| Lifecycle | Fixture statuses: `scheduled` → `live` → `completed` (also postponed/cancelled/forfeit). Clock **phase** string covers halves / ET / etc. Missing: `lineups_submitted`, `ready`, `full_time`, `confirmed`, `disputed`. |
| Officials | `FixtureReferee` = user allowed to score that fixture. Kickoff blocked if none (`Fixture.kickoff_problems`). No appointment accept/decline, no `RefereeProfile`, no role split (AR1/AR2/4th/TMO), no match card sign-off → `confirmed`. |
| Standings | `apps/standings/services.py`. Win/draw/loss from `PointsPolicy` / preset `league_points`. Rugby union preset already ships `table_bonus` (4+ tries, lose by ≤7). Soccer tiebreakers: points → GD → GF → H2H. |
| Realtime | Node service exists for live match channels; **no** referee/watch auth checks tied to appointed officials. |
| Watch / AI | No `/ref/watch/:matchId` PWA, no device tokens, no `AiEventSuggestion`, no vision worker / object storage pipeline. |
| Fantasy | Backend `apps/fantasy` + competition Fantasy tab gated by `showsFantasy()` and `releases.isOpen('fantasy')`. Soccer demo seeds fantasy squads. |

---

## End-to-end flow map (Soccer / Rugby Union)

| Step | Soccer today | Rugby Union today | Gap |
| --- | --- | --- | --- |
| 1. Create competition | Preset `soccer` / family Football; locked scoring | Preset `rugby_union`; locked scoring + bonus | Naming inconsistency (see known issues). Presets not fully “locked” against admin edits of categories in all UI paths. |
| 2. Teams | Participants + rosters | Same; rugby sheet 1–15 / 16–23 | OK for locked sports |
| 3. Squads / players | Team sheet min 14 (11+subs guidance) | min_squad 17, bench 8 | Custom comps still default to **14** (bug) |
| 4. Fixtures | Round-robin / knockout generators | Same + rugby draw resolution path | Can score without a real scheduled league fixture via criteria/`award_criterion` synthetic fixtures |
| 5. Match kickoff | Needs duration + ≥1 `FixtureReferee` + team sheet | Same + rugby numbers | No appointment workflow; admin can be “referee”; no accept step |
| 6. Score entry | Match day / fixture detail → `ScoreEvent` | Same + sin-bin / upgraded yellow | Admins/scorers can record live; not referee-only. No rich event taxonomy (assist, tackle, HIA, metres…). Score not exclusively referee-sourced |
| 7. Standings | 3/1/0 + GD/GF/H2H | 4/2/0 + try & losing bonus in preset | UI does not clearly separate **match score** vs **league points** on match centre / league for results sports |
| 8. Cup / knockout | ET + penalties on soccer structure | ET → sudden death → kicking | Penalties as structured events incomplete vs prompt; rugby kicking competition thin |
| 9. Season finish | `maybe_finish_competition` when no OPEN fixtures left and ≥1 counted result | Same | Finishes on `completed`/`forfeit`, **not** referee-confirmed. One synthetic result with no schedule finishes the season |
| 10. Player stats / profile | Appearances, ratings, score events aggregation | Same | Not full `MatchEvent` taxonomy; no AI verification badges |
| 11. Scouting | League squad / candidates / scouts under `/api/v1/scouting/leagues/...` | Sport catalogue keyed by sport | “Amend league squad” often → **League unavailable** (see below) |
| 12. Fantasy | Seeded in soccer demo; tab if release on | N/A for non-team/criteria | Demo claims fantasy; tab can be missing when release off or `showsFantasy` false |

---

## Known issues (confirmed)

### 1. Scouting — “Amend league squad” → “League unavailable” / API 404

- Setup button (`competition-setup.page.ts` → `openSquad()`) navigates to `/tabs/competitions/:id/squad`, which loads `LeagueSquadPage`.
- Page calls `GET /api/v1/scouting/leagues/:id/squad` (and `/scouts`, `/candidates`).
- Backend `_league()` returns the competition only if the user is an **admin+ of a visible competition**, or the league is in `scouting_leagues()` (open to scouts + scout access). Otherwise **404** `No competition found.` or **403** if visible but not open.
- UI maps any error to the empty state title **“League unavailable”** (`league-squad.page.ts`).
- Amend is offered even when the competition is not yet a usable scouting league (button sits outside the `open_to_scouts` block), so owners hit a dead end.
- Endpoints are mounted correctly under `api/v1/`; a bare 404 is usually authorization/visibility, not a missing route — but the product symptom matches the reported bug.

**Fix direction (later phases):** Gate Amend on scouting readiness; return actionable errors; ensure opening to scouts creates/selects a squad; never show the button when the API will 404.

### 2. Fantasy — demo claims it; tab often missing

- Demo guide welcome copy: *“…officials, line-ups, ratings and a fantasy game…”* and auto-runs feed post/like/comment.
- Fantasy tab only renders when `showsFantasy(competition) && releases.isOpen('fantasy')` (`competition-detail.page.ts`).
- Platform can disable the `fantasy` release; frontend default is open but production DB may have it closed.
- No standalone Fantasy entry in primary tabs — only inside a competition.

**Fix direction:** Keep tab visible for soccer demos when fantasy was seeded, or stop claiming fantasy in demo copy until the release + tab are reliably on.

### 3. Soccer naming — search “Soccer” vs “Football (11-a-side)” vs “Tap Soccer again”

- Preset `label`: **"Soccer"**; `family_label`: **"Football"**; `variant_label`: **"11-a-side"** (`presets.py` / soccer family cards).
- Create UI family card shows family label (**Football**) + caption (**11-a-side**). Focus hint uses `activePreset()?.label` → **“Tap Soccer again”**.
- Sport search matches `label`, `sport`, `family_label`, `variant_label` — so “Soccer” finds the Football card, which looks inconsistent.

**Fix direction:** Display label **“Football (Soccer)”** (or equivalent), search tokens for soccer **and** football, align hint with the visible card label.

### 4. Scores without a fixture / season finishes after one result

- Results sports should score only against scheduled fixtures. Criteria boards legitimately call `award_criterion` / `award_criterion_round`, which **create synthetic completed fixtures**.
- `season_is_finished()` (`season.py`): if there is ≥1 counted fixture and **zero** OPEN (`scheduled`/`live`/`postponed`) fixtures → mark competition **COMPLETED**.
- Therefore: no generated schedule + one recorded score ⇒ season finishes immediately.
- There is no `confirmed` gate; completing a live match updates standings without a signed match card.

**Fix direction:** Require a pre-existing scheduled fixture for results sports; finish season only when all fixtures are **confirmed** (or admin closes with reason).

### 5. Goal / try points vs league points unexplained in UI

- Setup/create and points-table standings have “How points are earned” for **criteria** boards.
- Match centre / league standings for soccer/rugby do **not** show a short note separating **match score** (goals/tries) from **table points** (3/1/0 or 4/2/0 + bonuses).

**Fix direction:** Add “How points work” on match centre and league standings for results sports.

### 6. “14 players per team” on custom / non-sport competitions

- `squadSizeOf()` (`models.ts`): if no `min_squad` / starters &lt; 11 → **defaults to 14**.
- Setup / team profile copy always uses `squadSize()` with that default.

**Fix direction:** Only apply sport team-sheet minima; custom/individual comps should not show “14 players”.

### 7. Tour auto post / like / comment without consent

- `DemoGuideService` feed step `actions` type into the composer, click Post, like, open comments, type and submit — **performed automatically** while the user watches (“I will do the clicks myself”).
- No consent prompt before creating social content as the guest/demo user.

**Fix direction:** Require explicit user tap for each social action, or ask consent before the coach automates feed writes.

---

## Broader gaps vs product brief (Phases 1–5)

### Match model & events (Phase 1)

- Need append-only **MatchEvent** (or evolve `ScoreEvent`) with clock mm:ss, period, team, player, secondary_player, `source` (`referee` \| `watch` \| `assistant` \| `ai_camera` \| `admin_correction`), confidence, `created_by`, `supersedes_event_id`.
- Soccer/rugby event taxonomies (assists, shots, HIA, metres, line-out/scrum, etc.) largely absent as first-class types.
- Lineup enforcement: soccer 11+5 / rugby 15+8 defaults exist in sheets but not as hard live-match guards everywhere.
- E2E automated season tests (4-team double RR soccer; rugby pool + knockout with bonus/sin-bin/discipline/player stats) incomplete vs acceptance criteria.
- Preset lock: prevent mutating official score types / league points for locked soccer & rugby union.

### Appointed referee (Phase 2)

- No `RefereeProfile`, appointment accept/decline, delegation to AR/4th/TMO, digital match card sign-off, 24h dispute window, or full audit log (who/when/device/source).
- Live event recording not restricted server-side to appointed referee/delegates (admins/scorers can edit live).
- No Referee dashboard (upcoming / accept / today’s matches / reports to sign).

### Smartwatch ref mode (Phase 3)

- No watch PWA route, pairing QR/6-digit match-scoped token, IndexedDB offline queue, Wake Lock, or Vibration half/sin-bin cues.
- No `/watch/README.md` or Wear OS / watchOS scaffolds.

### AI camera (Phase 4)

- No Record match UI, chunked upload to S3-compatible storage, worker + queue, `VisionProvider`, `AiEventSuggestion`, review timeline, accuracy metrics, or POPIA minor/consent gates for recording.
- Feature must stay off by default; Render has no GPUs — external inference required.

### Realtime, polish, deploy (Phase 5)

- Enrich `match:{id}` events (clock, score, event_added/corrected, period_change, sin_bin_tick) + opt-in push for goals/tries/FT.
- Fix all Phase 0 items; register new Ionic icons in `addIcons`.
- `render.yaml`: AI worker, Key Value, storage/AI env vars (Frankfurt only); migrations in pre-deploy.
- Docs still to write in later phases: `docs/MATCHDAY.md`, `docs/AI_CAMERA.md`, `/watch/README.md`.

---

## Reuse map (do not duplicate)

| Concern | Reuse |
| --- | --- |
| Presets / locked rules | `presets.py`, `catalog.py` (soccer, `rugby_union`), `soccer_presets.py`, `rugby_presets.py` |
| Fixtures & scoring | `Fixture`, `ScoreEvent`, `FixtureLineup`, `FixtureReferee`, `matchday.py`, `phases.py` |
| Standings & bonuses | `standings/services.py` (`table_bonus`, H2H, category try tiebreak) |
| Season close | `competitions/season.py` — extend, don’t replace |
| Match UI | `match-day.component.ts`, `fixture-detail.page.ts`, competition fixtures/standings tabs |
| Scouting | `apps/scouting` league squad/candidates/scouts APIs + `league-squad.page.ts` |
| Realtime | Existing Node realtime match rooms — add authz + event types |
| Icons | `app.component.ts` `addIcons` |

---

## Phase 0 exit criteria

- [x] Soccer & rugby flows traced create → scouting
- [x] Known issues confirmed with file-level evidence
- [x] Gaps for MatchEvent / referee / watch / AI / Render listed
- [x] Phases 1–5 close items — see `docs/MATCHDAY.md`, `docs/AI_CAMERA.md`, `watch/README.md`

### Resolution notes (Phases 1–5)

| Issue | Status |
| --- | --- |
| Amend league squad / 404 | Button gated on `open_to_scouts`; API still requires admin or open scouting league |
| Fantasy claim without tab | Demo/create copy no longer promises Fantasy unless the release is on |
| Soccer naming | Preset label **Football (Soccer)** |
| Score without fixture / early finish | Results sports need scheduled fixtures; finish waits for confirmation |
| Match vs league points | “How points work” on standings / match centre |
| 14-player custom | `squadSizeOf` no longer defaults custom comps to 14 |
| Tour auto social | Demo guide points only; no auto post/like/comment |
| AI / watch / officials | Scaffolded per phase commits |
