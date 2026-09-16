import { Injectable, inject, signal } from '@angular/core';
import { Capacitor } from '@capacitor/core';

import { environment } from '../../environments/environment';
import { ApiService } from './api.service';

const TOKEN_KEY = 'fm.push.token';

/**
 * Device registration for Firebase Cloud Messaging.
 *
 * Native builds go through Capacitor, which hands back an APNs/FCM token after
 * the OS permission prompt. The browser uses the Firebase JS SDK, which needs a
 * service worker at /firebase-messaging-sw.js and a VAPID key in the
 * environment. Either way, the token is POSTed to Django, which is the only
 * thing that ever talks to FCM's send API.
 */
@Injectable({ providedIn: 'root' })
export class PushService {
  private readonly api = inject(ApiService);

  readonly enabled = signal(Boolean(localStorage.getItem(TOKEN_KEY)));
  readonly busy = signal(false);

  supported(): boolean {
    if (Capacitor.isNativePlatform()) return true;
    return (
      'Notification' in globalThis &&
      'serviceWorker' in navigator &&
      Boolean(environment.firebase.apiKey)
    );
  }

  /** Returns a message to show the user, or null if nothing needs saying. */
  async enable(): Promise<string | null> {
    if (!this.supported()) {
      return 'Push notifications are not available here.';
    }

    this.busy.set(true);
    try {
      const token = Capacitor.isNativePlatform()
        ? await this.nativeToken()
        : await this.webToken();

      if (!token) {
        return 'Permission was declined, so notifications stay off.';
      }

      await this.register(token);
      return 'Push notifications are on.';
    } catch (error) {
      return error instanceof Error ? error.message : 'Could not turn on notifications.';
    } finally {
      this.busy.set(false);
    }
  }

  async disable(): Promise<string | null> {
    // The token stays valid with FCM; Django prunes it on the next failed send.
    // Clearing it locally is enough to stop this device asking again.
    localStorage.removeItem(TOKEN_KEY);
    this.enabled.set(false);
    return 'Push notifications are off.';
  }

  /** Re-register on launch so a rotated token never goes stale server-side. */
  async syncOnStartup(): Promise<void> {
    if (!this.enabled() || !this.supported()) return;

    try {
      const token = Capacitor.isNativePlatform()
        ? await this.nativeToken()
        : await this.webToken();
      if (token && token !== localStorage.getItem(TOKEN_KEY)) {
        await this.register(token);
      }
    } catch {
      // A failed refresh should never block app start.
    }
  }

  private async register(token: string): Promise<void> {
    const platform = Capacitor.isNativePlatform()
      ? (Capacitor.getPlatform() as 'ios' | 'android')
      : 'web';

    await new Promise<void>((resolve, reject) => {
      this.api.registerDevice(token, platform, navigator.userAgent.slice(0, 120)).subscribe({
        next: () => resolve(),
        error: (error: unknown) => reject(error),
      });
    });

    localStorage.setItem(TOKEN_KEY, token);
    this.enabled.set(true);
  }

  private async nativeToken(): Promise<string | null> {
    const { PushNotifications } = await import('@capacitor/push-notifications');

    let status = await PushNotifications.checkPermissions();
    if (status.receive === 'prompt' || status.receive === 'prompt-with-rationale') {
      status = await PushNotifications.requestPermissions();
    }
    if (status.receive !== 'granted') {
      return null;
    }

    return new Promise<string | null>((resolve) => {
      // `register` resolves before the OS delivers the token, so wait for the
      // event rather than the call, and give up rather than hang forever.
      const timeout = setTimeout(() => resolve(null), 15_000);

      void PushNotifications.addListener('registration', (token) => {
        clearTimeout(timeout);
        resolve(token.value);
      });
      void PushNotifications.addListener('registrationError', () => {
        clearTimeout(timeout);
        resolve(null);
      });
      void PushNotifications.register();
    });
  }

  private async webToken(): Promise<string | null> {
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') return null;

    const [{ initializeApp, getApps }, { getMessaging, getToken }] = await Promise.all([
      import('firebase/app'),
      import('firebase/messaging'),
    ]);

    const app = getApps()[0] ?? initializeApp(environment.firebase);
    const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js');

    return getToken(getMessaging(app), {
      vapidKey: environment.firebase.vapidKey,
      serviceWorkerRegistration: registration,
    });
  }
}
