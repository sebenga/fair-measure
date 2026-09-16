import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import {
  AlertController,
  IonAvatar,
  IonButton,
  IonContent,
  IonHeader,
  IonIcon,
  IonInput,
  IonItem,
  IonLabel,
  IonList,
  IonNote,
  IonSpinner,
  IonTextarea,
  IonTitle,
  IonToggle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';

import { AuthService } from '../../core/auth.service';
import { extractErrorMessage } from '../../core/error-message';
import { PushService } from '../../core/push.service';
import { RealtimeService } from '../../core/realtime.service';

@Component({
  selector: 'fm-profile',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    IonHeader,
    IonToolbar,
    IonTitle,
    IonContent,
    IonAvatar,
    IonList,
    IonItem,
    IonLabel,
    IonInput,
    IonTextarea,
    IonToggle,
    IonButton,
    IonIcon,
    IonNote,
    IonSpinner,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-header translucent="true">
      <ion-toolbar>
        <ion-title>Profile</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content fullscreen="true">
      <ion-header collapse="condense">
        <ion-toolbar>
          <ion-title size="large">Profile</ion-title>
        </ion-toolbar>
      </ion-header>

      @if (auth.user(); as user) {
        <div class="identity">
          <ion-avatar>
            @if (user.avatar_url) {
              <img [src]="user.avatar_url" [alt]="user.display_name" />
            } @else {
              <span class="initials">{{ initials(user.display_name) }}</span>
            }
          </ion-avatar>
          <h2>{{ user.display_name }}</h2>
          <p>{{ user.email }}</p>
        </div>

        <form [formGroup]="form" (ngSubmit)="save()">
          <ion-list inset="true">
            <ion-item>
              <ion-input
                label="Display name"
                labelPlacement="stacked"
                formControlName="display_name"
                maxlength="120"
              />
            </ion-item>
            <ion-item>
              <ion-textarea
                label="Bio"
                labelPlacement="stacked"
                formControlName="bio"
                autoGrow="true"
                rows="2"
                maxlength="500"
                placeholder="A line about you"
              />
            </ion-item>
            <ion-item>
              <ion-input
                label="Avatar URL"
                labelPlacement="stacked"
                formControlName="avatar_url"
                inputmode="url"
                placeholder="https://…"
              />
            </ion-item>
          </ion-list>

          @if (error()) {
            <p class="fm-form-error" role="alert">{{ error() }}</p>
          }

          <ion-button
            type="submit"
            expand="block"
            class="save"
            [disabled]="form.pristine || form.invalid || saving()"
          >
            @if (saving()) {
              <ion-spinner name="crescent" />
            } @else {
              Save changes
            }
          </ion-button>
        </form>

        <h3 class="fm-section-title">Notifications</h3>
        <ion-list inset="true">
          <ion-item>
            <ion-toggle
              [checked]="push.enabled()"
              [disabled]="!push.supported() || push.busy()"
              (ionChange)="togglePush($any($event).detail.checked)"
            >
              <ion-label>
                <h2>Push notifications</h2>
                <p>{{ pushDescription() }}</p>
              </ion-label>
            </ion-toggle>
          </ion-item>
        </ion-list>

        <h3 class="fm-section-title">Connection</h3>
        <ion-list inset="true">
          <ion-item lines="none">
            <ion-label>
              <h2>Live updates</h2>
              <p>{{ realtime.connected() ? 'Connected' : 'Offline' }}</p>
            </ion-label>
            <ion-icon
              slot="end"
              [name]="realtime.connected() ? 'ellipse' : 'ellipse-outline'"
              [color]="realtime.connected() ? 'success' : 'medium'"
              aria-hidden="true"
            />
          </ion-item>
        </ion-list>

        <ion-button expand="block" fill="clear" color="danger" (click)="confirmLogout()">
          Sign out
        </ion-button>

        <ion-note class="footnote">Member since {{ memberSince(user.date_joined) }}</ion-note>
      }
    </ion-content>
  `,
  styleUrl: './profile.page.scss',
})
export class ProfilePage implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly alerts = inject(AlertController);
  private readonly toasts = inject(ToastController);

  readonly auth = inject(AuthService);
  readonly realtime = inject(RealtimeService);
  readonly push = inject(PushService);

  readonly saving = signal(false);
  readonly error = signal<string | null>(null);

  readonly form = this.fb.nonNullable.group({
    display_name: ['', [Validators.required, Validators.maxLength(120)]],
    bio: [''],
    avatar_url: [''],
  });

  ngOnInit(): void {
    const user = this.auth.user();
    if (user) {
      this.form.patchValue({
        display_name: user.display_name,
        bio: user.bio,
        avatar_url: user.avatar_url,
      });
    }

    // The cached user may be stale after signing in on another device.
    this.auth.loadProfile().subscribe({
      next: (fresh) =>
        this.form.patchValue(
          {
            display_name: fresh.display_name,
            bio: fresh.bio,
            avatar_url: fresh.avatar_url,
          },
          { emitEvent: false },
        ),
      error: () => undefined,
    });
  }

  save(): void {
    if (this.form.invalid || this.saving()) return;

    this.saving.set(true);
    this.error.set(null);

    this.auth.updateProfile(this.form.getRawValue()).subscribe({
      next: async () => {
        this.saving.set(false);
        this.form.markAsPristine();
        await this.toast('Profile saved.', 'success');
      },
      error: (err: unknown) => {
        this.saving.set(false);
        this.error.set(extractErrorMessage(err, 'Could not save your profile.'));
      },
    });
  }

  async togglePush(enabled: boolean): Promise<void> {
    const message = enabled ? await this.push.enable() : await this.push.disable();
    if (message) {
      await this.toast(message, enabled ? 'success' : 'medium');
    }
  }

  pushDescription(): string {
    if (!this.push.supported()) {
      return 'Not available in this browser.';
    }
    return this.push.enabled()
      ? 'You will hear about goals, results, and mentions.'
      : 'Turn on to get match alerts.';
  }

  async confirmLogout(): Promise<void> {
    const alert = await this.alerts.create({
      header: 'Sign out?',
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        {
          text: 'Sign out',
          role: 'destructive',
          handler: () => {
            this.realtime.disconnect();
            this.auth.logout();
          },
        },
      ],
    });
    await alert.present();
  }

  initials(name: string): string {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((word) => word.charAt(0).toUpperCase())
      .join('');
  }

  memberSince(date: string): string {
    return new Date(date).toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
  }

  private async toast(message: string, color: string): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2400 });
    await toast.present();
  }
}
