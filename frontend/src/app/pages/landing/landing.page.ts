import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { IonContent, IonSpinner } from '@ionic/angular/standalone';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

import { ApiService } from '../../core/api.service';
import { FALLBACK_CORPORATE, FALLBACK_GOVERNMENT, FALLBACK_LOGOS } from '../../core/marketing-fallbacks';
import type { Competition, MarketingPlacement, Post, StandingRow } from '../../core/models';

const STRIPES = ['#0f766e', '#ea580c', '#2563eb', '#7c3aed', '#0891b2'];

@Component({
  selector: 'fm-landing',
  standalone: true,
  imports: [DatePipe, IonContent, IonSpinner],
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
            <button type="button" (click)="scrollTo('public')">Competitions</button>
            <button type="button" (click)="scrollTo('corporate')">Corporate</button>
            <button type="button" (click)="scrollTo('government')">Government</button>
            <button type="button" (click)="scrollTo('happening')">Discover</button>
          </nav>
          <div class="auth">
            <button type="button" class="ghost" (click)="go('/login')">Sign in</button>
            <button type="button" class="primary" (click)="go('/register')">Get started</button>
          </div>
        </header>

        <section class="hero" id="top">
          <div>
            <h1>Build any competition you can describe — then run it.</h1>
            <p>
              Custom scoring, live results, league tables and a feed. Browse public competitions
              below — no account needed to look around.
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
          <p class="live-pill">
            <span></span>
            {{ liveCount() }} competition{{ liveCount() === 1 ? '' : 's' }} live right now
          </p>
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
                @if (competitions().length === 0) {
                  <p class="empty">
                    No featured competitions yet. When you create one, choose to show it on the
                    landing page so visitors can find it here.
                  </p>
                } @else {
                  @for (competition of competitions(); track competition.id; let i = $index) {
                    <article class="comp">
                      <div class="stripe" [style.background]="stripe(i)"></div>
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
              </aside>
            </div>
          }
        </section>

        @if (banners().length) {
          <section class="commercial" id="commercial">
            @for (banner of banners(); track banner.id) {
              <article class="banner">
                <p class="eyebrow">Commercial</p>
                <h2>{{ banner.name }}</h2>
                @if (banner.tagline) {
                  <p>{{ banner.tagline }}</p>
                }
                @if (banner.cta_label) {
                  <button type="button" class="primary" (click)="openPlacement(banner)">
                    {{ banner.cta_label }}
                  </button>
                }
              </article>
            }
          </section>
        }

        <section class="partners" id="corporate">
          <p class="eyebrow">Corporate</p>
          <h2>Workplace leagues, brand and broadcast</h2>
          <p class="lede">
            Reserved commercial space for companies: staff competitions, naming rights, kit and
            live boards. Slots are managed in admin so a campaign can go live without a release.
          </p>
          <div class="offer-grid">
            @for (item of corporate(); track item.id) {
              <article class="offer">
                <h3>{{ item.name }}</h3>
                <p>{{ item.tagline || item.body }}</p>
                @if (item.body && item.tagline) {
                  <p class="hint">{{ item.body }}</p>
                }
                <button type="button" class="text" (click)="openPlacement(item)">
                  {{ item.cta_label || 'Enquire' }} →
                </button>
              </article>
            }
          </div>
        </section>

        <section class="partners government" id="government">
          <p class="eyebrow">Government</p>
          <h2>Schools, municipalities and public programmes</h2>
          <p class="lede">
            Public-sector competitions stay readable without an account. Departments and
            federations get a named programme on this page and a route to partner.
          </p>
          <div class="offer-grid">
            @for (item of government(); track item.id) {
              <article class="offer">
                <h3>{{ item.name }}</h3>
                <p>{{ item.tagline || item.body }}</p>
                @if (item.body && item.tagline) {
                  <p class="hint">{{ item.body }}</p>
                }
                <button type="button" class="text" (click)="openPlacement(item)">
                  {{ item.cta_label || 'Enquire' }} →
                </button>
              </article>
            }
          </div>
        </section>

        <section class="sponsors" id="sponsors">
          <p class="eyebrow">Sponsors</p>
          <h2>Partners on the pitch, the feed, and at work</h2>
          <ul>
            @for (sponsor of logos(); track sponsor.id) {
              <li>
                <strong>{{ sponsor.name }}</strong>
                <span>{{ sponsor.tagline }}</span>
              </li>
            }
          </ul>
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

        <section class="enquire" id="enquire">
          <p class="eyebrow">Partnerships</p>
          <h2>Book a corporate or government slot</h2>
          <p class="lede">
            Tell us who you are. We place logos, banners and feature cards on this landing page
            and on public competitions.
          </p>
          <form class="enquire-form" (submit)="submitEnquiry($event)">
            <div class="audience">
              <button
                type="button"
                class="vis"
                [class.selected]="enquiryAudience() === 'corporate'"
                (click)="enquiryAudience.set('corporate')"
              >
                Corporate
              </button>
              <button
                type="button"
                class="vis"
                [class.selected]="enquiryAudience() === 'government'"
                (click)="enquiryAudience.set('government')"
              >
                Government
              </button>
            </div>
            <label>
              Organisation
              <input name="organisation" required maxlength="200" [disabled]="enquirySending()" />
            </label>
            <label>
              Your name
              <input name="contact_name" required maxlength="160" [disabled]="enquirySending()" />
            </label>
            <label>
              Email
              <input name="email" type="email" required [disabled]="enquirySending()" />
            </label>
            <label>
              What would you like to run or sponsor?
              <textarea name="message" required minlength="12" rows="4" [disabled]="enquirySending()"></textarea>
            </label>
            @if (enquiryError()) {
              <p class="hint" role="alert">{{ enquiryError() }}</p>
            }
            @if (enquirySent()) {
              <p class="hint">Received. Partnerships will come back to you.</p>
            }
            <button type="submit" class="primary" [disabled]="enquirySending()">
              {{ enquirySending() ? 'Sending…' : 'Send enquiry' }}
            </button>
          </form>
        </section>
      </div>
    </ion-content>
  `,
})
export class LandingPage {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  readonly loading = signal(true);
  readonly competitions = signal<Competition[]>([]);
  readonly table = signal<StandingRow[]>([]);
  readonly updates = signal<Post[]>([]);
  readonly previewPosts = signal<Post[]>([]);
  readonly liveCount = signal(0);
  readonly placements = signal<MarketingPlacement[]>([]);
  readonly enquiryAudience = signal<'corporate' | 'government'>('corporate');
  readonly enquirySending = signal(false);
  readonly enquirySent = signal(false);
  readonly enquiryError = signal<string | null>(null);

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
  readonly logos = computed(() => {
    const rows = this.placements().filter((item) => item.slot === 'logo');
    return rows.length ? rows : FALLBACK_LOGOS;
  });

  constructor() {
    this.load();
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
    void this.router.navigate(['/register'], {
      queryParams: { next: '/tabs/competitions/new' },
      replaceUrl: true,
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

  submitEnquiry(event: Event): void {
    event.preventDefault();
    const form = event.target as HTMLFormElement;
    const data = new FormData(form);
    const organisation = String(data.get('organisation') ?? '').trim();
    const contact_name = String(data.get('contact_name') ?? '').trim();
    const email = String(data.get('email') ?? '').trim();
    const message = String(data.get('message') ?? '').trim();
    if (!organisation || !contact_name || !email || message.length < 12) {
      this.enquiryError.set('Fill in the organisation, your name, email and a short note.');
      return;
    }
    this.enquirySending.set(true);
    this.enquiryError.set(null);
    this.api
      .sendEnquiry({
        audience: this.enquiryAudience(),
        organisation,
        contact_name,
        email,
        message,
      })
      .subscribe({
        next: () => {
          this.enquirySending.set(false);
          this.enquirySent.set(true);
          form.reset();
        },
        error: () => {
          this.enquirySending.set(false);
          this.enquiryError.set('Could not send that just now. Try again, or email partnerships.');
        },
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
