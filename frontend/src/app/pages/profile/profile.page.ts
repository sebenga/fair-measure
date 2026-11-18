import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  AlertController,
  IonAvatar,
  IonButton,
  IonContent,
  IonHeader,
  IonIcon,
  IonInput,
  IonItem,
  IonLabel,
  IonList,
  IonNote,
  IonSpinner,
  IonTextarea,
  IonTitle,
  IonToggle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';
import { catchError, of } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { ReleasesService } from '../../core/releases.service';
import { extractErrorMessage } from '../../core/error-message';
import type { Competition } from '../../core/models';
import { PushService } from '../../core/push.service';
import { RealtimeService } from '../../core/realtime.service';
import { ProfileTalentComponent } from './profile-talent.component';
import { FeatureSwitchComponent } from '../../shared/feature-switch.component';
import { LegalFooterComponent } from '../../shared/legal-footer.component';

type DashTile = {
  id: string;
  label: string;
  hint: string;
  icon: string;
  link: string;
  accent?: boolean;
};

/**
 * Organiser dashboard: manage leagues and commercial tools first; account and
 * scouting details stay available below so the page scales as more admin
 * surfaces are added.
 */
@Component({
  selector: 'fm-profile',
  standalone: true,
  imports: [
    FeatureSwitchComponent,
    LegalFooterComponent,
    ReactiveFormsModule,
    RouterLink,
    IonHeader,
    IonToolbar,
    IonTitle,
    IonContent,
    IonAvatar,
    IonList,
    IonItem,
    IonLabel,
    IonInput,
    IonTextarea,
    IonToggle,
    IonButton,
    IonIcon,
    IonNote,
    IonSpinner,
    ProfileTalentComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-header translucent="true">
      <ion-toolbar>
        <ion-title>Dashboard</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content fullscreen="true">
      <ion-header collapse="condense">
        <ion-toolbar>
          <ion-title size="large">Dashboard</ion-title>
        </ion-toolbar>
      </ion-header>

      @if (auth.user(); as user) {
        <div class="dash">
          <header class="identity">
            <ion-avatar>
              @if (user.avatar_url) {
                <img [src]="user.avatar_url" [alt]="user.display_name" />
              } @else {
                <span class="initials">{{ initials(user.display_name) }}</span>
              }
            </ion-avatar>
            <div class="who">
              <h1>{{ user.display_name }}</h1>
              @if (legalName(user)) {
                <p class="legal">{{ legalName(user) }}</p>
              }
              <p>{{ user.email }}</p>
            </div>
            <button type="button" class="edit-account" (click)="scrollToAccount()">
              Edit account
            </button>
          </header>

          <section class="stats" aria-label="At a glance">
            <div class="stat">
              <strong>{{ managedCount() }}</strong>
              <span>Managed</span>
            </div>
            <div class="stat">
              <strong>{{ activeCount() }}</strong>
              <span>In play</span>
            </div>
            <div class="stat">
              <strong>{{ draftCount() }}</strong>
              <span>Draft</span>
            </div>
            <div class="stat">
              <strong [class.on]="realtime.connected()">{{ realtime.connected() ? 'Live' : 'Off' }}</strong>
              <span>Updates</span>
            </div>
          </section>

          <section class="panel" aria-labelledby="manage-heading">
            <div class="panel-head">
              <div>
                <p class="eyebrow">Organiser</p>
                <h2 id="manage-heading">Manage</h2>
              </div>
            </div>
            <div class="tiles">
              @for (tile of tiles(); track tile.id) {
                <a class="tile" [class.accent]="tile.accent" [routerLink]="tile.link">
                  <span class="tile-icon" aria-hidden="true">
                    <ion-icon [name]="tile.icon" />
                  </span>
                  <strong>{{ tile.label }}</strong>
                  <small>{{ tile.hint }}</small>
                </a>
              }
            </div>
            @if (releases.platformAdmin()) {
              <fm-feature-switch feature="games" label="Games" icon="trophy-outline" />
            }
          </section>

          <section class="panel" aria-labelledby="leagues-heading">
            <div class="panel-head">
              <div>
                <p class="eyebrow">Competitions</p>
                <h2 id="leagues-heading">Leagues you manage</h2>
              </div>
              <a routerLink="/tabs/competitions">All leagues</a>
            </div>

            @if (leaguesLoading()) {
              <div class="league-skeleton" aria-hidden="true">
                <span></span><span></span><span></span>
              </div>
            } @else if (leaguesError()) {
              <p class="panel-note" role="alert">{{ leaguesError() }}</p>
              <button type="button" class="text-btn" (click)="loadManaged()">Try again</button>
            } @else if (!managed().length) {
              <p class="panel-note">
                You do not manage a competition yet. Create one, or accept an admin invite.
              </p>
              <a class="text-btn" routerLink="/tabs/competitions/new">Create a competition</a>
            } @else {
              <ul class="league-list">
                @for (league of managedPreview(); track league.id) {
                  <li>
                    <a class="league" [routerLink]="['/tabs/competitions', league.id]">
                      <span class="badge" aria-hidden="true">{{ initials(league.name) }}</span>
                      <span class="grow">
                        <strong>{{ league.name }}</strong>
                        <small>
                          {{ roleLabel(league) }} · {{ statusLabel(league) }}
                          @if (league.sport) {
                            · {{ league.sport }}
                          }
                        </small>
                      </span>
                    </a>
                    <a
                      class="setup"
                      [routerLink]="['/tabs/competitions', league.id, 'setup']"
                      aria-label="Open setup for {{ league.name }}"
                    >
                      Setup
                    </a>
                  </li>
                }
              </ul>
              @if (managed().length > managedPreview().length) {
                <a class="text-btn" routerLink="/tabs/competitions">
                  View all {{ managed().length }} managed leagues
                </a>
              }
            }
          </section>

          <section class="panel soft" aria-labelledby="account-heading">
            <div class="panel-head">
              <div>
                <p class="eyebrow">Account</p>
                <h2 id="account-heading">Profile and scouting</h2>
              </div>
            </div>
            <p class="panel-note">
              Scouts only see profiles with every personal field filled in. ID number and phone stay
              private.
            </p>

            <fm-profile-talent />

            <form id="account-details" [formGroup]="form" (ngSubmit)="save()">
              <h3 class="fm-section-title">Display</h3>
              <ion-list inset="true">
                <ion-item>
                  <ion-input
                    label="Display name"
                    labelPlacement="stacked"
                    formControlName="display_name"
                    maxlength="120"
                  />
                </ion-item>
                <ion-item>
                  <ion-textarea
                    label="Bio"
                    labelPlacement="stacked"
                    formControlName="bio"
                    autoGrow="true"
                    rows="2"
                    maxlength="500"
                    placeholder="A line about you"
                  />
                </ion-item>
                <ion-item>
                  <ion-input
                    label="Avatar URL"
                    labelPlacement="stacked"
                    formControlName="avatar_url"
                    inputmode="url"
                    placeholder="https://…"
                  />
                </ion-item>
              </ion-list>

              <h3 class="fm-section-title">Personal details</h3>
              <ion-list inset="true">
                <ion-item>
                  <ion-input label="Name" labelPlacement="stacked" formControlName="given_name" maxlength="80" />
                </ion-item>
                <ion-item>
                  <ion-input
                    label="Surname"
                    labelPlacement="stacked"
                    formControlName="family_name"
                    maxlength="80"
                  />
                </ion-item>
                <ion-item>
                  <ion-input
                    label="Date of birth"
                    labelPlacement="stacked"
                    type="date"
                    formControlName="date_of_birth"
                  />
                </ion-item>
                <ion-item>
                  <ion-input
                    label="ID number (required)"
                    labelPlacement="stacked"
                    formControlName="id_number"
                    maxlength="40"
                    autocomplete="off"
                    errorText="Your ID number is required."
                  />
                </ion-item>
                <ion-item>
                  <ion-input
                    label="Phone"
                    labelPlacement="stacked"
                    type="tel"
                    formControlName="phone"
                    maxlength="40"
                  />
                </ion-item>
                <ion-item>
                  <ion-input label="City" labelPlacement="stacked" formControlName="city" maxlength="80" />
                </ion-item>
                <ion-item>
                  <ion-input
                    label="Country"
                    labelPlacement="stacked"
                    formControlName="country"
                    maxlength="80"
                  />
                </ion-item>
              </ion-list>

              @if (form.controls.id_number.invalid) {
                <p class="hint">Add your ID number to save your profile.</p>
              }
              @if (error()) {
                <p class="fm-form-error" role="alert">{{ error() }}</p>
              }

              <ion-button
                type="submit"
                expand="block"
                class="save"
                [disabled]="form.pristine || form.invalid || saving()"
              >
                @if (saving()) {
                  <ion-spinner name="crescent" />
                } @else {
                  Save changes
                }
              </ion-button>
            </form>

            <h3 class="fm-section-title">Notifications</h3>
            <ion-list inset="true">
              <ion-item>
                <ion-toggle
                  [checked]="push.enabled()"
                  [disabled]="!push.supported() || push.busy()"
                  (ionChange)="togglePush($any($event).detail.checked)"
                >
                  <ion-label>
                    <h2>Push notifications</h2>
                    <p>{{ pushDescription() }}</p>
                  </ion-label>
                </ion-toggle>
              </ion-item>
            </ion-list>

            <h3 class="fm-section-title">Connection</h3>
            <ion-list inset="true">
              <ion-item lines="none">
                <ion-label>
                  <h2>Live updates</h2>
                  <p>{{ realtime.connected() ? 'Connected' : 'Offline' }}</p>
                </ion-label>
                <ion-icon
                  slot="end"
                  [name]="realtime.connected() ? 'ellipse' : 'ellipse-outline'"
                  [color]="realtime.connected() ? 'success' : 'medium'"
                  aria-hidden="true"
                />
              </ion-item>
            </ion-list>

            <ion-button expand="block" fill="clear" color="danger" (click)="confirmLogout()">
              Sign out
            </ion-button>

            <ion-note class="footnote">Member since {{ memberSince(user.date_joined) }}</ion-note>
          </section>
        </div>
      }
      <fm-legal-footer />
    </ion-content>
  `,
  styleUrl: './profile.page.scss',
})
export class ProfilePage implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(ApiService);
  private readonly alerts = inject(AlertController);
  private readonly toasts = inject(ToastController);

  readonly auth = inject(AuthService);
  readonly releases = inject(ReleasesService);
  readonly realtime = inject(RealtimeService);
  readonly push = inject(PushService);

  private readonly talent = viewChild(ProfileTalentComponent);

  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly leaguesLoading = signal(true);
  readonly leaguesError = signal<string | null>(null);
  readonly mine = signal<Competition[]>([]);

  readonly managed = computed(() =>
    this.mine().filter((row) => row.my_role === 'owner' || row.my_role === 'admin'),
  );
  readonly managedPreview = computed(() => this.managed().slice(0, 6));
  readonly managedCount = computed(() => this.managed().length);
  readonly activeCount = computed(
    () => this.managed().filter((row) => row.status === 'active').length,
  );
  readonly draftCount = computed(
    () => this.managed().filter((row) => row.status === 'draft').length,
  );

  readonly tiles = computed<DashTile[]>(() => {
    const rows: DashTile[] = [
      {
        id: 'create',
        label: 'Create competition',
        hint: 'Start a league, cup or points board',
        icon: 'add-circle-outline',
        link: '/tabs/competitions/new',
        accent: true,
      },
      {
        id: 'leagues',
        label: 'My leagues',
        hint: this.managedCount()
          ? `${this.managedCount()} you manage`
          : 'Leagues you run or join',
        icon: 'trophy-outline',
        link: '/tabs/competitions',
      },
      {
        id: 'commercial',
        label: 'Costs and earnings',
        hint: 'Sponsorships, plans and payouts',
        icon: 'cash-outline',
        link: '/tabs/commercial',
      },
    ];
    if (this.releases.isOpen('partnerships')) {
      rows.push({
        id: 'partnerships',
        label: 'Partnerships',
        hint: 'Corporate and government slots',
        icon: 'briefcase-outline',
        link: '/tabs/partnerships',
      });
    }
    if (this.releases.isOpen('scouting')) {
      rows.push({
        id: 'scouting',
        label: 'Scouting',
        hint: 'Sports, visibility and reports',
        icon: 'ribbon-outline',
        link: '/tabs/scouting/profile',
      });
    }
    if (this.releases.platformAdmin()) {
      rows.push({
        id: 'platform',
        label: 'Platform releases',
        hint: 'What the public can see',
        icon: 'rocket-outline',
        link: '/tabs/platform',
      });
    }
    return rows;
  });

  readonly form = this.fb.nonNullable.group({
    display_name: ['', [Validators.required, Validators.maxLength(120)]],
    bio: [''],
    avatar_url: [''],
    given_name: [''],
    family_name: [''],
    date_of_birth: [''],
    id_number: ['', [Validators.required, Validators.maxLength(40)]],
    phone: [''],
    city: [''],
    country: [''],
  });

  ngOnInit(): void {
    const user = this.auth.user();
    if (user) this.form.patchValue(this.profileValue(user));

    this.auth.loadProfile().subscribe({
      next: (fresh) => this.form.patchValue(this.profileValue(fresh), { emitEvent: false }),
      error: () => undefined,
    });
    this.loadManaged();
  }

  ionViewDidEnter(): void {
    this.talent()?.refresh();
    this.loadManaged();
  }

  loadManaged(): void {
    this.leaguesLoading.set(true);
    this.leaguesError.set(null);
    this.api
      .listCompetitions({ mine: true, page_size: 50 })
      .pipe(catchError((err: unknown) => {
        this.leaguesError.set(extractErrorMessage(err, 'Could not load your leagues.'));
        return of({ count: 0, next: null, previous: null, results: [] as Competition[] });
      }))
      .subscribe({
        next: (page) => {
          this.mine.set(page.results);
          this.leaguesLoading.set(false);
        },
      });
  }

  scrollToAccount(): void {
    document.getElementById('account-details')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  save(): void {
    if (this.form.invalid || this.saving()) return;

    this.saving.set(true);
    this.error.set(null);

    const raw = this.form.getRawValue();
    this.auth.updateProfile({ ...raw, date_of_birth: raw.date_of_birth || null }).subscribe({
      next: async () => {
        this.saving.set(false);
        this.form.markAsPristine();
        this.talent()?.refresh();
        await this.toast('Profile saved.', 'success');
      },
      error: (err: unknown) => {
        this.saving.set(false);
        this.error.set(extractErrorMessage(err, 'Could not save your profile.'));
      },
    });
  }

  async togglePush(enabled: boolean): Promise<void> {
    const message = enabled ? await this.push.enable() : await this.push.disable();
    if (message) {
      await this.toast(message, enabled ? 'success' : 'medium');
    }
  }

  pushDescription(): string {
    if (!this.push.supported()) {
      return 'Not available in this browser.';
    }
    return this.push.enabled()
      ? 'You will hear about goals, results, and mentions.'
      : 'Turn on to get match alerts.';
  }

  async confirmLogout(): Promise<void> {
    const alert = await this.alerts.create({
      header: 'Sign out?',
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        {
          text: 'Sign out',
          role: 'destructive',
          handler: () => {
            this.realtime.disconnect();
            this.auth.logout();
          },
        },
      ],
    });
    await alert.present();
  }

  roleLabel(league: Competition): string {
    return league.my_role === 'owner' ? 'Owner' : 'Admin';
  }

  statusLabel(league: Competition): string {
    switch (league.status) {
      case 'active':
        return 'In play';
      case 'draft':
        return 'Draft';
      case 'completed':
        return 'Finished';
      case 'archived':
        return 'Archived';
      default:
        return league.status;
    }
  }

  legalName(user: { given_name?: string; family_name?: string }): string {
    return [user.given_name, user.family_name].filter(Boolean).join(' ');
  }

  initials(name: string): string {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((word) => word.charAt(0).toUpperCase())
      .join('');
  }

  memberSince(date: string): string {
    return new Date(date).toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
  }

  private profileValue(user: {
    display_name: string;
    bio: string;
    avatar_url: string;
    given_name?: string;
    family_name?: string;
    date_of_birth?: string | null;
    id_number?: string;
    phone?: string;
    city?: string;
    country?: string;
  }) {
    return {
      display_name: user.display_name,
      bio: user.bio ?? '',
      avatar_url: user.avatar_url ?? '',
      given_name: user.given_name ?? '',
      family_name: user.family_name ?? '',
      date_of_birth: user.date_of_birth ?? '',
      id_number: user.id_number ?? '',
      phone: user.phone ?? '',
      city: user.city ?? '',
      country: user.country ?? '',
    };
  }

  private async toast(message: string, color: string): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2400 });
    await toast.present();
  }
}
