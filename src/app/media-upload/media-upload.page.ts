import { Component } from '@angular/core';
import { IonHeader, IonToolbar, IonButtons, IonBackButton, IonTitle, IonContent } from '@ionic/angular/standalone';
import { MediaUploadComponent } from './media-upload.component';

@Component({
  selector: 'app-media-upload',
  templateUrl: './media-upload.page.html',
  styleUrls: ['./media-upload.page.scss'],
  standalone: true,
  imports: [
    IonHeader,
    IonToolbar,
    IonButtons,
    IonBackButton,
    IonTitle,
    IonContent,
    MediaUploadComponent
  ]
})
export class MediaUploadPage {
  constructor() {}
}