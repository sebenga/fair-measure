import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnDestroy,
  OnInit,
  effect,
  inject,
  signal,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import {
  ActionSheetController,
  IonBackButton,
  IonButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonSpinner,
  IonTitle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';

import { ApiService } from '../../core/api.service';
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
import { RelativeTimePipe } from '../../shared/relative-time.pipe';

@Component({
  selector: 'fm-fixture-detail',
  standalone: true,
  imports: [
    DatePipe,
    RelativeTimePipe,
    IonHeader,
    IonToolbar,
    IonTitle,
    IonButtons,
    IonBackButton,
    IonButton,
    IonIcon,
    IonContent,
    IonSpinner,
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
    </ion-header>

    <ion-content fullscreen="true">
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (error()) {
        <div class="fm-empty">
          <ion-icon name="alert-circle-outline" aria-hidden="true" />
          <h3>Could not load this fixture</h3>
          <p>{{ error() }}</p>
          <ion-button fill="clear" (click)="load()">Try again</ion-button>
        </div>
      } @else if (fixture(); as fx) {
        <section class="scoreboard">
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
                @if (inOvertime()) {
                  <span class="chip">Overtime</span>
                }
                @if (canScore()) {
                  <button type="button" [disabled]="kickoffBlocked()" (click)="startOrPause()">
                    {{ clockButtonLabel() }}
                  </button>
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
                <span class="score">{{ trim(side.score) }}</span>
                @if (side.forfeited) {
                  <span class="ff">forfeit</span>
                }
              </div>
            }
          </div>
        </section>

        @if (matchStats().length) {
          <h3 class="fm-section-title">Match stats</h3>
          <div class="fm-card match-stats">
            @for (row of matchStats(); track row.key) {
              <button
                type="button"
                class="stat"
                [disabled]="!row.userId"
                (click)="openPlayer(row.userId)"
              >
                <span class="who">
                  <strong>{{ row.name }}</strong>
                  <em>{{ row.team }}</em>
                </span>
                <span class="figures">
                  @for (figure of row.figures; track figure.label) {
                    <span>{{ figure.count }} {{ figure.label }}</span>
                  }
                </span>
              </button>
            }
          </div>
        }

        @if (canManage()) {
          <h3 class="fm-section-title">Game time</h3>
          <p class="hint">
            A time limit is required before kickoff. Overtime is optional; remove it for a game that ends at full time.
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

          <h3 class="fm-section-title">Referee</h3>
          <p class="hint">
            Every game needs a referee before kickoff. The referee scores this game; an admin can still score it too.
          </p>
          <div class="referees">
            @for (referee of fx.referees ?? []; track referee.id) {
              <div class="referee">
                <span>{{ referee.display_name || referee.email }}</span>
                <button type="button" (click)="removeReferee(referee.id)">Remove</button>
              </div>
            }
            <label>
              Add a referee
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

        @if (canScore() && fx.status !== 'completed' && fx.status !== 'cancelled') {
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

          @if (categories().length === 0) {
            <div class="fm-empty compact">
              <p>No scoring categories are configured for this competition yet.</p>
            </div>
          } @else {
            @for (side of fx.sides; track side.id) {
              <div class="fm-card scorer">
                <h4>{{ side.participant.short_name || side.participant.name }}</h4>
                @if (rosterFor(side).length) {
                  <p class="score-hint">Choose the profile. It is added to this match and to that profile.</p>
                  <div class="who">
                    <label>
                      Who
                      <select
                        [value]="scorerFor(side.id)"
                        (change)="setScorer(side.id, $any($event.target).value)"
                      >
                        <option value="">Choose a profile</option>
                        @for (member of rosterFor(side); track member.id) {
                          <option [value]="member.id">{{ member.name }}</option>
                        }
                      </select>
                    </label>
                    <label>
                      Rating this game
                      <input
                        type="number"
                        min="0"
                        max="10"
                        step="0.1"
                        placeholder="0–10"
                        [value]="ratingFor(side.id)"
                        (input)="setRating(side.id, $any($event.target).value)"
                      />
                    </label>
                  </div>
                }
                <div class="chips">
                  @for (category of categories(); track category.id) {
                    <button
                      type="button"
                      class="chip-button"
                      [disabled]="saving() || kickoffBlocked()"
                      (click)="record(side, category)"
                    >
                      <span class="label">{{ category.name }}</span>
                      @if (countsForOtherSide(category)) {
                        <span class="points">other side</span>
                      } @else if (category.affects_score) {
                        <span class="points">+{{ trim(category.points) }}</span>
                      }
                    </button>
                  }
                </div>
              </div>
            }
          }
        }

        <h3 class="fm-section-title">
          Timeline
          @if (fx.events.length) {
            <span class="count">{{ fx.events.length }}</span>
          }
        </h3>

        @if (fx.events.length === 0) {
          <div class="fm-empty compact">
            <p>Nothing has happened yet.</p>
          </div>
        } @else {
          <div class="fm-card timeline">
            @for (event of orderedEvents(); track event.id) {
              <div class="event">
                <span class="minute">
                  @if (event.minute !== null) {
                    {{ event.minute + "'" }}
                  } @else {
                    {{ event.created_at | date: 'HH:mm' }}
                  }
                </span>
                <span class="detail">
                  <strong>{{ participantName(event) }}</strong>
                  {{ event.scoring_category_name }}
                  @if (unitLabel(event); as unit) {
                    <span class="player">{{ unit }}</span>
                  }
                  @if (numeric(event.quantity) !== 1) {
                    <em>×{{ trim(event.quantity) }}</em>
                  }
                  @if (event.player_name) {
                    @if (event.player_user_id) {
                      <button
                        type="button"
                        class="player link"
                        (click)="openPlayer(event.player_user_id)"
                      >
                        {{ event.player_name }}
                      </button>
                    } @else {
                      <span class="player">{{ event.player_name }}</span>
                    }
                  }
                </span>
                <span class="points">{{ signed(event.points) }}</span>
                @if (canScore()) {
                  <button
                    type="button"
                    class="undo"
                    [disabled]="saving()"
                    (click)="removeEvent(event)"
                    aria-label="Remove event"
                  >
                    <ion-icon name="close-circle-outline" />
                  </button>
                }
              </div>
            }
          </div>

          <p class="updated">Last change {{ lastChangeAt() | relativeTime }}</p>
        }

        @if (fx.ratings.length) {
          <h3 class="fm-section-title">Ratings this game</h3>
          <div class="fm-card ratings">
            @for (rating of fx.ratings; track rating.id) {
              <button
                type="button"
                class="rating-row"
                [disabled]="!rating.player_user_id"
                (click)="openPlayer(rating.player_user_id)"
              >
                <span>{{ rating.player_name }}</span>
                <strong>{{ trim(rating.rating) }}</strong>
              </button>
            }
          </div>
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
  readonly clock = signal<MatchClock>({ running: false, elapsedMs: 0, runStartedAt: null });
  readonly unitIndex = signal(0);
  readonly scorers = signal<Record<string, string>>({});
  readonly gameRatings = signal<Record<string, string>>({});
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

    this.clock.set(readMatchClock(this.fixtureId));
    this.tickHandle = setInterval(() => this.now.set(Date.now()), 1000);

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
    return limits.overtime > 0
      ? `${limits.regulation} min + ${limits.overtime} overtime`
      : `${limits.regulation} min · no overtime`;
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

  inOvertime(): boolean {
    this.now();
    const limits = this.timeLimits();
    if (!limits || !this.showClock()) return false;
    const elapsed = this.displayedElapsed();
    return elapsed >= limits.regulation * 60_000 && elapsed < (limits.regulation + limits.overtime) * 60_000;
  }

  canEndGame(): boolean {
    const fixture = this.fixture();
    if (!fixture || !this.canScore()) return false;
    return fixture.status === 'live' || this.displayedElapsed() > 0 || this.clockRunning();
  }

  endGame(): void {
    this.pauseClock();
    this.setStatus('completed');
  }

  clockRunning(): boolean {
    return this.clock().running;
  }

  clockButtonLabel(): string {
    if (this.clockRunning()) return 'Pause';
    if (this.fixture()?.status === 'live' || this.displayedElapsed() > 0) return 'Resume';
    return 'Start';
  }

  clockLabel(): string {
    return formatClock(this.displayedElapsed());
  }

  /** Goals and cards take the minute showing on the match clock. */
  private clockMinute(category: ScoringCategory): number | null {
    if (!this.showClock() || !followsMatchClock(category)) return null;
    return Math.floor(this.displayedElapsed() / 60_000);
  }

  startOrPause(): void {
    if (this.clockRunning()) {
      this.pauseClock();
      return;
    }
    this.startClock();
  }

  private startClock(): void {
    const clock = this.clock();
    const next: MatchClock = {
      running: true,
      elapsedMs: clock.elapsedMs,
      runStartedAt: Date.now(),
    };
    this.clock.set(next);
    writeMatchClock(this.fixtureId, next);
    if (this.fixture()?.status === 'scheduled') {
      this.setStatus('live');
    }
  }

  private resetClock(): void {
    const empty: MatchClock = { running: false, elapsedMs: 0, runStartedAt: null };
    this.clock.set(empty);
    localStorage.removeItem(clockKey(this.fixtureId));
  }

  private pauseClock(): void {
    const next: MatchClock = {
      running: false,
      elapsedMs: this.displayedElapsed(),
      runStartedAt: null,
    };
    this.clock.set(next);
    writeMatchClock(this.fixtureId, next);
  }

  private displayedElapsed(): number {
    const clock = this.clock();
    if (!clock.running || clock.runStartedAt === null) return clock.elapsedMs;
    return clock.elapsedMs + Math.max(0, this.now() - clock.runStartedAt);
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);

    this.api.getCompetition(this.competitionId).subscribe({
      next: (competition) => {
        this.competition.set(competition);
        if (this.canManage()) this.ensureProfiles();
      },
      error: () => undefined,
    });

    this.api.getFixture(this.competitionId, this.fixtureId).subscribe({
      next: (fixture) => {
        if (fixture.status === 'scheduled') this.resetClock();
        this.fixture.set(fixture);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err));
        this.loading.set(false);
      },
    });
  }

  private reloadFixture(): void {
    this.api.getFixture(this.competitionId, this.fixtureId).subscribe({
      next: (fixture) => this.fixture.set(fixture),
      error: () => undefined,
    });
  }

  categories(): ScoringCategory[] {
    return this.competition()?.scoring_categories ?? [];
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
    const seen = new Map<string, number>();
    for (const block of structure) {
      if (!block || typeof block !== 'object') continue;
      const record = block as { unit?: string; count?: number; best_of?: number; repeat?: boolean };
      let count = Number(record.count || record.best_of || 1);
      if (record.repeat) count = Math.max(count, 3);
      const name = String(record.unit || 'unit').replaceAll('_', ' ');
      for (let offset = 0; offset < count; offset += 1) {
        const number = (seen.get(name) ?? 0) + 1;
        seen.set(name, number);
        slots.push({ index: slots.length, label: `${name} ${number}` });
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
        this.fixture.set(fixture);
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
        this.fixture.set(fixture);
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
    return `/tabs/competitions/${this.competitionId}?tab=fixtures`;
  }

  rosterFor(side: FixtureSide): RosterMember[] {
    return (
      this.competition()
        ?.participants.find((participant) => participant.id === side.participant.id)
        ?.roster.filter((member) => member.is_active) ?? []
    );
  }

  scorerFor(sideId: string): string {
    const chosen = this.scorers()[sideId];
    if (chosen) return chosen;
    const side = this.fixture()?.sides.find((item) => item.id === sideId);
    const roster = side ? this.rosterFor(side) : [];
    return roster.length === 1 ? roster[0].id : '';
  }

  ratingFor(sideId: string): string {
    return this.gameRatings()[sideId] ?? '';
  }

  setScorer(sideId: string, value: string): void {
    this.scorers.update((current) => ({ ...current, [sideId]: value }));
  }

  setRating(sideId: string, value: string): void {
    this.gameRatings.update((current) => ({ ...current, [sideId]: value }));
  }

  needsScorer(side: FixtureSide): boolean {
    return this.rosterFor(side).length > 0 && !this.scorerFor(side.id);
  }

  requiresProfile(category: ScoringCategory): boolean {
    const code = category.code.trim().toLowerCase();
    const name = category.name.trim().toLowerCase();
    return (
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
    );
  }

  matchStats(): Array<{
    key: string;
    name: string;
    team: string;
    userId: string | null;
    figures: Array<{ label: string; count: number }>;
  }> {
    const fixture = this.fixture();
    if (!fixture) return [];
    const grouped = new Map<
      string,
      { name: string; team: string; userId: string | null; counts: Map<string, number> }
    >();
    for (const event of fixture.events) {
      const key = event.player || event.player_name || event.id;
      const team = this.participantName(event);
      const current = grouped.get(key) ?? {
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

  async record(side: FixtureSide, category: ScoringCategory): Promise<void> {
    if (this.saving()) return;
    const roster = this.rosterFor(side);
    const playerId = this.scorerFor(side.id);
    if (this.requiresProfile(category) && !playerId) {
      await this.showToast(
        roster.length
          ? 'Choose the profile this applies to.'
          : 'Add a profile to this team first.',
        'danger',
      );
      return;
    }
    if (roster.length && !playerId) {
      await this.showToast('Choose the player first.', 'danger');
      return;
    }
    const rating = this.ratingFor(side.id).trim();
    if (rating) {
      const value = Number(rating);
      if (Number.isNaN(value) || value < 0 || value > 10) {
        await this.showToast('Rate this game from 0 to 10.', 'danger');
        return;
      }
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
    }
    if (rating) body['rating'] = Number(rating).toFixed(1);
    if (this.units().length) {
      body['unit_index'] = this.unitIndex();
      body['period'] = this.unitLabel({ unit_index: this.unitIndex() } as ScoreEvent);
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

  removeEvent(event: ScoreEvent): void {
    if (this.saving()) return;
    this.saving.set(true);

    this.api.deleteEvent(this.fixtureId, event.id).subscribe({
      next: () => {
        this.saving.set(false);
        this.reloadFixture();
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
      next: (fixture) => this.fixture.set(fixture),
      error: async (err: unknown) => {
        await this.showToast(extractErrorMessage(err, 'Could not change the status.'), 'danger');
      },
    });
  }

  private async showToast(message: string, color: string): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2600, position: 'bottom' });
    await toast.present();
  }

  orderedEvents(): ScoreEvent[] {
    return [...(this.fixture()?.events ?? [])].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
  }

  lastChangeAt(): string | null {
    return this.orderedEvents()[0]?.created_at ?? null;
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
}

function clockKey(fixtureId: string): string {
  return `fm.matchClock.${fixtureId}`;
}

function readMatchClock(fixtureId: string): MatchClock {
  const empty: MatchClock = { running: false, elapsedMs: 0, runStartedAt: null };
  try {
    const raw = localStorage.getItem(clockKey(fixtureId));
    if (!raw) return empty;
    const parsed = JSON.parse(raw) as Partial<MatchClock>;
    return {
      running: parsed.running === true,
      elapsedMs: typeof parsed.elapsedMs === 'number' ? parsed.elapsedMs : 0,
      runStartedAt: typeof parsed.runStartedAt === 'number' ? parsed.runStartedAt : null,
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
  return (
    code === 'goal' ||
    code === 'own-goal' ||
    code === 'yellow-card' ||
    code === 'red-card' ||
    code === 'touchdown' ||
    code === 'extra-point' ||
    code === 'two-point' ||
    code === 'safety' ||
    code === 'defensive-conversion' ||
    code === 'penalty' ||
    name === 'goal' ||
    name === 'own goal' ||
    name === 'yellow card' ||
    name === 'red card' ||
    name === 'touchdown' ||
    name === 'extra point' ||
    name === 'two-point conversion' ||
    name === 'safety' ||
    name === 'returned conversion' ||
    name === 'penalty'
  );
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
