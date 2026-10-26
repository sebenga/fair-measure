import { ChangeDetectionStrategy, Component, computed, inject, signal, viewChild } from '@angular/core';
import { Router } from '@angular/router';
import {
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonRefresher,
  IonRefresherContent,
  IonSpinner,
  IonTitle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';
import type { Competition } from '../../core/models';
import type { ContactRequestRow, ScoutingCatalog, ScoutingRoleKey } from '../../core/scouting.models';
import { RatingQueueService } from '../../core/rating-queue.service';
import { ROLE_GUIDE, ScoutingService } from '../../core/scouting.service';
import { InboxTrayComponent } from '../../shared/inbox-tray.component';
import { PromoSlotComponent } from '../../shared/promo-slot.component';

@Component({
  selector: 'fm-scouting-hub',
  standalone: true,
  imports: [
    IonHeader,
    IonToolbar,
    IonTitle,
    IonButtons,
    IonContent,
    IonIcon,
    IonSpinner,
    IonRefresher,
    IonRefresherContent,
    InboxTrayComponent,
    PromoSlotComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './scouting.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-title>Scouting</ion-title>
        <ion-buttons slot="end">
          <fm-inbox-tray />
        </ion-buttons>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      <ion-refresher slot="fixed" (ionRefresh)="refresh($event)">
        <ion-refresher-content />
      </ion-refresher>

      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else {
        <div class="discover-shell">
          <aside class="sponsored-rail left" aria-label="Sponsored">
            <fm-promo-slot
              kind="sponsored"
              eyebrow="Sponsored"
              title="Get found by scouts"
              body="Scouts see your Fair Measure profile. You decide what is shown."
              action="Open my profile"
              icon="person-outline"
              (open)="goAccount()"
            />
          </aside>

          <div class="feed">
        <section class="hero fm-enter">
          <h2>Find talent. Get found.</h2>
          <p>
            Scouts discover players through the match data Fair Measure already records.
            Players decide what is shown, and under-18s stay hidden until a guardian agrees.
          </p>
          @if (roleKeys().length) {
            <div class="chips">
              @for (key of roleKeys(); track key) {
                <span class="badge info">{{ roleTitle(key) }}</span>
              }
            </div>
          } @else {
            <p class="you"><strong>You have no scouting role yet.</strong> Pick one below.</p>
          }
        </section>

        @if (incoming().length || me()?.pending_guardian_requests) {
          <fm-promo-slot
            kind="suggested"
            eyebrow="Needs a reply"
            [title]="inboxTitle()"
            [body]="inboxBody()"
            action="Open inbox"
            icon="mail-outline"
            (open)="go(me()?.pending_guardian_requests ? 'guardian' : 'requests')"
          />
        }

        @if (trials().length) {
          <section class="rail">
            <h3 class="fm-section-title">Featured leagues looking for talent</h3>
            <div class="scroller">
              @for (league of trials(); track league.id) {
                <button type="button" class="chip" (click)="openLeague(league)">
                  <strong>{{ league.name }}</strong>
                  <small>Open to scouts · {{ league.sport || 'League' }}</small>
                </button>
              }
            </div>
          </section>
        }

        <div class="quick fm-stagger">
          <button type="button" class="tile" (click)="goAccount()">
            <ion-icon name="person-outline" aria-hidden="true" />
            <strong>My profile</strong>
            <small>Name, age and who can see you</small>
          </button>
          <button type="button" class="tile" (click)="go('guardian')">
            <ion-icon name="shield-checkmark-outline" aria-hidden="true" />
            <strong>Guardian consent</strong>
            <small>
              @if (me()?.pending_guardian_requests) {
                <span class="badge warn">{{ me()?.pending_guardian_requests }} waiting</span>
              } @else {
                {{ me()?.guarding ? me()?.guarding + ' player(s)' : 'For parents' }}
              }
            </small>
          </button>
          @if (canRate()) {
            <button type="button" class="tile" (click)="go('search')">
              <ion-icon name="options-outline" aria-hidden="true" />
              <strong>Talent search</strong>
              <small>Filters, saved searches and alerts</small>
            </button>
            <button type="button" class="tile" (click)="go('shortlists')">
              <ion-icon name="list-outline" aria-hidden="true" />
              <strong>Shortlists</strong>
              <small>Your organisation's targets</small>
            </button>
          }
          <button type="button" class="tile" (click)="go('requests')">
            <ion-icon name="mail-outline" aria-hidden="true" />
            <strong>Contact requests</strong>
            <small>{{ canRate() ? 'Sent and received' : 'Scouts who want to talk' }}</small>
          </button>
          @if (canRate()) {
            <button type="button" class="tile" (click)="go('rate')">
              <ion-icon name="star-outline" aria-hidden="true" />
              <strong>Rate a player</strong>
              <small>
                @if (queue.pending()) {
                  <span class="badge warn">{{ queue.pending() }} waiting to sync</span>
                } @else {
                  Pitch-side, works offline
                }
              </small>
            </button>
          }
          @if (canBrowse()) {
            <button type="button" class="tile" (click)="go('players')">
              <ion-icon name="search-outline" aria-hidden="true" />
              <strong>Browse players</strong>
              <small>Profiles and scouting reports</small>
            </button>
          }
          <button type="button" class="tile" (click)="go('leagues')">
            <ion-icon name="shirt-outline" aria-hidden="true" />
            <strong>League squads</strong>
            <small>Each league's best 23</small>
          </button>
          @if (isCoachOrPlayer()) {
            <button type="button" class="tile" (click)="go('record-test')">
              <ion-icon name="stopwatch-outline" aria-hidden="true" />
              <strong>Record a test result</strong>
              <small>Sprint, jump and fitness tests</small>
            </button>
          }
          <button type="button" class="tile" (click)="go('guide')">
            <ion-icon name="book-outline" aria-hidden="true" />
            <strong>Rating guide</strong>
            <small>Attributes, tests and stats per sport</small>
          </button>
          @for (organisation of me()?.organisations ?? []; track organisation.id) {
            <button type="button" class="tile" (click)="go('organisations/' + organisation.id)">
              <ion-icon name="business-outline" aria-hidden="true" />
              <strong>{{ organisation.name }}</strong>
              <small>{{ organisation.scout_count }} scout(s) · {{ organisation.my_role === 'scout_admin' ? 'Admin' : 'Scout' }}</small>
            </button>
          }
        </div>

        <h3 class="fm-section-title">Who uses scouting</h3>
        <div class="fm-stagger">
          @for (guide of roles; track guide.key) {
            <article class="role fm-card" [class.mine]="has(guide.key)">
              <header>
                <span class="icon"><ion-icon [name]="guide.icon" aria-hidden="true" /></span>
                <div>
                  <h4>{{ guide.title }}</h4>
                  <p>{{ guide.summary }}</p>
                </div>
                @if (has(guide.key)) {
                  <span class="badge ok">You</span>
                }
              </header>
              <ul>
                @for (line of guide.can; track line) {
                  <li>{{ line }}</li>
                }
              </ul>

              @switch (guide.key) {
                @case ('player') {
                  <button type="button" class="btn block" (click)="goAccount()">Open my profile</button>
                }
                @case ('guardian') {
                  <p class="how">A player invites you by email from their profile. Then confirm it here.</p>
                  <button type="button" class="btn ghost block" (click)="go('guardian')">Open guardian consent</button>
                }
                @case ('scout') {
                  <p class="how">A scout admin adds you to their organisation using your account email.</p>
                }
                @case ('scout_admin') {
                  @if (creatingOrg()) {
                    <form class="inline-form" (submit)="createOrganisation($event)">
                      <label class="field">
                        Organisation name
                        <input [value]="orgName()" (input)="orgName.set($any($event.target).value)" required maxlength="160" />
                      </label>
                      <div class="row">
                        <label class="field">
                          Type
                          <select [value]="orgKind()" (change)="orgKind.set($any($event.target).value)">
                            <option value="club">Club</option>
                            <option value="academy">Academy</option>
                            <option value="school">School</option>
                            <option value="agency">Agency</option>
                          </select>
                        </label>
                        <label class="field">
                          Region
                          <select [value]="orgRegion()" (change)="orgRegion.set($any($event.target).value)">
                            <option value="">Choose</option>
                            @for (region of catalog()?.regions ?? []; track region.key) {
                              <option [value]="region.key" [selected]="region.key === orgRegion()">{{ region.label }}</option>
                            }
                          </select>
                        </label>
                      </div>
                      <div class="row">
                        <button type="button" class="btn ghost" (click)="creatingOrg.set(false)">Cancel</button>
                        <button type="submit" class="btn" [disabled]="busy() || !orgName().trim()">Create</button>
                      </div>
                    </form>
                  } @else {
                    <button type="button" class="btn ghost block" (click)="creatingOrg.set(true)">
                      Create an organisation
                    </button>
                  }
                }
                @case ('coach') {
                  @if (teams().length) {
                    <label class="field">
                      Team you coach
                      <select [value]="teamChoice()" (change)="teamChoice.set($any($event.target).value)">
                        <option value="">Choose a team</option>
                        @for (team of teams(); track team.id) {
                          <option [value]="team.id">{{ team.name }} · {{ team.competition }}</option>
                        }
                      </select>
                    </label>
                    <button type="button" class="btn ghost block" [disabled]="!teamChoice() || busy()" (click)="becomeCoach()">
                      Coach this team
                    </button>
                  } @else {
                    <p class="how">Manage a team, or run a competition, to coach its players.</p>
                  }
                  @for (role of coachRoles(); track role.id) {
                    <p class="how">Coaching <strong>{{ role.team_name }}</strong></p>
                  }
                }
              }
            </article>
          }
        </div>
        <div class="tail"></div>
          </div>

          <aside class="sponsored-rail right" aria-label="Sponsored">
            @if (canRate()) {
              <fm-promo-slot
                kind="sponsored"
                eyebrow="Sponsored"
                title="Saved searches that ping you"
                body="Get notified when a player matches your filters — the same habit as a LinkedIn job alert."
                action="Set up talent alerts"
                icon="notifications-outline"
                (open)="go('search')"
              />
            } @else {
              <fm-promo-slot
                kind="sponsored"
                eyebrow="Sponsored"
                title="Talent alerts for scouts"
                body="When you join a scouting organisation, this rail is where saved-search ads land."
                action="Open rating guide"
                icon="notifications-outline"
                (open)="go('guide')"
              />
            }
            @if (trials()[0]; as lead) {
              <fm-promo-slot
                kind="sponsored"
                eyebrow="Sponsored"
                [title]="lead.name"
                [body]="'Looking for talent · ' + (lead.sport || 'League')"
                action="Open league"
                icon="ribbon-outline"
                (open)="openLeague(lead)"
              />
            }
          </aside>
        </div>
      }
    </ion-content>
  `,
  styles: [
    `
      .discover-shell {
        display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(128px, 34vw);
        align-items: start;
        gap: 12px;
        padding: 0 8px 24px;
      }

      .sponsored-rail {
        position: sticky;
        top: 8px;
        display: grid;
      }

      .sponsored-rail.left {
        display: none;
      }

      .feed {
        min-width: 0;
      }

      @media (min-width: 1024px) {
        .discover-shell {
          grid-template-columns: 220px minmax(0, 1fr) 220px;
          padding: 0 16px 24px;
        }

        .sponsored-rail.left {
          display: grid;
        }
      }

      .hero {
        margin: 12px 16px;
        padding: 20px 18px;
        border-radius: var(--fm-radius);
        color: #fff;
        background: linear-gradient(135deg, var(--ion-color-primary-shade), var(--ion-color-secondary));
        box-shadow: var(--fm-shadow);

        h2 {
          margin: 0 0 6px;
          font-size: 1.35rem;
          font-weight: 800;
        }

        p {
          margin: 0 0 12px;
          opacity: 0.92;
          line-height: 1.45;
          font-size: 0.92rem;
        }

        .you {
          margin: 0;
        }

        .badge.info {
          background: rgb(255 255 255 / 0.22);
          color: #fff;
        }
      }

      .quick {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
        padding: 0 16px;
      }

      .tile {
        display: grid;
        gap: 4px;
        justify-items: start;
        min-height: 104px;
        padding: 14px;
        border: 0;
        border-radius: var(--fm-radius);
        background: var(--ion-card-background, #fff);
        box-shadow: var(--fm-shadow);
        color: var(--ion-text-color);
        text-align: left;
        font: inherit;
        cursor: pointer;
        transition: transform 0.2s var(--fm-ease-spring);

        &:active {
          transform: scale(0.96);
        }

        ion-icon {
          font-size: 1.5rem;
          color: var(--ion-color-primary);
        }

        small {
          color: var(--ion-color-medium);
        }
      }

      .role header {
        display: flex;
        align-items: flex-start;
        gap: 12px;

        h4 {
          margin: 0;
          font-size: 1rem;
        }

        p {
          margin: 2px 0 0;
          color: var(--ion-color-medium);
          font-size: 0.86rem;
        }

        div {
          flex: 1 1 auto;
        }
      }

      .role .icon {
        display: grid;
        place-items: center;
        width: 40px;
        height: 40px;
        border-radius: 12px;
        font-size: 1.25rem;
        color: var(--ion-color-primary);
        background: color-mix(in srgb, var(--ion-color-primary) 12%, transparent);
      }

      .role.mine {
        box-shadow:
          var(--fm-shadow),
          inset 3px 0 0 var(--ion-color-success);
      }

      .role ul {
        margin: 10px 0 12px;
        padding-left: 1.1rem;
        font-size: 0.86rem;
        line-height: 1.55;
      }

      .how {
        margin: 0 0 10px;
        font-size: 0.84rem;
        color: var(--ion-color-medium);
      }

      .inline-form {
        display: grid;
      }

      .tail {
        height: 32px;
      }

      .rail {
        margin: 8px 0 16px;
      }

      .scroller {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        padding: 0 16px 4px;
      }

      .chip {
        flex: 0 0 210px;
        display: grid;
        gap: 2px;
        padding: 12px;
        border: 0;
        border-radius: 14px;
        background: var(--ion-card-background, #fff);
        box-shadow: var(--fm-shadow);
        color: inherit;
        font: inherit;
        text-align: left;
      }

      .chip small {
        color: var(--ion-color-medium);
      }
    `,
  ],
})
export class ScoutingHubPage {
  private readonly scouting = inject(ScoutingService);
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastController);

  readonly roles = ROLE_GUIDE;
  readonly me = this.scouting.me;
  readonly catalog = signal<ScoutingCatalog | null>(null);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly teams = signal<Array<{ id: string; name: string; competition: string }>>([]);
  readonly teamChoice = signal('');
  readonly creatingOrg = signal(false);
  readonly orgName = signal('');
  readonly orgKind = signal('club');
  readonly orgRegion = signal('');
  readonly incoming = signal<ContactRequestRow[]>([]);
  readonly trials = signal<Competition[]>([]);
  private readonly inbox = viewChild(InboxTrayComponent);

  readonly roleKeys = computed(() => this.me()?.role_keys ?? []);
  readonly coachRoles = computed(() => (this.me()?.roles ?? []).filter((role) => role.role === 'coach'));
  readonly canBrowse = computed(() =>
    this.roleKeys().some((key) => key === 'scout' || key === 'scout_admin' || key === 'coach'),
  );

  readonly queue = inject(RatingQueueService);
  readonly canRate = computed(() =>
    (this.scouting.me()?.role_keys ?? []).some((role) => role === 'scout' || role === 'scout_admin'),
  );

  readonly inboxTitle = computed(() => {
    const waiting = this.me()?.pending_guardian_requests ?? 0;
    if (waiting) return `${waiting} guardian request${waiting === 1 ? '' : 's'} waiting`;
    const mail = this.incoming().length;
    return `${mail} scout contact${mail === 1 ? '' : 's'} to review`;
  });

  readonly inboxBody = computed(() =>
    this.me()?.pending_guardian_requests
      ? 'A parent or player needs you to confirm access before a profile can be shown.'
      : 'Someone wants to talk. Reply from Contact requests — this is your talent inbox.',
  );

  readonly isCoachOrPlayer = computed(() => {
    const roles = this.scouting.me()?.role_keys ?? [];
    return roles.includes('coach') || !!this.scouting.me()?.profile_id;
  });

  ionViewWillEnter(): void {
    this.load();
    this.inbox()?.refresh();
  }

  load(done?: () => void): void {
    this.scouting.catalog().subscribe((catalog) => this.catalog.set(catalog));
    this.scouting.myTeams().subscribe((teams) => this.teams.set(teams));
    this.scouting.contactRequests('received').subscribe({
      next: (rows) => this.incoming.set(rows.filter((row) => row.status === 'pending')),
      error: () => this.incoming.set([]),
    });
    this.api.listCompetitions({ page_size: 20 }).subscribe({
      next: (page) => this.trials.set(page.results.filter((row) => row.open_to_scouts).slice(0, 8)),
      error: () => this.trials.set([]),
    });
    this.scouting.loadMe().subscribe({
      next: () => {
        this.loading.set(false);
        done?.();
      },
      error: async (err: unknown) => {
        this.loading.set(false);
        done?.();
        await this.toast(extractErrorMessage(err, 'Could not load scouting.'), 'danger');
      },
    });
  }

  refresh(event: Event): void {
    this.load(() => (event.target as HTMLIonRefresherElement).complete());
  }

  has(key: ScoutingRoleKey): boolean {
    return this.roleKeys().includes(key);
  }

  roleTitle(key: ScoutingRoleKey): string {
    return this.roles.find((role) => role.key === key)?.title ?? key;
  }

  go(path: string): void {
    void this.router.navigateByUrl(`/tabs/scouting/${path}`);
  }

  goAccount(): void {
    void this.router.navigateByUrl('/tabs/profile');
  }

  openLeague(league: Competition): void {
    void this.router.navigate(['/tabs/competitions', league.id]);
  }

  createOrganisation(event: Event): void {
    event.preventDefault();
    if (this.busy() || !this.orgName().trim()) return;
    this.busy.set(true);
    this.scouting
      .createOrganisation({ name: this.orgName().trim(), kind: this.orgKind(), region: this.orgRegion() })
      .subscribe({
        next: async (organisation) => {
          this.busy.set(false);
          this.creatingOrg.set(false);
          this.orgName.set('');
          await this.toast(`${organisation.name} created. You are its scout admin.`, 'success');
          this.load();
        },
        error: async (err: unknown) => {
          this.busy.set(false);
          await this.toast(extractErrorMessage(err, 'Could not create the organisation.'), 'danger');
        },
      });
  }

  becomeCoach(): void {
    if (!this.teamChoice() || this.busy()) return;
    this.busy.set(true);
    this.scouting.becomeCoach(this.teamChoice()).subscribe({
      next: async (role) => {
        this.busy.set(false);
        this.teamChoice.set('');
        await this.toast(`You now coach ${role.team_name}.`, 'success');
        this.load();
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not add the coach role.'), 'danger');
      },
    });
  }

  private async toast(message: string, color: 'success' | 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2600, position: 'top' });
    await toast.present();
  }
}
