import { Component, OnInit } from '@angular/core';
import { ApiService } from '../api.service';
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
    // Removed automatic sample creation to prevent API errors
    console.log('Tab1 page initialized');
  }
}
