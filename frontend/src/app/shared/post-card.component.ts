import {
  ChangeDetectionStrategy,
  Component,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import {
  AlertController,
  IonAvatar,
  IonBadge,
  IonButton,
  IonIcon,
  IonInput,
  IonSpinner,
} from '@ionic/angular/standalone';

import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import type { Comment, MediaAsset, Post } from '../core/models';
import { RelativeTimePipe } from './relative-time.pipe';

@Component({
  selector: 'fm-post-card',
  standalone: true,
  imports: [
    FormsModule,
    RelativeTimePipe,
    IonAvatar,
    IonIcon,
    IonButton,
    IonBadge,
    IonInput,
    IonSpinner,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <article class="fm-card post">
      <header>
        <ion-avatar>
          @if (post().author.avatar_url) {
            <img [src]="post().author.avatar_url" [alt]="post().author.display_name" />
          } @else {
            <span class="initials">{{ initials(post().author.display_name) }}</span>
          }
        </ion-avatar>

        <div class="who">
          <strong>{{ post().author.display_name }}</strong>
          <span class="when">{{ post().created_at | relativeTime }}</span>
        </div>

        @if (post().is_announcement) {
          <ion-badge color="warning">Announcement</ion-badge>
        }
        @if (post().is_pinned) {
          <ion-icon name="pin-outline" class="pin" aria-label="Pinned" />
        }
        @if (canDelete()) {
          <ion-button fill="clear" size="small" (click)="confirmDelete()">
            <ion-icon slot="icon-only" name="ellipsis-horizontal" aria-label="Post options" />
          </ion-button>
        }
      </header>

      @if (post().body) {
        <p class="body">{{ post().body }}</p>
      }

      @if (post().media.length) {
        <div class="media" [attr.data-count]="post().media.length">
          @for (item of post().media; track item.id) {
            <figure>
              @if (item.media_asset.kind === 'video') {
                @if (item.media_asset.status === 'ready') {
                  <video
                    controls
                    playsinline
                    preload="metadata"
                    [poster]="item.media_asset.thumbnail_url || null"
                    [src]="item.media_asset.playback_url || item.media_asset.url"
                  ></video>
                } @else {
                  <div class="processing">
                    <ion-spinner name="crescent" />
                    <span>{{ processingLabel(item.media_asset) }}</span>
                  </div>
                }
              } @else {
                <img [src]="item.media_asset.url" [alt]="item.media_asset.caption" loading="lazy" />
              }
            </figure>
          }
        </div>
      }

      <footer>
        <button
          type="button"
          class="action"
          [class.active]="post().my_reaction"
          (click)="toggleReaction()"
        >
          <ion-icon [name]="post().my_reaction ? 'heart' : 'heart-outline'" />
          @if (reactionCount() > 0) {
            <span>{{ reactionCount() }}</span>
          }
        </button>

        <button type="button" class="action" (click)="toggleComments()">
          <ion-icon name="chatbubble-outline" />
          @if (post().comment_count > 0) {
            <span>{{ post().comment_count }}</span>
          }
        </button>
      </footer>

      @if (commentsOpen()) {
        <div class="comments">
          @if (loadingComments()) {
            <div class="loading"><ion-spinner name="dots" /></div>
          } @else {
            @for (comment of comments(); track comment.id) {
              <div class="comment">
                <strong>{{ comment.author.display_name }}</strong>
                <span class="text">{{ comment.body }}</span>
                <span class="when">{{ comment.created_at | relativeTime }}</span>
              </div>
            } @empty {
              <p class="no-comments">No comments yet.</p>
            }
          }

          <form class="composer" (submit)="submitComment($event)">
            <ion-input
              [(ngModel)]="draft"
              name="comment"
              placeholder="Add a comment…"
              maxlength="2000"
              [disabled]="sendingComment()"
            />
            <ion-button
              type="submit"
              fill="clear"
              size="small"
              [disabled]="!draft.trim() || sendingComment()"
            >
              <ion-icon slot="icon-only" name="send-outline" aria-label="Send comment" />
            </ion-button>
          </form>
        </div>
      }
    </article>
  `,
  styleUrl: './post-card.component.scss',
})
export class PostCardComponent {
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly alerts = inject(AlertController);

  readonly post = input.required<Post>();
  readonly competitionId = input.required<string>();
  readonly canModerate = input(false);
  readonly deleted = output<string>();

  readonly comments = signal<Comment[]>([]);
  readonly commentsOpen = signal(false);
  readonly loadingComments = signal(false);
  readonly sendingComment = signal(false);
  readonly reactionOverride = signal<number | null>(null);

  draft = '';

  reactionCount(): number {
    return this.reactionOverride() ?? this.post().reaction_count;
  }

  initials(name: string): string {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((word) => word.charAt(0).toUpperCase())
      .join('');
  }

  processingLabel(asset: MediaAsset): string {
    return asset.status === 'failed' ? 'Video could not be processed' : 'Video is processing…';
  }

  canDelete(): boolean {
    return this.canModerate() || this.auth.user()?.id === this.post().author.id;
  }

  toggleReaction(): void {
    const wasReacted = Boolean(this.post().my_reaction);
    // Optimistic: the count nudges immediately, then the server's number wins.
    this.reactionOverride.set(this.reactionCount() + (wasReacted ? -1 : 1));

    this.api.reactToPost(this.competitionId(), this.post().id, 'like').subscribe({
      next: (result) => {
        this.reactionOverride.set(result.reaction_count);
        this.post().my_reaction = result.my_reaction;
      },
      error: () => this.reactionOverride.set(null),
    });
  }

  toggleComments(): void {
    const opening = !this.commentsOpen();
    this.commentsOpen.set(opening);

    if (opening && this.comments().length === 0) {
      this.loadingComments.set(true);
      this.api.listComments(this.post().id, { page_size: 50 }).subscribe({
        next: (page) => {
          this.comments.set(page.results);
          this.loadingComments.set(false);
        },
        error: () => this.loadingComments.set(false),
      });
    }
  }

  submitComment(event: Event): void {
    event.preventDefault();
    const body = this.draft.trim();
    if (!body || this.sendingComment()) return;

    this.sendingComment.set(true);
    this.api.createComment(this.post().id, body).subscribe({
      next: (comment) => {
        this.comments.update((current) => [...current, comment]);
        this.post().comment_count += 1;
        this.draft = '';
        this.sendingComment.set(false);
      },
      error: () => this.sendingComment.set(false),
    });
  }

  async confirmDelete(): Promise<void> {
    const alert = await this.alerts.create({
      header: 'Delete post?',
      message: 'This removes the post and its comments for everyone.',
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        {
          text: 'Delete',
          role: 'destructive',
          handler: () => {
            this.api.deletePost(this.competitionId(), this.post().id).subscribe({
              next: () => this.deleted.emit(this.post().id),
            });
          },
        },
      ],
    });
    await alert.present();
  }
}
