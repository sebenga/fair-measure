import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  inject,
  input,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import {
  IonButton,
  IonIcon,
  IonInfiniteScroll,
  IonInfiniteScrollContent,
  IonSpinner,
  type InfiniteScrollCustomEvent,
} from '@ionic/angular/standalone';

import { ApiService } from '../../../core/api.service';
import { extractErrorMessage } from '../../../core/error-message';
import type { CompetitionDetail, Post } from '../../../core/models';
import { RealtimeService } from '../../../core/realtime.service';
import { PostCardComponent } from '../../../shared/post-card.component';
import { PostComposerComponent } from '../../../shared/post-composer.component';

@Component({
  selector: 'fm-competition-feed',
  standalone: true,
  imports: [
    IonSpinner,
    IonIcon,
    IonButton,
    IonInfiniteScroll,
    IonInfiniteScrollContent,
    PostCardComponent,
    PostComposerComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (canPost()) {
      <fm-post-composer
        [competitionId]="competition().id"
        (posted)="prepend($event)"
      />
    }

    @if (newPostCount() > 0) {
      <button type="button" class="new-pill" (click)="load(false)">
        {{ newPostCount() }} new {{ newPostCount() === 1 ? 'post' : 'posts' }}
      </button>
    }

    @if (loading()) {
      <div class="centered"><ion-spinner name="crescent" /></div>
    } @else if (error()) {
      <div class="fm-empty">
        <ion-icon name="alert-circle-outline" aria-hidden="true" />
        <h3>Feed unavailable</h3>
        <p>{{ error() }}</p>
        <ion-button fill="clear" (click)="load()">Try again</ion-button>
      </div>
    } @else if (posts().length === 0) {
      <div class="fm-empty">
        <ion-icon name="chatbubbles-outline" aria-hidden="true" />
        <h3>Quiet in here</h3>
        <p>Share a match photo, a clip, or some trash talk to get things going.</p>
      </div>
    } @else {
      @for (post of posts(); track post.id) {
        <fm-post-card
          [post]="post"
          [competitionId]="competition().id"
          [canModerate]="canModerate()"
          (deleted)="remove(post.id)"
        />
      }

      <ion-infinite-scroll [disabled]="!nextUrl()" (ionInfinite)="loadMore($event)">
        <ion-infinite-scroll-content loadingSpinner="crescent" />
      </ion-infinite-scroll>
    }
  `,
  styles: [
    `
      .centered {
        display: grid;
        place-items: center;
        padding: 64px 0;
      }

      .new-pill {
        display: block;
        margin: 4px auto 0;
        padding: 7px 16px;
        border: none;
        border-radius: 999px;
        background: var(--ion-color-primary);
        color: #fff;
        font-size: 0.8rem;
        font-weight: 600;
        cursor: pointer;
        box-shadow: var(--fm-shadow);
      }
    `,
  ],
})
export class CompetitionFeedComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly realtime = inject(RealtimeService);
  private readonly destroyRef = inject(DestroyRef);

  readonly competition = input.required<CompetitionDetail>();

  readonly posts = signal<Post[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly nextUrl = signal<string | null>(null);
  readonly newPostCount = signal(0);

  ngOnInit(): void {
    this.load();

    // Someone else posting shouldn't yank the feed out from under the reader,
    // so surface a pill they can tap instead of splicing the post in.
    this.realtime
      .on<{ post_id: string; author_id: string }>('post.created')
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((payload) => {
        const alreadyShown = this.posts().some((post) => post.id === payload.post_id);
        if (!alreadyShown) {
          this.newPostCount.update((count) => count + 1);
        }
      });

    this.realtime
      .on<{ post_id: string }>('post.deleted')
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((payload) => this.remove(payload.post_id));
  }

  load(showSpinner = true): void {
    if (showSpinner) this.loading.set(true);
    this.error.set(null);

    this.api.listPosts(this.competition().id, { page_size: 20 }).subscribe({
      next: (page) => {
        this.posts.set(page.results);
        this.nextUrl.set(page.next);
        this.newPostCount.set(0);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err));
        this.loading.set(false);
      },
    });
  }

  loadMore(event: InfiniteScrollCustomEvent): void {
    const url = this.nextUrl();
    if (!url) {
      void event.target.complete();
      return;
    }

    this.api.loadMorePosts(url).subscribe({
      next: (page) => {
        this.posts.update((current) => [...current, ...page.results]);
        this.nextUrl.set(page.next);
        void event.target.complete();
      },
      error: () => void event.target.complete(),
    });
  }

  prepend(post: Post): void {
    this.posts.update((current) => [post, ...current]);
  }

  remove(postId: string): void {
    this.posts.update((current) => current.filter((post) => post.id !== postId));
  }

  canPost(): boolean {
    return this.competition().my_role !== null;
  }

  canModerate(): boolean {
    const role = this.competition().my_role;
    return role === 'owner' || role === 'admin';
  }
}
