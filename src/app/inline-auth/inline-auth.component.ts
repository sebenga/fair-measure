import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { firstValueFrom } from 'rxjs';
import { trigger, transition, style, animate } from '@angular/animations';
import {
  IonIcon,
  IonSpinner,
} from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import {
  eyeOutline,
  eyeOffOutline,
  mailOutline,
  lockClosedOutline,
  personOutline,
  logoGoogle,
  logoFacebook,
  logoLinkedin,
} from 'ionicons/icons';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-inline-auth',
  template: `
    <div class="inline-auth-container" [@fadeIn]>
      <div class="auth-card">
        <div class="auth-tabs">
          <button
            type="button"
            class="auth-tab"
            [class.active]="isLoginMode"
            (click)="switchToLogin()">
            Sign In
          </button>
          <button
            type="button"
            class="auth-tab"
            [class.active]="!isLoginMode"
            (click)="switchToRegister()">
            Sign Up
          </button>
        </div>

        <!-- Login Form -->
        <form *ngIf="isLoginMode" (ngSubmit)="onLogin()" class="auth-form">
          <div class="input-group">
            <ion-icon name="mail-outline" class="input-icon"></ion-icon>
            <input
              type="email"
              class="auth-input"
              [(ngModel)]="loginData.email"
              name="login_email"
              placeholder="Email address"
              required
              email
            />
          </div>

          <div class="input-group">
            <ion-icon name="lock-closed-outline" class="input-icon"></ion-icon>
            <input
              [type]="showLoginPassword ? 'text' : 'password'"
              class="auth-input"
              [(ngModel)]="loginData.password"
              name="login_password"
              placeholder="Password"
              required
            />
            <button
              type="button"
              class="password-toggle"
              (click)="showLoginPassword = !showLoginPassword"
            >
              <ion-icon [name]="showLoginPassword ? 'eye-off-outline' : 'eye-outline'"></ion-icon>
            </button>
          </div>

          <button
            type="submit"
            class="submit-btn"
            [disabled]="isLoading"
          >
            <ion-spinner name="crescent" *ngIf="isLoading"></ion-spinner>
            <span *ngIf="!isLoading">Sign In</span>
          </button>

          <div class="divider">
            <span>or</span>
          </div>

          <div class="social-buttons">
            <button type="button" class="social-btn google" (click)="onSocialLogin('google')">
              <ion-icon name="logo-google"></ion-icon>
            </button>
            <button type="button" class="social-btn facebook" (click)="onSocialLogin('facebook')">
              <ion-icon name="logo-facebook"></ion-icon>
            </button>
            <button type="button" class="social-btn linkedin" (click)="onSocialLogin('linkedin')">
              <ion-icon name="logo-linkedin"></ion-icon>
            </button>
          </div>
        </form>

        <!-- Register Form -->
        <form *ngIf="!isLoginMode" (ngSubmit)="onRegister()" class="auth-form">
          <div class="input-group">
            <ion-icon name="person-outline" class="input-icon"></ion-icon>
            <input
              type="text"
              class="auth-input"
              [(ngModel)]="registerData.fullName"
              name="register_name"
              placeholder="Full name"
              required
            />
          </div>

          <div class="input-group">
            <ion-icon name="mail-outline" class="input-icon"></ion-icon>
            <input
              type="email"
              class="auth-input"
              [(ngModel)]="registerData.email"
              name="register_email"
              placeholder="Email address"
              required
              email
            />
          </div>

          <div class="input-group">
            <ion-icon name="lock-closed-outline" class="input-icon"></ion-icon>
            <input
              [type]="showRegisterPassword ? 'text' : 'password'"
              class="auth-input"
              [(ngModel)]="registerData.password"
              name="register_password"
              placeholder="Password (min 6 characters)"
              required
              minlength="6"
            />
            <button
              type="button"
              class="password-toggle"
              (click)="showRegisterPassword = !showRegisterPassword"
            >
              <ion-icon [name]="showRegisterPassword ? 'eye-off-outline' : 'eye-outline'"></ion-icon>
            </button>
          </div>

          <div class="input-group">
            <ion-icon name="lock-closed-outline" class="input-icon"></ion-icon>
            <input
              [type]="showConfirmPassword ? 'text' : 'password'"
              class="auth-input"
              [(ngModel)]="registerData.confirmPassword"
              name="register_confirm"
              placeholder="Confirm password"
              required
            />
            <button
              type="button"
              class="password-toggle"
              (click)="showConfirmPassword = !showConfirmPassword"
            >
              <ion-icon [name]="showConfirmPassword ? 'eye-off-outline' : 'eye-outline'"></ion-icon>
            </button>
          </div>

          <button
            type="submit"
            class="submit-btn register-btn"
            [disabled]="isLoading"
          >
            <ion-spinner name="crescent" *ngIf="isLoading"></ion-spinner>
            <span *ngIf="!isLoading">Create Account</span>
          </button>

          <div class="divider">
            <span>or</span>
          </div>

          <div class="social-buttons">
            <button type="button" class="social-btn google" (click)="onSocialRegister('google')">
              <ion-icon name="logo-google"></ion-icon>
            </button>
            <button type="button" class="social-btn facebook" (click)="onSocialRegister('facebook')">
              <ion-icon name="logo-facebook"></ion-icon>
            </button>
            <button type="button" class="social-btn linkedin" (click)="onSocialRegister('linkedin')">
              <ion-icon name="logo-linkedin"></ion-icon>
            </button>
          </div>
        </form>

        <div class="error-message" *ngIf="errorMessage">
          {{ errorMessage }}
        </div>
      </div>
    </div>
  `,
  styles: [`
    .inline-auth-container {
      padding: 16px;
      max-width: 500px;
      margin: 0 auto;
    }

    .auth-card {
      background: white;
      border-radius: 16px;
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
      overflow: hidden;
      border: 1px solid #e4e6ea;
    }

    .auth-tabs {
      display: flex;
      border-bottom: 1px solid #e4e6ea;
    }

    .auth-tab {
      flex: 1;
      padding: 16px;
      border: none;
      background: transparent;
      font-size: 1rem;
      font-weight: 600;
      color: #65676b;
      cursor: pointer;
      transition: all 0.3s ease;
      position: relative;
    }

    .auth-tab.active {
      color: #ff8800;
    }

    .auth-tab.active::after {
      content: '';
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      height: 3px;
      background: linear-gradient(90deg, #ff8800, #ffaa00);
      border-radius: 3px 3px 0 0;
    }

    .auth-tab:hover:not(.active) {
      background: #f8f9fa;
    }

    .auth-form {
      padding: 24px;
    }

    .input-group {
      position: relative;
      margin-bottom: 16px;
    }

    .input-icon {
      position: absolute;
      left: 14px;
      top: 50%;
      transform: translateY(-50%);
      color: #65676b;
      font-size: 1.2rem;
      z-index: 2;
    }

    .auth-input {
      width: 100%;
      padding: 14px 14px 14px 46px;
      border: 2px solid #e4e6ea;
      border-radius: 10px;
      font-size: 1rem;
      color: #1c1e21;
      background: #f8f9fa;
      transition: all 0.3s ease;
      outline: none;
      box-sizing: border-box;
    }

    .auth-input:focus {
      border-color: #ff8800;
      background: white;
      box-shadow: 0 0 0 3px rgba(255, 136, 0, 0.1);
    }

    .password-toggle {
      position: absolute;
      right: 12px;
      top: 50%;
      transform: translateY(-50%);
      background: none;
      border: none;
      color: #65676b;
      cursor: pointer;
      padding: 4px;
      border-radius: 4px;
    }

    .password-toggle:hover {
      color: #ff8800;
    }

    .submit-btn {
      width: 100%;
      padding: 14px;
      background: linear-gradient(135deg, #ff6b35, #ff8800, #ffaa00);
      color: white;
      border: none;
      border-radius: 10px;
      font-size: 1rem;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: all 0.3s ease;
      box-shadow: 0 4px 15px rgba(255, 136, 0, 0.3);
    }

    .submit-btn:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(255, 136, 0, 0.4);
    }

    .submit-btn:disabled {
      opacity: 0.7;
      cursor: not-allowed;
    }

    .register-btn {
      background: linear-gradient(135deg, #28a745, #20c997);
      box-shadow: 0 4px 15px rgba(40, 167, 69, 0.3);
    }

    .register-btn:hover:not(:disabled) {
      box-shadow: 0 6px 20px rgba(40, 167, 69, 0.4);
    }

    .divider {
      display: flex;
      align-items: center;
      margin: 20px 0;
      color: #65676b;
      font-size: 0.9rem;
    }

    .divider::before,
    .divider::after {
      content: '';
      flex: 1;
      height: 1px;
      background: #e4e6ea;
    }

    .divider span {
      padding: 0 16px;
    }

    .social-buttons {
      display: flex;
      justify-content: center;
      gap: 12px;
    }

    .social-btn {
      width: 48px;
      height: 48px;
      border: 2px solid #e4e6ea;
      border-radius: 50%;
      background: white;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.3s ease;
      color: #65676b;
      font-size: 1.3rem;
    }

    .social-btn.google:hover {
      border-color: #db4437;
      color: #db4437;
      transform: translateY(-2px);
    }

    .social-btn.facebook:hover {
      border-color: #4267b2;
      color: #4267b2;
      transform: translateY(-2px);
    }

    .social-btn.linkedin:hover {
      border-color: #0077b5;
      color: #0077b5;
      transform: translateY(-2px);
    }

    .error-message {
      margin-top: 16px;
      padding: 12px;
      background: #fef2f2;
      border: 1px solid #fecaca;
      border-radius: 8px;
      color: #dc2626;
      font-size: 0.9rem;
      text-align: center;
    }

    ion-spinner {
      --color: white;
      width: 20px;
      height: 20px;
    }

    @media (max-width: 480px) {
      .inline-auth-container {
        padding: 12px;
      }

      .auth-form {
        padding: 16px;
      }

      .auth-tab {
        padding: 12px;
        font-size: 0.9rem;
      }
    }
  `],
  standalone: true,
  animations: [
    trigger('fadeIn', [
      transition(':enter', [
        style({ opacity: 0, transform: 'translateY(-20px)' }),
        animate('400ms ease-out', style({ opacity: 1, transform: 'translateY(0)' })),
      ]),
    ]),
  ],
  imports: [CommonModule, FormsModule, IonIcon, IonSpinner],
})
export class InlineAuthComponent {
  isLoginMode = true;
  isLoading = false;
  errorMessage = '';

  loginData = { email: '', password: '' };
  registerData = { fullName: '', email: '', password: '', confirmPassword: '' };

  showLoginPassword = false;
  showRegisterPassword = false;
  showConfirmPassword = false;

  constructor(private auth: AuthService) {
    addIcons({
      eyeOutline,
      eyeOffOutline,
      mailOutline,
      lockClosedOutline,
      personOutline,
      logoGoogle,
      logoFacebook,
      logoLinkedin,
    });
  }

  switchToLogin(): void {
    this.isLoginMode = true;
    this.errorMessage = '';
  }

  switchToRegister(): void {
    this.isLoginMode = false;
    this.errorMessage = '';
  }

  async onLogin(): Promise<void> {
    if (!this.loginData.email || !this.loginData.password) {
      this.errorMessage = 'Please fill in all fields';
      return;
    }

    this.isLoading = true;
    this.errorMessage = '';

    try {
      await firstValueFrom(
        this.auth.login({
          email: this.loginData.email,
          password: this.loginData.password,
        })
      );

      if (!this.auth.isLoggedIn()) {
        throw new Error('Login succeeded but session could not be saved');
      }
    } catch (error) {
      this.errorMessage = error instanceof Error ? error.message : 'Login failed';
    } finally {
      this.isLoading = false;
    }
  }

  async onRegister(): Promise<void> {
    if (!this.registerData.fullName.trim()) {
      this.errorMessage = 'Please enter your name';
      return;
    }
    if (!this.registerData.email.trim()) {
      this.errorMessage = 'Please enter your email';
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(this.registerData.email)) {
      this.errorMessage = 'Please enter a valid email';
      return;
    }
    if (this.registerData.password.length < 6) {
      this.errorMessage = 'Password must be at least 6 characters';
      return;
    }
    if (this.registerData.password !== this.registerData.confirmPassword) {
      this.errorMessage = 'Passwords do not match';
      return;
    }

    this.isLoading = true;
    this.errorMessage = '';

    try {
      await firstValueFrom(
        this.auth.register({
          email: this.registerData.email,
          password: this.registerData.password,
          fullName: this.registerData.fullName.trim(),
        })
      );
    } catch (error) {
      this.errorMessage = error instanceof Error ? error.message : 'Registration failed';
    } finally {
      this.isLoading = false;
    }
  }

  onSocialLogin(provider: string): void {
    this.errorMessage = `${provider} login coming soon`;
  }

  onSocialRegister(provider: string): void {
    this.errorMessage = `${provider} registration coming soon`;
  }
}
