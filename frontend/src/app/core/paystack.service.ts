import { Injectable, inject } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { ApiService } from './api.service';
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
 * Opens a Paystack checkout for a visibility upgrade. Prefers the inline popup;
 * falls back to a full-page redirect when the script cannot load.
 */
@Injectable({ providedIn: 'root' })
export class PaystackService {
  private readonly api = inject(ApiService);
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
      }));
    }
    return this.configPromise;
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
    return this.openCheckout(checkout);
  }

  async openCheckout(checkout: VisibilityCheckout): Promise<'paid' | 'cancelled' | 'redirect'> {
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
            .then((fresh) => resolve(fresh.status === 'paid' ? 'paid' : 'paid'))
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
