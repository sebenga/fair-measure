import { ChangeDetectionStrategy, Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import {
  AlertController,
  IonBackButton,
  IonButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonSegment,
  IonSegmentButton,
  IonLabel,
  IonSpinner,
  IonTitle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';
import type { CompetitionDetail } from '../../core/models';
import { RealtimeService, competitionRoom } from '../../core/realtime.service';
import { CompetitionFeedComponent } from './tabs/competition-feed.component';
import { CompetitionFixturesComponent } from './tabs/competition-fixtures.component';
import { CompetitionStandingsComponent } from './tabs/competition-standings.component';

type Tab = 'feed' | 'fixtures' | 'standings';

@Component({
  selector: 'fm-competition-detail',
  standalone: true,
  imports: [
    IonHeader,
    IonToolbar,
    IonTitle,
    IonButtons,
    IonBackButton,
    IonButton,
    IonIcon,
    IonContent,
    IonSegment,
    IonSegmentButton,
    IonLabel,
    IonSpinner,
    CompetitionFeedComponent,
    CompetitionFixturesComponent,
    CompetitionStandingsComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start">
          <ion-back-button defaultHref="/tabs/competitions" />
        </ion-buttons>
        <ion-title>{{ competition()?.name ?? 'Competition' }}</ion-title>
        <ion-buttons slot="end">
          @if (realtime.connected()) {
            <span class="fm-live" title="Live updates on">Live</span>
          }
          @if (canManage()) {
            <ion-button (click)="openSetup()">
              <ion-icon slot="icon-only" name="options-outline" aria-label="Setup" />
            </ion-button>
          }
          @if (isOwner()) {
            <ion-button color="danger" (click)="confirmDelete()">
              <ion-icon slot="icon-only" name="trash-outline" aria-label="Delete competition" />
            </ion-button>
          }
        </ion-buttons>
      </ion-toolbar>

      <ion-toolbar>
        <ion-segment [value]="tab()" (ionChange)="selectTab($any($event).detail.value)">
          <ion-segment-button value="feed">
            <ion-label>Feed</ion-label>
          </ion-segment-button>
          <ion-segment-button value="fixtures">
            <ion-label>Fixtures</ion-label>
          </ion-segment-button>
          <ion-segment-button value="standings">
            <ion-label>Table</ion-label>
          </ion-segment-button>
        </ion-segment>
      </ion-toolbar>
    </ion-header>

    <ion-content fullscreen="true">
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (error()) {
        <div class="fm-empty">
          <ion-icon name="alert-circle-outline" aria-hidden="true" />
          <h3>Could not load this competition</h3>
          <p>{{ error() }}</p>
          <ion-button fill="clear" (click)="load()">Try again</ion-button>
        </div>
      } @else if (competition(); as comp) {
        @switch (tab()) {
          @case ('feed') {
            <fm-competition-feed [competition]="comp" />
          }
          @case ('fixtures') {
            <fm-competition-fixtures [competition]="comp" />
          }
          @case ('standings') {
            <fm-competition-standings [competition]="comp" />
          }
        }
      }
    </ion-content>
  `,
  styles: [
    `
      .centered {
        display: grid;
        place-items: center;
        padding: 64px 0;
      }
    `,
  ],
})
export class CompetitionDetailPage implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly alerts = inject(AlertController);
  private readonly toasts = inject(ToastController);
  readonly realtime = inject(RealtimeService);

  private competitionId = '';

  readonly competition = signal<CompetitionDetail | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly tab = signal<Tab>('feed');

  ngOnInit(): void {
    this.competitionId = this.route.snapshot.paramMap.get('id') ?? '';

    const requestedTab = this.route.snapshot.queryParamMap.get('tab');
    if (requestedTab === 'fixtures' || requestedTab === 'standings') {
      this.tab.set(requestedTab);
    }

    this.load();
    this.realtime.subscribe(competitionRoom(this.competitionId));

    this.realtime
      .on<{ competition_id: string }>('competition.updated')
      .pipe(takeUntilDestroyed())
      .subscribe((payload) => {
        if (payload.competition_id === this.competitionId) {
          this.load(false);
        }
      });
  }

  ngOnDestroy(): void {
    if (this.competitionId) {
      this.realtime.unsubscribe(competitionRoom(this.competitionId));
    }
  }

  load(showSpinner = true): void {
    if (showSpinner) this.loading.set(true);
    this.error.set(null);

    this.api.getCompetition(this.competitionId).subscribe({
      next: (competition) => {
        this.competition.set(competition);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err));
        this.loading.set(false);
      },
    });
  }

  selectTab(value: string | undefined): void {
    if (value === 'feed' || value === 'fixtures' || value === 'standings') {
      this.tab.set(value);
      void this.router.navigate([], {
        relativeTo: this.route,
        queryParams: { tab: value },
        replaceUrl: true,
      });
    }
  }

  canManage(): boolean {
    const role = this.competition()?.my_role;
    return role === 'owner' || role === 'admin';
  }

  isOwner(): boolean {
    return this.competition()?.my_role === 'owner';
  }

  openSetup(): void {
    void this.router.navigate(['/competitions', this.competitionId, 'setup']);
  }

  async confirmDelete(): Promise<void> {
    const name = this.competition()?.name ?? 'this competition';
    const alert = await this.alerts.create({
      header: `Delete ${name}?`,
      message: 'Scoring, fixtures, and the feed are removed. This cannot be undone.',
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        { text: 'Delete', role: 'destructive' },
      ],
    });
    await alert.present();

    const { role } = await alert.onDidDismiss();
    if (role !== 'destructive') {
      return;
    }

    this.api.deleteCompetition(this.competitionId).subscribe({
      next: () => {
        void this.toast('Competition deleted.', 'success');
        void this.router.navigate(['/tabs/competitions'], { replaceUrl: true });
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err, 'Could not delete that competition.'));
        void this.toast(
          extractErrorMessage(err, 'Could not delete that competition.'),
          'danger',
        );
      },
    });
  }

  private async toast(message: string, color: string): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2600 });
    await toast.present();
  }
}
