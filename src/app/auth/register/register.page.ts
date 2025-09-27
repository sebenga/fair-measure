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
  IonToast,
  IonCheckbox
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
  checkmarkOutline
} from 'ionicons/icons';

@Component({
  selector: 'app-register',
  templateUrl: './register.page.html',
  styleUrls: ['./register.page.scss'],
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
    IonToast,
    IonCheckbox
  ]
})
export class RegisterPage {
  registerData = {
    firstName: '',
    lastName: '',
    email: '',
    password: '',
    confirmPassword: ''
  };

  showPassword = false;
  showConfirmPassword = false;
  agreeToTerms = false;
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
      personOutline,
      checkmarkOutline
    });
  }

  togglePasswordVisibility(field: 'password' | 'confirmPassword') {
    if (field === 'password') {
      this.showPassword = !this.showPassword;
    } else {
      this.showConfirmPassword = !this.showConfirmPassword;
    }
  }

  async onRegister() {
    if (!this.validateForm()) {
      return;
    }

    this.isLoading = true;

    try {
      // Simulate registration API call
      await new Promise(resolve => setTimeout(resolve, 2500));
      
      // Mock successful registration
      this.showToastMessage('Account created successfully! Welcome to Fair-Measure!', 'success');
      
      setTimeout(() => {
        this.router.navigate(['/tabs/tab1']);
      }, 1500);
      
    } catch (error) {
      this.showToastMessage('Registration failed. Please try again.', 'danger');
    } finally {
      this.isLoading = false;
    }
  }

  async onSocialRegister(provider: 'google' | 'linkedin' | 'facebook') {
    this.isLoading = true;
    
    try {
      // Simulate social registration API call
      await new Promise(resolve => setTimeout(resolve, 1500));
      
      this.showToastMessage(`Account created with ${provider.charAt(0).toUpperCase() + provider.slice(1)}!`, 'success');
      
      setTimeout(() => {
        this.router.navigate(['/tabs/tab1']);
      }, 1500);
      
    } catch (error) {
      this.showToastMessage(`${provider.charAt(0).toUpperCase() + provider.slice(1)} registration failed. Please try again.`, 'danger');
    } finally {
      this.isLoading = false;
    }
  }

  goToLogin() {
    this.router.navigate(['/auth/login']);
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

    if (!this.isValidEmail(this.registerData.email)) {
      this.showToastMessage('Please enter a valid email address', 'warning');
      return false;
    }

    if (!this.registerData.password) {
      this.showToastMessage('Please enter a password', 'warning');
      return false;
    }

    if (this.registerData.password.length < 6) {
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

  private isValidEmail(email: string): boolean {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }

  private showToastMessage(message: string, color: string) {
    this.toastMessage = message;
    this.toastColor = color;
    this.showToast = true;
  }
}