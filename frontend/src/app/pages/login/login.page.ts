import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { IonContent, IonIcon, IonSpinner } from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import { checkmarkCircle, eyeOffOutline, eyeOutline, logoGoogle } from 'ionicons/icons';

import { environment } from '../../../environments/environment';
import { AuthService } from '../../core/auth.service';
import { extractErrorMessage } from '../../core/error-message';

@Component({
  selector: 'fm-login',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, IonContent, IonIcon, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './login.page.scss',
  template: `
    <ion-content [fullscreen]="true">
      <div class="login-page">
        <div class="login-card">
          <aside class="brand" aria-hidden="false">
            <div class="brand-top">
              <span class="logo" aria-hidden="true"><span></span></span>
              <span class="wordmark">Fair Measure</span>
            </div>
            <div class="brand-copy">
              <h1>Welcome back to fair, transparent competition.</h1>
              <p>
                Sign in to run your leagues, enter scores and follow live results — from any
                device.
              </p>
            </div>
            <ul class="perks">
              <li>
                <ion-icon name="checkmark-circle" aria-hidden="true" />
                Your seasons, fixtures and squads — exactly as you left them
              </li>
              <li>
                <ion-icon name="checkmark-circle" aria-hidden="true" />
                Live score entry with instant league-table updates
              </li>
              <li>
                <ion-icon name="checkmark-circle" aria-hidden="true" />
                Stay signed in safely — no repeated logins on your own device
              </li>
            </ul>
          </aside>

          <section class="panel">
            <h2>Sign in</h2>
            <p class="lede">Good to see you again.</p>

            @if (error()) {
              <p class="error" role="alert">{{ error() }}</p>
            }

            <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
              <label class="field">
                Email
                <input
                  type="email"
                  inputmode="email"
                  autocomplete="email"
                  formControlName="email"
                  placeholder="alex@example.com"
                />
              </label>

              <label class="field">
                Password
                <span class="password-row">
                  <input
                    [type]="showPassword() ? 'text' : 'password'"
                    autocomplete="current-password"
                    formControlName="password"
                    placeholder="••••••••••••"
                  />
                  <button
                    type="button"
                    class="ghost"
                    [attr.aria-pressed]="showPassword()"
                    [attr.aria-label]="showPassword() ? 'Hide password' : 'Show password'"
                    (click)="togglePassword()"
                  >
                    <ion-icon
                      [name]="showPassword() ? 'eye-off-outline' : 'eye-outline'"
                      aria-hidden="true"
                    />
                  </button>
                </span>
              </label>

              <button type="button" class="link forgot" (click)="forgotPassword()">
                Forgot password?
              </button>

              <button type="submit" class="primary" [disabled]="loading()">
                @if (loading()) {
                  <ion-spinner name="crescent" />
                } @else {
                  Sign in
                }
              </button>
            </form>

            <div class="divider"><span>or</span></div>

            <button type="button" class="google" (click)="continueWithGoogle()" [disabled]="loading()">
              <ion-icon name="logo-google" aria-hidden="true" />
              Continue with Google
            </button>

            <p class="switch">
              New to Fair Measure?
              <a routerLink="/register">Create a free account</a>
            </p>
          </section>
        </div>
      </div>
    </ion-content>
  `,
})
export class LoginPage {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly showPassword = signal(false);
  readonly googleEnabled = Boolean(environment.googleClientId);

  readonly form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required]],
  });

  constructor() {
    addIcons({ checkmarkCircle, eyeOffOutline, eyeOutline, logoGoogle });
  }

  togglePassword(): void {
    this.showPassword.update((visible) => !visible);
  }

  forgotPassword(): void {
    this.error.set(
      'Password reset is not available yet. Try the email you registered with, or create a new account.',
    );
  }

  continueWithGoogle(): void {
    this.error.set(
      this.googleEnabled
        ? 'Google sign-in could not start. Try email and password.'
        : 'Google sign-in is not configured on this build. Use email and password.',
    );
  }

  submit(): void {
    if (this.loading()) return;
    if (this.form.invalid) {
      this.error.set('Enter the email and password for your account.');
      return;
    }

    this.loading.set(true);
    this.error.set(null);

    const { email, password } = this.form.getRawValue();
    this.auth.login(email.trim(), password).subscribe({
      next: () => {
        this.loading.set(false);
        const next = this.route.snapshot.queryParamMap.get('next');
        void this.router.navigateByUrl(next ?? '/tabs/competitions');
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(
          extractErrorMessage(err, 'That email and password do not match. Please try again, or reset your password below.'),
        );
      },
    });
  }
}
