import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { ApiService, CompetitionCard } from '../api.service';
import { AuthService } from '../services/auth.service';
import { CREATE_COMPETITION_URL } from '../constants/routes';
import {
  IonAvatar,
  IonInfiniteScroll,
  IonInfiniteScrollContent,
  IonItem,
  IonLabel,
  IonList,
  IonCard,
  IonButton,
  IonIcon,
} from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import { addOutline, cameraOutline } from 'ionicons/icons';
import { UserProfileComponent } from '../user-profile/user-profile.component';
import { RightbarComponent } from '../rightbar/rightbar.component';

@Component({
  selector: 'app-infinit-scroll',
  templateUrl: './infinit-scroll.component.html',
  styleUrls: ['./infinit-scroll.component.scss'],
  standalone: true,
  imports: [
    IonAvatar,
    IonInfiniteScroll,
    IonInfiniteScrollContent,
    IonItem,
    IonLabel,
    IonList,
    IonCard,
    IonButton,
    IonIcon,
    UserProfileComponent,
    RightbarComponent,
  ],
})
export class InfinitScrollComponent implements OnInit {
  competitions: CompetitionCard[] = [];
  loading = false;
  maxCompetitions = 100;

  constructor(
    private apiService: ApiService,
    private router: Router,
    private auth: AuthService
  ) {
    addIcons({ addOutline, cameraOutline });
  }

  ngOnInit(): void {
    this.refreshCompetitions();
  }

  refreshCompetitions(): void {
    this.loading = true;
    this.apiService.getCompetitions().subscribe({
      next: (data) => {
        this.competitions = data;
        this.loading = false;
      },
      error: () => {
        this.competitions = [];
        this.loading = false;
      },
    });
  }

  goToCreateCompetition(): void {
    if (!this.auth.isLoggedIn()) {
      void this.router.navigate(['/auth/login']);
      return;
    }

    void this.router.navigate([CREATE_COMPETITION_URL]);
  }

  openMediaUploadPage(event?: Event): void {
    event?.preventDefault();
    event?.stopPropagation();
    void this.router.navigate(['/media-upload']);
  }

  openMediaUpload(competition: CompetitionCard): void {
    localStorage.setItem('selectedCompetition', JSON.stringify(competition));
    this.router.navigate(['/media-upload']);
  }

  onIonInfinite(event: Event): void {
    const target = event.target as HTMLIonInfiniteScrollElement;
    target.complete();
    if (this.competitions.length >= this.maxCompetitions) {
      target.disabled = true;
    }
  }
}
