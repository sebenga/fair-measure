import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AlertController, IonIcon, ToastController } from '@ionic/angular/standalone';

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';
import type { MatchRaters } from '../../core/models';
import { RealtimeService } from '../../core/realtime.service';

/** Appointed raters for one match, and the ratings they give each player. */
@Component({
  selector: 'fm-match-raters',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [IonIcon],
  template: `
    @if (data(); as d) {
      <h3 class="fm-section-title">
        Raters
        <span class="count">{{ d.raters.length }}</span>
      </h3>
      <div class="fm-card raters">
        @if (!d.enough) {
          <p class="warn">
            Appoint at least {{ d.minimum }} raters. A player's rating counts once {{ d.minimum }} raters have marked them.
          </p>
        } @else {
          <p class="hint">
            Rate each player from the stats recorded in this match. The match rating is the average of the raters' marks, shown once {{ d.minimum }} have rated them.
          </p>
        }

        @for (rater of d.raters; track rater.id) {
          <div class="rater">
            <ion-icon name="person-circle-outline" aria-hidden="true" />
            <span class="who">
              <strong>{{ rater.name }}</strong>
              <em>{{ rater.rated }} {{ rater.rated === 1 ? 'player' : 'players' }} rated</em>
            </span>
            @if (d.can_manage) {
              <button type="button" class="remove" [disabled]="busy()" (click)="confirmRemove(rater.user_id, rater.name)">
                Remove
              </button>
            }
          </div>
        } @empty {
          <p class="muted">No raters appointed yet.</p>
        }

        @if (d.can_manage) {
          <label class="field">
            Appoint a rater
            <input
              placeholder="Search profiles by name or email"
              [value]="query()"
              (input)="search($any($event.target).value)"
            />
          </label>
          <p class="hint">Active players in this competition cannot rate and are left out of the search.</p>
          @for (person of d.candidates; track person.id) {
            <button type="button" class="choice" [disabled]="busy()" (click)="appoint(person.id)">
              <strong>{{ person.name }}</strong>
              <em>{{ person.email }}</em>
            </button>
          } @empty {
            @if (query().trim()) {
              <p class="muted">No profiles match who are not playing.</p>
            }
          }
        }
      </div>

      @if (d.teams.length) {
        <h3 class="fm-section-title">Player ratings</h3>
        @if (d.is_rater && !d.can_rate) {
          <p class="note">
            @if (!d.enough) {
              Rating opens once {{ d.minimum }} raters are appointed.
            } @else {
              Rating opens at kickoff.
            }
          </p>
        }
        <div class="fm-team-columns" [class.many]="d.teams.length > 2">
          @for (team of d.teams; track team.side_id) {
            <div class="fm-card team">
              <span class="fm-team-head">{{ team.team }}</span>
              @for (player of team.players; track player.player_id) {
                <div class="player" [class.rated]="hasMark(player)">
                  <span class="name">
                    @if (player.number !== null) {
                      <span class="num">{{ player.number }}</span>
                    }
                    {{ player.name }}
                  </span>
                  <span class="avg" [class.pending]="!player.average">
                    @if (player.average) {
                      {{ player.average }}
                    } @else {
                      {{ player.count }}/{{ d.minimum }}
                    }
                  </span>
                  @if (context(player); as note) {
                    <p class="context">{{ note }}</p>
                  }
                  <p class="basis">Record player stats, then rate from them</p>
                  <dl class="sheet">
                    @for (stat of player.stats; track stat.code) {
                      @if (stat.kind === 'minutes' && d.can_record_stats) {
                        <label class="minutes">
                          <input
                            type="number"
                            min="0"
                            max="300"
                            inputmode="numeric"
                            [value]="stat.count"
                            [disabled]="busy()"
                            (change)="setMinutes(player.player_id, $any($event.target).value)"
                          />
                          <span>{{ stat.label }}</span>
                        </label>
                      } @else if (stat.editable && d.can_record_stats) {
                        <div class="step" [class.hot]="stat.recorded">
                          <button
                            type="button"
                            [disabled]="busy() || !stat.recorded"
                            [attr.aria-label]="'Remove one ' + stat.label + ' from ' + player.name"
                            (click)="adjust(player.player_id, stat.code, -1)"
                          >
                            −
                          </button>
                          <strong>{{ stat.count }}</strong>
                          <span>{{ stat.label }}</span>
                          <button
                            type="button"
                            [disabled]="busy()"
                            [attr.aria-label]="'Add one ' + stat.label + ' for ' + player.name"
                            (click)="adjust(player.player_id, stat.code, 1)"
                          >
                            +
                          </button>
                        </div>
                      } @else {
                        <div [class]="stat.kind ?? ''" [class.zero]="!stat.recorded" [class.hot]="stat.recorded">
                          <strong>{{ stat.count }}</strong>
                          <span>{{ stat.label }}</span>
                        </div>
                      }
                    } @empty {
                      <em>No player stats for this sport yet.</em>
                    }
                  </dl>
                  <div class="marks" role="radiogroup" [attr.aria-label]="'Rate ' + player.name + ' from these stats'">
                    @for (mark of scale; track mark) {
                      <button
                        type="button"
                        role="radio"
                        [class.on]="isMark(player, mark)"
                        [attr.aria-checked]="isMark(player, mark)"
                        [disabled]="busy() || !canMark(d)"
                        (click)="rate(player.player_id, mark)"
                      >
                        {{ mark }}
                      </button>
                    }
                  </div>
                </div>
              } @empty {
                <p class="muted">No players to rate.</p>
              }
            </div>
          }
        </div>
      }
    }
  `,
  styles: [
    `
      .raters {
        display: grid;
        gap: 10px;
        margin: 0 16px 16px;
        padding: 12px 14px;
      }
      .warn {
        margin: 0;
        padding: 8px 10px;
        border-radius: 10px;
        background: color-mix(in srgb, var(--ion-color-warning) 20%, transparent);
        font-size: 0.84rem;
      }
      .hint,
      .note {
        margin: 0;
        font-size: 0.78rem;
        color: var(--ion-color-medium);
      }
      .note {
        margin: -4px 20px 10px;
      }
      .muted {
        margin: 0;
        font-size: 0.85rem;
        color: var(--ion-color-medium);
      }
      .rater {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .rater ion-icon {
        font-size: 1.6rem;
        color: var(--ion-color-primary);
      }
      .who {
        flex: 1 1 auto;
        display: grid;
        min-width: 0;
      }
      .who em,
      .choice em {
        font-style: normal;
        font-size: 0.76rem;
        color: var(--ion-color-medium);
      }
      .remove {
        padding: 6px 10px;
        border: 0;
        border-radius: 999px;
        background: none;
        color: var(--ion-color-danger);
        font: inherit;
        font-size: 0.82rem;
        font-weight: 700;
        cursor: pointer;
      }
      .field {
        display: grid;
        gap: 4px;
        font-size: 0.75rem;
        font-weight: 650;
        color: var(--ion-color-medium);
      }
      .field input {
        width: 100%;
        min-height: 40px;
        padding: 6px 10px;
        border: 1px solid var(--ion-color-step-200, #d7d8da);
        border-radius: 10px;
        background: var(--ion-background-color, #fff);
        color: var(--ion-text-color);
        font: inherit;
        font-size: 0.9rem;
      }
      .choice {
        display: grid;
        gap: 2px;
        padding: 8px 12px;
        border: 0;
        border-radius: 10px;
        background: var(--ion-color-light);
        color: var(--ion-color-light-contrast);
        font: inherit;
        text-align: left;
        cursor: pointer;
      }
      .team {
        display: grid;
        gap: 6px;
        padding: 12px;
      }
      .player {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        align-items: center;
        gap: 6px 8px;
        padding: 10px 0;
        border-bottom: 1px solid var(--ion-color-step-50, #f4f5f7);
        font-size: 0.86rem;
      }
      .player:last-child {
        border-bottom: 0;
      }
      .context,
      .basis,
      .sheet,
      .marks {
        grid-column: 1 / -1;
      }
      .context {
        margin: 0;
        font-size: 0.72rem;
        font-weight: 700;
        color: var(--ion-color-primary);
      }
      .basis {
        margin: 2px 0 0;
        font-size: 0.68rem;
        font-weight: 650;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        color: var(--ion-color-medium);
      }
      .sheet {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(58px, 1fr));
        gap: 4px;
        margin: 0;
      }
      .sheet div {
        display: grid;
        justify-items: center;
        gap: 1px;
        padding: 6px 3px 5px;
        border-radius: 8px;
        background: var(--ion-color-light);
        color: var(--ion-color-light-contrast);
      }
      .sheet strong {
        font-size: 0.95rem;
        font-variant-numeric: tabular-nums;
        line-height: 1.1;
      }
      .sheet span {
        font-size: 0.6rem;
        font-weight: 700;
        text-align: center;
        line-height: 1.15;
      }
      .sheet .zero {
        opacity: 0.42;
      }
      .sheet .hot {
        box-shadow: inset 0 0 0 1px var(--ion-color-primary);
      }
      .sheet .card.hot {
        box-shadow: inset 0 0 0 1px var(--ion-color-warning);
      }
      .sheet .step,
      .sheet .minutes {
        display: grid;
        justify-items: center;
        gap: 2px;
        padding: 6px 3px 5px;
        border-radius: 8px;
        background: var(--ion-color-light);
        color: var(--ion-color-light-contrast);
      }
      .sheet .step {
        grid-template-columns: 1fr 1fr;
      }
      .sheet .step strong,
      .sheet .step span {
        grid-column: 1 / -1;
      }
      .sheet .step button {
        min-height: 28px;
        border: 0;
        border-radius: 6px;
        background: var(--ion-background-color, #fff);
        color: inherit;
        font: inherit;
        font-weight: 800;
        cursor: pointer;
      }
      .sheet .step button:disabled {
        opacity: 0.35;
        cursor: not-allowed;
      }
      .sheet .minutes input {
        width: 100%;
        min-height: 28px;
        padding: 0 4px;
        border: 1px solid var(--ion-color-step-200, #d7d8da);
        border-radius: 6px;
        background: var(--ion-background-color, #fff);
        color: inherit;
        font: inherit;
        font-weight: 800;
        font-variant-numeric: tabular-nums;
        text-align: center;
      }
      .sheet em {
        grid-column: 1 / -1;
        font-style: normal;
        font-size: 0.72rem;
        color: var(--ion-color-medium);
      }
      .marks {
        display: grid;
        grid-template-columns: repeat(6, minmax(0, 1fr));
        gap: 4px;
      }
      .marks button {
        min-height: 32px;
        padding: 0;
        border: 1px solid var(--ion-color-step-200, #d7d8da);
        border-radius: 8px;
        background: var(--ion-color-light);
        color: var(--ion-color-light-contrast);
        font: inherit;
        font-size: 0.78rem;
        font-weight: 800;
        font-variant-numeric: tabular-nums;
        cursor: pointer;
      }
      .marks button.on {
        border-color: var(--ion-color-primary);
        background: var(--ion-color-primary);
        color: var(--ion-color-primary-contrast);
      }
      .marks button:disabled {
        opacity: 0.45;
        cursor: not-allowed;
      }
      .num {
        display: inline-block;
        min-width: 20px;
        font-weight: 800;
        color: var(--ion-color-primary);
      }
      .avg {
        font-weight: 800;
        font-variant-numeric: tabular-nums;
      }
      .avg.pending {
        font-weight: 600;
        font-size: 0.74rem;
        color: var(--ion-color-medium);
      }
    `,
  ],
})
export class MatchRatersComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly realtime = inject(RealtimeService);
  private readonly alerts = inject(AlertController);
  private readonly toasts = inject(ToastController);
  private readonly destroyRef = inject(DestroyRef);

  readonly competitionId = input.required<string>();
  readonly fixtureId = input.required<string>();
  /** Emitted after ratings change so the page can refresh its own ratings list. */
  readonly changed = output<void>();

  readonly data = signal<MatchRaters | null>(null);
  readonly busy = signal(false);
  readonly query = signal('');
  readonly drafts = signal<Record<string, string>>({});
  readonly scale = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
  private searchTimer: ReturnType<typeof setTimeout> | undefined;

  ngOnInit(): void {
    this.load();
    this.realtime
      .onAny<{ fixture_id: string }>(['fixture.updated'])
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((message) => {
        if (message.payload.fixture_id === this.fixtureId() && !Object.keys(this.drafts()).length) this.load();
      });
    this.destroyRef.onDestroy(() => clearTimeout(this.searchTimer));
  }

  search(value: string): void {
    this.query.set(value);
    clearTimeout(this.searchTimer);
    this.searchTimer = setTimeout(() => this.load(), 250);
  }

  markFor(player: { player_id: string; mine: string | null }): string | null {
    return this.drafts()[player.player_id] ?? player.mine;
  }

  hasMark(player: { player_id: string; mine: string | null }): boolean {
    return this.markFor(player) != null && this.markFor(player) !== '';
  }

  isMark(player: { player_id: string; mine: string | null }, mark: number): boolean {
    const value = this.markFor(player);
    return value != null && value !== '' && Number(value) === mark;
  }

  context(player: { role: string; position: string; captain: boolean }): string {
    return [player.captain ? 'Captain' : '', player.role, player.position].filter(Boolean).join(' · ');
  }

  adjust(playerId: string, code: string, delta: number): void {
    if (!this.data()?.can_record_stats) return;
    this.run(
      this.api.recordPlayerStat(this.competitionId(), this.fixtureId(), { player: playerId, code, delta }),
      'Could not update that stat.',
    );
  }

  setMinutes(playerId: string, value: string): void {
    if (!this.data()?.can_record_stats) return;
    const minutes = Number(value);
    if (!Number.isInteger(minutes) || minutes < 0 || minutes > 300) {
      void this.toast('Minutes played must be a whole number.');
      return;
    }
    this.run(
      this.api.recordPlayerStat(this.competitionId(), this.fixtureId(), { player: playerId, minutes }),
      'Could not save minutes.',
    );
  }

  canMark(data: MatchRaters): boolean {
    const open = data.status === 'live' || data.status === 'completed' || data.status === 'forfeit';
    return data.can_rate || (data.can_manage && data.enough && open);
  }

  rate(playerId: string, mark: number): void {
    const data = this.data();
    if (!data || !this.canMark(data)) return;
    this.drafts.update((drafts) => ({ ...drafts, [playerId]: String(mark) }));
    this.run(
      this.api.submitRatings(this.competitionId(), this.fixtureId(), [{ player: playerId, rating: String(mark) }]),
      'Could not save that rating.',
      () => {
        this.drafts.update((drafts) => {
          const next = { ...drafts };
          delete next[playerId];
          return next;
        });
      },
    );
  }

  appoint(userId: string): void {
    this.run(this.api.appointRater(this.competitionId(), this.fixtureId(), userId), 'Could not appoint that rater.', () =>
      this.query.set(''),
    );
  }

  async confirmRemove(userId: string, name: string): Promise<void> {
    const alert = await this.alerts.create({
      header: 'Remove rater?',
      message: `${name}'s ratings for this match are removed too.`,
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        {
          text: 'Remove',
          role: 'destructive',
          handler: () =>
            this.run(this.api.removeRater(this.competitionId(), this.fixtureId(), userId), 'Could not remove that rater.'),
        },
      ],
    });
    await alert.present();
  }

  private run(
    request: ReturnType<ApiService['matchRaters']>,
    failure: string,
    done?: () => void,
  ): void {
    if (this.busy()) return;
    this.busy.set(true);
    request.subscribe({
      next: (data) => {
        this.busy.set(false);
        done?.();
        this.data.set(data);
        this.changed.emit();
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, failure));
      },
    });
  }

  private load(): void {
    this.api.matchRaters(this.competitionId(), this.fixtureId(), this.query()).subscribe({
      next: (data) => this.data.set(data),
      error: () => this.data.set(null),
    });
  }

  private async toast(message: string, color: 'danger' | 'success' = 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, duration: 2500, color });
    await toast.present();
  }
}
