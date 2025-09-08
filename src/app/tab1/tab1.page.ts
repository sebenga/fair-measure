import { Component, OnInit } from '@angular/core';
import { ApiService } from '../api.service';
import { createSampleCompetitions } from '../create-sample-competitions';
import { IonContent } from '@ionic/angular/standalone';
import { InfinitScrollComponent } from '../infinit-scroll/infinit-scroll.component';
import { FbHeaderComponent } from '../fb-header/fb-header.component';

@Component({
  selector: 'app-tab1',
  templateUrl: 'tab1.page.html',
  styleUrls: ['tab1.page.scss'],
  imports: [IonContent, InfinitScrollComponent, FbHeaderComponent],
})
export class Tab1Page implements OnInit {
  constructor(private apiService: ApiService) {}

  async ngOnInit() {
    await createSampleCompetitions(this.apiService);
  }
}
