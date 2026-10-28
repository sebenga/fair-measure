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
  IonBadge,
  IonButton,
  IonIcon,
  IonInput,
  IonSpinner,
} from '@ionic/angular/standalone';

import { Router } from '@angular/router';

import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import type { Comment, MediaAsset, Post } from '../core/models';
import { UploadService } from '../core/upload.service';
import { AttachmentQueue } from './attachment-queue';
import { AttachmentTrayComponent } from './attachment-tray.component';
import { RelativeTimePipe } from './relative-time.pipe';

@Component({
  selector: 'fm-post-card',
  standalone: true,
  imports: [
    FormsModule,
    RelativeTimePipe,
    IonIcon,
    IonButton,
    IonBadge,
    IonInput,
    IonSpinner,
    AttachmentTrayComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <article class="fm-card post" [attr.data-kind]="kind()">
      <header>
        <button type="button" class="crest" (click)="openLeague()" [attr.aria-label]="leagueName()">
          @if (post().competition_logo_url) {
            <img [src]="post().competition_logo_url" [alt]="" />
          } @else {
            <span>{{ initials(leagueName()) }}</span>
          }
        </button>

        <div class="who">
          <button type="button" class="name" (click)="kind() === 'profile' ? openProfile() : openLeague()">
            {{ kind() === 'profile' ? post().author.display_name : leagueName() }}
          </button>
          @if (kind() === 'profile' && (post().author.headline || post().author.city)) {
            <span class="headline">
              {{ post().author.headline || post().author.city }}
            </span>
          }
          @if (kind() !== 'profile') {
            <span class="headline">{{ post().author.display_name }}</span>
          }
          <span class="when">
            {{ post().created_at | relativeTime }}
            @if (kind() === 'profile' && showLeague() && post().competition_name) {
              ·
              <button type="button" class="league" (click)="openLeague()">
                {{ post().competition_name }}
              </button>
            }
          </span>
        </div>

        <ion-badge [color]="kindColor()">{{ kindLabel() }}</ion-badge>
        @if (post().is_announcement && kind() !== 'competition') {
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

      @if (post().fixture && (post().fixture_label || post().scoreline)) {
        <button type="button" class="match" (click)="openMatch()">
          @if (post().competition_logo_url) {
            <img class="match-crest" [src]="post().competition_logo_url" alt="" />
          } @else {
            <ion-icon name="football-outline" aria-hidden="true" />
          }
          <span>
            <strong>{{ post().fixture_label || 'Match' }}</strong>
            @if (post().scoreline) {
              <small>{{ post().scoreline }}</small>
            }
          </span>
        </button>
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
                @if (comment.body) {
                  <span class="text">{{ comment.body }}</span>
                }
                @if (comment.media.length) {
                  <div class="comment-media" [attr.data-count]="comment.media.length">
                    @for (item of comment.media; track item.id) {
                      @if (item.media_asset.kind === 'video') {
                        <video
                          controls
                          playsinline
                          preload="metadata"
                          [poster]="item.media_asset.thumbnail_url || null"
                          [src]="item.media_asset.playback_url || item.media_asset.url"
                        ></video>
                      } @else {
                        <img
                          [src]="item.media_asset.url"
                          [alt]="item.media_asset.caption || 'Comment photo'"
                        />
                      }
                    }
                  </div>
                }
                <span class="when">{{ comment.created_at | relativeTime }}</span>
              </div>
            } @empty {
              <p class="no-comments">No comments yet.</p>
            }
          }

          @if (auth.isAuthenticated()) {
          <fm-attachment-tray [queue]="attachments" [small]="true" />
          <form class="composer" (submit)="submitComment($event)">
            <input
              #commentPhoto
              type="file"
              accept="image/*"
              hidden
              (change)="pickComment($event)"
            />
            <input
              #commentVideo
              type="file"
              accept="video/*"
              hidden
              (change)="pickComment($event)"
            />
            <ion-button
              type="button"
              fill="clear"
              size="small"
              [disabled]="sendingComment() || attachments.full()"
              (click)="commentPhoto.click()"
            >
              <ion-icon slot="icon-only" name="image-outline" aria-label="Add a photo" />
            </ion-button>
            <ion-button
              type="button"
              fill="clear"
              size="small"
              [disabled]="sendingComment() || attachments.full()"
              (click)="commentVideo.click()"
            >
              <ion-icon slot="icon-only" name="videocam-outline" aria-label="Add a video" />
            </ion-button>
            <ion-input
              [(ngModel)]="draft"
              name="comment"
              placeholder="Write a comment or attach a photo…"
              maxlength="2000"
              [disabled]="sendingComment()"
            />
            <ion-button
              type="submit"
              fill="clear"
              size="small"
              [disabled]="!canSendComment()"
            >
              <ion-icon slot="icon-only" name="send-outline" aria-label="Send comment" />
            </ion-button>
          </form>
          } @else {
            <p class="no-comments">Sign in to join the conversation.</p>
          }
        </div>
      }
    </article>
  `,
  styleUrl: './post-card.component.scss',
})
export class PostCardComponent {
  private readonly api = inject(ApiService);
  readonly auth = inject(AuthService);
  private readonly alerts = inject(AlertController);
  private readonly router = inject(Router);

  readonly post = input.required<Post>();
  readonly competitionId = input.required<string>();
  readonly canModerate = input(false);
  readonly showLeague = input(false);
  readonly deleted = output<string>();
  readonly attachments = new AttachmentQueue(inject(UploadService), () => this.competitionId());

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
    if (this.kind() === 'live') return this.canModerate();
    return this.canModerate() || this.auth.user()?.id === this.post().author.id;
  }

  canSendComment(): boolean {
    if (this.sendingComment() || this.attachments.uploading()) return false;
    return this.draft.trim().length > 0 || this.attachments.readyIds().length > 0;
  }

  leagueName(): string {
    return this.post().competition_name || 'League';
  }

  kind(): Post['kind'] {
    return this.post().kind || 'profile';
  }

  kindLabel(): string {
    switch (this.kind()) {
      case 'live':
        return 'Live';
      case 'competition':
        return 'League';
      default:
        return 'Profile';
    }
  }

  kindColor(): string {
    return this.kind() === 'live' ? 'danger' : this.kind() === 'competition' ? 'warning' : 'medium';
  }

  openLeague(): void {
    void this.router.navigate(['/tabs/competitions', this.competitionId()]);
  }

  openProfile(): void {
    void this.router.navigate([
      '/tabs/competitions',
      this.competitionId(),
      'players',
      this.post().author.id,
    ]);
  }

  openMatch(): void {
    const fixtureId = this.post().fixture;
    if (!fixtureId) return;
    void this.router.navigate([
      '/tabs/competitions',
      this.competitionId(),
      'fixtures',
      fixtureId,
    ]);
  }

  pickComment(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.attachments.add(input.files);
    input.value = '';
  }

  toggleReaction(): void {
    if (!this.auth.isAuthenticated()) {
      void this.router.navigate(['/login'], {
        queryParams: { next: `/tabs/competitions/${this.competitionId()}` },
      });
      return;
    }
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
    if (!this.canSendComment()) return;

    const body = this.draft.trim();
    this.sendingComment.set(true);
    this.api.createComment(this.post().id, body, null, this.attachments.readyIds()).subscribe({
      next: (comment) => {
        this.comments.update((current) => [...current, comment]);
        this.post().comment_count += 1;
        this.draft = '';
        this.attachments.clear();
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
