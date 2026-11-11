import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
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

import { AuthService } from '../../core/auth.service';
import { ReleasesService } from '../../core/releases.service';
import { ApiService } from '../../core/api.service';
import { InvitesService } from '../../core/invites.service';
import { extractErrorMessage } from '../../core/error-message';
import type { Competition } from '../../core/models';
import { CompetitionCardComponent } from '../../shared/competition-card.component';
import { InboxTrayComponent } from '../../shared/inbox-tray.component';
import { PageHeroComponent } from '../../shared/page-hero.component';

@Component({
  selector: 'fm-competition-list',
  standalone: true,
  imports: [
    InboxTrayComponent,
    NgTemplateOutlet,
    PageHeroComponent,
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
        <ion-title>{{ auth.isAuthenticated() ? 'My leagues' : 'Leagues' }}</ion-title>
        <ion-buttons slot="end">
          @if (auth.isAuthenticated()) {
            <fm-inbox-tray />
            @if (releases.isOpen('games')) {
              <ion-button type="button" routerLink="/tabs/games" routerDirection="forward">
                <ion-icon slot="start" name="trophy-outline" aria-hidden="true" />
                Games
              </ion-button>
            }
            <ion-button type="button" routerLink="/tabs/competitions/new" routerDirection="forward">
              <ion-icon slot="icon-only" name="add-outline" aria-label="New competition" />
            </ion-button>
          } @else {
            <ion-button type="button" routerLink="/login">Sign in</ion-button>
          }
        </ion-buttons>
      </ion-toolbar>
    </ion-header>

    <ion-content fullscreen="true">
      <ion-refresher slot="fixed" (ionRefresh)="refresh($event)">
        <ion-refresher-content />
      </ion-refresher>

      <div class="page-body">
        @if (loading() || error() || competitions().length === 0) {
          <ng-container [ngTemplateOutlet]="createBanner" />
        }
        @for (invite of competitionInvites.pending(); track invite.id) {
          <div class="pick-banner">
            <p>
              <strong>{{ invite.invited_by_name || 'An organiser' }}</strong> invited you to
              <strong>{{ invite.competition_name }}</strong>.
            </p>
            <ion-button
              size="small"
              (click)="competitionInvites.accept(invite)"
              [disabled]="competitionInvites.answering() === invite.id"
            >
              Accept
            </ion-button>
            <ion-button
              size="small"
              fill="outline"
              (click)="competitionInvites.decline(invite)"
              [disabled]="competitionInvites.answering() === invite.id"
            >
              Decline
            </ion-button>
          </div>
        }
        @for (pick of competitionInvites.teamPicks(); track pick.id) {
          <div class="pick-banner">
            <p>
              <strong>{{ pick.team_name }}</strong> picked you in {{ pick.competition_name }}.
            </p>
            <ion-button
              size="small"
              (click)="competitionInvites.answerPick(pick, 'accept')"
              [disabled]="competitionInvites.answering() === pick.id"
            >
              Accept
            </ion-button>
            <ion-button
              size="small"
              fill="outline"
              (click)="competitionInvites.answerPick(pick, 'decline')"
              [disabled]="competitionInvites.answering() === pick.id"
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
          <h3>{{ auth.isAuthenticated() ? 'No competitions yet' : 'No featured leagues yet' }}</h3>
          <p>
            @if (auth.isAuthenticated()) {
              A league can hold several competitions — an official sport, or one
              with scoring you define. Create one from the banner above.
            } @else {
              Public leagues appear here once organisers feature them. Open one to see the
              table, fixtures and feed — no account needed.
            }
          </p>
        </div>
      } @else {
        @for (competition of competitions(); track competition.id; let index = $index) {
          <fm-competition-card
            [style.--i]="index"
            [competition]="competition"
            [canDelete]="competition.my_role === 'owner'"
            (open)="openCompetition(competition.id)"
            (deleteClick)="confirmDelete(competition)"
          />
        }

        <!-- Competitions are the point of this page, so they come first. -->
        <ng-container [ngTemplateOutlet]="createBanner" />

        <p class="footnote">
          <ion-badge color="light">{{ competitions().length }}</ion-badge>
          shown · last refreshed {{ refreshedAt() | date: 'shortTime' }}
        </p>
      }

      </div>

      <ng-template #createBanner>
        <fm-page-hero
          [eyebrow]="auth.isAuthenticated() ? 'My leagues' : 'Leagues'"
          [title]="auth.isAuthenticated() ? 'Your leagues, live.' : 'See how a league runs.'"
          subtitle="Run as many competitions as you need, each with its own scoring, table and feed."
          image="assets/landing/moment-fans.jpg"
          compact
        >
          <ion-button
            size="small"
            type="button"
            [routerLink]="auth.isAuthenticated() ? '/tabs/competitions/new' : '/register'"
            routerDirection="forward"
          >
            {{ auth.isAuthenticated() ? 'Create a competition' : 'Create an account' }}
          </ion-button>
        </fm-page-hero>
      </ng-template>

      @if (auth.isAuthenticated()) {
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
      }
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
  readonly auth = inject(AuthService);
  readonly releases = inject(ReleasesService);
  private readonly router = inject(Router);
  private readonly alerts = inject(AlertController);
  private readonly toasts = inject(ToastController);

  readonly competitions = signal<Competition[]>([]);
  readonly competitionInvites = inject(InvitesService);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly refreshedAt = signal(new Date());

  constructor() {
    // A new invite or an answered one changes this list.
    this.competitionInvites.arrived.pipe(takeUntilDestroyed()).subscribe(() => this.load(false));
  }

  ionViewWillEnter(): void {
    this.load(this.competitions().length === 0);
    this.competitionInvites.refresh();
  }

  private listQuery(): { mine?: boolean; show_on_landing?: boolean; page_size: number } {
    return this.auth.isAuthenticated()
      ? { mine: true, page_size: 50 }
      : { show_on_landing: true, page_size: 50 };
  }

  load(showSpinner = true): void {
    if (showSpinner) this.loading.set(true);
    this.error.set(null);

    this.api.listCompetitions(this.listQuery()).subscribe({
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
  }

  refresh(event: RefresherCustomEvent): void {
    this.api.listCompetitions(this.listQuery()).subscribe({
      next: (page) => {
        this.competitions.set(page.results);
        this.refreshedAt.set(new Date());
        void event.target.complete();
      },
      error: () => void event.target.complete(),
    });
    this.competitionInvites.refresh();
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
