import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  inject,
  input,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { IonIcon } from '@ionic/angular/standalone';
import { interval } from 'rxjs';

import { ApiService } from '../core/api.service';
import type { CompetitionDetail, Fixture, MatchPhase } from '../core/models';
import { RealtimeService } from '../core/realtime.service';

/** Live events can be missed while the phone sleeps, so the strip also re-checks. */
const RECHECK_MS = 30_000;

const PHASE_SHORT: Partial<Record<MatchPhase, string>> = {
  first_half: '1st half',
  half_time: 'Half-time',
  second_half: '2nd half',
  extra_time: 'Extra time next',
  extra_first: 'Extra time',
  extra_half_time: 'ET half-time',
  extra_second: 'Extra time',
  penalties: 'Penalties',
};

/**
 * Every game in play, pinned under the competition's tabs so it is seen before any
 * scrolling. Shows nothing while no game is live.
 */
@Component({
  selector: 'fm-live-strip',
  standalone: true,
  imports: [IonIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (live().length) {
      <div class="strip" role="region" aria-label="Live games">
        @for (fixture of live(); track fixture.id) {
          <button type="button" class="game" (click)="open(fixture)">
            <span class="fm-live">Live</span>
            @if (fixture.sides.length === 2) {
              <span class="teams">
                <span class="name">{{ sideName(fixture, 0) }}</span>
                <strong class="score">{{ score(fixture, 0) }}–{{ score(fixture, 1) }}</strong>
                <span class="name">{{ sideName(fixture, 1) }}</span>
              </span>
            } @else {
              <span class="teams"><span class="name">{{ fixture.label }}</span></span>
            }
            @if (phase(fixture); as label) {
              <small class="phase">{{ label }}</small>
            }
            <ion-icon name="chevron-forward-outline" aria-hidden="true" />
          </button>
        }
      </div>
    }
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .strip {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        padding: 6px 12px 8px;
        scrollbar-width: none;
        -webkit-overflow-scrolling: touch;
      }

      .strip::-webkit-scrollbar {
        display: none;
      }

      .game {
        flex: 0 0 auto;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        max-width: min(92vw, 420px);
        padding: 8px 10px 8px 12px;
        border: 1px solid rgba(var(--ion-color-danger-rgb), 0.35);
        border-radius: 999px;
        background: rgba(var(--ion-color-danger-rgb), 0.08);
        color: var(--ion-text-color);
        font: inherit;
        cursor: pointer;
      }

      .game:only-child {
        flex: 1 1 auto;
        max-width: none;
      }

      .teams {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        min-width: 0;
        font-size: 0.92rem;
      }

      .name {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        max-width: 9.5em;
      }

      .score {
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
      }

      .phase {
        margin-left: auto;
        color: var(--ion-color-medium-shade);
        white-space: nowrap;
      }

      ion-icon {
        flex: 0 0 auto;
        color: var(--ion-color-medium);
      }
    `,
  ],
})
export class LiveStripComponent implements OnInit {
  readonly competition = input.required<CompetitionDetail>();

  private readonly api = inject(ApiService);
  private readonly realtime = inject(RealtimeService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  readonly live = signal<Fixture[]>([]);

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
      .subscribe(() => this.load());
    interval(RECHECK_MS)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => {
        if (document.visibilityState === 'visible') this.load();
      });
  }

  private load(): void {
    this.api.listFixtures(this.competition().id, { status: 'live', page_size: 20 }).subscribe({
      next: (page) => this.live.set(page.results),
      // A failed check keeps whatever was showing; the next event or re-check retries.
      error: () => undefined,
    });
  }

  sideName(fixture: Fixture, index: number): string {
    const side = [...fixture.sides].sort((a, b) => a.position - b.position)[index];
    return side?.participant?.short_name || side?.participant?.name || 'TBC';
  }

  score(fixture: Fixture, index: number): string {
    const side = [...fixture.sides].sort((a, b) => a.position - b.position)[index];
    const value = Number(side?.score ?? 0);
    return Number.isFinite(value) ? String(value) : String(side?.score ?? '0');
  }

  phase(fixture: Fixture): string {
    return (fixture.phase && PHASE_SHORT[fixture.phase]) || '';
  }

  open(fixture: Fixture): void {
    const competition = this.competition();
    const events = Boolean(competition.settings_json?.['result_type']);
    void this.router.navigate([
      '/tabs/competitions',
      competition.id,
      events ? 'events' : 'fixtures',
      fixture.id,
    ]);
  }
}
