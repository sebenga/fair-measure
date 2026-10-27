import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnDestroy,
  OnInit,
  inject,
  signal,
  viewChild,
} from '@angular/core';
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
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';

import { forkJoin } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';
import type { CompetitionDetail, TeamPick } from '../../core/models';
import { isPointsTable, showsFantasy } from '../../core/models';
import { RealtimeService, competitionRoom } from '../../core/realtime.service';
import { CompetitionCupComponent } from './tabs/competition-cup.component';
import { CompetitionFantasyComponent } from './tabs/competition-fantasy.component';
import { CompetitionFeedComponent } from './tabs/competition-feed.component';
import { CompetitionFixturesComponent } from './tabs/competition-fixtures.component';
import { CompetitionStandingsComponent } from './tabs/competition-standings.component';

type Tab = 'feed' | 'fixtures' | 'cup' | 'standings' | 'fantasy';

@Component({
  selector: 'fm-competition-detail',
  standalone: true,
  imports: [
    IonHeader,
    IonToolbar,
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
    CompetitionCupComponent,
    CompetitionStandingsComponent,
    CompetitionFantasyComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start">
          <ion-back-button defaultHref="/tabs/competitions" />
        </ion-buttons>
        <div class="title-cluster" slot="start">
          <span class="name">{{ competition()?.name ?? 'Competition' }}</span>
          @if (realtime.connected()) {
            <span class="fm-live" title="Live updates on">Live</span>
          }
        </div>
        <ion-buttons slot="end">
          @if (canScore()) {
            @if (pointsLeague()) {
              <ion-button (click)="openScore()">
                <ion-icon slot="icon-only" name="add-outline" aria-label="Add points" />
              </ion-button>
            } @else {
              <ion-button (click)="openScore()">
                <ion-icon slot="icon-only" name="create-outline" aria-label="Record scores" />
              </ion-button>
            }
          }
          @if (canManage()) {
            <ion-button (click)="openSetup()">
              <ion-icon slot="start" name="options-outline" aria-hidden="true" />
              Setup
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
        <ion-segment [value]="tab()" [scrollable]="true">
          <ion-segment-button value="feed" (click)="selectTab('feed')">
            <ion-label>Feed</ion-label>
          </ion-segment-button>
          @if (showsFixtures()) {
            <ion-segment-button value="fixtures" (click)="selectTab('fixtures')">
              <ion-label>Fixtures</ion-label>
            </ion-segment-button>
          }
          @if (showsCup()) {
            <ion-segment-button value="cup" (click)="selectTab('cup')">
              <ion-label>Cup</ion-label>
            </ion-segment-button>
          }
          @if (competition()?.format !== 'knockout') {
            <ion-segment-button value="standings" (click)="selectTab('standings')">
              <ion-label>Table</ion-label>
            </ion-segment-button>
          }
          @if (showsFantasyTab()) {
            <ion-segment-button value="fantasy" (click)="selectTab('fantasy')">
              <ion-label>Fantasy</ion-label>
            </ion-segment-button>
          }
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
        @if (demoExpiryLabel(); as expiry) {
          <div class="pick-banner">
            <p>This is a one-hour demo. It deletes at {{ expiry }}.</p>
          </div>
        }
        @if (canManage()) {
          <div class="pick-banner">
            <p>Change teams, scoring, fixtures or officials from setup.</p>
            <ion-button size="small" (click)="openSetup()">Open setup</ion-button>
          </div>
        }
        @for (pick of myPicks(); track pick.id) {
          <div class="pick-banner">
            <p><strong>{{ pick.team_name }}</strong> picked you. Accept to join the team.</p>
            <ion-button size="small" (click)="acceptPick(pick)" [disabled]="responding()">Accept</ion-button>
            <ion-button size="small" fill="outline" (click)="declinePick(pick)" [disabled]="responding()">
              Decline
            </ion-button>
          </div>
        }
        @if (tab() !== 'fantasy') {
          @if (governance(); as g) {
            <section class="governance fm-card fm-enter">
              <ion-icon name="ribbon-outline" aria-hidden="true" />
              <div>
                <strong>{{ g.body }}</strong>
                @if (g.rulebook) {
                  <small>Rules: {{ g.rulebook }}</small>
                }
                @if (g.local) {
                  <small>Locally: {{ g.local }}</small>
                }
                @if (howItScores()) {
                  <p>{{ howItScores() }}</p>
                }
              </div>
            </section>
          } @else if (howItScores()) {
            <p class="how-points fm-enter">{{ howItScores() }}</p>
          }
          @if (comp.open_to_scouts || canManage()) {
            <button type="button" class="scouted fm-enter" (click)="openSquad()">
              <ion-icon name="ribbon-outline" aria-hidden="true" />
              <span>
                <strong>{{ canManage() ? 'League squad' : 'Open to scouts' }}</strong>
                <small>
                  {{
                    canManage()
                      ? 'Amend the league squad: add, drop or move players by position.'
                      : 'See the league squad: its best players, picked by position.'
                  }}
                </small>
              </span>
              <ion-icon name="chevron-forward-outline" aria-hidden="true" />
            </button>
          }
          @if (canScheduleNext()) {
            <section class="next-season fm-card fm-enter">
              <ion-icon name="calendar-outline" aria-hidden="true" />
              <div>
                <strong>This season is finished</strong>
                <p>Schedule a new season, or a knockout from the table.</p>
                <div class="actions">
                  <ion-button size="small" [disabled]="scheduling()" (click)="scheduleNext('season')">
                    New season
                  </ion-button>
                  <ion-button size="small" fill="outline" [disabled]="scheduling()" (click)="scheduleNext('knockout')">
                    Knockout
                  </ion-button>
                </div>
              </div>
            </section>
          }
          @if (comp.rules.length) {
            <details class="rules fm-card fm-enter">
              <summary>
                <ion-icon name="book-outline" aria-hidden="true" />
                Rules of play
                <span class="count">{{ comp.rules.length }}</span>
              </summary>
              <ol class="fm-stagger">
                @for (rule of comp.rules; track rule.id) {
                  <li>
                    <strong>{{ rule.name }}</strong>
                    @if (rule.description) {
                      <p>{{ rule.description }}</p>
                    }
                  </li>
                }
              </ol>
            </details>
          }
        }
        @switch (tab()) {
          @case ('feed') {
            <fm-competition-feed [competition]="comp" />
          }
          @case ('fixtures') {
            @if (showsFixtures()) {
              <fm-competition-fixtures [competition]="comp" />
            }
          }
          @case ('cup') {
            @if (showsCup()) {
              <fm-competition-cup [competition]="comp" (changed)="competition.set($event)" />
            }
          }
          @case ('standings') {
            @if (pointsLeague() && canScore()) {
              <div class="add-points">
                <ion-button expand="block" (click)="openScore()">Add points</ion-button>
              </div>
            }
            <fm-competition-standings [competition]="comp" />
          }
          @case ('fantasy') {
            <fm-competition-fantasy [competition]="comp" />
          }
        }
      }
    </ion-content>
  `,
  styles: [
    `
      .title-cluster {
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
        max-width: min(52vw, 240px);
        padding-inline-end: 6px;
      }

      .title-cluster .name {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-size: 1.05rem;
        font-weight: 600;
      }

      @media (max-width: 479px) {
        .title-cluster {
          max-width: min(44vw, 168px);
        }

        .title-cluster .fm-live {
          font-size: 0;
          letter-spacing: 0;
          gap: 0;
        }
      }

      .centered {
        display: grid;
        place-items: center;
        padding: 64px 0;
      }

      .add-points {
        margin: 12px 16px 0;
      }

      .how-points {
        margin: 16px 32px 0;
        color: var(--ion-color-medium);
        font-size: 0.95rem;
        line-height: 1.45;
      }

      .governance {
        display: flex;
        gap: 12px;
        margin: 12px 16px 0;
        padding: 14px 16px;

        > ion-icon {
          flex: 0 0 auto;
          font-size: 1.4rem;
          color: var(--ion-color-primary);
        }

        div {
          display: grid;
          gap: 2px;
        }

        small {
          color: var(--ion-color-medium);
        }

        p {
          margin: 6px 0 0;
          color: var(--ion-color-medium);
          font-size: 0.9rem;
          line-height: 1.45;
        }
      }

      .scouted {
        display: flex;
        align-items: center;
        gap: 12px;
        width: calc(100% - 32px);
        margin: 12px 16px 0;
        padding: 12px 14px;
        border: 0;
        border-radius: 16px;
        background: color-mix(in srgb, var(--ion-color-primary) 10%, transparent);
        color: var(--ion-text-color);
        font: inherit;
        text-align: left;
        cursor: pointer;

        > ion-icon:first-child {
          font-size: 1.4rem;
          color: var(--ion-color-primary);
        }

        span {
          flex: 1 1 auto;
          display: grid;
        }

        small {
          color: var(--ion-color-medium);
        }
      }

      .rules {
        padding: 0;
        overflow: hidden;
      }

      .rules summary {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 14px 16px;
        font-weight: 650;
        cursor: pointer;
        list-style: none;
        transition: background-color 0.2s ease;
      }

      .rules summary::-webkit-details-marker {
        display: none;
      }

      .rules summary::after {
        content: '';
        margin-left: auto;
        width: 8px;
        height: 8px;
        border-right: 2px solid var(--ion-color-medium);
        border-bottom: 2px solid var(--ion-color-medium);
        transform: rotate(45deg);
        transition: transform 0.3s var(--fm-ease-spring);
      }

      .rules[open] summary::after {
        transform: rotate(225deg);
      }

      .rules summary:active {
        background: var(--ion-color-step-50, #f4f5f8);
      }

      .rules .count {
        padding: 1px 8px;
        border-radius: 999px;
        font-size: 0.72rem;
        background: var(--ion-color-step-100, #e9ecf1);
      }

      .rules ol {
        margin: 0;
        padding: 0 16px 14px 36px;
      }

      .rules li + li {
        margin-top: 10px;
      }

      .rules li p {
        margin: 2px 0 0;
        color: var(--ion-color-medium);
        font-size: 0.86rem;
        line-height: 1.45;
      }

      .next-season {
        display: flex;
        gap: 12px;
        margin: 12px 16px 0;
        padding: 14px 16px;

        > ion-icon {
          flex: 0 0 auto;
          font-size: 1.4rem;
          color: var(--ion-color-primary);
        }

        div {
          min-width: 0;
        }

        p {
          margin: 4px 0 10px;
          color: var(--ion-color-medium);
          font-size: 0.9rem;
          line-height: 1.45;
        }

        .actions {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }
      }

      .pick-banner {
        margin: 12px 16px 0;
        padding: 12px;
        border-radius: 12px;
        background: var(--ion-color-light);
        color: var(--ion-color-light-contrast);
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
      }

      .pick-banner p {
        margin: 0;
        flex: 1 1 180px;
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
  private readonly destroyRef = inject(DestroyRef);
  readonly realtime = inject(RealtimeService);

  private competitionId = '';

  private readonly standings = viewChild(CompetitionStandingsComponent);

  readonly competition = signal<CompetitionDetail | null>(null);
  readonly myPicks = signal<TeamPick[]>([]);
  readonly loading = signal(true);
  readonly responding = signal(false);
  readonly error = signal<string | null>(null);
  readonly tab = signal<Tab>('feed');
  readonly scheduling = signal(false);

  ngOnInit(): void {
    this.competitionId = this.route.snapshot.paramMap.get('id') ?? '';
    const requestedTab = this.route.snapshot.queryParamMap.get('tab');
    if (
      requestedTab === 'feed' ||
      requestedTab === 'fixtures' ||
      requestedTab === 'cup' ||
      requestedTab === 'standings' ||
      requestedTab === 'fantasy'
    ) {
      this.tab.set(requestedTab);
    }

    this.load();
    this.realtime.subscribe(competitionRoom(this.competitionId));

    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const tab = params.get('tab');
      if (tab === 'feed' || tab === 'fixtures' || tab === 'cup' || tab === 'standings' || tab === 'fantasy') {
        this.tab.set(tab);
      }
    });

    this.realtime
      .on<{ competition_id: string }>('competition.updated')
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((payload) => {
        if (payload.competition_id === this.competitionId) {
          this.load(false);
        }
      });
  }

  ionViewWillEnter(): void {
    this.standings()?.load(false);
    if (this.competitionId) this.load(false);
  }

  ngOnDestroy(): void {
    if (this.competitionId) {
      this.realtime.unsubscribe(competitionRoom(this.competitionId));
    }
  }

  load(showSpinner = true): void {
    if (showSpinner) this.loading.set(true);
    this.error.set(null);

    forkJoin({
      competition: this.api.getCompetition(this.competitionId),
      picks: this.api.myTeamPicks(this.competitionId),
    }).subscribe({
      next: ({ competition, picks }) => {
        this.competition.set(competition);
        this.myPicks.set(picks);
        if (isPointsTable(competition) && this.tab() === 'fixtures') {
          this.selectTab('standings');
        }
        if (!showsFantasy(competition) && this.tab() === 'fantasy') {
          this.selectTab('feed');
        }
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err));
        this.loading.set(false);
      },
    });
  }

  acceptPick(pick: TeamPick): void {
    this.respond(pick, 'accept');
  }

  declinePick(pick: TeamPick): void {
    this.respond(pick, 'decline');
  }

  private respond(pick: TeamPick, action: 'accept' | 'decline'): void {
    if (this.responding()) return;
    this.responding.set(true);
    const request =
      action === 'accept'
        ? this.api.acceptTeamPick(this.competitionId, pick.id)
        : this.api.declineTeamPick(this.competitionId, pick.id);
    request.subscribe({
      next: () => {
        this.responding.set(false);
        this.load(false);
      },
      error: async (err: unknown) => {
        this.responding.set(false);
        const toast = await this.toasts.create({
          message: extractErrorMessage(err, 'Could not update that pick.'),
          color: 'danger',
          duration: 2500,
        });
        await toast.present();
      },
    });
  }

  pointsLeague(): boolean {
    const competition = this.competition();
    return competition ? isPointsTable(competition) : false;
  }

  /** Governing body and rulebook, for presets that follow one. */
  governance(): { body: string; rulebook: string; local: string } | null {
    const settings = this.competition()?.settings_json ?? {};
    const body = String(settings['governing_body'] ?? '').trim();
    if (!body) return null;
    return {
      body,
      rulebook: String(settings['rulebook'] ?? '').trim(),
      local: String(settings['local_body'] ?? '').trim(),
    };
  }

  howItScores(): string {
    const value = this.competition()?.settings_json?.['description'];
    return typeof value === 'string' ? value : '';
  }

  demoExpiryLabel(): string {
    const settings = this.competition()?.settings_json?.['demo_league'];
    const raw =
      settings && typeof settings === 'object'
        ? (settings as { active?: boolean; expires_at?: string }).expires_at
        : undefined;
    if (!raw || !(settings as { active?: boolean }).active) return '';
    const when = new Date(raw);
    return Number.isNaN(when.getTime()) ? '' : when.toLocaleString();
  }

  showsFixtures(): boolean {
    const structure = this.competition()?.settings_json?.['match_structure'];
    if (Array.isArray(structure) && structure.length > 0) return true;
    return !this.pointsLeague();
  }

  showsCup(): boolean {
    const format = this.competition()?.format;
    return format === 'league' || format === 'league_knockout' || format === 'group_knockout';
  }

  showsFantasyTab(): boolean {
    const competition = this.competition();
    return competition ? showsFantasy(competition) : false;
  }

  selectTab(value: string | undefined): void {
    if (value === 'fixtures' && !this.showsFixtures()) return;
    if (value === 'cup' && !this.showsCup()) return;
    if (value === 'fantasy' && !this.showsFantasyTab()) return;
    if (
      value !== 'feed' &&
      value !== 'fixtures' &&
      value !== 'cup' &&
      value !== 'standings' &&
      value !== 'fantasy'
    ) {
      return;
    }
    if (value === this.tab()) return;
    this.tab.set(value);
  }

  canScore(): boolean {
    const role = this.competition()?.my_role;
    return role === 'owner' || role === 'admin' || role === 'scorer';
  }

  canManage(): boolean {
    const role = this.competition()?.my_role;
    return role === 'owner' || role === 'admin';
  }

  canScheduleNext(): boolean {
    const competition = this.competition();
    return !!competition?.season_finished && this.canManage() && this.showsFixtures();
  }

  async scheduleNext(kind: 'season' | 'knockout'): Promise<void> {
    const competition = this.competition();
    if (!competition || this.scheduling()) return;

    const start = new Date();
    start.setDate(start.getDate() + 7);
    const startsOn = start.toISOString().slice(0, 10);
    const sides = competition.participants.length;
    const inputs: Array<{
      name: string;
      type: 'date' | 'time' | 'number';
      value?: string | number;
      placeholder?: string;
      min?: number;
      max?: number;
    }> = [
      { name: 'starts_on', type: 'date', value: startsOn },
      { name: 'kickoff', type: 'time', value: '15:00' },
    ];
    if (kind === 'knockout' && sides > 2) {
      const suggested = sides >= 8 ? 8 : sides >= 4 ? 4 : sides;
      inputs.push({
        name: 'advance',
        type: 'number',
        value: suggested,
        placeholder: 'Sides that advance',
        min: 2,
        max: sides,
      });
    }

    const alert = await this.alerts.create({
      header: kind === 'knockout' ? 'Schedule a knockout' : 'Schedule a new season',
      message:
        kind === 'knockout'
          ? 'The table order is the seed. Leave the number blank to include every side.'
          : 'Everyone plays everyone again. Completed matches stay in the record.',
      inputs,
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        { text: 'Schedule', role: 'confirm' },
      ],
    });
    await alert.present();
    const { role, data } = await alert.onDidDismiss();
    if (role !== 'confirm') return;

    const values = (data?.values ?? {}) as { starts_on?: string; kickoff?: string; advance?: string };
    const starts = values.starts_on || startsOn;
    const rawKickoff = values.kickoff || '15:00';
    const kickoff = rawKickoff.length === 5 ? `${rawKickoff}:00` : rawKickoff;
    const advance = Number(values.advance);
    this.scheduling.set(true);
    this.api
      .scheduleNextSeason(this.competitionId, {
        kind,
        starts_on: starts,
        kickoff,
        weekdays: competition.match_weekdays,
        ...(kind === 'knockout' && advance >= 2 ? { advance } : {}),
      })
      .subscribe({
        next: (result) => {
          this.scheduling.set(false);
          this.competition.set(result.competition);
          this.selectTab('fixtures');
          void this.toast(
            kind === 'knockout'
              ? `${result.stage.name} is scheduled.`
              : `${result.stage.name} is scheduled.`,
            'success',
          );
        },
        error: (err: unknown) => {
          this.scheduling.set(false);
          void this.toast(
            extractErrorMessage(err, 'Could not schedule the next season.'),
            'danger',
          );
        },
      });
  }

  isOwner(): boolean {
    return this.competition()?.my_role === 'owner';
  }

  openScore(): void {
    void this.router.navigate(['/tabs/competitions', this.competitionId, 'score']);
  }

  openSetup(): void {
    void this.router.navigate(['/tabs/competitions', this.competitionId, 'setup']);
  }

  openSquad(): void {
    void this.router.navigate(['/tabs/competitions', this.competitionId, 'squad']);
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
