import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import {
  AlertController,
  IonBadge,
  IonButton,
  IonButtons,
  IonContent,
  IonFab,
  IonFabButton,
  IonHeader,
  IonIcon,
  IonRefresher,
  IonRefresherContent,
  IonSkeletonText,
  IonTitle,
  IonToolbar,
  ToastController,
  type RefresherCustomEvent,
} from '@ionic/angular/standalone';

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';
import type { Competition, TeamPick } from '../../core/models';
import { CompetitionCardComponent } from '../../shared/competition-card.component';

@Component({
  selector: 'fm-competition-list',
  standalone: true,
  imports: [
    DatePipe,
    RouterLink,
    IonHeader,
    IonToolbar,
    IonTitle,
    IonButtons,
    IonButton,
    IonContent,
    IonRefresher,
    IonRefresherContent,
    IonFab,
    IonFabButton,
    IonIcon,
    IonBadge,
    IonSkeletonText,
    CompetitionCardComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-header translucent="true">
      <ion-toolbar>
        <ion-title>My leagues</ion-title>
        <ion-buttons slot="end">
          <ion-button type="button" routerLink="/tabs/games" routerDirection="forward">
            <ion-icon slot="start" name="trophy-outline" aria-hidden="true" />
            Games
          </ion-button>
          <ion-button type="button" routerLink="/tabs/competitions/new" routerDirection="forward">
            <ion-icon slot="icon-only" name="add-outline" aria-label="New competition" />
          </ion-button>
        </ion-buttons>
      </ion-toolbar>
    </ion-header>

    <ion-content fullscreen="true">
      <ion-refresher slot="fixed" (ionRefresh)="refresh($event)">
        <ion-refresher-content />
      </ion-refresher>

      <div class="page-body">
        @for (invite of invites(); track invite.id) {
          <div class="pick-banner">
            <p>
              <strong>{{ invite.team_name }}</strong> picked you in {{ invite.competition_name }}.
            </p>
            <ion-button size="small" (click)="acceptInvite(invite)" [disabled]="responding() === invite.id">
              Accept
            </ion-button>
            <ion-button
              size="small"
              fill="outline"
              (click)="declineInvite(invite)"
              [disabled]="responding() === invite.id"
            >
              Decline
            </ion-button>
          </div>
        }
        @if (loading()) {
          @for (placeholder of [1, 2, 3]; track placeholder) {
            <div class="fm-card">
              <ion-skeleton-text animated style="width: 55%; height: 20px" />
              <ion-skeleton-text animated style="width: 35%" />
              <ion-skeleton-text animated style="width: 80%" />
            </div>
          }
        } @else if (error()) {
        <div class="fm-empty">
          <ion-icon name="flag-outline" aria-hidden="true" />
          <h3>Could not load your leagues</h3>
          <p>{{ error() }}</p>
          <ion-button fill="clear" (click)="load()">Try again</ion-button>
        </div>
      } @else if (competitions().length === 0) {
        <div class="fm-empty">
          <ion-icon name="trophy-outline" aria-hidden="true" />
          <h3>No competitions yet</h3>
          <p>
            A league can hold several competitions — an official sport, or one
            with scoring you define. Create one, then add more from here.
          </p>
          <ion-button type="button" routerLink="/tabs/competitions/new" routerDirection="forward">
            Create a competition
          </ion-button>
        </div>
      } @else {
        <p class="lede">
          You can run as many competitions as you need. Each has its own scoring.
        </p>
        @for (competition of competitions(); track competition.id; let index = $index) {
          <fm-competition-card
            [style.--i]="index"
            [competition]="competition"
            [canDelete]="competition.my_role === 'owner'"
            (open)="openCompetition(competition.id)"
            (deleteClick)="confirmDelete(competition)"
          />
        }

        <p class="footnote">
          <ion-badge color="light">{{ competitions().length }}</ion-badge>
          shown · last refreshed {{ refreshedAt() | date: 'shortTime' }}
        </p>
      }

      </div>

      <ion-fab slot="fixed" vertical="bottom" horizontal="end">
        <ion-fab-button
          type="button"
          routerLink="/tabs/competitions/new"
          routerDirection="forward"
          aria-label="New competition"
        >
          <ion-icon name="add-outline" />
        </ion-fab-button>
      </ion-fab>
    </ion-content>
  `,
  styles: [
    `
      .lede {
        margin: 16px 20px 4px;
        font-size: 0.82rem;
        line-height: 1.45;
        color: var(--ion-color-medium);
      }

      .footnote {
        text-align: center;
        color: var(--ion-color-medium);
        font-size: 0.78rem;
        margin: 20px 16px 96px;
      }

      .page-body {
        position: relative;
        z-index: 1;
      }

      .pick-banner {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 8px;
        margin: 12px 16px 0;
        padding: 12px 14px;
        border-radius: 14px;
        background: color-mix(in srgb, var(--ion-color-primary) 12%, transparent);
      }

      .pick-banner p {
        flex: 1 1 160px;
        margin: 0;
        font-size: 0.9rem;
        line-height: 1.4;
      }
    `,
  ],
})
export class CompetitionListPage {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly alerts = inject(AlertController);
  private readonly toasts = inject(ToastController);

  readonly competitions = signal<Competition[]>([]);
  readonly invites = signal<TeamPick[]>([]);
  readonly responding = signal<string | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly refreshedAt = signal(new Date());

  ionViewWillEnter(): void {
    this.load(this.competitions().length === 0);
  }

  load(showSpinner = true): void {
    if (showSpinner) this.loading.set(true);
    this.error.set(null);

    this.api.listCompetitions({ mine: true, page_size: 50 }).subscribe({
      next: (page) => {
        this.competitions.set(page.results);
        this.refreshedAt.set(new Date());
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err));
        this.loading.set(false);
      },
    });
    this.api.myPendingTeamPicks().subscribe({
      next: (picks) => this.invites.set(picks),
      error: () => this.invites.set([]),
    });
  }

  refresh(event: RefresherCustomEvent): void {
    this.api.listCompetitions({ mine: true, page_size: 50 }).subscribe({
      next: (page) => {
        this.competitions.set(page.results);
        this.refreshedAt.set(new Date());
        void event.target.complete();
      },
      error: () => void event.target.complete(),
    });
    this.api.myPendingTeamPicks().subscribe({
      next: (picks) => this.invites.set(picks),
    });
  }

  acceptInvite(invite: TeamPick): void {
    this.respondInvite(invite, 'accept');
  }

  declineInvite(invite: TeamPick): void {
    this.respondInvite(invite, 'decline');
  }

  private respondInvite(invite: TeamPick, action: 'accept' | 'decline'): void {
    if (this.responding()) return;
    this.responding.set(invite.id);
    const request =
      action === 'accept'
        ? this.api.acceptTeamPick(invite.competition, invite.id)
        : this.api.declineTeamPick(invite.competition, invite.id);
    request.subscribe({
      next: () => {
        this.responding.set(null);
        this.invites.update((rows) => rows.filter((row) => row.id !== invite.id));
        this.load(false);
        void this.toast(
          action === 'accept' ? `You joined ${invite.team_name}.` : 'Invite declined.',
          'success',
        );
      },
      error: (err: unknown) => {
        this.responding.set(null);
        void this.toast(extractErrorMessage(err, 'Could not update that invite.'), 'danger');
      },
    });
  }

  openCompetition(id: string): void {
    void this.router.navigate(['/tabs/competitions', id]);
  }

  async confirmDelete(competition: Competition): Promise<void> {
    const alert = await this.alerts.create({
      header: `Delete ${competition.name}?`,
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

    this.api.deleteCompetition(competition.id).subscribe({
      next: () => {
        this.competitions.update((current) =>
          current.filter((item) => item.id !== competition.id),
        );
        void this.toast('Competition deleted.', 'success');
      },
      error: (err: unknown) => {
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
