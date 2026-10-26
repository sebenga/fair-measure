import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import {
  AlertController,
  IonBadge,
  IonButton,
  IonIcon,
  IonSegment,
  IonSegmentButton,
  IonLabel,
  ToastController,
} from '@ionic/angular/standalone';

import { ApiService } from '../../../core/api.service';
import { extractErrorMessage } from '../../../core/error-message';
import type { CompetitionDetail, Fixture, FixtureHighlight, MatchRating } from '../../../core/models';
import { RealtimeService } from '../../../core/realtime.service';
import { ResultsService } from '../../../core/results.service';
import { KnockoutTreeComponent } from './knockout-tree.component';

type Filter = 'upcoming' | 'results' | 'all';

const MAX_MOMENTS = 8;

interface FixtureGroup {
  key: string;
  label: string;
  fixtures: Fixture[];
}

@Component({
  selector: 'fm-competition-fixtures',
  standalone: true,
  imports: [
    DatePipe,
    IonIcon,
    IonButton,
    IonBadge,
    IonSegment,
    IonSegmentButton,
    IonLabel,
    KnockoutTreeComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (resultType() && canManage()) {
      <div class="event-bar">
        <button type="button" class="new-event" (click)="newEvent()">
          <ion-icon name="add-outline" aria-hidden="true" />
          New event
        </button>
        <span>Every active entrant is entered. Results are recorded on the event's page.</span>
      </div>
    }
    <div class="filter">
      <ion-segment [value]="filter()" (ionChange)="setFilter($any($event).detail.value)">
        <ion-segment-button value="upcoming"><ion-label>Upcoming</ion-label></ion-segment-button>
        <ion-segment-button value="results"><ion-label>Results</ion-label></ion-segment-button>
        <ion-segment-button value="all"><ion-label>All</ion-label></ion-segment-button>
      </ion-segment>
    </div>

    @if (structureLayout(); as layout) {
      @if (fixtures().length) {
        <fm-knockout-tree [fixtures]="fixtures()" [layout]="layout" (select)="openFixture($event)" />
      }
    }

    @if (loading()) {
      <div aria-busy="true" aria-label="Loading fixtures">
        @for (n of skeletons; track n) {
          <div class="fixture fm-card skeleton-card">
            <span class="fm-skeleton" style="width: 44px; height: 30px"></span>
            <span class="skeleton-lines">
              <span class="fm-skeleton" style="width: 70%"></span>
              <span class="fm-skeleton" style="width: 55%"></span>
            </span>
          </div>
        }
      </div>
    } @else if (error()) {
      <div class="fm-empty">
        <ion-icon name="alert-circle-outline" aria-hidden="true" />
        <h3>Fixtures unavailable</h3>
        <p>{{ error() }}</p>
        <ion-button fill="clear" (click)="load()">Try again</ion-button>
      </div>
    } @else if (groups().length === 0 && !(structureLayout() && fixtures().length)) {
      <div class="fm-empty">
        <ion-icon name="calendar-outline" aria-hidden="true" />
        <h3>{{ emptyTitle() }}</h3>
        <p>
          @if (canManage()) {
            Add participants, then generate a schedule from the setup screen.
          } @else {
            Nothing scheduled here yet.
          }
        </p>
        @if (canManage()) {
          <ion-button (click)="openSetup()">Open setup</ion-button>
        }
      </div>
    } @else {
      @for (group of groups(); track group.key) {
        <h3 class="fm-section-title">{{ group.label }}</h3>

        @for (fixture of group.fixtures; track fixture.id; let index = $index) {
          <button
            type="button"
            class="fixture fm-card fm-lift fm-enter"
            [class.is-live]="fixture.status === 'live'"
            [style.animation-delay.ms]="index * 50"
            (click)="openFixture(fixture)"
          >
            <div class="when">
              @if (fixture.status === 'live') {
                <span class="fm-live">Live</span>
              } @else if (fixture.scheduled_at) {
                <span class="time">{{ fixture.scheduled_at | date: 'HH:mm' }}</span>
              } @else {
                <span class="time tbd">TBD</span>
              }
              @if (fixture.round_number) {
                <span class="round">R{{ fixture.round_number }}</span>
              }
            </div>

            <div class="sides">
              @for (side of fixture.sides; track side.id) {
                <div class="side" [class.winner]="side.outcome === 'win'">
                  <span class="name">{{ side.participant.short_name || side.participant.name }}</span>
                  @if (side.forfeited) {
                    <ion-badge color="danger">FF</ion-badge>
                  }
                  <span class="score" [class.fm-bump]="bumped().has(side.id)">{{
                    showScores(fixture) ? trim(side.score) : '–'
                  }}</span>
                </div>
              }

              @if (highlightsFor(fixture); as moments) {
                @if (moments.shown.length) {
                  <ul class="moments" [attr.aria-label]="'Match events'">
                    @for (moment of moments.shown; track moment.id; let last = $last) {
                      <li
                        class="moment"
                        [class.away]="isAway(fixture, moment.side)"
                        [class.latest]="last && fixture.status === 'live' && moments.hidden === 0"
                      >
                        <span class="minute">{{ moment.minute !== null ? moment.minute + "'" : '' }}</span>
                        @switch (moment.kind) {
                          @case ('yellow') {
                            <span class="card yellow" aria-label="Yellow card"></span>
                          }
                          @case ('red') {
                            <span class="card red" aria-label="Red card"></span>
                          }
                          @case ('green') {
                            <span class="card green" aria-label="Green card"></span>
                          }
                          @default {
                            <ion-icon
                              class="ball"
                              [name]="isGoal(moment) ? 'football-outline' : 'ellipse'"
                              [attr.aria-label]="moment.label"
                            />
                          }
                        }
                        <span class="who">
                          {{ moment.player_name || moment.label }}
                          @if (moment.kind === 'own_goal') {
                            <em>(OG)</em>
                          } @else if (moment.kind === 'score' && !isGoal(moment) && moment.player_name) {
                            <em>{{ moment.label }}</em>
                          }
                        </span>
                      </li>
                    }
                  </ul>
                  @if (moments.hidden) {
                    <p class="more">+{{ moments.hidden }} more</p>
                  }
                }
              }
              @if (ratingsFor(fixture); as rates) {
                @if (rates.length) {
                  <p class="rates">
                    @for (row of rates; track row.id) {
                      <span>{{ row.player_name }} {{ row.rating }}</span>
                    }
                  </p>
                }
              }
            </div>

            <ion-icon name="chevron-forward-outline" class="chevron" aria-hidden="true" />
          </button>
        }
      }

      <div class="tail"></div>
    }
  `,
  styles: [
    `
      .event-bar {
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 12px 16px 0;
        font-size: 0.8rem;
        color: var(--ion-color-medium);
      }

      .new-event {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        flex: 0 0 auto;
        min-height: 40px;
        padding: 8px 16px;
        border: 0;
        border-radius: 999px;
        background: var(--ion-color-primary);
        color: var(--ion-color-primary-contrast);
        font: inherit;
        font-weight: 700;
        cursor: pointer;
      }

      .filter {
        padding: 12px 16px 4px;
      }

      .skeleton-card {
        display: flex;
        gap: 14px;
        align-items: center;
      }

      .skeleton-lines {
        flex: 1;
        display: grid;
        gap: 8px;
      }

      .fixture.is-live {
        position: relative;
        box-shadow:
          var(--fm-shadow),
          inset 3px 0 0 var(--ion-color-danger);
      }

      .fixture.is-live::after {
        content: '';
        position: absolute;
        inset: 0;
        border-radius: inherit;
        pointer-events: none;
        animation: fm-ring 2.2s ease-out infinite;
      }

      .fixture {
        display: flex;
        align-items: center;
        gap: 12px;
        width: calc(100% - 32px);
        margin: 8px 16px;
        padding: 12px 14px;
        border: none;
        text-align: left;
        cursor: pointer;
        background: var(--ion-card-background, #fff);
      }

      .when {
        flex: 0 0 auto;
        width: 52px;
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 4px;

        .time {
          font-size: 0.9rem;
          font-weight: 650;
          font-variant-numeric: tabular-nums;
        }

        .time.tbd {
          color: var(--ion-color-medium);
          font-weight: 500;
        }

        .round {
          font-size: 0.65rem;
          color: var(--ion-color-medium);
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
      }

      .sides {
        flex: 1 1 auto;
        min-width: 0;
        display: grid;
        gap: 4px;
      }

      .side {
        display: flex;
        align-items: center;
        gap: 8px;

        .name {
          flex: 1 1 auto;
          min-width: 0;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          font-size: 0.92rem;
          color: var(--ion-color-medium-shade);
        }

        .score {
          flex: 0 0 auto;
          font-size: 0.95rem;
          font-weight: 600;
          font-variant-numeric: tabular-nums;
          color: var(--ion-color-medium);
        }

        ion-badge {
          font-size: 0.6rem;
        }
      }

      .side.winner {
        .name,
        .score {
          color: var(--ion-text-color);
          font-weight: 700;
        }
      }

      .chevron {
        flex: 0 0 auto;
        color: var(--ion-color-medium);
      }

      .moments {
        display: grid;
        gap: 3px;
        margin: 6px 0 0;
        padding: 6px 0 0;
        border-top: 1px solid var(--ion-color-step-100, #eef0f2);
        list-style: none;
      }

      .moment {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 2px 6px;
        border-radius: 6px;
        font-size: 0.76rem;
        color: var(--ion-color-medium-shade);
        transition: background 0.3s ease;
      }

      .moment.away {
        flex-direction: row-reverse;
        text-align: right;
      }

      .moment.latest {
        background: rgba(var(--ion-color-success-rgb, 45, 211, 111), 0.12);
        color: var(--ion-text-color);
        font-weight: 650;
        animation: moment-in 0.6s ease-out;
      }

      .moment .minute {
        flex: 0 0 auto;
        min-width: 24px;
        font-variant-numeric: tabular-nums;
        color: var(--ion-color-medium);
      }

      .moment .ball {
        flex: 0 0 auto;
        font-size: 0.85rem;
      }

      .moment .card {
        flex: 0 0 auto;
        width: 8px;
        height: 11px;
        border-radius: 1.5px;
      }

      .card.yellow {
        background: #f5c400;
      }

      .card.red {
        background: #e0242e;
      }

      .card.green {
        background: #22a34a;
      }

      .moment .who {
        min-width: 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;

        em {
          font-style: normal;
          color: var(--ion-color-medium);
        }
      }

      .more {
        margin: 2px 6px 0;
        font-size: 0.72rem;
        color: var(--ion-color-medium);
      }

      .rates {
        display: flex;
        flex-wrap: wrap;
        gap: 4px 8px;
        margin: 4px 6px 0;
        font-size: 0.72rem;
        color: var(--ion-color-medium);
      }

      @keyframes moment-in {
        from {
          background: rgba(var(--ion-color-success-rgb, 45, 211, 111), 0.35);
        }
      }

      .tail {
        height: 32px;
      }
    `,
  ],
})
export class CompetitionFixturesComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly realtime = inject(RealtimeService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly results = inject(ResultsService);
  private readonly alerts = inject(AlertController);
  private readonly toasts = inject(ToastController);

  readonly competition = input.required<CompetitionDetail>();

  readonly fixtures = signal<Fixture[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly filter = signal<Filter>('upcoming');
  readonly skeletons = [0, 1, 2];
  /** Sides whose score just changed, so the number can pop. */
  readonly bumped = signal<Set<string>>(new Set());
  private lastScores = new Map<string, string>();
  private bumpTimer: ReturnType<typeof setTimeout> | undefined;

  isKnockout(): boolean {
    return this.competition().format === 'knockout';
  }

  structureLayout(): 'bracket' | 'rounds' | null {
    if (this.resultType()) return null;
    const format = this.competition().format;
    if (format === 'knockout') return 'bracket';
    if (format === 'league' || format === 'ladder' || format === 'group_knockout' || format === 'league_knockout') {
      return 'rounds';
    }
    return null;
  }

  readonly groups = computed<FixtureGroup[]>(() => {
    const filtered = this.fixtures().filter((fixture) => this.matchesFilter(fixture));
    const buckets = new Map<string, FixtureGroup>();

    for (const fixture of filtered) {
      const key = fixture.scheduled_at ? fixture.scheduled_at.slice(0, 10) : 'unscheduled';
      let bucket = buckets.get(key);
      if (!bucket) {
        bucket = { key, label: this.groupLabel(key, fixture), fixtures: [] };
        buckets.set(key, bucket);
      }
      bucket.fixtures.push(fixture);
    }

    const groups = [...buckets.values()];
    // Results read best newest-first; a schedule reads best soonest-first.
    const descending = this.filter() === 'results';
    groups.sort((a, b) => {
      if (a.key === 'unscheduled') return 1;
      if (b.key === 'unscheduled') return -1;
      return descending ? b.key.localeCompare(a.key) : a.key.localeCompare(b.key);
    });
    return groups;
  });

  ngOnInit(): void {
    if (this.isKnockout()) this.filter.set('all');
    this.load();

    this.realtime
      .onAny([
        'fixture.created',
        'fixture.updated',
        'fixture.deleted',
        'fixture.live',
        'fixture.completed',
        'fixtures.generated',
        'score.recorded',
        'score.corrected',
        'score.removed',
      ])
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.load(false));
  }

  load(showSpinner = true): void {
    if (showSpinner) this.loading.set(true);
    this.error.set(null);

    this.api.listFixtures(this.competition().id, { page_size: 200 }).subscribe({
      next: (page) => {
        this.noteScoreChanges(page.results);
        this.fixtures.set(page.results);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err));
        this.loading.set(false);
      },
    });
  }

  private noteScoreChanges(next: Fixture[]): void {
    const changed = new Set<string>();
    const scores = new Map<string, string>();
    for (const fixture of next) {
      for (const side of fixture.sides) {
        scores.set(side.id, side.score);
        const before = this.lastScores.get(side.id);
        if (before !== undefined && before !== side.score) changed.add(side.id);
      }
    }
    this.lastScores = scores;
    clearTimeout(this.bumpTimer);
    this.bumped.set(changed);
    if (changed.size) this.bumpTimer = setTimeout(() => this.bumped.set(new Set()), 1200);
  }

  setFilter(value: string | undefined): void {
    if (value === 'upcoming' || value === 'results' || value === 'all') {
      this.filter.set(value);
    }
  }

  private matchesFilter(fixture: Fixture): boolean {
    switch (this.filter()) {
      case 'upcoming':
        return ['scheduled', 'live', 'postponed'].includes(fixture.status);
      case 'results':
        return ['completed', 'forfeit'].includes(fixture.status);
      default:
        return true;
    }
  }

  private groupLabel(key: string, fixture: Fixture): string {
    if (key === 'unscheduled') {
      return fixture.round_number ? `Round ${fixture.round_number} · date TBD` : 'Date to be confirmed';
    }

    const date = new Date(`${key}T00:00:00`);
    const today = new Date();
    const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const dayDelta = Math.round((date.getTime() - startOfToday.getTime()) / 86_400_000);

    if (dayDelta === 0) return 'Today';
    if (dayDelta === 1) return 'Tomorrow';
    if (dayDelta === -1) return 'Yesterday';

    return date.toLocaleDateString(undefined, {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      ...(date.getFullYear() === today.getFullYear() ? {} : { year: 'numeric' }),
    });
  }

  highlightsFor(fixture: Fixture): { shown: FixtureHighlight[]; hidden: number } {
    const all = fixture.highlights ?? [];
    const shown = fixture.status === 'live' ? all.slice(-MAX_MOMENTS) : all.slice(0, MAX_MOMENTS);
    return { shown, hidden: all.length - shown.length };
  }

  isAway(fixture: Fixture, sideId: string): boolean {
    const side = fixture.sides.find((item) => item.id === sideId);
    return !!side && side.position > 0;
  }

  isGoal(moment: FixtureHighlight): boolean {
    return moment.kind === 'own_goal' || moment.label.trim().toLowerCase() === 'goal';
  }

  ratingsFor(fixture: Fixture): MatchRating[] {
    return [...(fixture.ratings ?? [])]
      .sort((left, right) => Number(right.rating) - Number(left.rating))
      .slice(0, 3);
  }

  showScores(fixture: Fixture): boolean {
    return ['live', 'completed', 'forfeit'].includes(fixture.status);
  }

  trim(value: string): string {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? String(parsed) : value;
  }

  emptyTitle(): string {
    switch (this.filter()) {
      case 'upcoming':
        return 'Nothing scheduled';
      case 'results':
        return 'No results yet';
      default:
        return 'No fixtures yet';
    }
  }

  canManage(): boolean {
    const role = this.competition().my_role;
    return role === 'owner' || role === 'admin';
  }

  openFixture(fixture: Fixture): void {
    void this.router.navigate([
      '/tabs/competitions',
      this.competition().id,
      this.resultType() ? 'events' : 'fixtures',
      fixture.id,
    ]);
  }

  /** Performance-result competitions run events (races, classes, rides) instead of matches. */
  resultType(): string | null {
    return (this.competition().settings_json?.['result_type'] as string | undefined) ?? null;
  }

  async newEvent(): Promise<void> {
    const alert = await this.alerts.create({
      header: 'New event',
      inputs: [{ name: 'label', type: 'text', placeholder: 'e.g. Race 3 or Class 1' }],
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        {
          text: 'Create',
          handler: (values: { label?: string }) => {
            const label = (values?.label ?? '').trim();
            if (!label) return false;
            this.results.createEvent(this.competition().id, { label }).subscribe({
              next: (sheet) =>
                void this.router.navigate(['/tabs/competitions', this.competition().id, 'events', sheet.fixture.id]),
              error: async (err: unknown) => {
                const toast = await this.toasts.create({
                  message: extractErrorMessage(err, 'Could not create the event.'),
                  color: 'danger',
                  duration: 2600,
                  position: 'top',
                });
                await toast.present();
              },
            });
            return true;
          },
        },
      ],
    });
    await alert.present();
  }

  openSetup(): void {
    void this.router.navigate(['/tabs/competitions', this.competition().id, 'setup']);
  }
}
