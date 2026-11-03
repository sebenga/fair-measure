import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import {
  AlertController,
  IonBackButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonLabel,
  IonSearchbar,
  IonSegment,
  IonSegmentButton,
  IonSpinner,
  IonTitle,
  IonToggle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';
import { Subject, debounceTime } from 'rxjs';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';

import { extractErrorMessage } from '../../core/error-message';
import {
  PlatformCompetition,
  ReleaseFeature,
  ReleaseSport,
  ReleasesService,
} from '../../core/releases.service';
import { PageHeroComponent } from '../../shared/page-hero.component';

type Section = 'sports' | 'features' | 'competitions';
type SportFilter = 'all' | 'live' | 'hidden';

interface SportGroup {
  label: string;
  sports: ReleaseSport[];
  live: number;
}

const TYPES_LABEL = 'Competition types';

type ToggleChange = CustomEvent<{ checked: boolean }> & { target: HTMLIonToggleElement };

@Component({
  selector: 'fm-platform-admin',
  standalone: true,
  imports: [
    IonHeader,
    IonToolbar,
    IonTitle,
    IonButtons,
    IonBackButton,
    IonContent,
    IonSegment,
    IonSegmentButton,
    IonLabel,
    IonSearchbar,
    IonToggle,
    IonIcon,
    IonSpinner,
    PageHeroComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './platform-admin.page.scss',
  template: `
    <ion-header translucent="true">
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button defaultHref="/tabs/profile" /></ion-buttons>
        <ion-title>Platform releases</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content fullscreen="true">
      <fm-page-hero
        eyebrow="Platform admin"
        title="Release Fair Measure one step at a time"
        subtitle="Open sports, features and competitions to the public when they are ready. Hidden items are hidden for every account, yours included, so you see what the public sees."
        image="assets/landing/hero.jpg"
      >
        <span class="hero-chip"><ion-icon name="trophy-outline" aria-hidden="true" /> {{ liveSports() }} of {{ sportsOnly().length }} sports live</span>
        <span class="hero-chip"><ion-icon name="layers-outline" aria-hidden="true" /> {{ liveFeatures() }} of {{ features().length }} features live</span>
      </fm-page-hero>

      <ion-segment [value]="section()" (ionChange)="section.set($any($event.detail.value))">
        <ion-segment-button value="sports"><ion-label>Sports</ion-label></ion-segment-button>
        <ion-segment-button value="features"><ion-label>Features</ion-label></ion-segment-button>
        <ion-segment-button value="competitions"><ion-label>Competitions</ion-label></ion-segment-button>
      </ion-segment>

      @if (loading()) {
        <div class="center"><ion-spinner /></div>
      } @else {
        @switch (section()) {
          @case ('sports') {
            <p class="hint">
              A hidden sport disappears from the create page and the sport pickers, and its public competitions leave
              Discover, search and the landing page. Members of those competitions keep their access.
            </p>
            <ion-searchbar
              placeholder="Search sports"
              [value]="sportQuery()"
              (ionInput)="sportQuery.set($any($event.detail.value) ?? '')"
            />
            <div class="filters" role="group" aria-label="Show">
              @for (option of sportFilters; track option.value) {
                <button
                  type="button"
                  class="filter"
                  [class.on]="sportFilter() === option.value"
                  (click)="sportFilter.set(option.value)"
                >
                  {{ option.label }}
                </button>
              }
            </div>

            @for (group of sportGroups(); track group.label) {
              <section class="group fm-card">
                <header>
                  <div>
                    <h3>{{ group.label }}</h3>
                    <small>{{ group.live }} of {{ group.sports.length }} live</small>
                  </div>
                  <div class="bulk">
                    <button type="button" class="pill" [disabled]="busy()" (click)="setGroup(group, true)">
                      Release all
                    </button>
                    <button type="button" class="pill ghost" [disabled]="busy()" (click)="setGroup(group, false)">
                      Hide all
                    </button>
                  </div>
                </header>
                @for (sport of group.sports; track sport.key) {
                  <div class="row" [class.off]="!sport.live">
                    <span class="icon"><ion-icon [name]="sport.icon || 'trophy-outline'" aria-hidden="true" /></span>
                    <span class="grow">
                      <strong>{{ sport.label }}</strong>
                      <small>
                        {{ sport.live ? 'Live' : 'Hidden' }}{{ sport.family_label ? ' · ' + sport.family_label : '' }}
                        @if (sport.competitions) {
                          · {{ sport.competitions }} {{ sport.competitions === 1 ? 'competition' : 'competitions' }}
                        }
                      </small>
                    </span>
                    <ion-toggle
                      [checked]="sport.live"
                      [disabled]="busy()"
                      [attr.aria-label]="(sport.live ? 'Hide ' : 'Release ') + sport.label"
                      (ionChange)="setSport(sport, $event)"
                    />
                  </div>
                }
              </section>
            } @empty {
              <p class="hint">No sport matches.</p>
            }
          }

          @case ('features') {
            <p class="hint">A hidden feature leaves the navigation for every account, and its pages and API answer “not open yet”.</p>
            @for (feature of features(); track feature.key) {
              <section class="feature fm-card" [class.off]="!feature.live">
                <span class="icon"><ion-icon [name]="featureIcon(feature.key)" aria-hidden="true" /></span>
                <span class="grow">
                  <strong>{{ feature.label }}</strong>
                  <small>{{ feature.description }}</small>
                  <span class="state" [class.live]="feature.live">{{ feature.live ? 'Live' : 'Hidden' }}</span>
                </span>
                <ion-toggle
                  [checked]="feature.live"
                  [disabled]="busy()"
                  [attr.aria-label]="(feature.live ? 'Hide ' : 'Release ') + feature.label"
                  (ionChange)="setFeature(feature, $event)"
                />
              </section>
            }
          }

          @case ('competitions') {
            <p class="hint">
              Hide one competition from the public without touching its sport. Its members, officials and admins still
              see it as before.
            </p>
            <ion-searchbar
              placeholder="Search by name, sport or owner"
              [value]="competitionQuery()"
              (ionInput)="searchCompetitions($any($event.detail.value) ?? '')"
            />
            <div class="filters" role="group" aria-label="Show">
              <button type="button" class="filter" [class.on]="!hiddenOnly()" (click)="showHiddenOnly(false)">All</button>
              <button type="button" class="filter" [class.on]="hiddenOnly()" (click)="showHiddenOnly(true)">
                Hidden by you
              </button>
            </div>
            @if (competitionsLoading()) {
              <div class="center"><ion-spinner /></div>
            } @else {
              <p class="count">
                {{ competitionCount() }} {{ competitionCount() === 1 ? 'competition' : 'competitions' }}
                @if (competitionCount() > competitions().length) {
                  · showing the newest {{ competitions().length }}
                }
              </p>
              <section class="group fm-card">
                @for (competition of competitions(); track competition.id) {
                  <div class="row" [class.off]="competition.platform_hidden">
                    <span class="grow">
                      <strong>{{ competition.name }}</strong>
                      <small>
                        {{ competition.preset_label || competition.sport || 'No sport' }} · {{ competition.owner }} ·
                        {{ competition.participants }} {{ competition.participants === 1 ? 'entrant' : 'entrants' }}
                      </small>
                      <span class="tags">
                        <span class="tag status">{{ competition.status }}</span>
                        @if (competition.is_private) {
                          <span class="tag">Private</span>
                        }
                        @if (!competition.sport_live) {
                          <span class="tag warn">Sport hidden</span>
                        }
                        @if (competition.platform_hidden) {
                          <span class="tag warn">Hidden by you</span>
                        }
                      </span>
                    </span>
                    <ion-toggle
                      [checked]="!competition.platform_hidden"
                      [disabled]="busy()"
                      [attr.aria-label]="(competition.platform_hidden ? 'Show ' : 'Hide ') + competition.name"
                      (ionChange)="setCompetition(competition, $event)"
                    />
                  </div>
                } @empty {
                  <p class="hint">No competition matches.</p>
                }
              </section>
            }
          }
        }
      }
    </ion-content>
  `,
})
export class PlatformAdminPage implements OnInit {
  private readonly releases = inject(ReleasesService);
  private readonly toasts = inject(ToastController);
  private readonly alerts = inject(AlertController);

  readonly sportFilters: Array<{ value: SportFilter; label: string }> = [
    { value: 'all', label: 'All' },
    { value: 'live', label: 'Live' },
    { value: 'hidden', label: 'Hidden' },
  ];

  readonly section = signal<Section>('sports');
  readonly loading = signal(true);
  readonly busy = signal(false);

  readonly sports = signal<ReleaseSport[]>([]);
  readonly features = signal<ReleaseFeature[]>([]);
  readonly sportQuery = signal('');
  readonly sportFilter = signal<SportFilter>('all');

  readonly competitions = signal<PlatformCompetition[]>([]);
  readonly competitionCount = signal(0);
  readonly competitionQuery = signal('');
  readonly hiddenOnly = signal(false);
  readonly competitionsLoading = signal(false);
  private readonly competitionSearch = new Subject<void>();

  readonly sportsOnly = computed(() => this.sports().filter((sport) => sport.kind === 'sport'));
  readonly liveSports = computed(() => this.sportsOnly().filter((sport) => sport.live).length);
  readonly liveFeatures = computed(() => this.features().filter((feature) => feature.live).length);

  readonly sportGroups = computed<SportGroup[]>(() => {
    const query = this.sportQuery().trim().toLowerCase();
    const filter = this.sportFilter();
    const groups = new Map<string, ReleaseSport[]>();
    for (const sport of this.sports()) {
      if (filter === 'live' && !sport.live) continue;
      if (filter === 'hidden' && sport.live) continue;
      const label = sport.kind === 'sport' ? sport.group_label || 'Other sports' : TYPES_LABEL;
      if (
        query &&
        !`${sport.label} ${sport.family_label} ${label} ${sport.key}`.toLowerCase().includes(query)
      ) {
        continue;
      }
      const rows = groups.get(label) ?? [];
      rows.push(sport);
      groups.set(label, rows);
    }
    const ordered = [...groups.entries()].sort(([a], [b]) =>
      a === TYPES_LABEL ? -1 : b === TYPES_LABEL ? 1 : 0,
    );
    return ordered.map(([label, sports]) => ({
      label,
      sports,
      live: sports.filter((sport) => sport.live).length,
    }));
  });

  constructor() {
    this.competitionSearch
      .pipe(debounceTime(300), takeUntilDestroyed())
      .subscribe(() => this.loadCompetitions());
  }

  ngOnInit(): void {
    this.releases.catalogue().subscribe({
      next: (catalogue) => {
        this.sports.set(catalogue.sports);
        this.features.set(catalogue.features);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        void this.toast(extractErrorMessage(err));
      },
    });
    this.loadCompetitions();
  }

  featureIcon(key: string): string {
    const icons: Record<string, string> = {
      games: 'trophy-outline',
      scouting: 'ribbon-outline',
      fantasy: 'star-outline',
      discover: 'search-outline',
      partnerships: 'briefcase-outline',
      horses: 'paw-outline',
    };
    return icons[key] ?? 'layers-outline';
  }

  setSport(sport: ReleaseSport, event: ToggleChange): void {
    const live = event.detail.checked;
    if (sport.live === live) return;
    this.save('sport', [sport.key], live, `${sport.label} is ${live ? 'live' : 'hidden'}.`, event.target);
  }

  setFeature(feature: ReleaseFeature, event: ToggleChange): void {
    const live = event.detail.checked;
    if (feature.live === live) return;
    this.save('feature', [feature.key], live, `${feature.label} is ${live ? 'live' : 'hidden'}.`, event.target);
  }

  async setGroup(group: SportGroup, live: boolean): Promise<void> {
    const keys = group.sports.filter((sport) => sport.live !== live).map((sport) => sport.key);
    if (!keys.length) return;
    const alert = await this.alerts.create({
      header: live ? `Release ${keys.length} sports?` : `Hide ${keys.length} sports?`,
      message: live
        ? `Everyone can start ${group.label.toLowerCase()} competitions straight away.`
        : `New ${group.label.toLowerCase()} competitions stop, and their public competitions leave public lists.`,
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        {
          text: live ? 'Release' : 'Hide',
          role: live ? 'confirm' : 'destructive',
          handler: () => this.save('sport', keys, live, `${keys.length} sports ${live ? 'released' : 'hidden'}.`),
        },
      ],
    });
    await alert.present();
  }

  searchCompetitions(value: string): void {
    this.competitionQuery.set(value);
    this.competitionSearch.next();
  }

  showHiddenOnly(value: boolean): void {
    this.hiddenOnly.set(value);
    this.loadCompetitions();
  }

  setCompetition(competition: PlatformCompetition, event: ToggleChange): void {
    const hidden = !event.detail.checked;
    if (competition.platform_hidden === hidden) return;
    this.busy.set(true);
    this.releases.setCompetitionHidden(competition.id, hidden).subscribe({
      next: (row) => {
        this.competitions.update((rows) => rows.map((item) => (item.id === row.id ? row : item)));
        this.busy.set(false);
        void this.toast(`${row.name} is ${hidden ? 'hidden from the public' : 'public again'}.`);
      },
      error: (err: unknown) => {
        this.busy.set(false);
        event.target.checked = !hidden;
        void this.toast(extractErrorMessage(err));
      },
    });
  }

  private loadCompetitions(): void {
    this.competitionsLoading.set(true);
    this.releases.competitions(this.competitionQuery().trim(), this.hiddenOnly()).subscribe({
      next: (page) => {
        this.competitions.set(page.results);
        this.competitionCount.set(page.count);
        this.competitionsLoading.set(false);
      },
      error: (err: unknown) => {
        this.competitionsLoading.set(false);
        void this.toast(extractErrorMessage(err));
      },
    });
  }

  private save(
    kind: 'sport' | 'feature',
    keys: string[],
    live: boolean,
    message: string,
    toggle?: HTMLIonToggleElement,
  ): void {
    this.busy.set(true);
    this.releases.setLive(kind, keys, live).subscribe({
      next: (catalogue) => {
        this.sports.set(catalogue.sports);
        this.features.set(catalogue.features);
        this.busy.set(false);
        void this.toast(message);
        if (kind === 'sport') this.loadCompetitions();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        if (toggle) toggle.checked = !live;
        void this.toast(extractErrorMessage(err));
      },
    });
  }

  private async toast(message: string): Promise<void> {
    const toast = await this.toasts.create({ message, duration: 2200, position: 'top' });
    await toast.present();
  }
}
