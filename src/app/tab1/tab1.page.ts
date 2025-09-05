import { Component, OnInit } from '@angular/core';
import { ApiService } from '../api.service';
import { createSampleCompetitions } from '../create-sample-competitions';
import { IonHeader, IonToolbar, IonTitle, IonContent } from '@ionic/angular/standalone';
import { InfinitScrollComponent } from '../infinit-scroll/infinit-scroll.component';

@Component({
  selector: 'app-tab1',
  templateUrl: 'tab1.page.html',
  styleUrls: ['tab1.page.scss'],
  imports: [IonHeader, IonToolbar, IonTitle, IonContent, InfinitScrollComponent],
})
export class Tab1Page implements OnInit {
  constructor(private apiService: ApiService) {}

  async ngOnInit() {
    await createSampleCompetitions(this.apiService);
  }
}
