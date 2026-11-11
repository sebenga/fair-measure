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
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { IonIcon } from '@ionic/angular/standalone';
import { catchError, forkJoin, interval, of } from 'rxjs';

import { ApiService } from '../../core/api.service';
import type { CompetitionDetail, Fixture, FixtureHighlight, Paginated, StandingsResponse } from '../../core/models';
import { RealtimeService } from '../../core/realtime.service';

interface TickerItem {
  key: string;
  tag: 'LIVE' | 'FT' | 'TOP';
  text: string;
}

interface Stat {
  key: string;
  label: string;
  value: number;
  live?: boolean;
}

/** Colours and icon per sport; anything else gets the club teal. */
const SPORT_LOOK: Record<string, { icon: string; from: string; to: string }> = {
  soccer: { icon: 'football-outline', from: '#15803d', to: '#052e16' },
  football: { icon: 'football-outline', from: '#15803d', to: '#052e16' },
  rugby: { icon: 'american-football-outline', from: '#b45309', to: '#2b1406' },
  basketball: { icon: 'basketball-outline', from: '#ea580c', to: '#2a1004' },
  netball: { icon: 'basketball-outline', from: '#be185d', to: '#2a0516' },
  tennis: { icon: 'tennisball-outline', from: '#65a30d', to: '#1a2e05' },
  cricket: { icon: 'baseball-outline', from: '#0f766e', to: '#04201d' },
  baseball: { icon: 'baseball-outline', from: '#1d4ed8', to: '#0b1640' },
  golf: { icon: 'golf-outline', from: '#16a34a', to: '#062a14' },
  athletics: { icon: 'stopwatch-outline', from: '#dc2626', to: '#2b0707' },
};
const DEFAULT_LOOK = { icon: 'trophy-outline', from: '#0f766e', to: '#04201d' };

const REFRESH_MS = 30_000;
const COUNT_MS = 700;
const FLASH_MS = 3200;
const HEADLINE_MS = 6000;

/**
 * The scoreboard band at the top of a competition: numbers that count up, one headline at a
 * time from goals and results, and a short notice when a live score changes.
 */
@Component({
  selector: 'fm-match-centre',
  standalone: true,
  imports: [IonIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section
      class="board"
      [style.--from]="look().from"
      [style.--to]="look().to"
      aria-label="Match centre"
    >
      <span class="stripes" aria-hidden="true"></span>
      <div class="top">
        <span class="crest" aria-hidden="true"><ion-icon [name]="look().icon" /></span>
        <div class="stats">
          @for (stat of stats(); track stat.key) {
            <div class="stat" [class.live]="stat.live && stat.value > 0">
              <strong>{{ shown()[stat.key] ?? 0 }}</strong>
              <span>{{ stat.label }}</span>
            </div>
          }
        </div>
      </div>
      @if (headline(); as item) {
        <div class="ticker" aria-label="Latest updates">
          @for (line of [item]; track line.key) {
            <span class="item">
              <b [class]="'tag ' + line.tag.toLowerCase()">{{ line.tag }}</b>
              <span class="text">{{ line.text }}</span>
            </span>
          }
        </div>
      }
      @if (flash(); as message) {
        <div class="flash" role="status" aria-live="polite">
          <span>{{ message }}</span>
        </div>
      }
    </section>
  `,
  styles: [
    `
      :host {
        display: block;
        margin: 10px 16px 0;
      }

      .board {
        position: relative;
        overflow: hidden;
        border-radius: 18px;
        color: #fff;
        background: linear-gradient(120deg, var(--from), var(--to));
        box-shadow: 0 8px 20px rgb(4 10 22 / 16%);
        animation: fade-in 0.4s ease-out backwards;
      }

      .stripes {
        position: absolute;
        inset: 0;
        background: repeating-linear-gradient(
          115deg,
          rgb(255 255 255 / 4%) 0 14px,
          transparent 14px 34px
        );
        pointer-events: none;
      }

      .top {
        position: relative;
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 14px 8px;
      }

      .crest {
        flex: 0 0 auto;
        display: grid;
        place-items: center;
        width: 40px;
        height: 40px;
        border-radius: 12px;
        background: rgb(255 255 255 / 14%);
        font-size: 1.4rem;
      }

      .stats {
        flex: 1 1 auto;
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(58px, 1fr));
        gap: 4px;
      }

      .stat {
        display: grid;
        justify-items: center;
        gap: 1px;
      }

      .stat strong {
        position: relative;
        font-size: 1.35rem;
        font-weight: 800;
        line-height: 1.1;
        font-variant-numeric: tabular-nums;
      }

      .stat span {
        font-size: 0.62rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        opacity: 0.85;
      }

      .stat.live strong::after {
        content: '';
        position: absolute;
        top: 3px;
        right: -10px;
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #f87171;
        animation: breathe 2.8s ease-in-out infinite;
      }

      .ticker {
        position: relative;
        display: flex;
        align-items: center;
        min-height: 32px;
        padding: 6px 14px 7px;
        background: rgb(0 0 0 / 20%);
      }

      .item {
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
        font-size: 0.82rem;
        font-weight: 600;
        animation: fade-in 0.6s ease-out backwards;
      }

      .text {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .tag {
        flex: 0 0 auto;
        padding: 1px 6px;
        border-radius: 5px;
        font-size: 0.62rem;
        font-weight: 800;
        letter-spacing: 0.06em;
        background: rgb(255 255 255 / 20%);
      }

      .tag.live {
        background: #dc2626;
      }

      .tag.top {
        background: #ca8a04;
      }

      .flash {
        position: absolute;
        inset: 0;
        display: grid;
        place-items: center;
        background: rgb(0 0 0 / 28%);
        pointer-events: none;
        animation: flash 3.2s ease-in-out forwards;
      }

      .flash span {
        padding: 6px 16px;
        border-radius: 999px;
        background: #fff;
        color: var(--to);
        font-size: 1.05rem;
        font-weight: 800;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        box-shadow: 0 6px 18px rgb(0 0 0 / 22%);
      }

      @keyframes fade-in {
        from {
          opacity: 0;
        }
      }

      @keyframes breathe {
        50% {
          opacity: 0.4;
        }
      }

      @keyframes flash {
        0%,
        100% {
          opacity: 0;
        }
        15%,
        85% {
          opacity: 1;
        }
      }

      @media (prefers-reduced-motion: reduce) {
        .board,
        .item,
        .flash,
        .stat.live strong::after {
          animation: none;
        }
      }
    `,
  ],
})
export class MatchCentreComponent implements OnInit {
  readonly competition = input.required<CompetitionDetail>();

  private readonly api = inject(ApiService);
  private readonly realtime = inject(RealtimeService);
  private readonly destroyRef = inject(DestroyRef);

  private readonly live = signal<Fixture[]>([]);
  private readonly recent = signal<Fixture[]>([]);
  private readonly played = signal(0);
  private readonly toPlay = signal(0);
  private readonly leader = signal<{ name: string; points: string } | null>(null);
  readonly flash = signal<string | null>(null);
  /** The numbers as drawn right now, rolling up towards the real values. */
  readonly shown = signal<Record<string, number>>({});

  private scores = new Map<string, number>();
  private flashTimer: ReturnType<typeof setTimeout> | undefined;
  private readonly calm =
    typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;

  readonly look = computed(() => {
    const sport = (this.competition().sport || '').toLowerCase();
    const key = Object.keys(SPORT_LOOK).find((name) => sport.includes(name));
    return key ? SPORT_LOOK[key] : DEFAULT_LOOK;
  });

  readonly stats = computed<Stat[]>(() => {
    const stats: Stat[] = [
      {
        key: 'teams',
        label: 'Entrants',
        value: this.competition().participants?.length ?? this.competition().participant_count ?? 0,
      },
    ];
    if (this.played() || this.toPlay() || this.live().length) {
      stats.push(
        { key: 'played', label: 'Played', value: this.played() },
        { key: 'live', label: 'Live', value: this.live().length, live: true },
        { key: 'toPlay', label: 'To play', value: this.toPlay() },
      );
    }
    return stats;
  });

  readonly ticker = computed<TickerItem[]>(() => {
    const items: TickerItem[] = [];
    for (const fixture of this.live()) {
      const moment = fixture.highlights?.at(-1);
      const score = this.scoreLine(fixture);
      items.push({
        key: `live-${fixture.id}`,
        tag: 'LIVE',
        text: moment
          ? [`${moment.minute !== null ? moment.minute + "' " : ''}${moment.label}`, moment.player_name, score]
              .filter(Boolean)
              .join(' · ')
          : score,
      });
    }
    const top = this.leader();
    if (top) {
      items.push({ key: 'top', tag: 'TOP', text: `${top.name} lead the table on ${top.points} pts` });
    }
    for (const fixture of this.recent()) {
      items.push({ key: `ft-${fixture.id}`, tag: 'FT', text: this.scoreLine(fixture) });
    }
    return items;
  });

  private readonly headlineIndex = signal(0);
  readonly headline = computed(() => {
    const items = this.ticker();
    return items.length ? items[this.headlineIndex() % items.length] : null;
  });

  ngOnInit(): void {
    interval(HEADLINE_MS)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => {
        if (document.visibilityState === 'visible' && this.ticker().length > 1) {
          this.headlineIndex.update((index) => index + 1);
        }
      });
    this.load();
    this.realtime
      .onAny([
        'score.recorded',
        'score.corrected',
        'score.removed',
        'fixture.live',
        'fixture.completed',
        'fixture.updated',
        'standings.updated',
      ])
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.load());
    interval(REFRESH_MS)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => {
        if (document.visibilityState === 'visible') this.load();
      });
    this.destroyRef.onDestroy(() => clearTimeout(this.flashTimer));
  }

  private load(): void {
    const id = this.competition().id;
    const none = of(null);
    forkJoin({
      live: this.api.listFixtures(id, { status: 'live', page_size: 10 }).pipe(catchError(() => none)),
      recent: this.api
        .listFixtures(id, { status: 'completed', ordering: '-scheduled_at', page_size: 5 })
        .pipe(catchError(() => none)),
      upcoming: this.api
        .listFixtures(id, { status: 'scheduled', page_size: 1 })
        .pipe(catchError(() => none)),
      table: this.api.getStandings(id).pipe(catchError(() => of(null as StandingsResponse | null))),
    }).subscribe(({ live, recent, upcoming, table }) => {
      const livePage = live as Paginated<Fixture> | null;
      const recentPage = recent as Paginated<Fixture> | null;
      const upcomingPage = upcoming as Paginated<Fixture> | null;
      if (livePage) {
        this.noticeGoals(livePage.results);
        this.live.set(livePage.results);
      }
      if (recentPage) {
        this.recent.set(recentPage.results);
        this.played.set(recentPage.count ?? recentPage.results.length);
      }
      if (upcomingPage) this.toPlay.set(upcomingPage.count ?? upcomingPage.results.length);
      const first = table?.rows?.[0];
      this.leader.set(
        first && Number(first.points) > 0
          ? {
              name: first.participant.short_name || first.participant.name,
              points: String(Number(first.points)),
            }
          : null,
      );
      this.rollNumbers();
    });
  }

  /** A live score that went up since the last look gets a moment on the board. */
  private noticeGoals(fixtures: Fixture[]): void {
    const first = this.scores.size === 0;
    for (const fixture of fixtures) {
      for (const side of fixture.sides) {
        const score = Number(side.score) || 0;
        const before = this.scores.get(side.id);
        this.scores.set(side.id, score);
        if (!first && before !== undefined && score > before) {
          const label = this.newestScore(fixture, side.id)?.label || 'Score';
          const team = side.participant.short_name || side.participant.name;
          this.showFlash(`${label}! ${team}`);
        }
      }
    }
  }

  /** Highlights come ordered by match minute, so the newest score is found by when it was recorded. */
  private newestScore(fixture: Fixture, sideId: string): FixtureHighlight | undefined {
    const scores = (fixture.highlights ?? []).filter((item) => item.kind === 'score' || item.kind === 'own_goal');
    const pool = scores.some((item) => item.side === sideId) ? scores.filter((item) => item.side === sideId) : scores;
    return pool.reduce<FixtureHighlight | undefined>(
      (newest, item) => (!newest || item.created_at > newest.created_at ? item : newest),
      undefined,
    );
  }

  private showFlash(message: string): void {
    clearTimeout(this.flashTimer);
    this.flash.set(null);
    queueMicrotask(() => this.flash.set(message));
    this.flashTimer = setTimeout(() => this.flash.set(null), FLASH_MS);
  }

  /** Counts each figure up from where it was to its new value. */
  private rollNumbers(): void {
    const targets = Object.fromEntries(this.stats().map((stat) => [stat.key, stat.value]));
    const start = { ...this.shown() };
    if (this.calm || typeof requestAnimationFrame !== 'function') {
      this.shown.set(targets);
      return;
    }
    const began = performance.now();
    const step = (now: number) => {
      const progress = Math.min(1, (now - began) / COUNT_MS);
      const eased = 1 - Math.pow(1 - progress, 3);
      const next: Record<string, number> = {};
      for (const [key, target] of Object.entries(targets)) {
        const from = start[key] ?? 0;
        next[key] = Math.round(from + (target - from) * eased);
      }
      this.shown.set(next);
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  private scoreLine(fixture: Fixture): string {
    const sides = [...fixture.sides].sort((a, b) => a.position - b.position);
    if (sides.length !== 2) return fixture.label;
    const name = (index: number) =>
      sides[index].participant.short_name || sides[index].participant.name;
    const score = (index: number) => String(Number(sides[index].score) || 0);
    return `${name(0)} ${score(0)}–${score(1)} ${name(1)}`;
  }
}
