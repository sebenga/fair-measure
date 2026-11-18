import { Injectable, inject } from '@angular/core';
import { AlertController } from '@ionic/angular/standalone';
import { firstValueFrom } from 'rxjs';

import { ApiService } from './api.service';
import { randAmount } from './commercial';
import type { BillingConfig, VisibilityCheckout, VisibilityCheckoutKind } from './models';

declare global {
  interface Window {
    PaystackPop?: {
      setup: (options: Record<string, unknown>) => { openIframe: () => void };
    };
  }
}

const SCRIPT_URL = 'https://js.paystack.co/v1/inline.js';

/**
 * Opens a payment checkout for a visibility upgrade.
 * Prefers Paystack popup when keys are set; otherwise shows the local stub popup.
 */
@Injectable({ providedIn: 'root' })
export class PaystackService {
  private readonly api = inject(ApiService);
  private readonly alerts = inject(AlertController);
  private scriptPromise: Promise<void> | null = null;
  private configPromise: Promise<BillingConfig> | null = null;

  config(): Promise<BillingConfig> {
    if (!this.configPromise) {
      this.configPromise = firstValueFrom(this.api.getBillingConfig()).catch(() => ({
        enabled: false,
        public_key: '',
        currency: 'ZAR',
        private_cents: 9900,
        landing_cents: 14900,
        gateway: 'paystack',
        stub: false,
      }));
    }
    return this.configPromise;
  }

  /** Drop cached config after env changes (local server restart). */
  refreshConfig(): void {
    this.configPromise = null;
  }

  async paymentsEnabled(): Promise<boolean> {
    const config = await this.config();
    return !!config.enabled;
  }

  async startCheckout(
    competitionId: string,
    kind: VisibilityCheckoutKind,
  ): Promise<'paid' | 'cancelled' | 'redirect'> {
    const checkout = await firstValueFrom(
      this.api.createVisibilityCheckout(competitionId, kind),
    );
    if (checkout.status === 'paid') {
      return 'paid';
    }
    if (checkout.stub || !(checkout.public_key || (await this.config()).public_key)) {
      return this.openStubCheckout(checkout);
    }
    return this.openPaystackCheckout(checkout);
  }

  private async openStubCheckout(
    checkout: VisibilityCheckout,
  ): Promise<'paid' | 'cancelled' | 'redirect'> {
    const label =
      checkout.kind === 'private' ? 'Private competition' : 'Landing page placement';
    const amount = randAmount(checkout.amount_cents);
    const alert = await this.alerts.create({
      header: 'Pay with Paystack (test)',
      subHeader: label,
      message: `Confirm ${amount} to unlock this. No card is charged in local stub mode.`,
      backdropDismiss: false,
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        { text: `Pay ${amount}`, role: 'confirm' },
      ],
    });
    await alert.present();
    const { role } = await alert.onDidDismiss();
    if (role !== 'confirm') {
      return 'cancelled';
    }
    await firstValueFrom(this.api.completeStubCheckout(checkout.reference));
    return 'paid';
  }

  private async openPaystackCheckout(
    checkout: VisibilityCheckout,
  ): Promise<'paid' | 'cancelled' | 'redirect'> {
    const publicKey = checkout.public_key || (await this.config()).public_key;
    if (!publicKey || !checkout.email) {
      if (checkout.authorization_url) {
        window.location.assign(checkout.authorization_url);
        return 'redirect';
      }
      throw new Error('Paystack is not ready for checkout.');
    }

    try {
      await this.loadScript();
    } catch {
      if (checkout.authorization_url) {
        window.location.assign(checkout.authorization_url);
        return 'redirect';
      }
      throw new Error('Could not load Paystack.');
    }

    return new Promise((resolve, reject) => {
      if (!window.PaystackPop) {
        if (checkout.authorization_url) {
          window.location.assign(checkout.authorization_url);
          resolve('redirect');
          return;
        }
        reject(new Error('Paystack popup is unavailable.'));
        return;
      }

      const handler = window.PaystackPop.setup({
        key: publicKey,
        email: checkout.email,
        amount: checkout.amount_cents,
        currency: checkout.currency || 'ZAR',
        ref: checkout.reference,
        callback: () => {
          void firstValueFrom(this.api.getVisibilityCheckout(checkout.reference))
            .then(() => resolve('paid'))
            .catch(() => resolve('paid'));
        },
        onClose: () => resolve('cancelled'),
      });
      handler.openIframe();
    });
  }

  private loadScript(): Promise<void> {
    if (window.PaystackPop) return Promise.resolve();
    if (this.scriptPromise) return this.scriptPromise;
    this.scriptPromise = new Promise((resolve, reject) => {
      const existing = document.querySelector<HTMLScriptElement>(`script[src="${SCRIPT_URL}"]`);
      if (existing) {
        existing.addEventListener('load', () => resolve());
        existing.addEventListener('error', () => reject(new Error('Paystack script failed.')));
        return;
      }
      const script = document.createElement('script');
      script.src = SCRIPT_URL;
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error('Paystack script failed.'));
      document.body.appendChild(script);
    });
    return this.scriptPromise;
  }
}
