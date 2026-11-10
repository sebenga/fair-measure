import { ChangeDetectionStrategy, Component, inject, input, signal } from '@angular/core';
import { AlertController, IonIcon, IonSpinner, ToastController } from '@ionic/angular/standalone';

import { extractErrorMessage } from '../core/error-message';
import { type FeatureKey, ReleasesService } from '../core/releases.service';

/**
 * Staff-only Active / Inactive control for one platform feature. It is the same
 * switch as Platform releases, so it changes the feature for every account.
 */
@Component({
  selector: 'fm-feature-switch',
  standalone: true,
  imports: [IonIcon, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="switch fm-card" [class.off]="!active()">
      <span class="icon"><ion-icon [name]="icon()" aria-hidden="true" /></span>
      <span class="copy">
        <strong>{{ label() }}</strong>
        <small>{{ active() ? 'Active for everyone' : 'Inactive: hidden for every account' }}</small>
      </span>
      <div class="choice" role="radiogroup" [attr.aria-label]="label() + ' status'">
        <button
          type="button"
          role="radio"
          class="on"
          [class.selected]="active()"
          [attr.aria-checked]="active()"
          [disabled]="busy()"
          (click)="set(true)"
        >
          @if (busy() && !active()) {
            <ion-spinner name="crescent" />
          } @else {
            Active
          }
        </button>
        <button
          type="button"
          role="radio"
          class="off"
          [class.selected]="!active()"
          [attr.aria-checked]="!active()"
          [disabled]="busy()"
          (click)="set(false)"
        >
          @if (busy() && active()) {
            <ion-spinner name="crescent" />
          } @else {
            Inactive
          }
        </button>
      </div>
    </section>
  `,
  styles: [
    `
      .switch {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 10px 12px;
        align-items: center;
        margin: 10px 16px 4px;
        padding: 14px 16px;
      }

      .icon {
        display: grid;
        place-items: center;
        width: 40px;
        height: 40px;
        border-radius: 12px;
        background: rgba(var(--ion-color-success-rgb), 0.14);
        color: var(--ion-color-success-shade);
        font-size: 20px;
      }

      .switch.off .icon {
        background: var(--ion-color-step-100, #eceff3);
        color: var(--ion-color-medium);
      }

      .copy {
        display: grid;
        gap: 2px;
      }

      .copy small {
        color: var(--ion-color-medium);
      }

      .choice {
        grid-column: 1 / -1;
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 4px;
        padding: 4px;
        border-radius: 12px;
        background: var(--ion-color-step-50, #f4f5f8);
      }

      .choice button {
        min-height: 38px;
        border: 0;
        border-radius: 9px;
        background: transparent;
        color: var(--ion-color-medium-shade);
        font: inherit;
        font-weight: 650;
        cursor: pointer;
      }

      .choice button.on.selected {
        background: var(--ion-color-success);
        color: var(--ion-color-success-contrast);
      }

      .choice button.off.selected {
        background: var(--ion-color-medium);
        color: var(--ion-color-medium-contrast);
      }

      .choice button:disabled {
        cursor: default;
      }

      ion-spinner {
        width: 18px;
        height: 18px;
      }
    `,
  ],
})
export class FeatureSwitchComponent {
  readonly feature = input.required<FeatureKey>();
  readonly label = input.required<string>();
  readonly icon = input('layers-outline');

  private readonly releases = inject(ReleasesService);
  private readonly alerts = inject(AlertController);
  private readonly toasts = inject(ToastController);

  readonly busy = signal(false);

  active(): boolean {
    return this.releases.isOpen(this.feature());
  }

  async set(live: boolean): Promise<void> {
    if (this.busy() || live === this.active()) return;
    const alert = await this.alerts.create({
      header: live ? `Make ${this.label()} active?` : `Make ${this.label()} inactive?`,
      message: live
        ? `${this.label()} becomes visible to every account.`
        : `${this.label()} is hidden for every account, yours included. Nothing is deleted.`,
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        { text: live ? 'Make active' : 'Make inactive', role: 'confirm' },
      ],
    });
    await alert.present();
    const { role } = await alert.onDidDismiss();
    if (role !== 'confirm') return;

    this.busy.set(true);
    this.releases.setLive('feature', [this.feature()], live).subscribe({
      next: async () => {
        await this.releases.refresh();
        this.busy.set(false);
        await this.toast(`${this.label()} is now ${live ? 'active' : 'inactive'}.`, 'success');
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, `Could not change ${this.label()}.`), 'danger');
      },
    });
  }

  private async toast(message: string, color: 'success' | 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2400 });
    await toast.present();
  }
}
