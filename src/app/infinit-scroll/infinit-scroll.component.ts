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
// ...existing code...

@Component({
  selector: 'app-infinit-scroll',
  templateUrl: './infinit-scroll.component.html',
  styleUrls: ['./infinit-scroll.component.scss'],
  imports: [IonAvatar, IonContent, IonInfiniteScroll, IonInfiniteScrollContent, IonItem, IonLabel, IonList, IonCard, IonButton, IonIcon, UserProfileComponent, RightbarComponent],
})

export class InfinitScrollComponent implements OnInit {
  competitions: any[] = [];
  page: number = 1;
  pageSize: number = 20;
  maxCompetitions: number = 100; // Set this to your desired maximum

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

  onIonInfinite(event: any) {
    // Simulate loading more competitions
    setTimeout(() => {
      // Add more competitions to your array here
      // this.loadMoreCompetitions();
      
      event.target.complete();
      
      // Disable infinite scroll if no more data
      if (this.competitions.length >= this.maxCompetitions) {
        event.target.disabled = true;
      }
    }, 1000);
  }
}
