import { Component, OnInit } from '@angular/core';
import { ApiService } from '../api.service';
import {
  InfiniteScrollCustomEvent,
  IonAvatar,
  IonContent,
  IonInfiniteScroll,
  IonInfiniteScrollContent,
  IonItem,
  IonLabel,
  IonList,
  IonCard,
  IonButton,
  IonIcon,
} from '@ionic/angular/standalone';
import { UserProfileComponent } from '../user-profile/user-profile.component';
import { RightbarComponent } from '../rightbar/rightbar.component';
import { FbHeaderComponent } from '../fb-header/fb-header.component';

@Component({
  selector: 'app-infinit-scroll',
  templateUrl: './infinit-scroll.component.html',
  styleUrls: ['./infinit-scroll.component.scss'],
  imports: [IonAvatar, IonContent, IonInfiniteScroll, IonInfiniteScrollContent, IonItem, IonLabel, IonList, IonCard, IonButton, IonIcon, UserProfileComponent, RightbarComponent, FbHeaderComponent],
})

export class InfinitScrollComponent implements OnInit {
  competitions: any[] = [];
  page: number = 1;
  pageSize: number = 20;

  constructor(private apiService: ApiService) {}

  ngOnInit(): void {
    this.loadCompetitions();
  }

  private loadCompetitions() {
    this.apiService.getCompetitions().subscribe((data: any) => {
      // If API supports pagination, adjust accordingly
      this.competitions = this.competitions.concat(data);
    });
  }

  onIonInfinite(event: InfiniteScrollCustomEvent) {
    this.page++;
    this.loadCompetitions();
    setTimeout(() => {
      event.target.complete();
    }, 500);
  }
}
