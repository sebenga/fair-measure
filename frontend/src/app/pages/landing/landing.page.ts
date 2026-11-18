import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { IonContent, IonSpinner, ToastController } from '@ionic/angular/standalone';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { extractErrorMessage } from '../../core/error-message';
import {
  FALLBACK_CORPORATE,
  FALLBACK_GOVERNMENT,
  FALLBACK_LOGOS,
  showcaseSlides,
} from '../../core/marketing-fallbacks';
import type { Competition, MarketingPlacement, Post, StandingRow } from '../../core/models';
import {
  CORPORATE_STORIES,
  GOVERNMENT_STORIES,
  HeroMediaComponent,
  LandingMomentsComponent,
  StoryTilesComponent,
} from './landing-media.component';
import { LandingEnquiryComponent } from './landing-enquiry.component';
import { LegalFooterComponent } from '../../shared/legal-footer.component';
import { SponsorShowcaseComponent } from './sponsor-showcase.component';
import {
  CompetitionStripComponent,
  type StripDemo,
} from '../../shared/competition-strip.component';

const STRIPES = ['#0f766e', '#ea580c', '#2563eb', '#7c3aed', '#0891b2'];

@Component({
  selector: 'fm-landing',
  standalone: true,
  imports: [
    CompetitionStripComponent,
    DatePipe,
    IonContent,
    IonSpinner,
    HeroMediaComponent,
    LandingMomentsComponent,
    StoryTilesComponent,
    SponsorShowcaseComponent,
    LandingEnquiryComponent,
    LegalFooterComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'ion-page' },
  styleUrl: './landing.page.scss',
  template: `
    <ion-content [fullscreen]="true">
      <div class="landing">
        <header class="nav">
          <button type="button" class="brand" (click)="scrollTo('top')">
            <span class="logo" aria-hidden="true"><span></span></span>
            Fair Measure
          </button>
          <nav>
            <button type="button" (click)="scrollTo('try')">Try demos</button>
            <button type="button" (click)="scrollTo('public')">Competitions</button>
            <button type="button" (click)="scrollTo('corporate')">Corporate</button>
            <button type="button" (click)="scrollTo('government')">Government</button>
            <button type="button" (click)="scrollTo('happening')">Discover</button>
          </nav>
          <div class="auth">
            @if (auth.isAuthenticated()) {
              <button type="button" class="primary" (click)="go('/tabs/competitions')">My leagues</button>
            } @else {
              <button type="button" class="ghost" (click)="go('/login')">Sign in</button>
              <button type="button" class="primary" (click)="go('/register')">Get started</button>
            }
          </div>
        </header>

        <fm-competition-strip
          class="top-competitions"
          title="Competitions on Fair Measure"
          [competitions]="competitions()"
          [demos]="stripDemos()"
          (open)="openCompetition($event.id)"
          (tryDemo)="startDemo($event)"
        />

        <section class="hero" id="top">
          <fm-hero-media />
          <div class="hero-copy">
            <h1>Build any competition you can describe — then run it.</h1>
            <p>
              Custom scoring, live results, league tables and a feed to share every moment.
              Browse public competitions below — no account needed to look around.
            </p>
            <div class="hero-actions">
              <button type="button" class="primary" (click)="startCompetition()">
                Create a competition
              </button>
              <button type="button" class="ghost" (click)="scrollTo('public')">
                Browse examples
              </button>
            </div>
          </div>
          @if (liveCount() > 0) {
            <p class="live-pill">
              <span></span>
              {{ liveCount() }} competition{{ liveCount() === 1 ? '' : 's' }} live right now
            </p>
          }
        </section>

        <fm-landing-moments />

        <section class="try-demos" id="try">
          <div class="section-head">
            <div>
              <p class="eyebrow">Try before you build</p>
              <h2>One-hour demos</h2>
            </div>
          </div>
          <p class="lede try-lede">
            Jump straight into a filled competition — soccer, a custom VS league, or an individual
            points board where you score everyone together. Each demo deletes itself after an hour.
          </p>
          <div class="demo-grid">
            <article class="demo-card soccer">
              <p class="demo-kind">Soccer</p>
              <h3>Football league demo</h3>
              <p>
                16 teams, a season in play, a cup, team sheets and ratings — the full soccer look
                and feel.
              </p>
              <button
                type="button"
                class="primary"
                [disabled]="demoBusy() !== null"
                (click)="startDemo('soccer')"
              >
                @if (demoBusy() === 'soccer') {
                  <ion-spinner name="crescent" />
                  Building…
                } @else {
                  Try soccer for 1 hour
                }
              </button>
            </article>
            <article class="demo-card custom">
              <p class="demo-kind">Custom VS</p>
              <h3>Your-rules VS demo</h3>
              <p>
                A head-to-head league with scoring you would define yourself — same boards, sheets
                and live match centre.
              </p>
              <button
                type="button"
                class="primary"
                [disabled]="demoBusy() !== null"
                (click)="startDemo('custom')"
              >
                @if (demoBusy() === 'custom') {
                  <ion-spinner name="crescent" />
                  Building…
                } @else {
                  Try custom VS for 1 hour
                }
              </button>
            </article>
            <article class="demo-card points">
              <p class="demo-kind">Custom points</p>
              <h3>Individual points demo</h3>
              <p>
                People on a points board with sample KPIs — score everyone on one criterion in the
                same round.
              </p>
              <button
                type="button"
                class="primary"
                [disabled]="demoBusy() !== null"
                (click)="startDemo('custom_points')"
              >
                @if (demoBusy() === 'custom_points') {
                  <ion-spinner name="crescent" />
                  Building…
                } @else {
                  Try points board for 1 hour
                }
              </button>
            </article>
          </div>
          <p class="hint try-hint">No account needed — each demo lasts one hour, then deletes itself.</p>
        </section>

        <section class="public" id="public">
          <div class="section-head">
            <h2>Public competitions</h2>
            <button type="button" class="text" (click)="go('/tabs/competitions')">View all →</button>
          </div>

          @if (loading()) {
            <div class="centered"><ion-spinner name="crescent" /></div>
          } @else {
            <div class="board">
              <div class="cards">
                <article class="comp demo-comp soccer">
                  <div class="stripe" [style.background]="stripe(0)"></div>
                  <p class="meta">Soccer · one-hour demo</p>
                  <h3>Football league demo</h3>
                  <p class="meta">
                    16 teams, a live match, cup, sheets and ratings. Deletes after an hour.
                  </p>
                  <div class="card-foot">
                    <span>Try the look and feel</span>
                    <button
                      type="button"
                      class="text"
                      [disabled]="demoBusy() !== null"
                      (click)="startDemo('soccer')"
                    >
                      @if (demoBusy() === 'soccer') {
                        Building…
                      } @else {
                        Try soccer →
                      }
                    </button>
                  </div>
                </article>
                <article class="comp demo-comp custom">
                  <div class="stripe" [style.background]="stripe(1)"></div>
                  <p class="meta">Custom VS · one-hour demo</p>
                  <h3>Your-rules VS demo</h3>
                  <p class="meta">
                    Head-to-head league with custom scoring — same boards and match centre.
                  </p>
                  <div class="card-foot">
                    <span>Try the look and feel</span>
                    <button
                      type="button"
                      class="text"
                      [disabled]="demoBusy() !== null"
                      (click)="startDemo('custom')"
                    >
                      @if (demoBusy() === 'custom') {
                        Building…
                      } @else {
                        Try custom VS →
                      }
                    </button>
                  </div>
                </article>
                <article class="comp demo-comp points">
                  <div class="stripe" [style.background]="stripe(2)"></div>
                  <p class="meta">Custom points · one-hour demo</p>
                  <h3>Individual points demo</h3>
                  <p class="meta">
                    People on a KPI board — score everyone on one criterion together.
                  </p>
                  <div class="card-foot">
                    <span>Try the look and feel</span>
                    <button
                      type="button"
                      class="text"
                      [disabled]="demoBusy() !== null"
                      (click)="startDemo('custom_points')"
                    >
                      @if (demoBusy() === 'custom_points') {
                        Building…
                      } @else {
                        Try points board →
                      }
                    </button>
                  </div>
                </article>
                @for (competition of competitions(); track competition.id; let i = $index) {
                    <article class="comp">
                      <div class="stripe" [style.background]="stripe(i + 3)"></div>
                      <p class="meta">
                        {{ competition.sport || 'Multi-sport' }} ·
                        {{ formatLabel(competition.format) }}
                      </p>
                      <h3>{{ competition.name }}</h3>
                      <p class="meta">
                        {{ competition.participant_count }}
                        {{ competition.participant_count === 1 ? 'entrant' : 'entrants' }}
                        · {{ competition.status }}
                      </p>
                      <div class="card-foot">
                        <span>Updated {{ competition.created_at | date: 'MMM d' }}</span>
                        <button
                          type="button"
                          class="text"
                          (click)="openCompetition(competition.id)"
                        >
                          View →
                        </button>
                      </div>
                    </article>
                }
              </div>

              <aside>
                <div class="card">
                  <h3>Top of the table</h3>
                  @if (table().length === 0) {
                    <p class="hint">Tables appear here once a public league has results.</p>
                  } @else {
                    <ol>
                      @for (row of table(); track row.participant.id) {
                        <li>
                          <span>{{ row.position }}</span>
                          <strong>{{ row.participant.name }}</strong>
                          <em>{{ row.points }} pts</em>
                        </li>
                      }
                    </ol>
                  }
                </div>
                @if (auth.isAuthenticated()) {
                  <div class="card why">
                    <h3>You're signed in</h3>
                    <p>Pick up where you left off: your leagues, live games and the feed.</p>
                    <button type="button" class="primary block" (click)="go('/tabs/competitions')">
                      My leagues
                    </button>
                    <button type="button" class="ghost block" (click)="go('/tabs/discover')">
                      Discover
                    </button>
                  </div>
                } @else {
                  <div class="card why">
                    <h3>Why sign in?</h3>
                    <p>
                      Browsing is always free and open. Sign in only when you want to enter a
                      competition, run your own, or follow live results.
                    </p>
                    <button type="button" class="primary block" (click)="go('/register')">
                      Get started
                    </button>
                    <button type="button" class="ghost block" (click)="go('/login')">Sign in</button>
                  </div>
                }
              </aside>
            </div>
          }
        </section>

        @if (banners().length) {
          <section class="commercial" id="commercial">
            <fm-sponsor-showcase
              label="Commercial"
              [sponsors]="bannerSlides()"
              (open)="openPlacement($event)"
            />
          </section>
        }

        <section class="partners" id="corporate">
          <p class="eyebrow">Corporate</p>
          <h2>Workplace leagues, brand and broadcast</h2>
          <p class="lede">
            Reserved commercial space for companies: staff competitions, naming rights, kit and
            live boards. Slots are managed in admin so a campaign can go live without a release.
          </p>
          <fm-story-tiles [stories]="corporateStories" />
          <fm-sponsor-showcase
            class="offers"
            label="Corporate offers"
            [sponsors]="corporateSlides()"
            (open)="openPlacement($event)"
          />
        </section>

        <section class="partners government" id="government">
          <p class="eyebrow">Government</p>
          <h2>Schools, municipalities and public programmes</h2>
          <p class="lede">
            Public-sector competitions stay readable without an account. Departments and
            federations get a named programme on this page and a route to partner.
          </p>
          <fm-story-tiles [stories]="governmentStories" />
          <fm-sponsor-showcase
            class="offers"
            label="Government offers"
            [sponsors]="governmentSlides()"
            (open)="openPlacement($event)"
          />
        </section>

        <section class="sponsors" id="sponsors">
          <p class="eyebrow">Sponsors</p>
          <h2>Partners on the pitch, the feed, and at work</h2>
          <fm-sponsor-showcase [sponsors]="logos()" (open)="openPlacement($event)" />
          <button type="button" class="text become" (click)="scrollTo('enquire')">
            Become a sponsor or partner →
          </button>
        </section>

        <section class="happening" id="happening">
          <div>
            <p class="eyebrow">Inside the app</p>
            <h2>What’s happening right now</h2>
            <p class="lede">
              A live preview of public updates — scores, tables and the conversation — without
              creating an account.
            </p>
            <div class="phone" aria-hidden="true">
              <div class="phone-bar">Fair Measure</div>
              <article class="feed-item photo">
                <img src="assets/landing/moment-rugby.jpg" alt="" loading="lazy" width="900" height="675" />
                <strong>Full time at the club</strong>
                <small>Photo post · Club league</small>
                <p>What a finish. Rate the players before Sunday.</p>
              </article>
              @for (post of previewPosts(); track post.id) {
                <article class="feed-item">
                  <strong>{{ post.author.display_name || 'Member' }}</strong>
                  <small>{{ post.competition_name || 'Public league' }}</small>
                  <p>{{ post.body }}</p>
                </article>
              } @empty {
                <article class="feed-item">
                  <strong>Live board</strong>
                  <small>Public update</small>
                  <p>Results, ratings and tables will land here as leagues go live.</p>
                </article>
              }
            </div>
          </div>

          <div class="updates">
            <h3>Public updates</h3>
            @if (updates().length === 0) {
              <p class="hint">When a public competition posts, it shows up here.</p>
            } @else {
              <ul>
                @for (post of updates(); track post.id) {
                  <li>
                    <button type="button" (click)="openCompetition(post.competition)">
                      <strong>{{ post.competition_name || 'Competition' }}</strong>
                      <span>{{ post.body }}</span>
                      <small>{{ post.created_at | date: 'short' }}</small>
                    </button>
                  </li>
                }
              </ul>
            }
          </div>
        </section>

        <section id="enquire">
          <fm-landing-enquiry />
        </section>
        <fm-legal-footer />
      </div>
    </ion-content>
  `,
})
export class LandingPage {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly toasts = inject(ToastController);
  readonly auth = inject(AuthService);

  readonly corporateStories = CORPORATE_STORIES;
  readonly governmentStories = GOVERNMENT_STORIES;
  readonly loading = signal(true);
  readonly competitions = signal<Competition[]>([]);
  readonly table = signal<StandingRow[]>([]);
  readonly updates = signal<Post[]>([]);
  readonly previewPosts = signal<Post[]>([]);
  readonly liveCount = signal(0);
  readonly placements = signal<MarketingPlacement[]>([]);
  readonly demoBusy = signal<'soccer' | 'custom' | 'custom_points' | null>(null);
  /** Always offer the one-hour demos in the top strip, including when logged out. */
  readonly stripDemos = computed<StripDemo[]>(() => [
    {
      kind: 'soccer',
      name: 'Football league demo',
      sport: 'Soccer',
      blurb: '16 teams · live match',
    },
    {
      kind: 'custom',
      name: 'Custom VS demo',
      sport: 'Custom',
      blurb: 'Your rules · 1 hour',
    },
    {
      kind: 'custom_points',
      name: 'Individual points demo',
      sport: 'Custom',
      blurb: 'Score everyone · 1 hour',
    },
  ]);

  readonly banners = computed(() =>
    this.placements().filter((item) => item.slot === 'banner'),
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
  readonly bannerSlides = computed(() => showcaseSlides(this.banners(), 'Commercial', 'Find out more'));
  readonly corporateSlides = computed(() => showcaseSlides(this.corporate(), 'Corporate', 'Enquire'));
  readonly governmentSlides = computed(() => showcaseSlides(this.government(), 'Government', 'Enquire'));
  readonly logos = computed(() => {
    const rows = this.placements().filter((item) => item.slot === 'logo');
    return rows.length ? rows : FALLBACK_LOGOS;
  });

  constructor() {
    this.load();
    const pending = this.route.snapshot.queryParamMap.get('demo');
    if (
      (pending === 'soccer' || pending === 'custom' || pending === 'custom_points') &&
      this.auth.isAuthenticated()
    ) {
      void this.router.navigate([], {
        relativeTo: this.route,
        queryParams: { demo: null },
        queryParamsHandling: 'merge',
        replaceUrl: true,
      });
      this.startDemo(pending);
    }
  }

  stripe(index: number): string {
    return STRIPES[index % STRIPES.length];
  }

  formatLabel(format: string): string {
    return format.replaceAll('_', ' ');
  }

  go(path: string): void {
    void this.router.navigateByUrl(path, { replaceUrl: path === '/login' || path === '/register' });
  }

  startCompetition(): void {
    if (this.auth.isAuthenticated()) {
      void this.router.navigateByUrl('/tabs/competitions/new');
      return;
    }
    void this.router.navigate(['/register'], {
      queryParams: { next: '/tabs/competitions/new' },
      replaceUrl: true,
    });
  }

  startDemo(kind: 'soccer' | 'custom' | 'custom_points'): void {
    if (this.demoBusy()) return;
    this.demoBusy.set(kind);
    this.api.tryDemo(kind).subscribe({
      next: (payload) => {
        if (payload.access && payload.refresh && payload.user) {
          this.auth.acceptSession({
            access: payload.access,
            refresh: payload.refresh,
            user: payload.user,
          });
        }
        this.demoBusy.set(null);
        const path =
          kind === 'custom_points'
            ? `/tabs/competitions/${payload.competition_id}/score`
            : `/tabs/competitions/${payload.competition_id}/setup`;
        void this.router.navigateByUrl(path, { replaceUrl: true });
      },
      error: async (err: unknown) => {
        this.demoBusy.set(null);
        const toast = await this.toasts.create({
          message: extractErrorMessage(err, 'Could not start that demo.'),
          duration: 3200,
          color: 'danger',
        });
        await toast.present();
      },
    });
  }

  openCompetition(id: string): void {
    void this.router.navigateByUrl(`/tabs/competitions/${id}`);
  }

  openPlacement(placement: MarketingPlacement): void {
    if (placement.cta_url) {
      window.open(placement.cta_url, '_blank', 'noopener');
      return;
    }
    const audience = placement.audience === 'government' ? 'government' : 'corporate';
    void this.router.navigate(['/partnerships'], {
      queryParams: { audience, placement: placement.id },
    });
  }

  scrollTo(id: string): void {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  private load(): void {
    forkJoin({
      competitions: this.api
        .listCompetitions({ page_size: 8, show_on_landing: true })
        .pipe(catchError(() => this.api.listCompetitions({ page_size: 8, is_private: false }))),
      posts: this.api.listDiscoverPosts({ page_size: 8 }).pipe(
        catchError(() => of({ next: null, previous: null, results: [] })),
      ),
      placements: this.api.listPlacements().pipe(catchError(() => of([]))),
    }).subscribe({
      next: ({ competitions, posts, placements }) => {
        this.placements.set(placements);
        const rows = competitions.results.filter(
          (item) => !item.is_private && item.show_on_landing !== false && item.status !== 'archived',
        );
        this.competitions.set(rows.slice(0, 3));
        this.liveCount.set(rows.filter((item) => item.status === 'active').length || rows.length);
        this.updates.set(posts.results.slice(0, 6));
        this.previewPosts.set(posts.results.slice(0, 3));
        this.loading.set(false);
        const first = rows[0];
        if (first) {
          this.api.getStandings(first.id).subscribe({
            next: (standings) => this.table.set(standings.rows.slice(0, 3)),
            error: () => this.table.set([]),
          });
        }
      },
      error: () => this.loading.set(false),
    });
  }
}
