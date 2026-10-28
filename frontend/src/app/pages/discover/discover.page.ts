import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { Subject, debounceTime, distinctUntilChanged, forkJoin, of, switchMap } from 'rxjs';
import { catchError } from 'rxjs/operators';
import {
  IonButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonSearchbar,
  IonSpinner,
  IonTitle,
  IonToolbar,
} from '@ionic/angular/standalone';

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';
import {
  FALLBACK_CAMPAIGN,
  FALLBACK_CORPORATE,
  FALLBACK_GOVERNMENT,
  FALLBACK_LOGOS,
} from '../../core/marketing-fallbacks';
import type { Competition, MarketingPlacement, Post } from '../../core/models';
import {
  CompetitionCardComponent,
  type CompetitionCardPromo,
} from '../../shared/competition-card.component';
import { InboxTrayComponent } from '../../shared/inbox-tray.component';
import { PostCardComponent } from '../../shared/post-card.component';
import { PostComposerComponent } from '../../shared/post-composer.component';
import { PromoSlotComponent } from '../../shared/promo-slot.component';

type FeedItem =
  | { kind: 'competition'; id: string; competition: Competition }
  | { kind: 'post'; id: string; post: Post }
  | { kind: 'promo'; id: string; placement: MarketingPlacement };

const EMPTY_PAGE = { count: 0, next: null, previous: null, results: [] };

@Component({
  selector: 'fm-discover',
  standalone: true,
  imports: [
    IonHeader,
    IonToolbar,
    IonTitle,
    IonButtons,
    IonContent,
    IonSearchbar,
    IonSpinner,
    IonIcon,
    IonButton,
    CompetitionCardComponent,
    InboxTrayComponent,
    PostCardComponent,
    PostComposerComponent,
    PromoSlotComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './discover.page.scss',
  template: `
    <ion-header translucent="true">
      <ion-toolbar>
        <ion-title>Discover</ion-title>
        <ion-buttons slot="end">
          <fm-inbox-tray />
        </ion-buttons>
      </ion-toolbar>
      <ion-toolbar>
        <ion-searchbar
          placeholder="Search public competitions"
          [debounce]="0"
          (ionInput)="onQuery($any($event).detail.value ?? '')"
        />
      </ion-toolbar>
    </ion-header>

    <ion-content fullscreen="true">
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (error()) {
        <div class="fm-empty">
          <ion-icon name="alert-circle-outline" aria-hidden="true" />
          <h3>Search unavailable</h3>
          <p>{{ error() }}</p>
          <ion-button fill="clear" (click)="load()">Try again</ion-button>
        </div>
      } @else {
        <div class="discover-shell">
          <aside class="sponsored-rail left" aria-label="Corporate marketing">
            <p class="rail-kicker">Commercial</p>
            <h3 class="rail-title">Corporate</h3>
            @for (ad of corporate(); track ad.id) {
              <fm-promo-slot
                kind="corporate"
                eyebrow="Corporate"
                [title]="ad.name"
                [body]="ad.tagline || ad.body"
                [action]="ad.cta_label || 'Talk to partnerships'"
                [logo]="ad.logo_url"
                icon="briefcase-outline"
                (open)="openPlacement(ad)"
              />
            }
            @if (logos().length) {
              <div class="logo-card">
                <p>Partners on this page</p>
                <div class="logo-row">
                  @for (logo of logos(); track logo.id) {
                    <button type="button" (click)="openPlacement(logo)">
                      @if (logo.logo_url) {
                        <img [src]="logo.logo_url" [alt]="logo.name" />
                      } @else {
                        <span>{{ logo.name }}</span>
                      }
                    </button>
                  }
                </div>
              </div>
            }
          </aside>

          <div class="feed">
            <div class="market-strip" aria-label="Corporate, government and current competitions">
              @if (corporate()[0]; as ad) {
                <fm-promo-slot
                  kind="corporate"
                  eyebrow="Corporate"
                  [title]="ad.name"
                  [body]="ad.tagline"
                  [action]="ad.cta_label || 'Enquire'"
                  icon="briefcase-outline"
                  (open)="openPlacement(ad)"
                />
              }
              @if (government()[0]; as ad) {
                <fm-promo-slot
                  kind="government"
                  eyebrow="Government"
                  [title]="ad.name"
                  [body]="ad.tagline"
                  [action]="ad.cta_label || 'Enquire'"
                  icon="business-outline"
                  (open)="openPlacement(ad)"
                />
              }
              @if (currentCompetitions()[0]; as league) {
                <fm-promo-slot
                  kind="competition"
                  eyebrow="Current competition"
                  [title]="league.name"
                  [body]="(league.sport || 'League') + ' · on the public landing page'"
                  action="Open"
                  [logo]="league.logo_url"
                  icon="trophy-outline"
                  (open)="open(league)"
                />
              }
            </div>

            <fm-promo-slot
              kind="banner"
              eyebrow="Campaign"
              [title]="campaign().name"
              [body]="campaign().tagline || campaign().body"
              [action]="campaign().cta_label || 'Create a public league'"
              icon="megaphone-outline"
              (open)="openPlacement(campaign())"
            />

            @if (composerLeague(); as league) {
              <div class="composer-wrap">
                @if (mine().length > 1) {
                  <label>
                    Posting to
                    <select
                      [value]="league.id"
                      (change)="composerLeagueId.set($any($event.target).value)"
                    >
                      @for (row of mine(); track row.id) {
                        <option [value]="row.id">{{ row.name }}</option>
                      }
                    </select>
                  </label>
                }
                <fm-post-composer
                  [competitionId]="league.id"
                  placeholder="Post as yourself — an update, a photo or a clip for this league"
                  (posted)="prependPost($event)"
                />
              </div>
            }

            @if (currentCompetitions().length) {
              <section class="rail">
                <div class="section-head">
                  <p>Marketing</p>
                  <h3>Current competitions</h3>
                </div>
                <div class="scroller">
                  @for (league of currentCompetitions(); track league.id) {
                    <button type="button" class="chip" data-kind="competition" (click)="open(league)">
                      <span>On landing page</span>
                      <strong>{{ league.name }}</strong>
                      <small>{{ league.sport || 'League' }} · {{ league.participant_count }} sides</small>
                    </button>
                  }
                </div>
              </section>
            }

            @if (featured().length) {
              <section class="rail">
                <div class="section-head">
                  <p>Scouting</p>
                  <h3>Open to scouts</h3>
                </div>
                <div class="scroller">
                  @for (league of featured(); track league.id) {
                    <button type="button" class="chip" (click)="open(league)">
                      <span>Talent pathway</span>
                      <strong>{{ league.name }}</strong>
                      <small>{{ league.sport || 'League' }} · {{ league.participant_count }} sides</small>
                    </button>
                  }
                </div>
              </section>
            }

            @if (stream().length === 0) {
              <div class="fm-empty">
                <ion-icon name="search-outline" aria-hidden="true" />
                <h3>{{ query() ? 'Nothing matched' : 'No public competitions yet' }}</h3>
                <p>
                  @if (query()) {
                    Try a shorter search, or a sport name.
                  } @else {
                    Public competitions others create will show up here.
                  }
                </p>
              </div>
            } @else {
              @for (item of stream(); track item.kind + item.id; let index = $index) {
                @if (item.kind === 'competition') {
                  <fm-competition-card
                    [style.--i]="index"
                    [competition]="item.competition"
                    [size]="isSoccerLeague(item.competition) ? 'large' : 'default'"
                    [promo]="cardPromo(item.competition, index)"
                    (open)="open(item.competition)"
                    (promoClick)="onCardPromo(item.competition, index)"
                  />
                } @else if (item.kind === 'promo') {
                  <fm-promo-slot
                    [style.--i]="index"
                    [kind]="promoKind(item.placement)"
                    [eyebrow]="promoEyebrow(item.placement)"
                    [title]="item.placement.name"
                    [body]="item.placement.tagline || item.placement.body"
                    [action]="item.placement.cta_label || 'Learn more'"
                    [logo]="item.placement.logo_url"
                    [icon]="promoIcon(item.placement)"
                    (open)="openPlacement(item.placement)"
                  />
                } @else {
                  <fm-post-card
                    [style.--i]="index"
                    [post]="item.post"
                    [competitionId]="item.post.competition"
                    [showLeague]="true"
                    (deleted)="removePost($event)"
                  />
                }
              }
            }

            @if (suggested().length) {
              <section class="suggest">
                <div class="section-head">
                  <p>For you</p>
                  <h3>Suggested leagues</h3>
                </div>
                <p class="suggest-copy">Leagues like the ones people in your network join.</p>
                @for (league of suggested(); track league.id) {
                  <fm-promo-slot
                    kind="suggested"
                    eyebrow="Suggested"
                    [title]="league.name"
                    [body]="(league.sport || 'League') + ' · ' + league.participant_count + ' entrants'"
                    action="Open"
                    icon="people-outline"
                    (open)="open(league)"
                  />
                }
              </section>
            }
          </div>

          <aside class="sponsored-rail right" aria-label="Government and current competitions">
            <p class="rail-kicker">Public sector</p>
            <h3 class="rail-title">Government</h3>
            @for (ad of government(); track ad.id) {
              <fm-promo-slot
                kind="government"
                eyebrow="Government"
                [title]="ad.name"
                [body]="ad.tagline || ad.body"
                [action]="ad.cta_label || 'Plan a programme'"
                [logo]="ad.logo_url"
                icon="business-outline"
                (open)="openPlacement(ad)"
              />
            }

            <p class="rail-kicker later">Featured</p>
            <h3 class="rail-title">Current competitions</h3>
            @for (league of currentCompetitions().slice(0, 4); track league.id) {
              <fm-promo-slot
                kind="competition"
                eyebrow="Current competition"
                [title]="league.name"
                [body]="(league.sport || 'League') + ' · ' + league.participant_count + ' sides'"
                action="Open"
                [logo]="league.logo_url"
                icon="trophy-outline"
                (open)="open(league)"
              />
            }
            @if (!currentCompetitions().length) {
              <fm-promo-slot
                kind="competition"
                eyebrow="Current competition"
                title="Put your league here"
                body="Opt in when you create a competition so Discover and the landing page carry it."
                action="Create a public league"
                icon="megaphone-outline"
                (open)="createLeague()"
              />
            }
          </aside>
        </div>
      }
    </ion-content>
  `,
})
export class DiscoverPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly queries = new Subject<string>();

  readonly results = signal<Competition[]>([]);
  readonly posts = signal<Post[]>([]);
  readonly mine = signal<Competition[]>([]);
  readonly landing = signal<Competition[]>([]);
  readonly placements = signal<MarketingPlacement[]>([]);
  readonly composerLeagueId = signal('');
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly query = signal('');
  private readonly inbox = viewChild(InboxTrayComponent);

  readonly featured = computed(() =>
    this.results().filter((row) => row.open_to_scouts).slice(0, 8),
  );
  readonly suggested = computed(() =>
    this.results()
      .filter((row) => !row.open_to_scouts && row.status === 'active')
      .slice(0, 3),
  );
  readonly currentCompetitions = computed(() => {
    const opted = this.landing().length ? this.landing() : this.results().filter((row) => row.show_on_landing);
    return opted.slice(0, 8);
  });
  readonly campaign = computed(
    () => this.placements().find((item) => item.slot === 'banner') ?? FALLBACK_CAMPAIGN,
  );
  readonly corporate = computed(() => {
    const rows = this.placements().filter(
      (item) => item.audience === 'corporate' && item.slot === 'feature',
    );
    return rows.length ? rows : FALLBACK_CORPORATE;
  });
  readonly government = computed(() => {
    const rows = this.placements().filter(
      (item) => item.audience === 'government' && item.slot === 'feature',
    );
    return rows.length ? rows : FALLBACK_GOVERNMENT;
  });
  readonly logos = computed(() => {
    const rows = this.placements().filter((item) => item.slot === 'logo');
    return rows.length ? rows : FALLBACK_LOGOS;
  });
  readonly composerLeague = computed(
    () => this.mine().find((row) => row.id === this.composerLeagueId()) ?? this.mine()[0] ?? null,
  );
  readonly stream = computed<FeedItem[]>(() => {
    const competitions = this.results();
    const posts = this.query() ? [] : this.posts();
    const ads = this.inFeedAds();
    const items: FeedItem[] = [];
    let postIndex = 0;
    let adIndex = 0;
    let sinceAd = 0;
    for (const competition of competitions) {
      items.push({ kind: 'competition', id: competition.id, competition });
      sinceAd += 1;
      if (sinceAd >= 2 && ads[adIndex]) {
        items.push(ads[adIndex]);
        adIndex += 1;
        sinceAd = 0;
      }
      const post = posts[postIndex];
      if (post) {
        items.push({ kind: 'post', id: post.id, post });
        postIndex += 1;
      }
    }
    while (postIndex < posts.length) {
      const post = posts[postIndex];
      items.push({ kind: 'post', id: post.id, post });
      postIndex += 1;
    }
    return items;
  });

  constructor() {
    this.queries
      .pipe(
        debounceTime(280),
        distinctUntilChanged(),
        switchMap((query) => {
          this.loading.set(true);
          this.query.set(query);
          return this.api.listCompetitions({ search: query, page_size: 30 });
        }),
        takeUntilDestroyed(),
      )
      .subscribe({
        next: (page) => {
          this.results.set(page.results);
          this.loading.set(false);
        },
        error: (err: unknown) => {
          this.error.set(extractErrorMessage(err));
          this.loading.set(false);
        },
      });
  }

  ngOnInit(): void {
    this.load();
  }

  ionViewWillEnter(): void {
    this.load(this.results().length === 0);
    this.inbox()?.refresh();
  }

  load(showSpinner = true): void {
    if (showSpinner) this.loading.set(true);
    this.error.set(null);

    forkJoin({
      competitions: this.api.listCompetitions({ search: this.query(), page_size: 30 }),
      posts: this.api.listDiscoverPosts({ page_size: 20 }).pipe(
        catchError(() => of({ next: null, previous: null, results: [] as Post[] })),
      ),
      mine: this.api.listCompetitions({ mine: true, page_size: 20 }).pipe(
        catchError(() => of({ ...EMPTY_PAGE, results: [] as Competition[] })),
      ),
      placements: this.api.listPlacements().pipe(catchError(() => of([] as MarketingPlacement[]))),
      landing: this.api.listCompetitions({ show_on_landing: true, page_size: 8 }).pipe(
        catchError(() => of({ ...EMPTY_PAGE, results: [] as Competition[] })),
      ),
    }).subscribe({
      next: ({ competitions, posts, mine, placements, landing }) => {
        this.results.set(competitions.results);
        this.posts.set(posts.results);
        this.mine.set(mine.results);
        this.placements.set(placements);
        this.landing.set(landing.results);
        if (!this.composerLeagueId() && mine.results[0]) {
          this.composerLeagueId.set(mine.results[0].id);
        }
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err));
        this.loading.set(false);
      },
    });
  }

  prependPost(post: Post): void {
    this.posts.update((current) => [post, ...current.filter((row) => row.id !== post.id)]);
  }

  removePost(postId: string): void {
    this.posts.update((current) => current.filter((row) => row.id !== postId));
  }

  onQuery(value: string): void {
    this.queries.next(value.trim());
  }

  isSoccerLeague(competition: Competition): boolean {
    const sport = (competition.sport || '').toLowerCase();
    const name = (competition.name || '').toLowerCase();
    return /soccer|football|premier/.test(`${sport} ${name}`);
  }

  cardPromo(competition: Competition, index: number): CompetitionCardPromo | null {
    if (competition.show_on_landing) {
      return {
        kind: 'featured',
        eyebrow: 'Current competition',
        title: 'Featured on the public landing page',
      };
    }
    const corporate = this.corporate();
    const government = this.government();
    if (index % 3 === 0 && corporate.length) {
      const ad = corporate[Math.floor(index / 3) % corporate.length];
      return { kind: 'corporate', eyebrow: 'Corporate', title: ad.name };
    }
    if (index % 3 === 1 && government.length) {
      const ad = government[Math.floor(index / 3) % government.length];
      return { kind: 'government', eyebrow: 'Government', title: ad.name };
    }
    const featured = this.currentCompetitions()[0];
    if (featured) {
      return {
        kind: 'competition',
        eyebrow: 'Current competition',
        title: featured.name,
      };
    }
    return null;
  }

  onCardPromo(competition: Competition, index: number): void {
    const promo = this.cardPromo(competition, index);
    if (!promo) return;
    if (promo.kind === 'featured' || promo.kind === 'competition') {
      const featured = this.currentCompetitions().find((row) => row.name === promo.title);
      this.open(featured ?? competition);
      return;
    }
    const pool = promo.kind === 'government' ? this.government() : this.corporate();
    const match = pool.find((row) => row.name === promo.title) ?? pool[0];
    if (match) this.openPlacement(match);
  }

  promoKind(placement: MarketingPlacement): 'banner' | 'corporate' | 'government' | 'sponsored' {
    if (placement.audience === 'corporate') return 'corporate';
    if (placement.audience === 'government') return 'government';
    if (placement.slot === 'banner') return 'banner';
    return 'sponsored';
  }

  promoEyebrow(placement: MarketingPlacement): string {
    if (placement.audience === 'corporate') return 'Corporate';
    if (placement.audience === 'government') return 'Government';
    return placement.slot === 'banner' ? 'Campaign' : 'Sponsored';
  }

  promoIcon(placement: MarketingPlacement): string {
    if (placement.audience === 'corporate') return 'briefcase-outline';
    if (placement.audience === 'government') return 'business-outline';
    return 'megaphone-outline';
  }

  open(competition: Competition): void {
    void this.router.navigate(['/tabs/competitions', competition.id]);
  }

  createLeague(): void {
    void this.router.navigate(['/tabs/competitions/new']);
  }

  openPlacement(placement: MarketingPlacement): void {
    if (placement.id === 'grow' && !placement.cta_url) {
      this.createLeague();
      return;
    }
    if (placement.cta_url) {
      window.open(placement.cta_url, '_blank', 'noopener');
      return;
    }
    const audience = placement.audience === 'government' ? 'government' : 'corporate';
    void this.router.navigate(['/tabs/partnerships'], {
      queryParams: { audience, placement: placement.id },
    });
  }

  private inFeedAds(): FeedItem[] {
    const ads: MarketingPlacement[] = [];
    const corporate = this.corporate()[0];
    const government = this.government()[0];
    if (corporate) ads.push(corporate);
    if (government) ads.push(government);
    const extra = [...this.corporate().slice(1), ...this.government().slice(1)];
    ads.push(...extra);
    return ads.map((placement) => ({
      kind: 'promo' as const,
      id: `promo-${placement.id}`,
      placement,
    }));
  }
}
