import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import {
  IonBackButton,
  IonButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonInput,
  IonItem,
  IonList,
  IonNote,
  IonSpinner,
  IonText,
  IonTitle,
  IonToolbar,
} from '@ionic/angular/standalone';

import { AuthService } from '../../core/auth.service';
import { extractErrorMessage } from '../../core/error-message';

@Component({
  selector: 'fm-register',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    IonHeader,
    IonToolbar,
    IonTitle,
    IonButtons,
    IonBackButton,
    IonContent,
    IonList,
    IonItem,
    IonInput,
    IonButton,
    IonNote,
    IonSpinner,
    IonText,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start">
          <ion-back-button defaultHref="/login" />
        </ion-buttons>
        <ion-title>Create account</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content class="ion-padding">
      <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
        <ion-list inset="true">
          <ion-item>
            <ion-input
              label="Name"
              labelPlacement="stacked"
              formControlName="displayName"
              autocomplete="name"
              placeholder="How should we call you?"
            />
          </ion-item>
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
              type="password"
              autocomplete="new-password"
              formControlName="password"
              placeholder="At least 8 characters"
            />
          </ion-item>
        </ion-list>

        <ion-note class="hint">
          Passwords are checked against Django's validators, so avoid anything
          too common or too similar to your email.
        </ion-note>

        @if (error()) {
          <ion-text color="danger">
            <p class="error" role="alert">{{ error() }}</p>
          </ion-text>
        }

        <ion-button type="submit" expand="block" [disabled]="form.invalid || loading()">
          @if (loading()) {
            <ion-spinner name="crescent" />
          } @else {
            Create account
          }
        </ion-button>
      </form>

      <p class="switch">
        <ion-note>Already have an account?</ion-note>
        <a routerLink="/login">Sign in</a>
      </p>
    </ion-content>
  `,
  styles: [
    `
      form ion-button {
        margin: 16px;
      }

      .hint {
        display: block;
        margin: 0 20px;
        font-size: 0.8rem;
        line-height: 1.5;
      }

      .error {
        margin: 8px 16px 0;
        font-size: 0.85rem;
      }

      .switch {
        display: flex;
        gap: 6px;
        justify-content: center;
        align-items: center;
        margin-top: 24px;
        font-size: 0.9rem;

        a {
          color: var(--ion-color-primary);
          font-weight: 600;
          text-decoration: none;
        }
      }
    `,
  ],
})
export class RegisterPage {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  readonly form = this.fb.nonNullable.group({
    displayName: ['', [Validators.required, Validators.maxLength(120)]],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8)]],
  });

  submit(): void {
    if (this.form.invalid || this.loading()) return;

    this.loading.set(true);
    this.error.set(null);

    const { email, password, displayName } = this.form.getRawValue();
    this.auth.register(email, password, displayName).subscribe({
      next: () => {
        this.loading.set(false);
        void this.router.navigateByUrl('/tabs/competitions');
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(extractErrorMessage(err, 'We could not create that account.'));
      },
    });
  }
}
