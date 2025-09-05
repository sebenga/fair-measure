import { Component } from '@angular/core';
import { IonHeader, IonToolbar, IonTitle, IonSearchbar, IonButton, IonIcon } from '@ionic/angular/standalone';

@Component({
  selector: 'app-fb-header',
  templateUrl: './fb-header.component.html',
  styleUrls: ['./fb-header.component.scss'],
  standalone: true,
  imports: [IonHeader, IonToolbar, IonTitle, IonSearchbar, IonButton, IonIcon]
})
export class FbHeaderComponent {}
