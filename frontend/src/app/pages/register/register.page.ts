import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { IonContent, IonIcon, IonSpinner } from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import { arrowForwardOutline } from 'ionicons/icons';

import { AuthService } from '../../core/auth.service';
import { extractErrorMessage } from '../../core/error-message';
import { AuthShellComponent } from '../login/auth-shell.component';

@Component({
  selector: 'fm-register',
  standalone: true,
  imports: [ReactiveFormsModule, IonContent, IonIcon, IonSpinner, AuthShellComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'ion-page' },
  styleUrl: '../login/login.page.scss',
  template: `
    <ion-content [fullscreen]="true">
      <fm-auth-shell
        eyebrow="Join free"
        title="Join as a player, fan, or organiser."
        subtitle="From the township league to the provincial final and the office KPI cup: one account for the match, the conversation and the admin."
        [photos]="photos"
      >
        <h2>Create account</h2>
        <p class="lede">A minute to start. Use it for a club, a feed, or a workplace league.</p>

        @if (error()) {
          <p class="error" role="alert">{{ error() }}</p>
        }

        <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
          <label class="field">
            Name
            <input
              type="text"
              autocomplete="name"
              formControlName="displayName"
              placeholder="How should we call you?"
            />
          </label>
          <label class="field">
            Email
            <input
              type="email"
              inputmode="email"
              autocomplete="email"
              formControlName="email"
              placeholder="you@example.com"
            />
          </label>
          <label class="field">
            Password
            <input
              type="password"
              autocomplete="new-password"
              formControlName="password"
              placeholder="At least 8 characters"
            />
          </label>

          <p class="hint">Avoid anything too common or too close to your email.</p>

          <button type="submit" class="primary" [disabled]="loading()">
            @if (loading()) {
              <ion-spinner name="crescent" />
            } @else {
              Create account
              <ion-icon name="arrow-forward-outline" aria-hidden="true" />
            }
          </button>
        </form>

        <p class="switch">
          Already have an account?
          <button type="button" class="link" (click)="goLogin()">Sign in</button>
        </p>
      </fm-auth-shell>
    </ion-content>
  `,
})
export class RegisterPage {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly photos = [
    'assets/landing/hero.jpg',
    'assets/landing/gov-cleanup.jpg',
    'assets/landing/corp-kpi.jpg',
  ];

  constructor() {
    addIcons({ arrowForwardOutline });
  }

  readonly form = this.fb.nonNullable.group({
    displayName: ['', [Validators.required, Validators.maxLength(120)]],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8)]],
  });

  goLogin(): void {
    void this.router.navigateByUrl('/login', { replaceUrl: true });
  }

  submit(): void {
    if (this.form.invalid || this.loading()) {
      if (this.form.invalid) {
        this.error.set('Name, email and a password of at least 8 characters are required.');
      }
      return;
    }

    this.loading.set(true);
    this.error.set(null);

    const { email, password, displayName } = this.form.getRawValue();
    this.auth.register(email.trim(), password, displayName.trim()).subscribe({
      next: () => {
        this.loading.set(false);
        const next = this.route.snapshot.queryParamMap.get('next');
        void this.router.navigateByUrl(next ?? '/tabs/competitions', { replaceUrl: true });
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(extractErrorMessage(err, 'We could not create that account.'));
      },
    });
  }
}
