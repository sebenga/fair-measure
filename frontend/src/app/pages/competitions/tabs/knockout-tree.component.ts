import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, output, signal } from '@angular/core';
import { IonIcon } from '@ionic/angular/standalone';

import { ApiService } from '../../../core/api.service';
import type { Fixture, FixtureHighlight, FixtureSide, MatchRating } from '../../../core/models';

interface TreeSide {
  id: string;
  name: string;
  score: string;
  win: boolean;
  lose: boolean;
}

interface TreeMoment {
  id: string;
  away: boolean;
  minute: number | null;
  kind: string;
  label: string;
  player: string;
}

interface TreeTie {
  id: string;
  fixture: Fixture;
  done: boolean;
  live: boolean;
  sides: TreeSide[];
  moments: TreeMoment[];
  ratings: MatchRating[];
}

interface TreeRound {
  key: number;
  label: string;
  ties: TreeTie[];
}

@Component({
  selector: 'fm-knockout-tree',
  standalone: true,
  imports: [IonIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (rounds().length) {
      <section class="tree" [class.rounds]="layout() === 'rounds'" [attr.aria-label]="layout() === 'rounds' ? 'League structure' : 'Knockout structure'">
        @if (layout() === 'bracket' && champion(); as name) {
          <p class="banner">
            <ion-icon name="trophy-outline" aria-hidden="true" />
            <span>{{ name }} won the competition</span>
          </p>
        }
        <p class="hint">
          @if (layout() === 'rounds') {
            Each matchday: who scored, who was booked, and the match ratings.
          } @else {
            Scroll sideways to follow each round.
          }
        </p>
        <div class="scroll">
          @for (round of rounds(); track round.key) {
            <div class="col">
              <p class="label">{{ round.label }}</p>
              <div class="slots" [style.--count]="round.ties.length">
                @for (tie of round.ties; track tie.id) {
                  <button
                    type="button"
                    class="tie"
                    [class.done]="tie.done"
                    [class.live]="tie.live"
                    (click)="select.emit(tie.fixture)"
                  >
                    @for (side of tie.sides; track side.id) {
                      <span class="row" [class.win]="side.win" [class.lose]="side.lose">
                        <em>{{ side.name }}</em>
                        <b>{{ side.score }}</b>
                      </span>
                    }
                    @if (tie.moments.length) {
                      <ul class="moments" [attr.aria-label]="'Match events'">
                        @for (moment of tie.moments; track moment.id) {
                          <li [class.away]="moment.away">
                            <span class="min">{{ moment.minute !== null ? moment.minute + "'" : '' }}</span>
                            @if (moment.kind === 'yellow' || moment.kind === 'red' || moment.kind === 'green') {
                              <i class="card" [attr.data-kind]="moment.kind" [attr.aria-label]="moment.label"></i>
                            } @else {
                              <ion-icon name="football-outline" aria-hidden="true" />
                            }
                            <span class="who">{{ moment.player || moment.label }}</span>
                          </li>
                        }
                      </ul>
                    }
                    @if (tie.ratings.length) {
                      <p class="rates">
                        @for (row of tie.ratings; track row.id) {
                          <span>{{ row.player_name }} {{ row.rating }}</span>
                        }
                      </p>
                    }
                  </button>
                }
              </div>
            </div>
          }
          @if (layout() === 'bracket' && champion(); as name) {
            <div class="col champ">
              <p class="label">Champion</p>
              <div class="slots" style="--count: 1">
                <div class="crown">
                  <ion-icon name="trophy-outline" aria-hidden="true" />
                  <strong>{{ name }}</strong>
                </div>
              </div>
            </div>
          }
        </div>
      </section>
    }
  `,
  styles: [
    `
      .tree {
        margin: 8px 0 4px;
      }

      .banner {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 0 16px 8px;
        padding: 10px 14px;
        border-radius: 12px;
        background: color-mix(in srgb, var(--ion-color-warning) 16%, transparent);
        color: var(--ion-text-color);
        font-size: 0.9rem;
        font-weight: 650;
      }

      .banner ion-icon {
        color: var(--ion-color-warning-shade, #c08812);
        font-size: 1.2rem;
      }

      .hint {
        margin: 0 16px 6px;
        font-size: 0.75rem;
        color: var(--ion-color-medium);
      }

      .scroll {
        display: flex;
        align-items: stretch;
        gap: 0;
        overflow-x: auto;
        padding: 4px 16px 20px;
        scroll-snap-type: x proximity;
      }

      .col {
        flex: 0 0 220px;
        display: flex;
        flex-direction: column;
        scroll-snap-align: start;
      }

      .label {
        margin: 0 0 8px;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: var(--ion-color-medium);
      }

      .slots {
        flex: 1 1 auto;
        display: flex;
        flex-direction: column;
        justify-content: space-around;
        min-height: calc(var(--count, 1) * 148px);
      }

      .tie {
        position: relative;
        display: grid;
        width: calc(100% - 20px);
        margin: 8px 20px 8px 0;
        padding: 0;
        border: 1.5px solid var(--ion-color-step-150, #dbe2ea);
        border-radius: 10px;
        background: var(--ion-card-background, #fff);
        color: inherit;
        text-align: left;
        cursor: pointer;
        box-shadow: var(--fm-shadow, 0 1px 4px rgba(0, 0, 0, 0.06));
      }

      .tie.done {
        border-color: color-mix(in srgb, var(--ion-color-primary) 35%, var(--ion-color-step-150, #dbe2ea));
      }

      .tie.live {
        border-color: var(--ion-color-danger);
      }

      .tie::after {
        content: '';
        position: absolute;
        top: 50%;
        right: -20px;
        width: 20px;
        height: 2px;
        background: var(--ion-color-step-150, #dbe2ea);
      }

      .col:last-child .tie::after,
      .champ .crown::after {
        display: none;
      }

      .row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        padding: 8px 10px;
        min-height: 36px;
      }

      .row + .row {
        border-top: 1px solid var(--ion-color-step-100, #eef0f2);
      }

      .row em {
        min-width: 0;
        font-style: normal;
        font-size: 0.82rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        color: var(--ion-color-medium-shade);
      }

      .row b {
        flex: 0 0 auto;
        font-size: 0.85rem;
        font-variant-numeric: tabular-nums;
        color: var(--ion-color-medium);
      }

      .row.win em,
      .row.win b {
        color: var(--ion-text-color);
        font-weight: 750;
      }

      .row.lose em,
      .row.lose b {
        opacity: 0.55;
      }

      .crown {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        gap: 6px;
        width: calc(100% - 20px);
        margin: 8px 0;
        padding: 14px 12px;
        border-radius: 10px;
        background: color-mix(in srgb, var(--ion-color-warning) 14%, var(--ion-card-background, #fff));
      }

      .crown ion-icon {
        font-size: 1.3rem;
        color: var(--ion-color-warning-shade, #c08812);
      }

      .crown strong {
        font-size: 0.95rem;
      }

      .moments {
        list-style: none;
        margin: 0;
        padding: 4px 8px 8px;
        border-top: 1px solid var(--ion-color-step-100, #eef0f2);
      }

      .moments li {
        display: flex;
        align-items: center;
        gap: 5px;
        padding: 2px 0;
        font-size: 0.7rem;
        color: var(--ion-text-color);
      }

      .moments li.away {
        justify-content: flex-end;
        text-align: right;
      }

      .moments .min {
        flex: 0 0 22px;
        font-variant-numeric: tabular-nums;
        color: var(--ion-color-medium);
      }

      .moments li.away .min {
        order: 3;
        text-align: right;
      }

      .moments ion-icon {
        font-size: 0.85rem;
        color: var(--ion-color-medium-shade);
      }

      .moments .card {
        display: inline-block;
        width: 8px;
        height: 11px;
        border-radius: 1px;
        background: var(--ion-color-medium);
      }

      .moments .card[data-kind='yellow'] {
        background: #facc15;
      }

      .moments .card[data-kind='red'] {
        background: #dc2626;
      }

      .moments .who {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .rates {
        display: flex;
        flex-wrap: wrap;
        gap: 4px 8px;
        margin: 0;
        padding: 0 8px 8px;
        font-size: 0.68rem;
        color: var(--ion-color-medium);
      }

      .tree.rounds .tie::after {
        display: none;
      }

      .tree.rounds .col {
        flex-basis: 240px;
      }

      .tree.rounds .slots {
        justify-content: flex-start;
        gap: 10px;
        min-height: 0;
      }
    `,
  ],
})
export class KnockoutTreeComponent implements OnInit {
  private readonly api = inject(ApiService);

  readonly fixtures = input<Fixture[] | null>(null);
  readonly competitionId = input<string | null>(null);
  readonly layout = input<'bracket' | 'rounds'>('bracket');
  readonly select = output<Fixture>();

  readonly loaded = signal<Fixture[]>([]);

  readonly source = computed(() => this.fixtures() ?? this.loaded());

  readonly rounds = computed(() => {
    const grouped = new Map<number, Fixture[]>();
    for (const fixture of this.source()) {
      const key = fixture.round_number ?? 1;
      const list = grouped.get(key) ?? [];
      list.push(fixture);
      grouped.set(key, list);
    }
    return [...grouped.entries()]
      .sort((left, right) => left[0] - right[0])
      .map(([key, fixtures]) => ({
        key,
        label: this.layout() === 'rounds' ? matchdayLabel(fixtures, key) : roundLabel(fixtures.length, key),
        ties: fixtures.map((fixture) => this.asTie(fixture)),
      }));
  });

  readonly champion = computed(() => {
    const last = this.rounds().at(-1);
    if (!last || last.ties.length !== 1) return null;
    const tie = last.ties[0];
    if (!tie.done) return null;
    return tie.sides.find((side) => side.win)?.name ?? null;
  });

  ngOnInit(): void {
    const id = this.competitionId();
    if (this.fixtures() !== null || !id) return;
    this.api.listFixtures(id, { page_size: 200 }).subscribe({
      next: (page) => this.loaded.set(page.results),
    });
  }

  private asTie(fixture: Fixture): TreeTie {
    const sides = [...fixture.sides].sort((left, right) => left.position - right.position);
    const rows = sides.length
      ? sides.map((side) => this.asSide(side, fixture))
      : [{ id: `${fixture.id}-empty`, name: 'TBD', score: '', win: false, lose: false }];
    if (rows.length === 1) {
      rows.push({ id: `${fixture.id}-bye`, name: 'Bye', score: '', win: false, lose: true });
    }
    return {
      id: fixture.id,
      fixture,
      done: fixture.status === 'completed' || fixture.status === 'forfeit',
      live: fixture.status === 'live',
      sides: rows,
      moments: momentsFor(fixture),
      ratings: topRatings(fixture.ratings ?? []),
    };
  }

  private asSide(side: FixtureSide, fixture: Fixture): TreeSide {
    const decided = fixture.status === 'completed' || fixture.status === 'forfeit' || fixture.status === 'live';
    return {
      id: side.id,
      name: side.participant.short_name || side.participant.name,
      score: decided ? trimScore(side.score) : '',
      win: side.outcome === 'win',
      lose: side.outcome === 'loss',
    };
  }
}

function matchdayLabel(fixtures: Fixture[], round: number): string {
  const labels = new Set(fixtures.map((fixture) => fixture.label).filter(Boolean));
  if (labels.size === 1) return [...labels][0];
  return `Matchday ${round}`;
}

function roundLabel(ties: number, round: number): string {
  if (ties === 1) return 'Final';
  if (ties === 2) return 'Semi-finals';
  if (ties === 4) return 'Quarter-finals';
  if (ties === 8) return 'Round of 16';
  if (ties === 16) return 'Round of 32';
  return `Round ${round}`;
}

function trimScore(value: string): string {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? String(parsed) : value;
}

function momentsFor(fixture: Fixture): TreeMoment[] {
  const home = fixture.sides.find((side) => side.position === 0)?.id;
  return (fixture.highlights ?? []).map((item: FixtureHighlight) => ({
    id: item.id,
    away: !!home && item.side !== home,
    minute: item.minute,
    kind: item.kind,
    label: item.label,
    player: item.player_name,
  }));
}

function topRatings(ratings: MatchRating[]): MatchRating[] {
  return [...ratings]
    .sort((left, right) => Number(right.rating) - Number(left.rating))
    .slice(0, 3);
}
