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
import { Subject, debounceTime, distinctUntilChanged, forkJoin, switchMap } from 'rxjs';
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
import type { Competition, Post } from '../../core/models';
import { CompetitionCardComponent } from '../../shared/competition-card.component';
import { InboxTrayComponent } from '../../shared/inbox-tray.component';
import { PostCardComponent } from '../../shared/post-card.component';
import { PostComposerComponent } from '../../shared/post-composer.component';
import { PromoSlotComponent } from '../../shared/promo-slot.component';

type FeedItem =
  | { kind: 'competition'; id: string; competition: Competition }
  | { kind: 'post'; id: string; post: Post };

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
          <aside class="sponsored-rail left" aria-label="Sponsored">
            <fm-promo-slot
              kind="sponsored"
              eyebrow="Sponsored"
              title="Fantasy on your own league"
              body="Pick an XI from the real roster. Points come from recorded match stats."
              action="See how it works"
              icon="football-outline"
              (open)="openFantasyHint()"
            />
          </aside>

          <div class="feed">
            <fm-promo-slot
              kind="banner"
              eyebrow="Campaign"
              title="Grow your league"
              body="Share Discover so players, parents and scouts can find you — the same way a page is found on Facebook."
              action="Create a public league"
              icon="megaphone-outline"
              (open)="createLeague()"
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

            @if (featured().length) {
              <section class="rail">
                <h3>Promoted · Open to scouts</h3>
                <div class="scroller">
                  @for (league of featured(); track league.id) {
                    <button type="button" class="chip" (click)="open(league)">
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
                    (open)="open(item.competition)"
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
                <h3>Suggested for you</h3>
                <p>Leagues like the ones people in your network join.</p>
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

          <aside class="sponsored-rail right" aria-label="Sponsored">
            <fm-promo-slot
              kind="sponsored"
              eyebrow="Sponsored"
              title="Promote this league"
              body="Put your competition in this rail so new players and scouts see it first."
              action="Create a public league"
              icon="megaphone-outline"
              (open)="createLeague()"
            />
            @if (featured()[0]; as lead) {
              <fm-promo-slot
                kind="sponsored"
                eyebrow="Sponsored"
                [title]="lead.name"
                [body]="'Open to scouts · ' + (lead.sport || 'League')"
                action="Open"
                icon="ribbon-outline"
                (open)="open(lead)"
              />
            }
          </aside>
        </div>
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
        gap: 0;
      }

      .sponsored-rail.left {
        display: none;
      }

      .feed {
        min-width: 0;
      }

      .composer-wrap {
        margin: 12px 0 4px;
      }

      .composer-wrap label {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 0 16px 8px;
        color: var(--ion-color-medium);
        font-size: 0.8rem;
        font-weight: 650;
      }

      .composer-wrap select {
        min-height: 36px;
        padding: 4px 8px;
        border: 1px solid var(--ion-color-step-200, #d7d8da);
        border-radius: 10px;
        background: var(--ion-background-color, #fff);
        color: inherit;
        font: inherit;
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

      .rail,
      .suggest {
        margin: 16px 0 8px;
      }

      .rail h3,
      .suggest h3 {
        margin: 0 16px 8px;
        font-size: 0.92rem;
      }

      .suggest p {
        margin: 0 16px 4px;
        color: var(--ion-color-medium);
        font-size: 0.86rem;
      }

      .scroller {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        padding: 0 16px 4px;
      }

      .chip {
        flex: 0 0 200px;
        display: grid;
        gap: 2px;
        padding: 12px;
        border: 0;
        border-radius: 14px;
        background: color-mix(in srgb, var(--ion-color-primary) 12%, #fff);
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
export class DiscoverPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly queries = new Subject<string>();

  readonly results = signal<Competition[]>([]);
  readonly posts = signal<Post[]>([]);
  readonly mine = signal<Competition[]>([]);
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
  readonly composerLeague = computed(
    () => this.mine().find((row) => row.id === this.composerLeagueId()) ?? this.mine()[0] ?? null,
  );
  readonly stream = computed<FeedItem[]>(() => {
    const competitions = this.results();
    const posts = this.query() ? [] : this.posts();
    const items: FeedItem[] = [];
    let postIndex = 0;
    for (const competition of competitions) {
      items.push({ kind: 'competition', id: competition.id, competition });
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
      posts: this.api.listDiscoverPosts({ page_size: 20 }),
      mine: this.api.listCompetitions({ mine: true, page_size: 20 }),
    }).subscribe({
      next: ({ competitions, posts, mine }) => {
        this.results.set(competitions.results);
        this.posts.set(posts.results);
        this.mine.set(mine.results);
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

  open(competition: Competition): void {
    void this.router.navigate(['/tabs/competitions', competition.id]);
  }

  createLeague(): void {
    void this.router.navigate(['/tabs/competitions/new']);
  }

  openFantasyHint(): void {
    const openToScouts = this.featured()[0] ?? this.results()[0];
    if (openToScouts) {
      void this.router.navigate(['/tabs/competitions', openToScouts.id], {
        queryParams: { tab: 'fantasy' },
      });
      return;
    }
    void this.router.navigate(['/tabs/competitions/new']);
  }
}
