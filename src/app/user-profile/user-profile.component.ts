import { Component } from '@angular/core';
import { IonCard, IonAvatar, IonButton, IonList, IonItem, IonIcon } from '@ionic/angular/standalone';

@Component({
  selector: 'app-user-profile',
  templateUrl: './user-profile.component.html',
  styleUrls: ['./user-profile.component.scss'],
  standalone: true,
  imports: [IonAvatar, IonButton, IonList, IonItem, IonIcon]
})
export class UserProfileComponent {}
