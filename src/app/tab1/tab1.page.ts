import { Component, ViewChild } from '@angular/core';
import { ViewWillEnter } from '@ionic/angular';
import { IonContent } from '@ionic/angular/standalone';
import { InfinitScrollComponent } from '../infinit-scroll/infinit-scroll.component';
import { FbHeaderComponent } from '../fb-header/fb-header.component';

@Component({
  selector: 'app-tab1',
  templateUrl: 'tab1.page.html',
  styleUrls: ['tab1.page.scss'],
  imports: [IonContent, InfinitScrollComponent, FbHeaderComponent],
})
export class Tab1Page implements ViewWillEnter {
  @ViewChild(InfinitScrollComponent) feed?: InfinitScrollComponent;

  ionViewWillEnter(): void {
    this.feed?.refreshCompetitions();
  }
}
