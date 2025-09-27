import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { IonHeader, IonToolbar, IonButtons, IonBackButton, IonTitle, IonContent } from '@ionic/angular/standalone';
import { MediaUploadComponent } from './media-upload.component';

@Component({
  selector: 'app-media-upload',
  templateUrl: './media-upload.page.html',
  styleUrls: ['./media-upload.page.scss'],
  standalone: true,
    imports: [
      CommonModule,
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
  selectedCompetition: any = null;

  constructor() {}

  ngOnInit() {
    // Check if a specific competition was selected
    const storedCompetition = localStorage.getItem('selectedCompetition');
    if (storedCompetition) {
      this.selectedCompetition = JSON.parse(storedCompetition);
      // Clear the stored competition
      localStorage.removeItem('selectedCompetition');
    }
  }
}