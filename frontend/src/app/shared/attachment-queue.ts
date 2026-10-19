import { computed, signal } from '@angular/core';
import type { Subscription } from 'rxjs';

import { extractErrorMessage } from '../core/error-message';
import type { MediaAsset } from '../core/models';
import type { UploadService } from '../core/upload.service';

export interface PendingMedia {
  file: File;
  previewUrl: string;
  asset: MediaAsset | null;
  failed: boolean;
  isVideo: boolean;
}

export const MAX_ATTACHMENTS = 4;

/**
 * Photos and videos picked for a post or comment. Each file uploads as soon as it
 * is chosen, so pressing Send only has to reference the finished asset ids.
 */
export class AttachmentQueue {
  readonly items = signal<PendingMedia[]>([]);
  readonly error = signal<string | null>(null);

  readonly uploading = computed(() => this.items().some((item) => !item.asset && !item.failed));
  readonly readyIds = computed(() =>
    this.items()
      .map((item) => item.asset?.id)
      .filter((id): id is string => Boolean(id)),
  );
  readonly full = computed(() => this.items().length >= MAX_ATTACHMENTS);

  /** Keyed by preview URL, which is unique per picked file. */
  private readonly uploads = new Map<string, Subscription>();

  constructor(
    private readonly uploader: UploadService,
    private readonly competitionId: () => string,
  ) {}

  add(files: FileList | File[] | null): void {
    const picked = Array.from(files ?? []);
    const room = MAX_ATTACHMENTS - this.items().length;
    if (picked.length > room) {
      this.error.set(`You can attach up to ${MAX_ATTACHMENTS} photos or videos.`);
    }

    for (const file of picked.slice(0, Math.max(room, 0))) {
      if (!file.type.startsWith('image/') && !file.type.startsWith('video/')) {
        this.error.set(`${file.name} is not a photo or video.`);
        continue;
      }

      const item: PendingMedia = {
        file,
        previewUrl: URL.createObjectURL(file),
        asset: null,
        failed: false,
        isVideo: file.type.startsWith('video/'),
      };
      this.items.update((current) => [...current, item]);

      const subscription = this.uploader
        .upload({ file, competitionId: this.competitionId() })
        .subscribe({
          next: (asset) => this.patch(item, { asset }),
          error: (err: unknown) => {
            this.patch(item, { failed: true });
            this.error.set(extractErrorMessage(err, `Could not upload ${file.name}.`));
          },
        });
      this.uploads.set(item.previewUrl, subscription);
    }
  }

  remove(target: PendingMedia): void {
    this.uploads.get(target.previewUrl)?.unsubscribe();
    this.uploads.delete(target.previewUrl);
    URL.revokeObjectURL(target.previewUrl);
    this.items.update((current) => current.filter((item) => item.previewUrl !== target.previewUrl));
    if (!this.items().some((item) => item.failed)) this.error.set(null);
  }

  clear(): void {
    for (const item of this.items()) {
      this.uploads.get(item.previewUrl)?.unsubscribe();
      URL.revokeObjectURL(item.previewUrl);
    }
    this.uploads.clear();
    this.items.set([]);
    this.error.set(null);
  }

  private patch(target: PendingMedia, change: Partial<PendingMedia>): void {
    this.items.update((current) =>
      current.map((item) => (item.previewUrl === target.previewUrl ? { ...item, ...change } : item)),
    );
  }
}
