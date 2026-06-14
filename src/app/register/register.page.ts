import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { IonContent, IonButton, IonIcon } from '@ionic/angular/standalone';
import { Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [IonIcon, IonContent, CommonModule, FormsModule, IonButton],
  templateUrl: './register.page.html',
})
export class RegisterPage {
  name = '';
  email = '';
  password = '';
  loading = false;
  error = '';

  constructor(
    private auth: AuthService,
    private router: Router
  ) {}

  onSubmit() {
    this.loading = true;
    this.error = '';
    this.auth
      .register({
        email: this.email,
        password: this.password,
        fullName: this.name,
      })
      .subscribe({
        next: () => {
          this.loading = false;
          this.router.navigate(['/home'], { replaceUrl: true });
        },
        error: (err) => {
          this.loading = false;
          this.error = err?.message || 'Registration failed. Please try again.';
        },
      });
  }
}
