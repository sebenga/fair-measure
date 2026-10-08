import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import {
  IonButton,
  IonContent,
  IonIcon,
  IonInput,
  IonItem,
  IonList,
  IonNote,
  IonSpinner,
  IonText,
} from '@ionic/angular/standalone';

import { AuthService } from '../../core/auth.service';
import { extractErrorMessage } from '../../core/error-message';

@Component({
  selector: 'fm-login',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    IonContent,
    IonList,
    IonItem,
    IonInput,
    IonButton,
    IonIcon,
    IonNote,
    IonSpinner,
    IonText,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './login.page.scss',
  template: `
    <ion-content class="ion-padding">
      <div class="auth-shell">
        <header class="auth-header">
          <div class="mark" aria-hidden="true">FM</div>
          <h1>Fair Measure</h1>
          <p>Run any competition you can describe.</p>
        </header>

        <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
          <ion-list inset="true">
            <ion-item>
              <ion-input
                label="Email"
                labelPlacement="stacked"
                type="email"
                inputmode="email"
                autocomplete="email"
                formControlName="email"
                placeholder="you@example.com"
              />
            </ion-item>
            <ion-item>
              <ion-input
                label="Password"
                labelPlacement="stacked"
                [type]="showPassword() ? 'text' : 'password'"
                autocomplete="current-password"
                formControlName="password"
                placeholder="Your password"
              >
                <ion-button
                  fill="clear"
                  slot="end"
                  type="button"
                  [attr.aria-pressed]="showPassword()"
                  [attr.aria-label]="showPassword() ? 'Hide password' : 'Show password'"
                  (click)="togglePassword()"
                >
                  <ion-icon
                    slot="icon-only"
                    [name]="showPassword() ? 'eye-off-outline' : 'eye-outline'"
                    aria-hidden="true"
                  />
                </ion-button>
              </ion-input>
            </ion-item>
          </ion-list>

          @if (error()) {
            <ion-text color="danger">
              <p class="error" role="alert">{{ error() }}</p>
            </ion-text>
          }

          <ion-button
            type="submit"
            expand="block"
            [disabled]="form.invalid || loading()"
          >
            @if (loading()) {
              <ion-spinner name="crescent" />
            } @else {
              Sign in
            }
          </ion-button>
        </form>

        <p class="switch">
          <ion-note>New here?</ion-note>
          <a routerLink="/register">Create an account</a>
        </p>
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

  readonly form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required]],
  });

  togglePassword(): void {
    this.showPassword.update((visible) => !visible);
  }

  submit(): void {
    if (this.form.invalid || this.loading()) return;

    this.loading.set(true);
    this.error.set(null);

    const { email, password } = this.form.getRawValue();
    this.auth.login(email, password).subscribe({
      next: () => {
        this.loading.set(false);
        const next = this.route.snapshot.queryParamMap.get('next');
        void this.router.navigateByUrl(next ?? '/tabs/competitions');
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(extractErrorMessage(err, 'That email and password did not match.'));
      },
    });
  }
}
