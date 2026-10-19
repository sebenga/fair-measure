# System review

Reviewed against the competition-type notes and a pass over the API, the scoring engine, the realtime bridge, and the Ionic app. Each item says how serious it is, where it lives, whether this change set fixes it, and what to do next.

Severity: **critical** (wrong results or a lock that does not hold), **high** (privacy or a broken competition path), **medium** (a rule the engine still simplifies), **low** (wording, unused data, or a later improvement).

## Competition engine

| Finding | Severity | Location | Status | Next step |
|---|---|---|---|---|
| Admins could unlock a locked preset by setting `lock_when_started`, or return a started KPI or cleaning competition to draft and edit scoring again. Rules text and the settings that drive scoring stayed writable. | critical | `backend/apps/competitions/presets.py` (`scoring_is_locked`), `serializers.py`, `views.py` `RuleViewSet` | Fixed | A permanently locked preset stays locked. A start-lock sets `scoring_sealed` when status leaves draft and does not clear it. Protected settings and rules return 403 while locked. Custom stays editable. |
| Knockout byes were created after the real matches, so advancing paired the wrong winners and a seeded bye did not meet the opposite half. | critical | `backend/apps/fixtures/services.py` `generate_knockout`, `competitions/views.py` `advance` | Fixed | First-round fixtures are created in bracket order, including bye placeholders. Seeds 1 and 2 in a six-player bracket meet the winners of the opposite half. |
| Golf stroke play ranked 0-stroke and short cards above a finished round. | critical | `backend/apps/standings/services.py` accumulation sort | Fixed | Lowest-first tables rank a more complete card first, then the lower total. An unplayed entrant sits last. Countback is still hole by hole, which matches this preset's description. The R&A 9/6/3/1 countback is not applied. |
| Bowling strike and spare bonuses used the next balls in the whole fixture, including the opponent, and tenth-frame bonus balls were added twice. | critical | `backend/apps/competitions/engine.py` `split_scores`, bowling preset in `catalog.py` | Fixed | Bonuses use the same side's later balls. A fill ball can supply a bonus and is not added to the total. A perfect game of 12 balls scores 300. |
| The "draws possible" checkbox wrote `PointsPolicy.allow_draws` and the engine ignored it. | high | `engine.py` `draws_are_allowed`, `PointsPolicyView` | Fixed | The engine refuses a draw when the policy or the preset says so. Saving the checkbox also writes `settings_json.draw_allowed`. Knockouts still require a winner. |
| `draw_resolution` is stored and was never read. Soccer penalties and extra time already lived on the match structure. | medium | `engine.py`, chess preset | Partially fixed | A level decider slot can name `tied_winner` (`home` or `away`). Chess Armageddon uses `away`, so a drawn Armageddon goes to Black. An unplayed decider stays pending. The `draw_resolution` string itself is still a label, not a second switch. |
| `formats_allowed` was enforced only on the create screen. `groups_knockout` and `ladder` were offered with no fixture generator. | high | `presets.py` `format_allowed`, `serializers.py`, `fixtures/views.py` `generate`, `competition-create.page.ts` | Fixed by hiding | Create, update, and fixture generation reject a format the preset does not allow. Groups-then-knockout and ladder are removed from preset lists and from the create screen. A competition whose format is already one of those two cannot generate a list. The generators are not built. |
| American football used 2/1/0 and baseball used 1/0/0. | high | `catalog.py` | Fixed | Both use 3 for a win, 1 for a draw, and 0 for a loss. Baseball still plays extra innings rather than leaving a league game drawn. |
| Darts accepted a visit that finished on any score, including a visit over 180, so double-out was not required. | medium | darts preset, `engine.py` remaining-score check | Fixed | A leg ends only on a checkout. A visit above 180 is ignored. Leaving 1, or going below 0, is still a bust. |
| Snooker fouls were fixed at 4 times a quantity, so 5, 6, and 7 could not be entered. | medium | snooker preset, `engine.py` quantity bounds | Fixed | A foul is entered as 4, 5, 6, or 7 and is given to the opponent. Values outside that range are ignored. |
| Volleyball repeated the label "set 1" for the fifth set, and every win was 3 points. | medium | `engine.py` `expand_units`, `fixture-detail.page.ts` `units()`, volleyball `unit_result_points` | Fixed | Set numbers run 1 to 5. League points follow the set score: 3 for 3-0 or 3-1, 2 for a 3-2 win, 1 for a 3-2 loss, 0 otherwise. |
| Cricket net run rate used the balls actually faced when a side was bowled out. | medium | `standings/services.py` `_attach_rate`, cricket `rate_basis` | Fixed | Ten wickets before 120 balls counts as 120 balls faced. A match that is not all out is unchanged. |
| A drawn chess Armageddon game stayed pending. | medium | chess preset, `engine.py` `_sequential_decider` | Fixed | See the decider note above. Black is the away side. |
| Archery tie-break counted bare 10s and then Xs, so an X lost to a 10. The test expected that order. | medium | archery preset, `standings/services.py` category tie-break | Fixed | The first tie-break is 10s including Xs (`category:ring-10,x`), then Xs. The test now expects the archer with the X to rank first when the totals and the 10-counts are level. |
| Quick "record result" wrote one point and left set, leg, and race contests undecided. | high | `fixtures/services.py` `record_result` | Fixed | A head-to-head total still records one scoring event. A sets contest records enough winning units. A countdown records a checkout of the starting total for the required legs. A first-to-target contest records the target. |
| Preset rules were saved and never shown. | medium | `competition-detail.page.ts` | Fixed | The competition page lists each rule name and description under the scoring summary, and says when official scoring is fixed. |
| The create screen told every points preset, including golf, that ranking was highest first. | low | `competition-create.page.ts` `lockedStructureHint` | Fixed | The hint follows `accumulation_ranking`. |
| `MatchUnit` rows are copied from the preset and the engine reads `settings_json.match_structure` instead. | low | `presets.py` `apply_preset`, `engine.py` | Not fixed | Keep one source. Either stop writing `MatchUnit` or teach the engine to read those rows. |
| Golf countback is last hole backwards, not the R&A last 9, 6, 3, then 1. Stableford already uses those windows. | low | golf stroke preset, `standings/services.py` | Not fixed | Add `countback_windows` to stroke play if the competition should follow Committee Procedures 5A. |
| Rugby union does not award try or losing bonus points. | low | rugby preset, `_policy` | Not fixed | The 3/1/0 table is the house rule. Bonus columns can be added as preset data later. |
| Rugby league golden-point extra time has no minutes. | low | rugby league preset | Not fixed | Set the extra-time length if the clock should show it. |
| American football overtime is 10 minutes. | low | american football preset | Not fixed | Playoff periods of 15 minutes would be a separate structure if a competition needs them. |
| Netball extra time may not match the current World Netball "lead by two" rule. | low | netball preset | Not fixed | Check the current rulebook before changing the decider. |
| Tennis, padel, and backgammon model the unit score (games, points, or match points), not every sub-point or the doubling cube's named steps. | low | those presets | Not fixed | The quick result and the unit score are enough to rank a match. Finer scoring can be more score types. |
| Quiz "nearest" treats a missing guess like a perfect one, and the joker is not limited. | low | quiz preset, engine best-aggregate | Not fixed | Give a missing guess a worse-than-any distance, and cap the joker in the preset. |
| Yahtzee's upper-section bonus only fires inside one fixture. | low | yahtzee preset `bonuses` | Not fixed | Decide whether the bonus is per game (current) or across a series. |
| Athletics next-attempt tie-break uses the competition's performance direction. A mixed meet can rank a field event the wrong way. | low | `standings/services.py` `_attempt_sort` | Not fixed | Store the direction on the attempt, which the event already can, and sort each fixture with that direction only. |
| Scrabble knockout replay leaves the fixture pending. | low | scrabble `draw_resolution: replay` | Not fixed | Pending is the honest result until someone schedules the replay. |

## API, privacy, and reliability

| Finding | Severity | Location | Status | Next step |
|---|---|---|---|---|
| Discover listed draft and private competitions. | high | `competitions/views.py` queryset, `discover.page.ts` | Fixed | `discover=1` returns public competitions that are active or completed. |
| Search could return a private or draft competition, or a side from one, when the index lagged. | high | `search/services.py` `only_public_hits`, Postgres fallback | Fixed | Hits are checked against the database. The fallback uses the same public, active-or-completed filter. |
| Membership lists showed every member's email. | high | `MembershipSerializer` | Fixed | A member sees their own email. An admin sees the list. |
| Login, register, Google sign-in, and token refresh had no rate limit. | medium | `accounts/views.py`, `core/throttling.py` | Fixed | Those views use a 20-per-minute limit and stay open if the cache is down, so a Redis outage does not block sign-in. |
| Standings loaded fixture sides and events one query at a time, and the competition list looked up the caller's role per row. | medium | `standings/services.py`, `competitions/views.py` | Fixed | Fixtures prefetch sides and events. The list prefetches the caller's membership. |
| Refresh tokens are not blacklisted after rotation. | medium | `config/settings/base.py` `BLACKLIST_AFTER_ROTATION` | Not fixed | Install the blacklist app and turn rotation blacklisting on before a public deploy. |
| Access and refresh tokens are kept in `localStorage`. | medium | `frontend/src/app/core/auth.service.ts` | Not fixed | Move the refresh token to a cookie the browser will not hand to script. |
| Profile ID numbers are stored and returned as plain text. | medium | `accounts/models.py` `id_number`, profile API | Not fixed | Store a hash or encrypt the value, and stop returning it on unrelated user payloads. |
| The development secret key is the insecure default until production settings reject it. | medium | `config/settings/base.py`, `prod.py` | Not fixed | Production already fails closed on the default. Keep secrets out of the repo. |
| The internal realtime API trusts `INTERNAL_API_TOKEN`. An empty token in development accepts nothing useful, but a shared network can call it if the token leaks. | medium | `core/internal.py` | Not fixed | Keep the token long and the internal routes off the public internet. |
| If Redis is down, live events and standings jobs are dropped. Writes still succeed. | medium | `core/bus.py` | Not fixed | Surface a failed publish to the scorer, and recompute standings in the request when the queue is down. |
| Per-fixture duration can still be edited on a locked preset. The competition time limit cannot. | low | fixture serializers | Not fixed | Treat the competition clock as the source, which the preset already sets. |

## Frontend

| Finding | Severity | Location | Status | Next step |
|---|---|---|---|---|
| `takeUntilDestroyed()` inside `ngOnInit` without an injection context threw NG0203 on the competition page. | high | `competition-detail.page.ts` | Fixed | The page takes a `DestroyRef` from the constructor context. Discover does the same. |
| The old Scrabble icon name `text-outline` rendered blank when a cached preset still used it. | low | `app.component.ts` | Fixed | `textOutline` is registered. New presets use `extension-puzzle-outline`. |
| The lock flag on the client checked `lock_when_started` before `scoring_locked`, so a tampered settings object looked editable. | high | `models.ts` `isScoringLocked` | Fixed | A sealed or `scoring_locked` competition stays read-only. Start-lock competitions are read-only after they leave draft. |
| Setup still offered time-limit edits on a locked preset. | medium | `competition-setup.page.ts` | Fixed | The time-limit fields are read-only and the save action is hidden while scoring is locked. |
| The quick score screen offered a draw when the preset or the checkbox forbids one. | medium | `competition-score.page.ts` | Fixed | The draw choice is hidden unless draws are allowed. |

## Realtime

The Node gateway authenticates the socket with the same JWT and asks Django which rooms the user may join. Smoke (`cd realtime && npm run smoke`) needs the API, Redis, and the gateway running. It was not run in this environment.

## What this change set does not claim

The engine still does not branch on a sport's name. New behaviour is preset data: quantity bounds, a checkout role, a fill role, a tied decider, unit-result points, and an all-out rate quota. Groups-then-knockout and ladder remain unimplemented and are no longer offered.
