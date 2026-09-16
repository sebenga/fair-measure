import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { IonButton, IonIcon, IonSpinner, IonTextarea } from '@ionic/angular/standalone';

import { ApiService } from '../core/api.service';
import { extractErrorMessage } from '../core/error-message';
import type { MediaAsset, Post } from '../core/models';
import { UploadService } from '../core/upload.service';

interface PendingMedia {
  file: File;
  previewUrl: string;
  asset: MediaAsset | null;
  failed: boolean;
}

const MAX_ATTACHMENTS = 4;

@Component({
  selector: 'fm-post-composer',
  standalone: true,
  imports: [FormsModule, IonTextarea, IonButton, IonIcon, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="fm-card composer">
      <ion-textarea
        [(ngModel)]="body"
        placeholder="Share a result, a clip, or some trash talk…"
        autoGrow="true"
        rows="2"
        maxlength="5000"
        [disabled]="posting()"
      />

      @if (pending().length) {
        <div class="attachments">
          @for (item of pending(); track item.previewUrl) {
            <div class="thumb" [class.failed]="item.failed">
              @if (item.file.type.startsWith('video/')) {
                <video [src]="item.previewUrl" muted playsinline></video>
                <ion-icon name="videocam" class="kind" aria-hidden="true" />
              } @else {
                <img [src]="item.previewUrl" alt="" />
              }

              @if (!item.asset && !item.failed) {
                <div class="veil"><ion-spinner name="crescent" /></div>
              }
              @if (item.failed) {
                <div class="veil"><ion-icon name="alert-circle" /></div>
              }

              <button
                type="button"
                class="remove"
                (click)="removeAttachment(item)"
                aria-label="Remove attachment"
              >
                <ion-icon name="close" />
              </button>
            </div>
          }
        </div>
      }

      @if (error()) {
        <p class="fm-form-error" role="alert">{{ error() }}</p>
      }

      <div class="actions">
        <input
          #fileInput
          type="file"
          accept="image/*,video/*"
          multiple
          hidden
          (change)="onFilesPicked($event)"
        />

        <ion-button
          fill="clear"
          size="small"
          [disabled]="posting() || pending().length >= maxAttachments"
          (click)="fileInput.click()"
        >
          <ion-icon slot="icon-only" name="image-outline" aria-label="Add photo or video" />
        </ion-button>

        <span class="spacer"></span>

        <ion-button size="small" [disabled]="!canSubmit()" (click)="submit()">
          @if (posting()) {
            <ion-spinner name="crescent" />
          } @else {
            Post
          }
        </ion-button>
      </div>
    </div>
  `,
  styleUrl: './post-composer.component.scss',
})
export class PostComposerComponent {
  private readonly api = inject(ApiService);
  private readonly uploads = inject(UploadService);

  readonly competitionId = input.required<string>();
  readonly fixtureId = input<string | null>(null);
  readonly posted = output<Post>();

  readonly maxAttachments = MAX_ATTACHMENTS;
  readonly pending = signal<PendingMedia[]>([]);
  readonly posting = signal(false);
  readonly error = signal<string | null>(null);

  body = '';

  canSubmit(): boolean {
    if (this.posting()) return false;
    const hasReadyMedia = this.pending().some((item) => item.asset);
    const stillUploading = this.pending().some((item) => !item.asset && !item.failed);
    return (this.body.trim().length > 0 || hasReadyMedia) && !stillUploading;
  }

  onFilesPicked(event: Event): void {
    const input = event.target as HTMLInputElement;
    const files = Array.from(input.files ?? []).slice(
      0,
      MAX_ATTACHMENTS - this.pending().length,
    );
    input.value = '';

    for (const file of files) {
      const item: PendingMedia = {
        file,
        previewUrl: URL.createObjectURL(file),
        asset: null,
        failed: false,
      };
      this.pending.update((current) => [...current, item]);

      // Upload as soon as the file is chosen so posting feels instant later.
      this.uploads.upload({ file, competitionId: this.competitionId() }).subscribe({
        next: (asset) => this.updateItem(item, { asset }),
        error: (err: unknown) => {
          this.updateItem(item, { failed: true });
          this.error.set(extractErrorMessage(err, `Could not upload ${file.name}.`));
        },
      });
    }
  }

  private updateItem(target: PendingMedia, patch: Partial<PendingMedia>): void {
    this.pending.update((current) =>
      current.map((item) => (item === target ? { ...item, ...patch } : item)),
    );
  }

  removeAttachment(target: PendingMedia): void {
    URL.revokeObjectURL(target.previewUrl);
    this.pending.update((current) => current.filter((item) => item !== target));
  }

  submit(): void {
    if (!this.canSubmit()) return;

    this.posting.set(true);
    this.error.set(null);

    const mediaIds = this.pending()
      .map((item) => item.asset?.id)
      .filter((id): id is string => Boolean(id));

    this.api
      .createPost(this.competitionId(), {
        body: this.body.trim(),
        media_ids: mediaIds,
        ...(this.fixtureId() ? { fixture: this.fixtureId() } : {}),
      })
      .subscribe({
        next: (post) => {
          this.posted.emit(post);
          this.reset();
        },
        error: (err: unknown) => {
          this.posting.set(false);
          this.error.set(extractErrorMessage(err, 'Could not publish that post.'));
        },
      });
  }

  private reset(): void {
    for (const item of this.pending()) {
      URL.revokeObjectURL(item.previewUrl);
    }
    this.pending.set([]);
    this.body = '';
    this.posting.set(false);
  }
}
