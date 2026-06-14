import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { ViewWillEnter } from '@ionic/angular';
import { HOME_URL } from '../../constants/routes';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { firstValueFrom } from 'rxjs';
import { trigger, transition, style, animate } from '@angular/animations';
import {
  IonContent,
  IonIcon,
  IonSpinner,
  IonToast,
} from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import {
  eyeOutline,
  eyeOffOutline,
  mailOutline,
  lockClosedOutline,
  logoGoogle,
  logoLinkedin,
  logoFacebook,
  personOutline,
} from 'ionicons/icons';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login',
  templateUrl: './login.page.html',
  styleUrls: ['./login.page.scss'],
  standalone: true,
  animations: [
    trigger('slideInUp', [
      transition(':enter', [
        style({ opacity: 0, transform: 'translateY(50px)' }),
        animate('600ms ease-out', style({ opacity: 1, transform: 'translateY(0)' })),
      ]),
    ]),
    trigger('fadeIn', [
      transition(':enter', [
        style({ opacity: 0 }),
        animate('800ms ease-out', style({ opacity: 1 })),
      ]),
    ]),
  ],
  imports: [CommonModule, FormsModule, IonContent, IonIcon, IonSpinner, IonToast],
})
export class LoginPage implements ViewWillEnter {
  loginData = { email: '', password: '' };
  showPassword = false;
  isLoading = false;
  showToast = false;
  toastMessage = '';
  toastColor = 'success';

  constructor(
    private router: Router,
    private auth: AuthService
  ) {
    addIcons({
      eyeOutline,
      eyeOffOutline,
      mailOutline,
      lockClosedOutline,
      logoGoogle,
      logoLinkedin,
      logoFacebook,
      personOutline,
    });
  }

  ionViewWillEnter(): void {
    if (this.auth.isLoggedIn()) {
      void this.redirectAfterLogin();
    }
  }

  togglePasswordVisibility(): void {
    this.showPassword = !this.showPassword;
  }

  async onLogin(): Promise<void> {
    if (!this.loginData.email || !this.loginData.password) {
      this.showToastMessage('Please fill in all fields', 'warning');
      return;
    }

    this.isLoading = true;
    let loginOk = false;

    try {
      await firstValueFrom(
        this.auth.login({
          email: this.loginData.email,
          password: this.loginData.password,
        })
      );

      if (!this.auth.isLoggedIn()) {
        throw new Error('Login succeeded but the session could not be saved.');
      }

      loginOk = true;
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Login failed. Please check your credentials.';
      this.showToastMessage(message, 'danger');
    } finally {
      this.isLoading = false;
    }

    if (!loginOk) {
      return;
    }

    // Login succeeded — redirect separately so router errors don't show as login failure
    try {
      await new Promise<void>((resolve) => setTimeout(resolve, 0));
      await this.redirectAfterLogin();
    } catch {
      window.location.assign(HOME_URL);
    }
  }

  private async redirectAfterLogin(): Promise<void> {
    if (this.router.url === HOME_URL || this.router.url.startsWith(`${HOME_URL}/`)) {
      return;
    }

    const ok = await this.router.navigateByUrl(HOME_URL, { replaceUrl: true });
    if (!ok) {
      window.location.assign(HOME_URL);
    }
  }

  goToRegister(): void {
    this.router.navigate(['/auth/register']);
  }

  onSocialLogin(_provider: 'google' | 'linkedin' | 'facebook'): void {
    this.showToastMessage('Social login is not available yet.', 'warning');
  }

  private showToastMessage(message: string, color: string): void {
    this.toastMessage = message;
    this.toastColor = color;
    this.showToast = true;
  }
}
