import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { IonHeader, IonToolbar, IonTitle, IonSearchbar, IonButton } from '@ionic/angular/standalone';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-fb-header',
  templateUrl: './fb-header.component.html',
  styleUrls: ['./fb-header.component.scss'],
  standalone: true,
  imports: [IonHeader, IonToolbar, IonTitle, IonSearchbar, IonButton],
})
export class FbHeaderComponent {
  constructor(
    private router: Router,
    private auth: AuthService
  ) {}

  goToLogin(): void {
    this.router.navigate(['/auth/login']);
  }

  goToRegister(): void {
    this.router.navigate(['/auth/register']);
  }

  logout(): void {
    this.auth.logout();
    this.router.navigate(['/auth/login']);
  }

  isLoggedIn(): boolean {
    return this.auth.isLoggedIn();
  }
}
