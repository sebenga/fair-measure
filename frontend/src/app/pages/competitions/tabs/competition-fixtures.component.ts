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
  IonBadge,
  IonButton,
  IonIcon,
  IonSegment,
  IonSegmentButton,
  IonLabel,
  IonSpinner,
} from '@ionic/angular/standalone';

import { ApiService } from '../../../core/api.service';
import { extractErrorMessage } from '../../../core/error-message';
import type { CompetitionDetail, Fixture } from '../../../core/models';
import { RealtimeService } from '../../../core/realtime.service';

type Filter = 'upcoming' | 'results' | 'all';

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
    IonSpinner,
    IonIcon,
    IonButton,
    IonBadge,
    IonSegment,
    IonSegmentButton,
    IonLabel,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="filter">
      <ion-segment [value]="filter()" (ionChange)="setFilter($any($event).detail.value)">
        <ion-segment-button value="upcoming"><ion-label>Upcoming</ion-label></ion-segment-button>
        <ion-segment-button value="results"><ion-label>Results</ion-label></ion-segment-button>
        <ion-segment-button value="all"><ion-label>All</ion-label></ion-segment-button>
      </ion-segment>
    </div>

    @if (competition().format === 'knockout' && bracket().length) {
      <section class="bracket">
        <h3 class="fm-section-title">Bracket</h3>
        @for (round of bracket(); track round.round) {
          <div class="round">
            <p class="round-label">Round {{ round.round }}</p>
            @for (fixture of round.fixtures; track fixture.id) {
              <button type="button" class="tie" (click)="openFixture(fixture)">
                @for (side of fixture.sides; track side.id) {
                  <span [class.winner]="side.outcome === 'win'">
                    {{ side.participant.short_name || side.participant.name }}
                    <strong>{{ trim(side.score) }}</strong>
                  </span>
                }
              </button>
            }
          </div>
        }
      </section>
    }

    @if (loading()) {
      <div class="centered"><ion-spinner name="crescent" /></div>
    } @else if (error()) {
      <div class="fm-empty">
        <ion-icon name="alert-circle-outline" aria-hidden="true" />
        <h3>Fixtures unavailable</h3>
        <p>{{ error() }}</p>
        <ion-button fill="clear" (click)="load()">Try again</ion-button>
      </div>
    } @else if (groups().length === 0) {
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

        @for (fixture of group.fixtures; track fixture.id) {
          <button type="button" class="fixture fm-card" (click)="openFixture(fixture)">
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
                  <span class="score">{{ showScores(fixture) ? trim(side.score) : '–' }}</span>
                </div>
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
      .filter {
        padding: 12px 16px 4px;
      }

      .bracket {
        padding: 4px 16px 8px;
      }

      .round-label {
        margin: 8px 0 4px;
        color: var(--ion-color-medium);
        font-size: 0.8rem;
      }

      .tie {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        width: 100%;
        margin: 0 0 8px;
        padding: 10px 12px;
        border: 0;
        border-radius: 12px;
        background: var(--fm-surface, var(--ion-color-light));
        color: inherit;
        text-align: left;
      }

      .tie .winner {
        font-weight: 700;
      }

      .centered {
        display: grid;
        place-items: center;
        padding: 64px 0;
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

  readonly competition = input.required<CompetitionDetail>();

  readonly fixtures = signal<Fixture[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly filter = signal<Filter>('upcoming');

  readonly bracket = computed(() => {
    const rounds = new Map<number, Fixture[]>();
    for (const fixture of this.fixtures()) {
      const round = fixture.round_number ?? 1;
      const list = rounds.get(round) ?? [];
      list.push(fixture);
      rounds.set(round, list);
    }
    return [...rounds.entries()]
      .sort((left, right) => left[0] - right[0])
      .map(([round, fixtures]) => ({ round, fixtures }));
  });

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
        this.fixtures.set(page.results);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err));
        this.loading.set(false);
      },
    });
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
      'fixtures',
      fixture.id,
    ]);
  }

  openSetup(): void {
    void this.router.navigate(['/tabs/competitions', this.competition().id, 'setup']);
  }
}
