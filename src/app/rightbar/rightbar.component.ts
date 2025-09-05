import { Component } from '@angular/core';
import { IonCard, IonAvatar, IonList, IonItem } from '@ionic/angular/standalone';

@Component({
  selector: 'app-rightbar',
  templateUrl: './rightbar.component.html',
  styleUrls: ['./rightbar.component.scss'],
  standalone: true,
  imports: [IonCard, IonAvatar, IonList, IonItem]
})
export class RightbarComponent {}
