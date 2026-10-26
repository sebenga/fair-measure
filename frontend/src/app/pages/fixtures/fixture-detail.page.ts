import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnDestroy,
  OnInit,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import {
  ActionSheetController,
  AlertController,
  IonBackButton,
  IonButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonLabel,
  IonSegment,
  IonSegmentButton,
  IonTitle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';

import { ApiService } from '../../core/api.service';
import { isCupFixture } from '../competitions/tabs/cup';
import { AuthService } from '../../core/auth.service';
import { extractErrorMessage } from '../../core/error-message';
import type {
  CompetitionDetail,
  FixtureDetail,
  FixtureSide,
  ProfileSummary,
  RosterMember,
  ScoreEvent,
  ScoringCategory,
} from '../../core/models';
import { RealtimeService, fixtureRoom } from '../../core/realtime.service';
import { MatchAwardsComponent } from './match-awards.component';
import { FixtureOverviewComponent } from './fixture-overview.component';
import { FixtureTimelineComponent } from './fixture-timeline.component';
import { MatchDayComponent } from './match-day.component';
import { MatchRatersComponent } from './match-raters.component';
import { ScrabbleScorerComponent } from './scrabble-scorer.component';

type FixtureTab = 'overview' | 'lineups' | 'live' | 'stats' | 'raters' | 'setup';
const FIXTURE_TABS: FixtureTab[] = ['overview', 'lineups', 'live', 'stats', 'raters', 'setup'];

interface Celebration {
  title: string;
  pieces: Array<{ dx: number; dy: number; rot: number; delay: number; color: string }>;
}

@Component({
  selector: 'fm-fixture-detail',
  standalone: true,
  imports: [
    DatePipe,
    MatchAwardsComponent,
    MatchDayComponent,
    MatchRatersComponent,
    ScrabbleScorerComponent,
    FixtureOverviewComponent,
    FixtureTimelineComponent,
    IonSegment,
    IonSegmentButton,
    IonLabel,
    IonHeader,
    IonToolbar,
    IonTitle,
    IonButtons,
    IonBackButton,
    IonButton,
    IonIcon,
    IonContent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start">
          <ion-back-button [defaultHref]="backHref()" />
        </ion-buttons>
        <ion-title>{{ fixture()?.label || 'Fixture' }}</ion-title>
        <ion-buttons slot="end">
          @if (canScore()) {
            <ion-button (click)="openStatusSheet()">
              <ion-icon slot="icon-only" name="ellipsis-horizontal" aria-label="Fixture status" />
            </ion-button>
          }
        </ion-buttons>
      </ion-toolbar>
      @if (fixture()) {
        <ion-toolbar>
          <ion-segment [value]="tab()" [scrollable]="true">
            @for (item of tabs(); track item.key) {
              <ion-segment-button [value]="item.key" (click)="selectTab(item.key)">
                <ion-label>
                  {{ item.label }}
                  @if (item.key === 'live' && fixture()?.status === 'live') {
                    <span class="tab-live" aria-label="Match is live"></span>
                  }
                </ion-label>
              </ion-segment-button>
            }
          </ion-segment>
        </ion-toolbar>
      }
    </ion-header>

    @if (celebration(); as moment) {
      <div class="fm-celebrate" aria-live="polite">
        <div class="fm-celebrate-banner">{{ moment.title }}</div>
        @for (piece of moment.pieces; track $index) {
          <span
            class="fm-confetti"
            [style.--dx]="piece.dx + 'px'"
            [style.--dy]="piece.dy + 'px'"
            [style.--rot]="piece.rot + 'deg'"
            [style.--delay]="piece.delay + 'ms'"
            [style.background]="piece.color"
          ></span>
        }
      </div>
    }

    <ion-content fullscreen="true">
      @if (loading()) {
        <div class="skeleton-board" aria-busy="true" aria-label="Loading the match">
          <span class="fm-skeleton" style="width: 40%; height: 14px"></span>
          <span class="fm-skeleton" style="height: 34px"></span>
          <span class="fm-skeleton" style="height: 34px"></span>
        </div>
      } @else if (error()) {
        <div class="fm-empty">
          <ion-icon name="alert-circle-outline" aria-hidden="true" />
          <h3>Could not load this fixture</h3>
          <p>{{ error() }}</p>
          <ion-button fill="clear" (click)="load()">Try again</ion-button>
        </div>
      } @else if (fixture(); as fx) {
        <section class="scoreboard fm-enter" [class.live]="fx.status === 'live'">
          <div class="status">
            @if (fx.status === 'live') {
              <span class="fm-live">Live</span>
            } @else {
              <span class="chip">{{ statusLabel(fx.status) }}</span>
            }
            @if (fx.scheduled_at) {
              <span class="kickoff">{{ fx.scheduled_at | date: 'EEE d MMM, HH:mm' }}</span>
            }
            @if (fx.location) {
              <span class="kickoff">{{ fx.location }}</span>
            }
            @if (showClock()) {
              <div class="match-clock">
                <span class="readout">{{ clockLabel() }}</span>
                <span class="chip">{{ periodLabel() }}</span>
                @if (canScore()) {
                  <button type="button" [disabled]="kickoffBlocked() || !canToggleClock()" (click)="startOrPause()">
                    {{ clockButtonLabel() }}
                  </button>
                  @if (canEndHalf()) {
                    <button type="button" class="end-game" (click)="endHalf()">End half</button>
                  }
                  @if (canEndGame()) {
                    <button type="button" class="end-game" (click)="endGame()">End game</button>
                  }
                }
              </div>
            }
            <span class="kickoff">{{ gameTimeLabel() }}</span>
          </div>

          @if (kickoffBlocked()) {
            <ul class="kickoff-problems">
              @for (problem of fx.kickoff_problems; track problem) {
                <li>{{ problem }}</li>
              }
            </ul>
          }

          <div class="line">
            @for (side of fx.sides; track side.id) {
              <div class="team" [class.winner]="side.outcome === 'win'">
                <span class="name">{{ side.participant.name }}</span>
                <span class="score" [class.fm-bump]="bumped().has(side.id)">{{ trim(side.score) }}</span>
                @if (side.forfeited) {
                  <span class="ff">forfeit</span>
                }
                @if (headStart(side); as start) {
                  <span class="ff">incl. {{ start }} handicap {{ start === '1' ? 'goal' : 'goals' }}</span>
                }
              </div>
            }
          </div>
        </section>

        @if (tab() === 'overview') {
          <fm-fixture-overview
            [fixture]="fx"
            [categories]="categories()"
            [competitionId]="competitionKey()"
            [competitionName]="competition()?.name ?? ''"
            [gameTime]="gameTimeLabel()"
          />
        }

        @if (tab() === 'stats' && !matchStats().length) {
          <div class="fm-empty compact">
            <p>No player stats for this match yet.</p>
          </div>
        }

        @if (tab() === 'stats' && matchStats().length) {
          <h3 class="fm-section-title">Match stats</h3>
          <div class="fm-team-columns" [class.many]="fx.sides.length > 2">
            @for (side of fx.sides; track side.id) {
              <div class="fm-card match-stats">
                <span class="fm-team-head">{{ side.participant.short_name || side.participant.name }}</span>
                @for (row of statsFor(side.id); track row.key) {
                  <button
                    type="button"
                    class="stat"
                    [disabled]="!row.userId"
                    (click)="openPlayer(row.userId)"
                  >
                    <span class="who">
                      <strong>{{ row.name }}</strong>
                    </span>
                    <span class="figures">
                      @for (figure of row.figures; track figure.label) {
                        <span>{{ figure.count }} {{ figure.label }}</span>
                      }
                    </span>
                  </button>
                } @empty {
                  <p class="hint">Nothing recorded.</p>
                }
              </div>
            }
          </div>
        }

        @if (tab() === 'setup' && canManage()) {
          <h3 class="fm-section-title">Game time</h3>
          <p class="hint">
            Prescribed time is split into two halves. A half must end after it overruns by 10% of the
            prescribed time. Overtime is optional; remove it for a game that ends at full time.
          </p>
          <form class="game-time" (submit)="saveGameTime($event)">
            <label>
              Time limit (minutes)
              <input
                type="number"
                min="1"
                required
                [value]="timeLimitDraft()"
                (input)="timeLimitDraft.set($any($event.target).value)"
              />
            </label>
            <label>
              Overtime (minutes)
              <input
                type="number"
                min="0"
                [value]="overtimeDraft()"
                (input)="overtimeDraft.set($any($event.target).value)"
              />
            </label>
            <div class="actions">
              <button type="submit" [disabled]="saving()">Save</button>
              @if ((fx.overtime_minutes ?? 0) > 0) {
                <button type="button" class="secondary" [disabled]="saving()" (click)="removeOvertime()">
                  Remove overtime
                </button>
              }
            </div>
          </form>

          <h3 class="fm-section-title">Officials</h3>
          <p class="hint">
            Pick the match officials before kickoff. Officials score this game; an admin can still score it too.
          </p>
          <div class="referees">
            @for (referee of fx.referees; track referee.id) {
              <div class="referee">
                <span>{{ referee.display_name || referee.email }}</span>
                <button type="button" (click)="removeReferee(referee.id)">Remove</button>
              </div>
            }
            <label>
              Add an official
              <input
                placeholder="Search profiles"
                [value]="refereeQuery()"
                (input)="refereeQuery.set($any($event.target).value)"
              />
            </label>
            @for (profile of refereeChoices(); track profile.id) {
              <button type="button" class="choice" (click)="assignReferee(profile.id)">
                {{ profile.display_name || profile.email }}
              </button>
            }
          </div>
        }

        @if (tab() === 'live' && wordScorer()) {
          <fm-scrabble-scorer
            [competitionId]="competitionKey()"
            [fixtureId]="fx.id"
            [sides]="fx.sides"
            [canScore]="canScore()"
            [kickoffBlocked]="kickoffBlocked()"
            (changed)="reloadFixture()"
          />
        }

        @if (tab() === 'live' && canScore() && !wordScorer() && fx.status !== 'completed' && fx.status !== 'cancelled') {
          <h3 class="fm-section-title">Record a score</h3>

          @if (units().length) {
            <div class="units">
              @for (unit of units(); track unit.index) {
                <button
                  type="button"
                  class="unit"
                  [class.selected]="unitIndex() === unit.index"
                  (click)="unitIndex.set(unit.index)"
                >
                  {{ unit.label }}
                </button>
              }
            </div>
          }

          @if (scoreCategories().length === 0) {
            <div class="fm-empty compact">
              <p>No scoring categories are configured for this competition yet.</p>
            </div>
          } @else {
            <p class="hint">
              @if (recordsMatchEvents()) {
                Tap a goal or card to confirm it. The match clock stamps the minute. Player ratings are on the Raters tab.
              } @else {
                Tap a goal or card on the player to confirm it. Player stats are recorded on the Raters tab.
              }
            </p>
            <div class="fm-team-columns" [class.many]="fx.sides.length > 2">
            @for (side of fx.sides; track side.id) {
              <div class="fm-card scorer">
                <span class="fm-team-head">{{ side.participant.short_name || side.participant.name }}</span>
                @if (awardedScoreCategories().length || !rosterFor(side).length) {
                  <div class="player">
                    <span class="name">Team</span>
                    <dl class="sheet">
                      @for (category of rosterFor(side).length ? awardedScoreCategories() : scoreCategories(); track category.id) {
                        @if (confirmOnRecord(category)) {
                          <div class="step tap" [class.hot]="scoreCount(side, category) > 0" [class.card]="isCard(category)">
                            <button
                              type="button"
                              [disabled]="saving() || kickoffBlocked()"
                              [attr.aria-label]="'Record ' + category.name + ' for ' + (side.participant.short_name || side.participant.name)"
                              (click)="confirmRecord(side, category, '', side.participant.short_name || side.participant.name)"
                            >
                              <strong>{{ scoreCount(side, category) }}</strong>
                              <span>{{ category.name }}@if (countsForOtherSide(category)) { · other side }</span>
                            </button>
                          </div>
                        } @else {
                          <div class="step" [class.hot]="scoreCount(side, category) > 0" [class.card]="isCard(category)">
                            <button
                              type="button"
                              [disabled]="saving() || kickoffBlocked() || scoreCount(side, category) === 0"
                              [attr.aria-label]="'Remove one ' + category.name + ' from ' + (side.participant.short_name || side.participant.name)"
                              (click)="adjustScore(side, category, '', -1)"
                            >−</button>
                            <strong>{{ scoreCount(side, category) }}</strong>
                            <span>{{ category.name }}@if (countsForOtherSide(category)) { · other side }</span>
                            <button
                              type="button"
                              [disabled]="saving() || kickoffBlocked()"
                              [attr.aria-label]="'Add one ' + category.name + ' for ' + (side.participant.short_name || side.participant.name)"
                              (click)="adjustScore(side, category, '', 1)"
                            >+</button>
                          </div>
                        }
                      }
                    </dl>
                  </div>
                }
                @for (member of rosterFor(side); track member.id) {
                  <div class="player">
                    <span class="name">
                      @if (member.number !== null) {
                        <span class="num">{{ member.number }}</span>
                      }
                      {{ member.name }}
                    </span>
                    <dl class="sheet">
                      @for (category of playerScoreCategories(); track category.id) {
                        @if (confirmOnRecord(category)) {
                          <div class="step tap" [class.hot]="scoreCount(side, category, member.id) > 0" [class.card]="isCard(category)">
                            <button
                              type="button"
                              [disabled]="saving() || kickoffBlocked()"
                              [attr.aria-label]="'Record ' + category.name + ' for ' + member.name"
                              (click)="confirmRecord(side, category, member.id, member.name)"
                            >
                              <strong>{{ scoreCount(side, category, member.id) }}</strong>
                              <span>{{ category.name }}@if (countsForOtherSide(category)) { · other side }</span>
                            </button>
                          </div>
                        } @else {
                          <div class="step" [class.hot]="scoreCount(side, category, member.id) > 0" [class.card]="isCard(category)">
                            <button
                              type="button"
                              [disabled]="saving() || kickoffBlocked() || scoreCount(side, category, member.id) === 0"
                              [attr.aria-label]="'Remove one ' + category.name + ' from ' + member.name"
                              (click)="adjustScore(side, category, member.id, -1)"
                            >−</button>
                            <strong>{{ scoreCount(side, category, member.id) }}</strong>
                            <span>{{ category.name }}@if (countsForOtherSide(category)) { · other side }</span>
                            <button
                              type="button"
                              [disabled]="saving() || kickoffBlocked()"
                              [attr.aria-label]="'Add one ' + category.name + ' for ' + member.name"
                              (click)="adjustScore(side, category, member.id, 1)"
                            >+</button>
                          </div>
                        }
                      }
                    </dl>
                  </div>
                }
              </div>
            }
            </div>
          }
        }

        @if (tab() === 'lineups' || (tab() === 'live' && fx.status === 'live')) {
          <fm-match-day
            [competitionId]="competitionKey()"
            [fixtureId]="fx.id"
            [status]="fx.status"
            [minute]="matchMinute()"
            [part]="tab() === 'live' ? 'subs' : 'all'"
          />
        }

        @if (tab() === 'live') {
        <h3 class="fm-section-title">
          Live updates
          @if (fx.events.length) {
            <span class="count">{{ fx.events.length }}</span>
          }
        </h3>

        <fm-fixture-timeline
          [fixture]="fx"
          [competitionId]="competitionKey()"
          [categories]="categories()"
          [statCodes]="statCodes()"
          [units]="units()"
          [canScore]="canScore()"
          [busy]="saving()"
          (remove)="removeEvent($event)"
          (openPlayer)="openPlayer($event)"
        />
        }

        @if (tab() === 'raters') {
          <fm-match-raters [competitionId]="competitionKey()" [fixtureId]="fx.id" (changed)="reloadFixture()" />
        }

        @if (tab() === 'overview' && hasAwards()) {
          <fm-match-awards [competitionId]="competitionKey()" [fixtureId]="fx.id" [players]="awardPlayers()" />
        }

        @if (tab() === 'stats') {
          <button type="button" class="fm-card report-link" (click)="selectTab('raters')">
            <ion-icon name="star-outline" aria-hidden="true" />
            <span>
              <strong>Rate players on the Raters tab</strong>
              <em>Match ratings come from appointed raters, from the stats recorded here.</em>
            </span>
            <ion-icon name="chevron-forward-outline" aria-hidden="true" />
          </button>
        }
      }
    </ion-content>
  `,
  styleUrl: './fixture-detail.page.scss',
})
export class FixtureDetailPage implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly route = inject(ActivatedRoute);
  private readonly realtime = inject(RealtimeService);
  private readonly router = inject(Router);
  private readonly actionSheets = inject(ActionSheetController);
  private readonly alerts = inject(AlertController);
  private readonly toasts = inject(ToastController);

  private competitionId = '';
  private fixtureId = '';

  readonly fixture = signal<FixtureDetail | null>(null);
  readonly competition = signal<CompetitionDetail | null>(null);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  /** Ticks so the clock appears at kickoff and the readout advances. */
  readonly now = signal(Date.now());
  readonly clock = signal<MatchClock>(emptyClock());
  readonly unitIndex = signal(0);
  /** Sides whose score just changed, so the number can pop. */
  readonly bumped = signal<Set<string>>(new Set());
  readonly celebration = signal<Celebration | null>(null);
  private bumpTimer: ReturnType<typeof setTimeout> | undefined;
  private celebrationTimer: ReturnType<typeof setTimeout> | undefined;
  readonly profiles = signal<ProfileSummary[]>([]);
  readonly refereeQuery = signal('');
  readonly timeLimitDraft = signal('');
  readonly overtimeDraft = signal('');
  private syncedGameTime = '';

  constructor() {
    effect(() => {
      const fixture = this.fixture();
      if (!fixture) return;
      const key = `${fixture.id}:${fixture.duration_minutes}:${fixture.overtime_minutes}`;
      if (key === this.syncedGameTime) return;
      this.syncedGameTime = key;
      this.timeLimitDraft.set(fixture.duration_minutes ? String(fixture.duration_minutes) : '');
      this.overtimeDraft.set(String(fixture.overtime_minutes ?? 0));
    });
  }

  private tickHandle: ReturnType<typeof setInterval> | null = null;

  ngOnInit(): void {
    this.competitionId = this.route.snapshot.paramMap.get('competitionId') ?? '';
    this.fixtureId = this.route.snapshot.paramMap.get('fixtureId') ?? '';
    const requested = this.route.snapshot.queryParamMap.get('tab') as FixtureTab | null;
    if (requested && FIXTURE_TABS.includes(requested)) {
      this.selectedTab.set(requested);
      this.tabChosen = true;
    }

    this.clock.set(readMatchClock(this.fixtureId));
    this.tickHandle = setInterval(() => {
      this.now.set(Date.now());
      this.enforcePeriodCap();
    }, 1000);

    this.load();
    this.realtime.subscribe(fixtureRoom(this.fixtureId));

    this.realtime
      .onAny<{ fixture_id: string }>([
        'score.recorded',
        'score.corrected',
        'score.removed',
        'fixture.updated',
        'fixture.live',
        'fixture.completed',
      ])
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((message) => {
        if (message.payload.fixture_id === this.fixtureId) {
          this.reloadFixture();
        }
      });
  }

  ngOnDestroy(): void {
    clearTimeout(this.bumpTimer);
    clearTimeout(this.celebrationTimer);
    if (this.tickHandle !== null) {
      clearInterval(this.tickHandle);
    }
    if (this.fixtureId) {
      this.realtime.unsubscribe(fixtureRoom(this.fixtureId));
    }
  }

  /** Shown while a scorer can run the match, or once a kickoff / time limit is set. */
  showClock(): boolean {
    const fixture = this.fixture();
    if (!fixture) return false;
    if (
      fixture.status === 'completed' ||
      fixture.status === 'cancelled' ||
      fixture.status === 'postponed' ||
      fixture.status === 'forfeit'
    ) {
      return false;
    }
    if (this.canScore()) return true;
    return !!fixture.scheduled_at || this.timeLimits() !== null;
  }

  timeLimits(): { regulation: number; overtime: number } | null {
    const fixture = this.fixture();
    const settings = this.competition()?.settings_json ?? {};
    const regulation = Number(fixture?.duration_minutes ?? settings['time_limit_minutes']);
    const overtime = Number(fixture?.overtime_minutes ?? settings['overtime_minutes'] ?? 0);
    if (!Number.isFinite(regulation) || regulation <= 0) return null;
    return { regulation, overtime: Number.isFinite(overtime) && overtime > 0 ? overtime : 0 };
  }

  /** A scheduled game cannot start until it has a time limit and a referee. */
  kickoffBlocked(): boolean {
    const fixture = this.fixture();
    return fixture?.status === 'scheduled' && (fixture.kickoff_problems?.length ?? 0) > 0;
  }

  gameTimeLabel(): string {
    const limits = this.timeLimits();
    if (!limits) return 'No time limit set';
    const half = formatDurationMinutes(halfMinutes(limits.regulation));
    const added = formatDurationMinutes(halfOverrunMinutes(limits.regulation));
    const halves = `2 × ${half} min · half ends at +${added}`;
    return limits.overtime > 0 ? `${halves} · ${limits.overtime} overtime` : halves;
  }

  saveGameTime(event: Event): void {
    event.preventDefault();
    const limit = Number(this.timeLimitDraft());
    const overtime = Number(this.overtimeDraft() || 0);
    if (!Number.isInteger(limit) || limit < 1) {
      void this.showToast('Enter a time limit of at least 1 minute.', 'danger');
      return;
    }
    if (!Number.isInteger(overtime) || overtime < 0) {
      void this.showToast('Overtime cannot be negative. Use 0 for no overtime.', 'danger');
      return;
    }
    this.updateGameTime({ duration_minutes: limit, overtime_minutes: overtime }, 'Game time saved.');
  }

  removeOvertime(): void {
    this.updateGameTime({ overtime_minutes: 0 }, 'Overtime removed for this game.');
  }

  private updateGameTime(body: Record<string, number>, message: string): void {
    if (this.saving()) return;
    this.saving.set(true);
    this.api.updateFixture(this.competitionId, this.fixtureId, body).subscribe({
      next: async () => {
        this.saving.set(false);
        this.reloadFixture();
        await this.showToast(message, 'success');
      },
      error: async (err: unknown) => {
        this.saving.set(false);
        await this.showToast(extractErrorMessage(err, 'Could not save the game time.'), 'danger');
      },
    });
  }

  periodLabel(): string {
    this.now();
    const clock = this.clock();
    if (clock.overtime) return clock.overtimeEnded ? 'Overtime ended' : 'Overtime';
    if (clock.half === 1) return clock.halfEnded ? 'Half-time' : 'First half';
    return clock.halfEnded ? 'Full time' : 'Second half';
  }

  private clockPeriodName(): string {
    const clock = this.clock();
    if (clock.overtime) return 'Overtime';
    return clock.half === 1 ? 'First half' : 'Second half';
  }

  canEndGame(): boolean {
    const fixture = this.fixture();
    if (!fixture || !this.canScore()) return false;
    const clock = this.clock();
    return (
      fixture.status === 'live' ||
      clock.half === 2 ||
      clock.overtime ||
      this.displayedElapsed() > 0 ||
      this.clockRunning()
    );
  }

  canEndHalf(): boolean {
    if (!this.canScore() || this.kickoffBlocked()) return false;
    const clock = this.clock();
    if (clock.overtime || clock.halfEnded) return false;
    return this.clockRunning() || this.displayedElapsed() > 0;
  }

  canToggleClock(): boolean {
    if (this.clockRunning()) return true;
    const clock = this.clock();
    if (clock.overtimeEnded) return false;
    if (clock.halfEnded && clock.half === 2 && !(this.hasOvertime() && !clock.overtime)) return false;
    return true;
  }

  endGame(): void {
    this.pauseClock();
    this.setStatus('completed');
  }

  endHalf(): void {
    this.endCurrentHalf();
  }

  clockRunning(): boolean {
    return this.clock().running;
  }

  clockButtonLabel(): string {
    if (this.clockRunning()) return 'Pause';
    const clock = this.clock();
    if (clock.halfEnded && clock.half === 1 && !clock.overtime) return 'Start second half';
    if (clock.halfEnded && clock.half === 2 && this.hasOvertime() && !clock.overtime) return 'Start overtime';
    if (clock.overtimeEnded || (clock.halfEnded && clock.half === 2)) return 'Ended';
    if (this.fixture()?.status === 'live' || this.displayedElapsed() > 0 || clock.half === 2 || clock.overtime) {
      return 'Resume';
    }
    return 'Start';
  }

  clockLabel(): string {
    return formatClock(this.displayedElapsed());
  }

  private readonly selectedTab = signal<FixtureTab>('overview');
  private tabChosen = false;
  readonly tab = computed<FixtureTab>(() => {
    const selected = this.selectedTab();
    return this.tabs().some((item) => item.key === selected) ? selected : 'overview';
  });

  readonly tabs = computed(() => {
    const settings = this.competition()?.settings_json ?? {};
    const teams = (settings['participant_type'] ?? 'team') === 'team';
    const items: Array<{ key: FixtureTab; label: string }> = [{ key: 'overview', label: 'Overview' }];
    if (teams) items.push({ key: 'lineups', label: 'Line-ups' });
    items.push({ key: 'live', label: 'Live' }, { key: 'stats', label: 'Stats' }, { key: 'raters', label: 'Raters' });
    if (this.canManage()) items.push({ key: 'setup', label: 'Setup' });
    return items;
  });

  selectTab(tab: FixtureTab): void {
    this.tabChosen = true;
    this.selectedTab.set(tab);
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { tab },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
  }

  readonly matchMinute = computed(() =>
    this.fixture()?.status === 'live' && this.showClock()
      ? Math.floor(this.matchElapsedMs() / 60_000)
      : null,
  );

  /** Goals and cards take the minute showing on the match clock. */
  private clockMinute(category: ScoringCategory): number | null {
    if (!this.showClock() || !followsMatchClock(category)) return null;
    return Math.floor(this.matchElapsedMs() / 60_000);
  }

  startOrPause(): void {
    if (this.clockRunning()) {
      this.pauseClock();
      return;
    }
    const clock = this.clock();
    if (clock.halfEnded && clock.half === 1 && !clock.overtime) {
      this.beginPeriod(2);
      return;
    }
    if (clock.halfEnded && clock.half === 2 && this.hasOvertime() && !clock.overtime) {
      this.beginPeriod(2, true);
      return;
    }
    if (this.periodIsCapped()) {
      this.endCurrentHalf();
      return;
    }
    this.startClock();
  }

  private startClock(): void {
    const clock = this.clock();
    const next: MatchClock = {
      ...clock,
      running: true,
      elapsedMs: clock.elapsedMs,
      runStartedAt: Date.now(),
      halfEnded: false,
    };
    this.clock.set(next);
    writeMatchClock(this.fixtureId, next);
    this.syncUnitIndex();
    if (this.fixture()?.status === 'scheduled') {
      this.setStatus('live');
    }
  }

  private beginPeriod(half: 1 | 2, overtime = false): void {
    const next: MatchClock = {
      running: true,
      elapsedMs: 0,
      runStartedAt: Date.now(),
      half,
      halfEnded: false,
      overtime,
      overtimeEnded: false,
    };
    this.clock.set(next);
    writeMatchClock(this.fixtureId, next);
    this.syncUnitIndex();
    if (this.fixture()?.status === 'scheduled') {
      this.setStatus('live');
    }
  }

  private resetClock(): void {
    this.clock.set(emptyClock());
    localStorage.removeItem(clockKey(this.fixtureId));
  }

  private pauseClock(): void {
    const next: MatchClock = {
      ...this.clock(),
      running: false,
      elapsedMs: this.displayedElapsed(),
      runStartedAt: null,
    };
    this.clock.set(next);
    writeMatchClock(this.fixtureId, next);
  }

  private endCurrentHalf(): void {
    const clock = this.clock();
    if (clock.overtime ? clock.overtimeEnded : clock.halfEnded) return;
    const max = this.periodMaxMs();
    const elapsed = max === null ? this.uncappedElapsed() : Math.min(this.uncappedElapsed(), max);
    const next: MatchClock = {
      ...clock,
      running: false,
      elapsedMs: elapsed,
      runStartedAt: null,
      halfEnded: !clock.overtime,
      overtimeEnded: clock.overtime,
    };
    this.clock.set(next);
    writeMatchClock(this.fixtureId, next);
    this.syncUnitIndex();
    const label = clock.overtime ? 'Overtime ended.' : clock.half === 1 ? 'First half ended.' : 'Second half ended.';
    void this.showToast(label, 'success');
  }

  private enforcePeriodCap(): void {
    if (!this.clock().running || !this.periodIsCapped()) return;
    this.endCurrentHalf();
  }

  private hasOvertime(): boolean {
    return (this.timeLimits()?.overtime ?? 0) > 0;
  }

  private periodMaxMs(): number | null {
    const limits = this.timeLimits();
    if (!limits) return null;
    if (this.clock().overtime) return limits.overtime * 60_000;
    return halfMaxMinutes(limits.regulation) * 60_000;
  }

  private periodIsCapped(): boolean {
    const max = this.periodMaxMs();
    return max !== null && this.uncappedElapsed() >= max;
  }

  private displayedElapsed(): number {
    const max = this.periodMaxMs();
    const elapsed = this.uncappedElapsed();
    return max === null ? elapsed : Math.min(elapsed, max);
  }

  private uncappedElapsed(): number {
    const clock = this.clock();
    if (!clock.running || clock.runStartedAt === null) return clock.elapsedMs;
    return clock.elapsedMs + Math.max(0, this.now() - clock.runStartedAt);
  }

  /** Match minute: first half from 0, second half from half length, overtime from full time. */
  private matchElapsedMs(): number {
    const limits = this.timeLimits();
    const clock = this.clock();
    const current = this.displayedElapsed();
    if (clock.overtime) return (limits?.regulation ?? 0) * 60_000 + current;
    if (clock.half === 2) return (limits ? halfMinutes(limits.regulation) : 0) * 60_000 + current;
    return current;
  }

  private syncUnitIndex(): void {
    const slots = this.units();
    if (!slots.length) return;
    const clock = this.clock();
    if (clock.overtime) {
      this.unitIndex.set(slots.length - 1);
      return;
    }
    this.unitIndex.set(Math.min(clock.half - 1, slots.length - 1));
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);

    this.api.getCompetition(this.competitionId).subscribe({
      next: (competition) => {
        this.competition.set(competition);
        this.syncUnitIndex();
        if (this.canManage()) this.ensureProfiles();
      },
      error: () => undefined,
    });

    this.api.getFixture(this.competitionId, this.fixtureId).subscribe({
      next: (fixture) => {
        if (fixture.status === 'scheduled') this.resetClock();
        if (!this.tabChosen) {
          this.tabChosen = true;
          this.selectedTab.set(fixture.status === 'live' ? 'live' : 'overview');
        }
        this.applyFixture(fixture);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err));
        this.loading.set(false);
      },
    });
  }

  /** Every fixture update comes through here so a changed score can react. */
  private applyFixture(next: FixtureDetail): void {
    const before = this.fixture();
    if (before && before.id === next.id) {
      const rose: string[] = [];
      const changed = new Set<string>();
      for (const side of next.sides) {
        const previous = before.sides.find((item) => item.id === side.id);
        if (previous && previous.score !== side.score) {
          changed.add(side.id);
          if (Number(side.score) > Number(previous.score)) rose.push(side.id);
        }
      }
      clearTimeout(this.bumpTimer);
      this.bumped.set(changed);
      if (changed.size) {
        this.bumpTimer = setTimeout(() => this.bumped.set(new Set()), 1200);
      }
      if (rose.length && next.status !== 'completed') this.celebrate(next, rose[0]);
    }
    this.fixture.set(next);
    this.syncUnitIndex();
  }

  private celebrate(next: FixtureDetail, sideId: string): void {
    const scoring = [...next.events]
      .filter((event) => Number(event.points) > 0)
      .sort((a, b) => a.created_at.localeCompare(b.created_at));
    const latest = scoring.at(-1);
    const side = next.sides.find((item) => item.id === sideId);
    const label = (latest?.scoring_category_name || 'Score').toUpperCase();
    const who = latest?.player_name || side?.participant.short_name || side?.participant.name || '';
    const colours = ['#f59e0b', '#14b8a6', '#2563eb', '#ec4899', '#22c55e', '#a855f7'];
    const pieces = Array.from({ length: 36 }, (_, index) => {
      const angle = (index / 36) * Math.PI * 2 + Math.random() * 0.4;
      const reach = 140 + Math.random() * 220;
      return {
        dx: Math.round(Math.cos(angle) * reach),
        dy: Math.round(Math.sin(angle) * reach * 0.8 + 120),
        rot: Math.round(Math.random() * 720 - 360),
        delay: Math.round(Math.random() * 120),
        color: colours[index % colours.length],
      };
    });
    clearTimeout(this.celebrationTimer);
    this.celebration.set({ title: who ? `${label}! ${who}` : `${label}!`, pieces });
    this.celebrationTimer = setTimeout(() => this.celebration.set(null), 2400);
  }

  reloadFixture(): void {
    this.api.getFixture(this.competitionId, this.fixtureId).subscribe({
      next: (fixture) => this.applyFixture(fixture),
      error: () => undefined,
    });
  }

  categories(): ScoringCategory[] {
    return this.competition()?.scoring_categories ?? [];
  }

  /** Score types the preset marks as player stats (assists, tackles, ...). */
  statCodes(): Set<string> {
    const types = this.competition()?.settings_json?.['score_types'];
    if (!Array.isArray(types)) return new Set();
    return new Set(
      types.filter((item: { stat?: boolean }) => item?.stat).map((item: { key: string }) => item.key),
    );
  }

  wordScorer(): boolean {
    const settings = this.competition()?.settings_json ?? {};
    return !!settings['tile_set'] || settings['preset'] === 'scrabble';
  }

  scoreCategories(): ScoringCategory[] {
    const stats = this.statCodes();
    return this.categories().filter((category) => !stats.has(category.code));
  }

  playerScoreCategories(): ScoringCategory[] {
    return this.scoreCategories().filter((category) => !this.noPlayer(category));
  }

  awardedScoreCategories(): ScoringCategory[] {
    return this.scoreCategories().filter((category) => this.noPlayer(category));
  }

  isCard(category: ScoringCategory): boolean {
    return category.code.toLowerCase().includes('card');
  }

  /** Goals and cards are recorded with one tap and a confirmation, not +/−. */
  confirmOnRecord(category: ScoringCategory): boolean {
    const code = category.code.trim().toLowerCase();
    const name = category.name.trim().toLowerCase();
    return (
      code === 'goal' ||
      code === 'own-goal' ||
      code === 'yellow-card' ||
      code === 'red-card' ||
      name === 'goal' ||
      name === 'own goal' ||
      name === 'yellow card' ||
      name === 'red card'
    );
  }

  scoreCount(side: FixtureSide, category: ScoringCategory, playerId = ''): number {
    return (this.fixture()?.events ?? []).reduce((total, event) => {
      if (event.side !== side.id || event.scoring_category !== category.id) return total;
      if (playerId ? event.player !== playerId : event.player) return total;
      const qty = Number(event.quantity);
      return total + (Number.isFinite(qty) ? qty : 1);
    }, 0);
  }

  lastScoreEvent(side: FixtureSide, category: ScoringCategory, playerId = ''): ScoreEvent | undefined {
    const matches = (this.fixture()?.events ?? []).filter((event) => {
      if (event.side !== side.id || event.scoring_category !== category.id) return false;
      return playerId ? event.player === playerId : !event.player;
    });
    return matches[matches.length - 1];
  }

  countsForOtherSide(category: ScoringCategory): boolean {
    const code = category.code.trim().toLowerCase();
    const name = category.name.trim().toLowerCase();
    return code === 'own-goal' || name === 'own goal';
  }

  units(): Array<{ index: number; label: string }> {
    const structure = this.competition()?.settings_json?.['match_structure'];
    if (!Array.isArray(structure)) return [];
    const slots: Array<{ index: number; label: string }> = [];
    const seen: Record<string, number> = {};
    for (const block of structure) {
      if (!block || typeof block !== 'object') continue;
      const record = block as { unit?: string; count?: number; best_of?: number; repeat?: boolean };
      let count = Number(record.count || record.best_of || 1);
      if (record.repeat) count = Math.max(count, 3);
      const name = String(record.unit || 'unit').replaceAll('_', ' ');
      for (let offset = 0; offset < count; offset += 1) {
        // Numbered across blocks so a deciding fifth set reads "set 5".
        seen[name] = (seen[name] ?? 0) + 1;
        slots.push({ index: slots.length, label: `${name} ${seen[name]}` });
      }
    }
    return slots;
  }

  unitLabel(event: ScoreEvent): string {
    if (event.unit_index === null || event.unit_index === undefined) return '';
    return this.units().find((unit) => unit.index === event.unit_index)?.label ?? '';
  }

  canScore(): boolean {
    const role = this.competition()?.my_role;
    if (role === 'owner' || role === 'admin') return true;
    const me = this.auth.user()?.id;
    const referees = this.fixture()?.referees ?? [];
    if (referees.some((referee) => referee.id === me)) return true;
    if (referees.length > 0) return false;
    return role === 'scorer';
  }

  canManage(): boolean {
    const role = this.competition()?.my_role;
    return role === 'owner' || role === 'admin';
  }

  refereeChoices(): ProfileSummary[] {
    const query = this.refereeQuery().trim().toLowerCase();
    if (!query) return [];
    const taken = new Set((this.fixture()?.referees ?? []).map((referee) => referee.id));
    return this.profiles()
      .filter((profile) => !taken.has(profile.id))
      .filter((profile) => {
        const name = (profile.display_name || '').toLowerCase();
        return name.includes(query) || profile.email.toLowerCase().includes(query);
      })
      .slice(0, 8);
  }

  assignReferee(userId: string): void {
    if (this.saving()) return;
    this.saving.set(true);
    this.api.assignReferee(this.competitionId, this.fixtureId, userId).subscribe({
      next: (fixture) => {
        this.applyFixture(fixture);
        this.refereeQuery.set('');
        this.saving.set(false);
      },
      error: async (err: unknown) => {
        this.saving.set(false);
        await this.showToast(extractErrorMessage(err, 'Could not add that referee.'), 'danger');
      },
    });
  }

  removeReferee(userId: string): void {
    if (this.saving()) return;
    this.saving.set(true);
    this.api.removeReferee(this.competitionId, this.fixtureId, userId).subscribe({
      next: (fixture) => {
        this.applyFixture(fixture);
        this.saving.set(false);
      },
      error: async (err: unknown) => {
        this.saving.set(false);
        await this.showToast(extractErrorMessage(err, 'Could not remove that referee.'), 'danger');
      },
    });
  }

  private ensureProfiles(): void {
    if (this.profiles().length) return;
    this.api.listProfiles().subscribe({
      next: (page) => this.profiles.set(page.results),
    });
  }

  backHref(): string {
    const competition = this.competition();
    const fixture = this.fixture();
    const tab =
      competition && fixture && isCupFixture(fixture, competition.stages) ? 'cup' : 'fixtures';
    return `/tabs/competitions/${this.competitionId}?tab=${tab}`;
  }

  rosterFor(side: FixtureSide): RosterMember[] {
    return (
      this.competition()
        ?.participants.find((participant) => participant.id === side.participant.id)
        ?.roster.filter((member) => member.is_active) ?? []
    );
  }

  isKnockout(): boolean {
    const format = this.competition()?.format;
    return format === 'knockout' || format === 'group_knockout' || format === 'league_knockout';
  }

  /** League, cup and ladder matches keep a named, timed timeline and ratings. */
  recordsMatchEvents(): boolean {
    const competition = this.competition();
    if (!competition) return false;
    const format = competition.format;
    if (
      format !== 'league' &&
      format !== 'knockout' &&
      format !== 'league_knockout' &&
      format !== 'group_knockout' &&
      format !== 'ladder'
    ) {
      return false;
    }
    return (competition.settings_json?.['table_mode'] as string | undefined) !== 'points';
  }

  requiresProfile(category: ScoringCategory): boolean {
    const code = category.code.trim().toLowerCase();
    const name = category.name.trim().toLowerCase();
    if (
      code === 'goal' ||
      code === 'own-goal' ||
      code === 'yellow-card' ||
      code === 'red-card' ||
      code === 'touchdown' ||
      code === 'extra-point' ||
      code === 'two-point' ||
      code === 'safety' ||
      code === 'defensive-conversion' ||
      code === 'home-run' ||
      name === 'goal' ||
      name === 'own goal' ||
      name === 'yellow card' ||
      name === 'red card' ||
      name === 'touchdown' ||
      name === 'extra point' ||
      name === 'two-point conversion' ||
      name === 'safety' ||
      name === 'returned conversion' ||
      name === 'home run'
    ) {
      return true;
    }
    return this.recordsMatchEvents() && this.tracksMatchEvents(category);
  }

  /** Scoring and cards belong on the match timeline with a name and a minute. */
  tracksMatchEvents(category: ScoringCategory): boolean {
    if (this.noPlayer(category) || this.statCodes().has(category.code)) return false;
    return this.isCard(category) || category.affects_score;
  }

  statsFor(sideId: string) {
    return this.matchStats().filter((row) => row.sideId === sideId);
  }

  matchStats(): Array<{
    key: string;
    sideId: string;
    name: string;
    team: string;
    userId: string | null;
    figures: Array<{ label: string; count: number }>;
  }> {
    const fixture = this.fixture();
    if (!fixture) return [];
    const grouped = new Map<
      string,
      { sideId: string; name: string; team: string; userId: string | null; counts: Map<string, number> }
    >();
    for (const event of fixture.events) {
      const key = event.player || event.player_name || event.id;
      const team = this.participantName(event);
      const current = grouped.get(key) ?? {
        sideId: event.side,
        name: event.player_name || team,
        team,
        userId: event.player_user_id,
        counts: new Map<string, number>(),
      };
      const qty = Number(event.quantity);
      const count = Number.isFinite(qty) ? qty : 1;
      const label = event.scoring_category_name;
      current.counts.set(label, (current.counts.get(label) ?? 0) + count);
      grouped.set(key, current);
    }
    return [...grouped.entries()].map(([key, row]) => ({
      key,
      sideId: row.sideId,
      name: row.name,
      team: row.team,
      userId: row.userId,
      figures: [...row.counts.entries()].map(([label, count]) => ({ label, count })),
    }));
  }

  openPlayer(userId: string | null): void {
    if (!userId) return;
    void this.router.navigate(['/tabs/competitions', this.competitionId, 'players', userId]);
  }

  /** An awarded score (no shot taken) belongs to the side, not a player. */
  noPlayer(category: ScoringCategory): boolean {
    const types = this.competition()?.settings_json?.['score_types'];
    if (!Array.isArray(types)) return false;
    return types.some(
      (item) => item && typeof item === 'object' && item.key === category.code && item.no_player === true,
    );
  }

  headStart(side: FixtureSide): string | null {
    const value = side.head_start;
    if (value === null || value === undefined || Number(value) === 0) return null;
    return this.trim(value);
  }

  hasAwards(): boolean {
    const awards = this.competition()?.settings_json?.['match_awards'];
    return Array.isArray(awards) && awards.length > 0;
  }

  competitionKey(): string {
    return this.competitionId;
  }

  awardPlayers(): Array<{ id: string; name: string; team: string }> {
    return (this.fixture()?.sides ?? []).flatMap((side) =>
      this.rosterFor(side).map((member) => ({
        id: member.id,
        name: member.number !== null ? `${member.number}. ${member.name}` : member.name,
        team: side.participant.name,
      })),
    );
  }

  async confirmRecord(
    side: FixtureSide,
    category: ScoringCategory,
    playerId: string,
    who: string,
  ): Promise<void> {
    if (this.saving() || this.kickoffBlocked()) return;
    const minute = this.clockMinute(category);
    const when = minute !== null ? ` at ${minute}'` : '';
    const alert = await this.alerts.create({
      header: category.name,
      message: `Record ${category.name.toLowerCase()} for ${who}${when}?`,
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        { text: 'Record', role: 'confirm' },
      ],
    });
    await alert.present();
    const { role } = await alert.onDidDismiss();
    if (role !== 'confirm') return;
    await this.record(side, category, playerId);
  }

  async adjustScore(
    side: FixtureSide,
    category: ScoringCategory,
    playerId: string,
    delta: number,
  ): Promise<void> {
    if (delta > 0) {
      await this.record(side, category, playerId);
      return;
    }
    const event = this.lastScoreEvent(side, category, playerId);
    if (!event) return;
    const fixture = this.fixture();
    const counted = fixture?.status === 'completed' || fixture?.status === 'forfeit';
    const official = this.competition()?.settings_json?.['official_results'] === true;
    if (counted && official) {
      await this.removeEvent(event);
      return;
    }
    this.deleteEvent(event, undefined, true);
  }

  async record(side: FixtureSide, category: ScoringCategory, playerId = ''): Promise<void> {
    if (this.saving()) return;
    const awarded = this.noPlayer(category);
    const roster = awarded ? [] : this.rosterFor(side);
    let named = '';
    if (!awarded && this.requiresProfile(category) && !playerId) {
      if (roster.length) {
        await this.showToast('Choose the profile this applies to.', 'danger');
        return;
      }
      if (this.recordsMatchEvents()) {
        named = await this.askPlayerName(category);
        if (!named) return;
      } else {
        await this.showToast('Add a profile to this team first.', 'danger');
        return;
      }
    }
    if (this.statCodes().has(category.code)) {
      await this.showToast('Player stats are recorded on the Raters tab.', 'danger');
      return;
    }
    this.saving.set(true);

    const body: Record<string, unknown> = {
      side: side.id,
      scoring_category: category.id,
      quantity: '1',
    };
    if (playerId) {
      body['player'] = playerId;
      const member = roster.find((item) => item.id === playerId);
      if (member) body['player_name'] = member.name;
    } else if (named) {
      body['player_name'] = named;
    }
    if (this.units().length) {
      body['unit_index'] = this.unitIndex();
      body['period'] = this.unitLabel({ unit_index: this.unitIndex() } as ScoreEvent);
    } else {
      body['unit_index'] = this.clock().overtime ? 2 : this.clock().half - 1;
      body['period'] = this.clockPeriodName();
    }
    const minute = this.clockMinute(category);
    if (minute !== null) body['minute'] = minute;

    this.api
      .recordEvent(this.fixtureId, body)
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.reloadFixture();
        },
        error: async (err: unknown) => {
          this.saving.set(false);
          await this.showToast(extractErrorMessage(err, 'Could not record that.'), 'danger');
        },
      });
  }

  private async askPlayerName(category: ScoringCategory): Promise<string> {
    const alert = await this.alerts.create({
      header: category.name,
      message: 'Who was this? The match timeline shows the name and the minute.',
      inputs: [{ name: 'player', type: 'text', placeholder: 'Player name' }],
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        { text: 'Record', role: 'confirm' },
      ],
    });
    await alert.present();
    const { role, data } = await alert.onDidDismiss<{ values?: { player?: string } }>();
    if (role !== 'confirm') return '';
    return String(data?.values?.player ?? '').trim();
  }

  /** Delete a recorded score after a confirmation; a counted official result also asks why. */
  async removeEvent(event: ScoreEvent): Promise<void> {
    if (this.saving()) return;
    const fixture = this.fixture();
    const counted = fixture?.status === 'completed' || fixture?.status === 'forfeit';
    const official = this.competition()?.settings_json?.['official_results'] === true;
    const needsReason = counted && official;
    const who = this.participantName(event);
    const what = `${event.scoring_category_name}${event.player_name ? ' by ' + event.player_name : ''}`;
    const points = this.signed(event.points);
    const alert = await this.alerts.create({
      header: 'Delete this score?',
      message: `${who}: ${what} (${points}). ${
        counted ? 'The result and the table are worked out again.' : 'The score is worked out again.'
      }`,
      inputs: needsReason
        ? [{ name: 'reason', type: 'textarea', placeholder: 'Why is it being removed? This is logged.' }]
        : [],
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        {
          text: 'Delete',
          role: 'destructive',
          handler: (values: { reason?: string } | undefined) => {
            const reason = (values?.reason ?? '').trim();
            if (needsReason && !reason) {
              void this.showToast('Give a reason; changes to an official result are logged.', 'danger');
              return false;
            }
            this.deleteEvent(event, reason || undefined);
            return true;
          },
        },
      ],
    });
    await alert.present();
  }

  private deleteEvent(event: ScoreEvent, reason?: string, quiet = false): void {
    this.saving.set(true);
    this.api.deleteEvent(this.fixtureId, event.id, reason).subscribe({
      next: () => {
        this.saving.set(false);
        this.reloadFixture();
        if (!quiet) void this.showToast('Score deleted.', 'success');
      },
      error: async (err: unknown) => {
        this.saving.set(false);
        await this.showToast(extractErrorMessage(err, 'Could not remove that event.'), 'danger');
      },
    });
  }

  async openStatusSheet(): Promise<void> {
    const current = this.fixture()?.status;
    const transitions: Array<{ status: string; label: string; destructive?: boolean }> = [
      { status: 'live', label: 'Start / mark live' },
      { status: 'completed', label: 'Complete fixture' },
      { status: 'scheduled', label: 'Back to scheduled' },
      { status: 'postponed', label: 'Postpone' },
      { status: 'cancelled', label: 'Cancel fixture', destructive: true },
    ].filter((option) => option.status !== current);

    const sheet = await this.actionSheets.create({
      header: 'Fixture status',
      buttons: [
        ...transitions.map((option) => ({
          text: option.label,
          role: option.destructive ? 'destructive' : undefined,
          handler: () => this.setStatus(option.status),
        })),
        { text: 'Cancel', role: 'cancel' },
      ],
    });
    await sheet.present();
  }

  private setStatus(status: string): void {
    this.api.setFixtureStatus(this.competitionId, this.fixtureId, status).subscribe({
      next: (fixture) => this.applyFixture(fixture),
      error: async (err: unknown) => {
        await this.showToast(extractErrorMessage(err, 'Could not change the status.'), 'danger');
      },
    });
  }

  private async showToast(message: string, color: string): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2600, position: 'bottom' });
    await toast.present();
  }

  participantName(event: ScoreEvent): string {
    const side = this.fixture()?.sides.find(
      (candidate) => candidate.participant.id === event.participant_id,
    );
    return side?.participant.short_name || side?.participant.name || '—';
  }

  statusLabel(status: string): string {
    const labels: Record<string, string> = {
      scheduled: 'Scheduled',
      live: 'Live',
      completed: 'Full time',
      postponed: 'Postponed',
      cancelled: 'Cancelled',
      forfeit: 'Forfeit',
    };
    return labels[status] ?? status;
  }

  numeric(value: string): number {
    return Number(value);
  }

  trim(value: string): string {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? String(parsed) : value;
  }

  signed(value: string): string {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return value;
    if (parsed === 0) return '0';
    return parsed > 0 ? `+${parsed}` : String(parsed);
  }
}

interface MatchClock {
  running: boolean;
  elapsedMs: number;
  runStartedAt: number | null;
  half: 1 | 2;
  halfEnded: boolean;
  overtime: boolean;
  overtimeEnded: boolean;
}

const HALF_OVERRUN_RATIO = 0.1;

function emptyClock(): MatchClock {
  return {
    running: false,
    elapsedMs: 0,
    runStartedAt: null,
    half: 1,
    halfEnded: false,
    overtime: false,
    overtimeEnded: false,
  };
}

function halfMinutes(regulation: number): number {
  return regulation / 2;
}

function halfOverrunMinutes(regulation: number): number {
  return regulation * HALF_OVERRUN_RATIO;
}

function halfMaxMinutes(regulation: number): number {
  return halfMinutes(regulation) + halfOverrunMinutes(regulation);
}

function formatDurationMinutes(value: number): string {
  if (Number.isInteger(value)) return String(value);
  return String(Math.round(value * 10) / 10);
}

function clockKey(fixtureId: string): string {
  return `fm.matchClock.${fixtureId}`;
}

function readMatchClock(fixtureId: string): MatchClock {
  const empty = emptyClock();
  try {
    const raw = localStorage.getItem(clockKey(fixtureId));
    if (!raw) return empty;
    const parsed = JSON.parse(raw) as Partial<MatchClock>;
    return {
      running: parsed.running === true,
      elapsedMs: typeof parsed.elapsedMs === 'number' ? parsed.elapsedMs : 0,
      runStartedAt: typeof parsed.runStartedAt === 'number' ? parsed.runStartedAt : null,
      half: parsed.half === 2 ? 2 : 1,
      halfEnded: parsed.halfEnded === true,
      overtime: parsed.overtime === true,
      overtimeEnded: parsed.overtimeEnded === true,
    };
  } catch {
    return empty;
  }
}

function writeMatchClock(fixtureId: string, clock: MatchClock): void {
  localStorage.setItem(clockKey(fixtureId), JSON.stringify(clock));
}

function followsMatchClock(category: ScoringCategory): boolean {
  const code = category.code.trim().toLowerCase();
  const name = category.name.trim().toLowerCase();
  return category.affects_score || code.endsWith('-card') || name.endsWith(' card');
}

function formatClock(elapsedMs: number): string {
  const total = Math.max(0, Math.floor(elapsedMs / 1000));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  const mm = String(minutes).padStart(2, '0');
  const ss = String(seconds).padStart(2, '0');
  return hours > 0 ? `${hours}:${mm}:${ss}` : `${mm}:${ss}`;
}
