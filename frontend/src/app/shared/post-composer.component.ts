import { ChangeDetectionStrategy, Component, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { IonButton, IonIcon, IonSpinner, IonTextarea } from '@ionic/angular/standalone';

import { ApiService } from '../core/api.service';
import { extractErrorMessage } from '../core/error-message';
import type { Post } from '../core/models';
import { UploadService } from '../core/upload.service';
import { AttachmentQueue } from './attachment-queue';
import { AttachmentTrayComponent } from './attachment-tray.component';

@Component({
  selector: 'fm-post-composer',
  standalone: true,
  imports: [FormsModule, IonTextarea, IonButton, IonIcon, IonSpinner, AttachmentTrayComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="fm-card composer">
      <ion-textarea
        [(ngModel)]="body"
        [placeholder]="placeholder()"
        autoGrow="true"
        rows="2"
        maxlength="5000"
        [disabled]="posting()"
      />

      <fm-attachment-tray [queue]="attachments" />

      @if (error() || attachments.error()) {
        <p class="fm-form-error" role="alert">{{ error() || attachments.error() }}</p>
      }

      <div class="actions">
        <input
          #photoInput
          type="file"
          accept="image/*"
          multiple
          hidden
          (change)="pick($event)"
        />
        <input
          #videoInput
          type="file"
          accept="video/*"
          hidden
          (change)="pick($event)"
        />

        <ion-button
          fill="clear"
          size="small"
          [disabled]="posting() || attachments.full()"
          (click)="photoInput.click()"
        >
          <ion-icon slot="start" name="image-outline" aria-hidden="true" />
          Photo
        </ion-button>
        <ion-button
          fill="clear"
          size="small"
          [disabled]="posting() || attachments.full()"
          (click)="videoInput.click()"
        >
          <ion-icon slot="start" name="videocam-outline" aria-hidden="true" />
          Video
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

  readonly competitionId = input.required<string>();
  readonly fixtureId = input<string | null>(null);
  readonly placeholder = input('Share a result, a photo, a clip, or some trash talk…');
  readonly posted = output<Post>();

  readonly attachments = new AttachmentQueue(inject(UploadService), () => this.competitionId());
  readonly posting = signal(false);
  readonly error = signal<string | null>(null);

  body = '';

  canSubmit(): boolean {
    if (this.posting() || this.attachments.uploading()) return false;
    return this.body.trim().length > 0 || this.attachments.readyIds().length > 0;
  }

  pick(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.attachments.add(input.files);
    input.value = '';
  }

  submit(): void {
    if (!this.canSubmit()) return;

    this.posting.set(true);
    this.error.set(null);

    this.api
      .createPost(this.competitionId(), {
        body: this.body.trim(),
        media_asset_ids: this.attachments.readyIds(),
        ...(this.fixtureId() ? { fixture: this.fixtureId() } : {}),
      })
      .subscribe({
        next: (post) => {
          this.posted.emit(post);
          this.attachments.clear();
          this.body = '';
          this.posting.set(false);
        },
        error: (err: unknown) => {
          this.posting.set(false);
          this.error.set(extractErrorMessage(err, 'Could not publish that post.'));
        },
      });
  }
}
