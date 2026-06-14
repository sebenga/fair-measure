import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { firstValueFrom } from 'rxjs';
import { trigger, transition, style, animate } from '@angular/animations';
import {
  IonContent,
  IonIcon,
  IonSpinner,
  IonToast,
  IonCheckbox,
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
  checkmarkOutline,
} from 'ionicons/icons';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-register',
  templateUrl: './register.page.html',
  styleUrls: ['./register.page.scss'],
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
  imports: [CommonModule, FormsModule, IonContent, IonIcon, IonSpinner, IonToast, IonCheckbox],
})
export class RegisterPage {
  registerData = {
    firstName: '',
    lastName: '',
    email: '',
    password: '',
    confirmPassword: '',
  };

  showPassword = false;
  showConfirmPassword = false;
  agreeToTerms = false;
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
      checkmarkOutline,
    });
  }

  togglePasswordVisibility(field: 'password' | 'confirmPassword'): void {
    if (field === 'password') {
      this.showPassword = !this.showPassword;
    } else {
      this.showConfirmPassword = !this.showConfirmPassword;
    }
  }

  async onRegister(): Promise<void> {
    if (!this.validateForm()) {
      return;
    }

    this.isLoading = true;
    const fullName = `${this.registerData.firstName.trim()} ${this.registerData.lastName.trim()}`.trim();

    try {
      await firstValueFrom(
        this.auth.register({
          email: this.registerData.email,
          password: this.registerData.password,
          fullName,
        })
      );
      await this.router.navigate(['/home'], { replaceUrl: true });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Registration failed. Please try again.';
      this.showToastMessage(message, 'danger');
    } finally {
      this.isLoading = false;
    }
  }

  goToLogin(): void {
    this.router.navigate(['/auth/login']);
  }

  onSocialRegister(_provider: 'google' | 'linkedin' | 'facebook'): void {
    this.showToastMessage('Social sign-up is not available yet.', 'warning');
  }

  private validateForm(): boolean {
    if (!this.registerData.firstName.trim()) {
      this.showToastMessage('Please enter your first name', 'warning');
      return false;
    }
    if (!this.registerData.lastName.trim()) {
      this.showToastMessage('Please enter your last name', 'warning');
      return false;
    }
    if (!this.registerData.email.trim()) {
      this.showToastMessage('Please enter your email address', 'warning');
      return false;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(this.registerData.email)) {
      this.showToastMessage('Please enter a valid email address', 'warning');
      return false;
    }
    if (!this.registerData.password || this.registerData.password.length < 6) {
      this.showToastMessage('Password must be at least 6 characters long', 'warning');
      return false;
    }
    if (this.registerData.password !== this.registerData.confirmPassword) {
      this.showToastMessage('Passwords do not match', 'warning');
      return false;
    }
    if (!this.agreeToTerms) {
      this.showToastMessage('Please agree to the Terms of Service and Privacy Policy', 'warning');
      return false;
    }
    return true;
  }

  private showToastMessage(message: string, color: string): void {
    this.toastMessage = message;
    this.toastColor = color;
    this.showToast = true;
  }
}
