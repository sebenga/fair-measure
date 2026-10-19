import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Router } from '@angular/router';
import { IonIcon, IonSpinner } from '@ionic/angular/standalone';

import { extractErrorMessage } from '../../core/error-message';
import type { PlayerStat, PlayerStats, TestSummary } from '../../core/scouting.models';
import { ScoutingService } from '../../core/scouting.service';

const PER: Record<string, string> = { match: 'total', '90min': 'per 90', game: 'per game' };

/** A player's Stats tab: season selector, stat cards with percentiles, charts and tests. */
@Component({
  selector: 'fm-player-stats',
  standalone: true,
  imports: [DatePipe, IonIcon, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './scouting.scss',
  template: `
    @if (loading() && !data()) {
      <div class="centered"><ion-spinner name="crescent" /></div>
    } @else if (error()) {
      <p class="lede">{{ error() }}</p>
    } @else if (data(); as d) {
      <div class="section filters">
        @if (d.sports.length > 1) {
          <div class="chips">
            @for (item of d.sports; track item.key) {
              <button type="button" class="chip" [class.on]="item.key === d.sport" (click)="choose({ sport: item.key, season: undefined, competition: undefined })">{{ item.label }}</button>
            }
          </div>
        }
        <div class="row">
          <label class="field">
            Season
            <select (change)="choose({ season: +$any($event.target).value })" [disabled]="!d.seasons.length">
              @for (year of d.seasons; track year) {
                <option [value]="year" [selected]="year === d.season">{{ year }}</option>
              } @empty {
                <option>{{ d.season }}</option>
              }
            </select>
          </label>
          <label class="field">
            Competition
            <select (change)="choose({ competition: $any($event.target).value })">
              <option value="" [selected]="!d.competition">All competitions</option>
              @for (row of d.competitions; track row.id) {
                <option [value]="row.id" [selected]="row.id === d.competition">{{ row.name }}</option>
              }
            </select>
          </label>
        </div>
      </div>

      <div class="summary section">
        <div><strong>{{ d.line.matches }}</strong><small>matches</small></div>
        <div><strong>{{ d.line.minutes }}</strong><small>minutes</small></div>
        <div><strong>{{ d.cohort }}</strong><small>in the comparison group</small></div>
      </div>
      @if (d.line.computed_at) {
        <p class="hint">Worked out {{ d.line.computed_at | date: 'd MMM, HH:mm' }} from confirmed results.</p>
      }

      @if (!d.line.matches) {
        <p class="lede">No confirmed matches for {{ sportLabel(d) }} in {{ d.season }} yet. Stats appear once scorers tag this player in completed fixtures.</p>
      } @else {
        <div class="stat-grid section">
          @for (row of shown(d); track row.key) {
            <button type="button" class="fm-card stat" [class.on]="chartKey() === row.key" (click)="chartKey.set(row.key)">
              <small>{{ row.label }}</small>
              <strong>{{ format(row.value) }}{{ row.unit === '%' ? '%' : '' }}</strong>
              <span class="meta">
                {{ perLabel(row) }}{{ row.per_match !== null && row.per !== '90min' ? ' · ' + format(row.per_match) + ' a match' : '' }}
              </span>
              @if (row.percentile !== null) {
                <span class="bar" [attr.aria-label]="row.percentile + 'th percentile'"><span [style.width.%]="row.percentile"></span></span>
                <span class="meta">{{ ordinal(row.percentile) }} percentile of {{ row.sample }}</span>
              } @else if (row.better && !d.competition) {
                <span class="meta muted">Percentile from {{ d.percentile_minimum }} players ({{ row.sample }} so far)</span>
              }
            </button>
          }
        </div>
      }

      @if (chart(d); as c) {
        <section class="fm-card section">
          <h3>{{ c.label }} by season</h3>
          <svg class="chart" [attr.viewBox]="'0 0 ' + c.width + ' 140'" role="img" [attr.aria-label]="c.label + ' by season'">
            @for (bar of c.bars; track bar.season) {
              <rect [attr.x]="bar.x" [attr.y]="bar.y" [attr.width]="bar.w" [attr.height]="bar.h" rx="4" />
              <text [attr.x]="bar.x + bar.w / 2" [attr.y]="bar.y - 4" text-anchor="middle" class="value">{{ format(bar.value) }}</text>
              <text [attr.x]="bar.x + bar.w / 2" y="136" text-anchor="middle">{{ bar.season }}</text>
            }
          </svg>
        </section>
      }

      <h3 class="fm-section-title">Physical tests</h3>
      @for (test of d.tests; track test.key) {
        <section class="fm-card section test">
          <header>
            <strong>{{ test.label }}</strong>
            <span class="badge">{{ test.better === 'lower' ? 'lower is better' : 'higher is better' }}</span>
          </header>
          <div class="test-row">
            <div>
              <small>Personal best</small>
              <strong>{{ format(test.personal_best.value) }} {{ test.unit }}</strong>
              <span class="badge" [class.ok]="test.personal_best.verified" [class.warn]="!test.personal_best.verified">{{ test.personal_best.label }}</span>
            </div>
            <div>
              <small>Latest · {{ test.latest.tested_on | date: 'd MMM y' }}</small>
              <strong>{{ format(test.latest.value) }} {{ test.unit }}</strong>
              <span class="badge" [class.ok]="test.latest.verified" [class.warn]="!test.latest.verified">{{ test.latest.label }}</span>
            </div>
            <div>
              <small>Trend</small>
              <strong>{{ trendLabel(test) }}</strong>
              @if (test.percentile !== null) {
                <span class="meta">{{ ordinal(test.percentile) }} percentile of {{ test.sample }}</span>
              } @else {
                <span class="meta muted">Percentile from {{ d.percentile_minimum }} players ({{ test.sample }} so far)</span>
              }
            </div>
          </div>
          @if (test.history.length > 1) {
            <svg class="spark" viewBox="0 0 300 60" role="img" [attr.aria-label]="test.label + ' results over time'">
              <polyline [attr.points]="spark(test)" />
              @for (point of sparkPoints(test); track $index) {
                <circle [attr.cx]="point.x" [attr.cy]="point.y" r="4" [class.self]="!point.verified" />
              }
            </svg>
          }
        </section>
      } @empty {
        <p class="lede">No physical tests recorded for {{ sportLabel(d) }} yet.</p>
      }

      @if (d.can_record_tests) {
        <div class="section">
          <button type="button" class="btn block" (click)="recordTest(d)">
            <ion-icon name="add-outline" aria-hidden="true" />
            Record a test result
          </button>
        </div>
      }
    }
  `,
  styles: [
    `
      .filters .row {
        margin-top: 10px;
      }
      .summary {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 8px;
        text-align: center;
      }
      .summary strong {
        display: block;
        font-size: 1.3rem;
      }
      .summary small,
      .meta {
        color: var(--ion-color-medium);
        font-size: 0.75rem;
      }
      .muted {
        font-style: italic;
      }
      .stat-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
        gap: 8px;
      }
      .stat {
        display: grid;
        gap: 3px;
        padding: 12px;
        border: 1.5px solid transparent;
        color: var(--ion-text-color);
        font: inherit;
        text-align: left;
        cursor: pointer;
      }
      .stat.on {
        border-color: var(--ion-color-primary);
      }
      .stat strong {
        font-size: 1.35rem;
        font-variant-numeric: tabular-nums;
      }
      .bar {
        display: block;
        height: 6px;
        border-radius: 3px;
        background: var(--ion-color-light);
        overflow: hidden;
      }
      .bar span {
        display: block;
        height: 100%;
        background: var(--ion-color-primary);
      }
      .chart {
        width: 100%;
        height: 160px;
      }
      .chart rect {
        fill: var(--ion-color-primary);
      }
      .chart text {
        font-size: 11px;
        fill: var(--ion-color-medium);
      }
      .chart .value {
        fill: var(--ion-text-color);
        font-weight: 700;
      }
      .test header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
      }
      .test-row {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 8px;
      }
      .test-row div {
        display: grid;
        gap: 2px;
        align-content: start;
      }
      .test-row small {
        color: var(--ion-color-medium);
        font-size: 0.72rem;
      }
      .spark {
        width: 100%;
        height: 60px;
        margin-top: 8px;
      }
      .spark polyline {
        fill: none;
        stroke: var(--ion-color-primary);
        stroke-width: 2;
      }
      .spark circle {
        fill: var(--ion-color-primary);
      }
      .spark circle.self {
        fill: var(--ion-background-color, #fff);
        stroke: var(--ion-color-warning);
        stroke-width: 2;
      }
    `,
  ],
})
export class PlayerStatsComponent {
  private readonly scouting = inject(ScoutingService);
  private readonly router = inject(Router);

  readonly profileId = input.required<string>();
  readonly data = signal<PlayerStats | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly chartKey = signal('');
  private filters: { sport?: string; season?: number; competition?: string } = {};

  ngOnInit(): void {
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.scouting.profileStats(this.profileId(), this.filters).subscribe({
      next: (data) => {
        this.data.set(data);
        this.loading.set(false);
        const first = data.stats.find((row) => row.value !== null && data.history.length);
        if (!data.stats.some((row) => row.key === this.chartKey())) this.chartKey.set(first?.key ?? '');
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(extractErrorMessage(err, 'Stats are not available for this player.'));
      },
    });
  }

  choose(change: { sport?: string; season?: number; competition?: string }): void {
    const data = this.data();
    this.filters = {
      sport: change.sport ?? data?.sport,
      season: 'season' in change ? change.season : data?.season,
      competition: 'competition' in change ? change.competition || undefined : data?.competition ?? undefined,
    };
    this.load();
  }

  shown(data: PlayerStats): PlayerStat[] {
    return data.stats.filter((row) => row.value !== null);
  }

  sportLabel(data: PlayerStats): string {
    return data.sports.find((item) => item.key === data.sport)?.label ?? data.sport;
  }

  perLabel(row: PlayerStat): string {
    if (row.unit === '%') return 'rate';
    return PER[row.per] ?? row.per;
  }

  format(value: number | null): string {
    if (value === null || value === undefined) return '–';
    return Number.isInteger(value) ? String(value) : value.toFixed(value < 10 ? 2 : 1).replace(/\.?0+$/, '');
  }

  ordinal(value: number): string {
    const rounded = Math.round(value);
    const suffix = rounded % 100 >= 11 && rounded % 100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[rounded % 10] ?? 'th';
    return `${rounded}${suffix}`;
  }

  trendLabel(test: TestSummary): string {
    const labels: Record<string, string> = { improving: 'Improving', declining: 'Declining', steady: 'Steady' };
    return test.trend ? labels[test.trend] : 'One result';
  }

  readonly chart = (data: PlayerStats) => {
    const key = this.chartKey();
    const stat = data.stats.find((row) => row.key === key);
    if (!stat) return null;
    const points = data.history.map((row) => ({ season: row.season, value: row.values[key] ?? 0 }));
    if (!points.length) return null;
    const max = Math.max(...points.map((point) => point.value ?? 0), 1);
    const w = 44;
    const gap = 24;
    const width = Math.max(points.length * (w + gap) + gap, 200);
    return {
      label: stat.label,
      width,
      bars: points.map((point, index) => {
        const h = Math.max(((point.value ?? 0) / max) * 100, 2);
        return { season: point.season, value: point.value, x: gap + index * (w + gap), y: 118 - h, w, h };
      }),
    };
  };

  sparkPoints(test: TestSummary): Array<{ x: number; y: number; verified: boolean }> {
    const values = test.history.map((row) => row.value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    const step = test.history.length > 1 ? 280 / (test.history.length - 1) : 0;
    return test.history.map((row, index) => {
      // Higher on the chart is always better, so lower-is-better tests are flipped.
      const ratio = (row.value - min) / span;
      const good = test.better === 'lower' ? 1 - ratio : ratio;
      return { x: 10 + index * step, y: 50 - good * 40, verified: row.verified };
    });
  }

  spark(test: TestSummary): string {
    return this.sparkPoints(test)
      .map((point) => `${point.x},${point.y}`)
      .join(' ');
  }

  recordTest(data: PlayerStats): void {
    void this.router.navigate(['/tabs/scouting/record-test'], {
      queryParams: { profile: data.profile_id, sport: data.sport },
    });
  }
}
