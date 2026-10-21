import { NgTemplateOutlet } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { IonIcon } from '@ionic/angular/standalone';

import { ApiService } from '../../core/api.service';
import type { FixtureDetail, ScoreEvent, ScoringCategory, SubstitutionRecord } from '../../core/models';
import { RealtimeService } from '../../core/realtime.service';
import { RelativeTimePipe } from '../../shared/relative-time.pipe';

interface Activity {
  id: string;
  side: number;
  minute: number | null;
  createdAt: string;
  kind: 'score' | 'yellow' | 'red' | 'card' | 'stat' | 'sub';
  title: string;
  player: string;
  playerUserId: string | null;
  /** The player coming off, for a substitution. */
  off: string;
  extra: string;
  points: string;
  /** Running score after a scoring event, e.g. "2–1". */
  score: string;
  event: ScoreEvent | null;
}

/** Live updates laid out by team: one column per side, the minute down the middle. */
@Component({
  selector: 'fm-fixture-timeline',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [IonIcon, NgTemplateOutlet, RelativeTimePipe],
  template: `
    @if (activity().length === 0) {
      <div class="fm-empty compact"><p>Nothing has happened yet.</p></div>
    } @else if (columns()) {
      <div class="fm-card board">
        <div class="heads">
          <span>{{ teamName(0) }}</span>
          <span></span>
          <span>{{ teamName(1) }}</span>
        </div>
        @for (item of activity(); track item.id) {
          <div class="row">
            <div class="cell home">
              @if (item.side === 0) {
                <ng-container *ngTemplateOutlet="entry; context: { $implicit: item }" />
              }
            </div>
            <div class="mid">
              <span class="min">{{ minuteLabel(item) }}</span>
              @if (item.score) {
                <span class="sc">{{ item.score }}</span>
              }
            </div>
            <div class="cell away">
              @if (item.side === 1) {
                <ng-container *ngTemplateOutlet="entry; context: { $implicit: item }" />
              }
            </div>
          </div>
        }
      </div>
    } @else {
      <div class="fm-card board single">
        @for (item of activity(); track item.id) {
          <div class="row">
            <div class="mid">
              <span class="min">{{ minuteLabel(item) }}</span>
            </div>
            <div class="cell">
              <span class="team">{{ teamName(item.side) }}</span>
              <ng-container *ngTemplateOutlet="entry; context: { $implicit: item }" />
            </div>
          </div>
        }
      </div>
    }

    <ng-template #entry let-item>
      <div class="entry" [attr.data-kind]="item.kind">
        <span class="badge" aria-hidden="true">
          @switch (item.kind) {
            @case ('score') {
              <ion-icon name="football-outline" />
            }
            @case ('sub') {
              <ion-icon name="swap-vertical-outline" />
            }
            @case ('stat') {
              <ion-icon name="stats-chart-outline" />
            }
            @default {
              <i class="card"></i>
            }
          }
        </span>
        <span class="text">
          <strong>{{ item.title }}</strong>
          @if (item.kind === 'sub') {
            <span class="on">↑ {{ item.player }}</span>
            <span class="off">↓ {{ item.off }}</span>
          } @else if (item.player) {
            @if (item.playerUserId) {
              <button type="button" class="link" (click)="openPlayer.emit(item.playerUserId)">{{ item.player }}</button>
            } @else {
              <span class="who">{{ item.player }}</span>
            }
          }
          @if (item.extra) {
            <em>{{ item.extra }}</em>
          }
        </span>
        @if (item.points) {
          <span class="pts">{{ item.points }}</span>
        }
        @if (canScore() && item.event) {
          <button
            type="button"
            class="undo"
            [disabled]="busy()"
            [attr.aria-label]="'Delete ' + item.title"
            (click)="remove.emit(item.event)"
          >
            <ion-icon name="trash-outline" />
          </button>
        }
      </div>
    </ng-template>

    @if (lastChange(); as at) {
      <p class="updated">Last change {{ at | relativeTime }}</p>
    }
  `,
  styles: [
    `
      .board {
        margin: 0 16px 8px;
        padding: 4px 0;
      }
      .heads {
        display: grid;
        grid-template-columns: 1fr 48px 1fr;
        gap: 6px;
        padding: 8px 12px;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: var(--ion-color-primary);
        border-bottom: 1px solid var(--ion-color-step-100, #eef0f3);
      }
      .heads span:first-child {
        text-align: right;
      }
      .row {
        display: grid;
        grid-template-columns: 1fr 48px 1fr;
        align-items: center;
        gap: 6px;
        padding: 8px 12px;
        border-bottom: 1px solid var(--ion-color-step-50, #f4f5f7);
      }
      .row:last-child {
        border-bottom: 0;
      }
      .single .row {
        grid-template-columns: 48px 1fr;
      }
      .mid {
        display: grid;
        justify-items: center;
        gap: 2px;
      }
      .min {
        font-size: 0.78rem;
        font-weight: 700;
        font-variant-numeric: tabular-nums;
        color: var(--ion-color-medium);
      }
      .sc {
        padding: 1px 6px;
        border-radius: 999px;
        background: var(--ion-color-primary);
        color: var(--ion-color-primary-contrast);
        font-size: 0.7rem;
        font-weight: 800;
        font-variant-numeric: tabular-nums;
      }
      .cell {
        min-width: 0;
      }
      .entry {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.84rem;
      }
      .home .entry {
        flex-direction: row-reverse;
        text-align: right;
      }
      .badge {
        flex: 0 0 auto;
        display: grid;
        place-items: center;
        width: 28px;
        height: 28px;
        border-radius: 50%;
        background: var(--ion-color-light);
        color: var(--ion-color-light-contrast);
        font-size: 0.95rem;
      }
      [data-kind='score'] .badge {
        background: color-mix(in srgb, var(--ion-color-success) 18%, transparent);
        color: var(--ion-color-success-shade);
      }
      [data-kind='sub'] .badge {
        background: color-mix(in srgb, var(--ion-color-secondary) 18%, transparent);
        color: var(--ion-color-secondary-shade);
      }
      .card {
        display: block;
        width: 10px;
        height: 14px;
        border-radius: 2px;
        background: var(--ion-color-medium);
      }
      [data-kind='yellow'] .card {
        background: #facc15;
      }
      [data-kind='red'] .card {
        background: #dc2626;
      }
      .text {
        display: grid;
        gap: 1px;
        min-width: 0;
        line-height: 1.3;
      }
      .text strong {
        font-weight: 700;
      }
      .text em,
      .who,
      .off {
        font-style: normal;
        font-size: 0.74rem;
        color: var(--ion-color-medium);
      }
      .on {
        font-size: 0.78rem;
        color: var(--ion-color-success-shade);
      }
      .link {
        padding: 0;
        border: 0;
        background: none;
        color: var(--ion-color-primary);
        font: inherit;
        font-size: 0.78rem;
        text-align: inherit;
        cursor: pointer;
      }
      .team {
        display: block;
        margin-bottom: 2px;
        font-size: 0.7rem;
        font-weight: 700;
        color: var(--ion-color-medium);
      }
      .pts {
        flex: 0 0 auto;
        font-weight: 800;
        font-size: 0.8rem;
        font-variant-numeric: tabular-nums;
      }
      .undo {
        flex: 0 0 auto;
        padding: 2px;
        border: 0;
        background: transparent;
        color: var(--ion-color-medium);
        cursor: pointer;
      }
      .undo ion-icon {
        display: block;
        font-size: 1.05rem;
      }
      .updated {
        margin: 6px 20px 40px;
        font-size: 0.74rem;
        color: var(--ion-color-medium);
      }
      @media (max-width: 380px) {
        .row,
        .heads {
          grid-template-columns: 1fr 40px 1fr;
          padding: 8px;
        }
        .badge {
          display: none;
        }
      }
    `,
  ],
})
export class FixtureTimelineComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly realtime = inject(RealtimeService);
  private readonly destroyRef = inject(DestroyRef);

  readonly fixture = input.required<FixtureDetail>();
  readonly competitionId = input.required<string>();
  readonly categories = input<ScoringCategory[]>([]);
  readonly statCodes = input<Set<string>>(new Set());
  readonly units = input<Array<{ index: number; label: string }>>([]);
  readonly canScore = input(false);
  readonly busy = input(false);
  readonly remove = output<ScoreEvent>();
  readonly openPlayer = output<string>();

  readonly substitutions = signal<SubstitutionRecord[]>([]);

  readonly columns = computed(() => this.fixture().sides.length === 2);

  readonly activity = computed<Activity[]>(() => {
    const fixture = this.fixture();
    const sideIndex = new Map(fixture.sides.map((side, index) => [side.id, index]));
    const categories = new Map(this.categories().map((category) => [category.id, category]));
    const units = new Map(this.units().map((unit) => [unit.index, unit.label]));
    const items: Activity[] = [];

    for (const event of fixture.events) {
      const category = categories.get(event.scoring_category);
      const code = (category?.code ?? '').toLowerCase();
      if (this.statCodes().has(category?.code ?? '') || this.statCodes().has(code)) continue;
      const points = Number(event.points);
      let kind: Activity['kind'] = 'stat';
      if (code.endsWith('-card')) {
        const colour = code.replace(/-card$/, '');
        kind = colour === 'yellow' || colour === 'red' ? colour : 'card';
      } else if (points !== 0 || category?.affects_score) {
        kind = 'score';
      }
      const extras = [
        event.unit_index !== null && event.unit_index !== undefined ? units.get(event.unit_index) ?? '' : '',
        Number(event.quantity) !== 1 ? `×${Number(event.quantity)}` : '',
      ].filter(Boolean);
      items.push({
        id: event.id,
        side: sideIndex.get(event.side) ?? 0,
        minute: event.minute,
        createdAt: event.created_at,
        kind,
        title: event.scoring_category_name,
        player: event.player_name,
        playerUserId: event.player_user_id,
        off: '',
        extra: extras.join(' · '),
        points: points === 0 ? '' : points > 0 ? `+${points}` : String(points),
        score: '',
        event,
      });
    }

    for (const sub of this.substitutions()) {
      items.push({
        id: `sub-${sub.id}`,
        side: sideIndex.get(sub.side_id) ?? 0,
        minute: sub.minute,
        createdAt: sub.created_at,
        kind: 'sub',
        title: 'Substitution',
        player: sub.player_on.name,
        playerUserId: sub.player_on.user_id,
        off: sub.player_off.name,
        extra: sub.reason === 'tactical' ? '' : sub.reason,
        points: '',
        score: '',
        event: null,
      });
    }

    // Running score, replayed oldest first. Shown only when the replay lands on the
    // scoreboard's final numbers, so set-based or unusual scoring never shows a wrong score.
    const chronological = [...items].sort((a, b) => a.createdAt.localeCompare(b.createdAt));
    if (this.columns()) {
      const totals = fixture.sides.map((side) => Number(side.head_start ?? 0) || 0);
      const scores = new Map<string, string>();
      for (const item of chronological) {
        if (!item.event) continue;
        const points = Number(item.event.points);
        if (!points) continue;
        const code = (categories.get(item.event.scoring_category)?.code ?? '').toLowerCase();
        const credited = code === 'own-goal' ? 1 - item.side : item.side;
        totals[credited] += points;
        scores.set(item.id, `${totals[0]}–${totals[1]}`);
      }
      const final = fixture.sides.map((side) => Number(side.score));
      if (totals[0] === final[0] && totals[1] === final[1]) {
        for (const item of chronological) item.score = scores.get(item.id) ?? '';
      }
    }

    return chronological.reverse();
  });

  readonly lastChange = computed(() => this.activity()[0]?.createdAt ?? null);

  ngOnInit(): void {
    this.loadSubstitutions();
    this.realtime
      .onAny<{ fixture_id: string }>(['fixture.updated'])
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((message) => {
        if (message.payload.fixture_id === this.fixture().id) this.loadSubstitutions();
      });
  }

  teamName(index: number): string {
    const side = this.fixture().sides[index];
    return side?.participant.short_name || side?.participant.name || '';
  }

  minuteLabel(item: Activity): string {
    if (item.minute !== null) return `${item.minute}'`;
    const at = new Date(item.createdAt);
    return `${String(at.getHours()).padStart(2, '0')}:${String(at.getMinutes()).padStart(2, '0')}`;
  }

  private loadSubstitutions(): void {
    this.api.teamSheets(this.competitionId(), this.fixture().id).subscribe({
      next: (day) => this.substitutions.set(day.substitutions ?? []),
      error: () => this.substitutions.set([]),
    });
  }
}
