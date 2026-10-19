import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';
import { IonIcon, ToastController } from '@ionic/angular/standalone';

import { AuthService } from '../../core/auth.service';
import { extractErrorMessage } from '../../core/error-message';
import type { FollowTarget, GamesFollow } from '../../core/games.service';
import { GamesService } from '../../core/games.service';

/** Follow an NOC, a sport or an athlete for start-time and result alerts. */
@Component({
  selector: 'fm-games-follow',
  standalone: true,
  imports: [IonIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (signedIn()) {
      <button
        type="button"
        class="follow"
        [class.on]="!!current()"
        [disabled]="busy()"
        [attr.aria-pressed]="!!current()"
        (click)="toggle()"
      >
        <ion-icon [name]="current() ? 'notifications' : 'notifications-outline'" aria-hidden="true" />
        {{ current() ? 'Following' : 'Follow' }}{{ label() ? ' ' + label() : '' }}
      </button>
    }
  `,
  styles: [
    `
      .follow {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        min-height: 34px;
        padding: 6px 14px;
        border: 1.5px solid var(--ion-color-primary);
        border-radius: 999px;
        background: transparent;
        color: var(--ion-color-primary);
        font: inherit;
        font-size: 0.82rem;
        font-weight: 700;
        cursor: pointer;
        transition: background 0.18s ease, color 0.18s ease;
      }
      .follow.on {
        background: var(--ion-color-primary);
        color: var(--ion-color-primary-contrast);
      }
      .follow:disabled {
        opacity: 0.6;
      }
    `,
  ],
})
export class GamesFollowComponent {
  private readonly service = inject(GamesService);
  private readonly auth = inject(AuthService);
  private readonly toasts = inject(ToastController);

  readonly gamesId = input.required<string>();
  readonly target = input.required<FollowTarget>();
  /** The NOC id, the athlete id, or the sport key. */
  readonly ref = input.required<string>();
  readonly label = input('');

  private readonly follows = signal<GamesFollow[]>([]);
  readonly busy = signal(false);
  readonly signedIn = computed(() => !!this.auth.getAccessToken());
  readonly current = computed(() =>
    this.follows().find((row) => {
      if (row.target !== this.target()) return false;
      if (row.target === 'noc') return row.noc_id === this.ref();
      if (row.target === 'athlete') return row.athlete_id === this.ref();
      return row.sport_key === this.ref();
    }),
  );

  ngOnInit(): void {
    if (!this.signedIn()) return;
    this.service.follows(this.gamesId()).subscribe({ next: (rows) => this.follows.set(rows) });
  }

  toggle(): void {
    const existing = this.current();
    this.busy.set(true);
    if (existing) {
      this.service.unfollow(this.gamesId(), existing.id).subscribe({
        next: () => {
          this.follows.update((rows) => rows.filter((row) => row.id !== existing.id));
          this.busy.set(false);
        },
        error: (err: unknown) => this.fail(err),
      });
      return;
    }
    const key = { noc: 'noc', athlete: 'athlete', sport: 'sport_key' }[this.target()];
    this.service.follow(this.gamesId(), { target: this.target(), [key]: this.ref() }).subscribe({
      next: async (row) => {
        this.follows.update((rows) => [...rows, row]);
        this.busy.set(false);
        const toast = await this.toasts.create({
          message: `Following ${row.label}: you'll get start-time and result alerts.`,
          color: 'success',
          duration: 2400,
          position: 'top',
        });
        await toast.present();
      },
      error: (err: unknown) => this.fail(err),
    });
  }

  private async fail(err: unknown): Promise<void> {
    this.busy.set(false);
    const toast = await this.toasts.create({
      message: extractErrorMessage(err, 'That did not save.'),
      color: 'danger',
      duration: 2400,
      position: 'top',
    });
    await toast.present();
  }
}
