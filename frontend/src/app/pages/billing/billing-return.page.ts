import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import {
  IonContent,
  IonHeader,
  IonSpinner,
  IonTitle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';

/** Return URL after a Paystack redirect checkout. Polls until paid, then opens Setup. */
@Component({
  selector: 'fm-billing-return',
  standalone: true,
  imports: [IonHeader, IonToolbar, IonTitle, IonContent, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-title>Confirming payment</ion-title>
      </ion-toolbar>
    </ion-header>
    <ion-content class="ion-padding">
      <div class="box">
        <ion-spinner name="crescent" />
        <p>{{ message() }}</p>
      </div>
    </ion-content>
  `,
  styles: `
    .box {
      display: grid;
      gap: 12px;
      place-items: center;
      min-height: 40vh;
      text-align: center;
      color: var(--ion-color-medium);
    }
  `,
})
export class BillingReturnPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastController);

  readonly message = signal('Confirming your Paystack payment…');

  ngOnInit(): void {
    const reference = this.route.snapshot.queryParamMap.get('reference') || '';
    const competitionId = this.route.snapshot.queryParamMap.get('competition') || '';
    if (!reference) {
      void this.fail('Missing payment reference.', competitionId);
      return;
    }
    void this.poll(reference, competitionId, 0);
  }

  private async poll(reference: string, competitionId: string, attempt: number): Promise<void> {
    this.api.getVisibilityCheckout(reference).subscribe({
      next: async (checkout) => {
        if (checkout.status === 'paid') {
          const toast = await this.toasts.create({
            message:
              checkout.kind === 'private'
                ? 'Private competition unlocked.'
                : 'Landing page placement unlocked.',
            color: 'success',
            duration: 2400,
          });
          await toast.present();
          const id = competitionId || checkout.competition;
          void this.router.navigate(['/tabs/competitions', id, 'setup'], { replaceUrl: true });
          return;
        }
        if (attempt >= 12) {
          await this.fail(
            'Payment is still pending. If you were charged, refresh Setup in a moment.',
            competitionId || checkout.competition,
          );
          return;
        }
        this.message.set('Waiting for Paystack to confirm…');
        setTimeout(() => void this.poll(reference, competitionId, attempt + 1), 1500);
      },
      error: async (err: unknown) => {
        await this.fail(
          extractErrorMessage(err, 'Could not confirm that payment.'),
          competitionId,
        );
      },
    });
  }

  private async fail(message: string, competitionId: string): Promise<void> {
    const toast = await this.toasts.create({ message, color: 'danger', duration: 3200 });
    await toast.present();
    if (competitionId) {
      void this.router.navigate(['/tabs/competitions', competitionId, 'setup'], { replaceUrl: true });
      return;
    }
    void this.router.navigateByUrl('/tabs/competitions', { replaceUrl: true });
  }
}
