import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { trigger, state, style, transition, animate } from '@angular/animations';
import {
  IonContent,
  IonButton,
  IonIcon,
  IonSpinner,
  IonToast
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
  personOutline
} from 'ionicons/icons';

@Component({
  selector: 'app-login',
  templateUrl: './login.page.html',
  styleUrls: ['./login.page.scss'],
  standalone: true,
  animations: [
    trigger('slideInUp', [
      transition(':enter', [
        style({ opacity: 0, transform: 'translateY(50px)' }),
        animate('600ms ease-out', style({ opacity: 1, transform: 'translateY(0)' }))
      ])
    ]),
    trigger('fadeIn', [
      transition(':enter', [
        style({ opacity: 0 }),
        animate('800ms ease-out', style({ opacity: 1 }))
      ])
    ])
  ],
  imports: [
    CommonModule,
    FormsModule,
    IonContent,
    IonButton,
    IonIcon,
    IonSpinner,
    IonToast
  ]
})
export class LoginPage {
  loginData = {
    email: '',
    password: ''
  };

  showPassword = false;
  isLoading = false;
  showToast = false;
  toastMessage = '';
  toastColor = 'success';

  constructor(private router: Router) {
    addIcons({ 
      eyeOutline, 
      eyeOffOutline, 
      mailOutline, 
      lockClosedOutline,
      logoGoogle,
      logoLinkedin,
      logoFacebook,
      personOutline
    });
  }

  togglePasswordVisibility() {
    this.showPassword = !this.showPassword;
  }

  async onLogin() {
    if (!this.loginData.email || !this.loginData.password) {
      this.showToastMessage('Please fill in all fields', 'warning');
      return;
    }

    this.isLoading = true;

    try {
      // Simulate login API call
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Mock successful login
      this.showToastMessage('Login successful! Welcome back!', 'success');
      
      setTimeout(() => {
        this.router.navigate(['/tabs/tab1']);
      }, 1500);
      
    } catch (error) {
      this.showToastMessage('Login failed. Please check your credentials.', 'danger');
    } finally {
      this.isLoading = false;
    }
  }

  async onSocialLogin(provider: 'google' | 'linkedin' | 'facebook') {
    this.isLoading = true;
    
    try {
      // Simulate social login API call
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      this.showToastMessage(`${provider.charAt(0).toUpperCase() + provider.slice(1)} login successful!`, 'success');
      
      setTimeout(() => {
        this.router.navigate(['/tabs/tab1']);
      }, 1500);
      
    } catch (error) {
      this.showToastMessage(`${provider.charAt(0).toUpperCase() + provider.slice(1)} login failed. Please try again.`, 'danger');
    } finally {
      this.isLoading = false;
    }
  }

  goToRegister() {
    this.router.navigate(['/auth/register']);
  }

  private showToastMessage(message: string, color: string) {
    this.toastMessage = message;
    this.toastColor = color;
    this.showToast = true;
  }
}