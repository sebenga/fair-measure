import { Component } from '@angular/core';
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
  constructor(private auth: AuthService) {}

  logout(): void {
    this.auth.logout();
  }

  isLoggedIn(): boolean {
    return this.auth.isLoggedIn();
  }
}
