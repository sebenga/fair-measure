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
import { ToastController } from '@ionic/angular/standalone';

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';
import type { FixtureAward } from '../../core/models';
import { RealtimeService } from '../../core/realtime.service';

/** The per-match awards a preset names (for example a best player and a best horse). */
@Component({
  selector: 'fm-match-awards',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (awards().length) {
      <h3 class="fm-section-title">Match awards</h3>
      <div class="fm-card awards">
        @for (award of awards(); track award.key) {
          <div class="award">
            <div class="head">
              <strong>{{ award.label }}</strong>
              @if (award.winner; as winner) {
                <span>
                  {{ winner.name }}
                  @if (award.kind === 'horse' && winner.player_name) {
                    <em>ridden by {{ winner.player_name }}</em>
                  } @else if (winner.team) {
                    <em>{{ winner.team }}</em>
                  }
                </span>
              } @else {
                <span class="none">Not given yet</span>
              }
            </div>
            @if (canAward()) {
              <div class="edit">
                @if (award.kind === 'horse') {
                  <input
                    [value]="draftName(award)"
                    placeholder="Horse's name"
                    [attr.aria-label]="award.label + ': name'"
                    (change)="setName(award.key, $event)"
                  />
                }
                <select
                  [attr.aria-label]="award.label + ': player'"
                  (change)="pick(award, value($event))"
                >
                  <option value="" [selected]="!award.winner?.player_id">
                    {{ award.kind === 'horse' ? 'Rider' : 'Choose a player' }}
                  </option>
                  @for (player of players(); track player.id) {
                    <option [value]="player.id" [selected]="award.winner?.player_id === player.id">
                      {{ player.name }} · {{ player.team }}
                    </option>
                  }
                </select>
                @if (award.kind === 'horse') {
                  <button type="button" [disabled]="busy()" (click)="saveHorse(award)">Save</button>
                }
                @if (award.winner) {
                  <button type="button" class="clear" [disabled]="busy()" (click)="clear(award)">Clear</button>
                }
              </div>
              @if (award.description) {
                <p class="note">{{ award.description }}</p>
              }
            }
          </div>
        }
      </div>
    }
  `,
  styles: [
    `
      .awards {
        display: grid;
        gap: 12px;
        margin: 0 16px 16px;
        padding: 12px 16px;
      }
      .head {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        font-size: 0.9rem;
      }
      .head em {
        display: block;
        font-style: normal;
        font-size: 0.75rem;
        color: var(--ion-color-medium);
        text-align: right;
      }
      .none {
        color: var(--ion-color-medium);
      }
      .edit {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 8px;
      }
      .edit input,
      .edit select {
        flex: 1 1 140px;
        padding: 6px 8px;
        border: 1px solid var(--ion-color-step-150, #dbe2ea);
        border-radius: 8px;
        background: var(--ion-background-color, #fff);
        color: var(--ion-text-color);
        font: inherit;
        font-size: 0.85rem;
      }
      .edit button {
        padding: 6px 12px;
        border: none;
        border-radius: 8px;
        background: var(--ion-color-primary);
        color: #fff;
        font-weight: 600;
        cursor: pointer;
      }
      .edit button.clear {
        background: transparent;
        color: var(--ion-color-danger);
      }
      .note {
        margin: 4px 0 0;
        font-size: 0.75rem;
        color: var(--ion-color-medium);
      }
    `,
  ],
})
export class MatchAwardsComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly realtime = inject(RealtimeService);
  private readonly toasts = inject(ToastController);
  private readonly destroyRef = inject(DestroyRef);

  readonly competitionId = input.required<string>();
  readonly fixtureId = input.required<string>();
  readonly players = input<Array<{ id: string; name: string; team: string }>>([]);

  readonly awards = signal<FixtureAward[]>([]);
  readonly canAward = signal(false);
  readonly busy = signal(false);
  readonly names = signal<Record<string, string>>({});
  readonly riders = signal<Record<string, string>>({});

  ngOnInit(): void {
    this.load();
    this.realtime
      .onAny<{ fixture_id: string }>(['fixture.updated'])
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((message) => {
        if (message.payload.fixture_id === this.fixtureId()) this.load();
      });
  }

  value(event: Event): string {
    return (event.target as HTMLInputElement | HTMLSelectElement).value.trim();
  }

  setName(key: string, event: Event): void {
    this.names.set({ ...this.names(), [key]: this.value(event) });
  }

  draftName(award: FixtureAward): string {
    return this.names()[award.key] ?? award.winner?.name ?? '';
  }

  pick(award: FixtureAward, playerId: string): void {
    if (award.kind === 'horse') {
      this.riders.set({ ...this.riders(), [award.key]: playerId });
      return;
    }
    this.send(playerId ? { key: award.key, player: playerId } : { key: award.key });
  }

  saveHorse(award: FixtureAward): void {
    const name = this.draftName(award);
    if (!name) {
      void this.toast("Give the horse's name.");
      return;
    }
    const rider = this.riders()[award.key] ?? award.winner?.player_id ?? '';
    this.send({ key: award.key, name, ...(rider ? { player: rider } : {}) });
  }

  clear(award: FixtureAward): void {
    this.names.set({ ...this.names(), [award.key]: '' });
    this.send({ key: award.key });
  }

  private send(body: Record<string, unknown>): void {
    if (this.busy()) return;
    this.busy.set(true);
    this.api.setFixtureAward(this.competitionId(), this.fixtureId(), body).subscribe({
      next: (response) => {
        this.awards.set(response.awards);
        this.canAward.set(response.can_award);
        this.busy.set(false);
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not save that award.'));
      },
    });
  }

  private load(): void {
    this.api.fixtureAwards(this.competitionId(), this.fixtureId()).subscribe({
      next: (response) => {
        this.awards.set(response.awards);
        this.canAward.set(response.can_award);
      },
      error: () => this.awards.set([]),
    });
  }

  private async toast(message: string): Promise<void> {
    const toast = await this.toasts.create({ message, duration: 2500, color: 'danger' });
    await toast.present();
  }
}
