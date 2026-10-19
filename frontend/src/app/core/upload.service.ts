import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, from, of, switchMap } from 'rxjs';

import type { MediaAsset, UploadTarget } from './models';
import { ApiService } from './api.service';

export interface UploadRequest {
  file: File;
  competitionId?: string;
  caption?: string;
}

/**
 * Uploads go straight from the browser to R2/S3 (or the video provider) using a
 * short-lived presigned URL, so large videos never pass through Django.
 *
 * The three steps are: ask the API for a target, PUT the bytes there, then tell
 * the API the bytes landed. Video assets come back as `processing` and are
 * finalised later by a provider webhook.
 */
@Injectable({ providedIn: 'root' })
export class UploadService {
  private readonly http = inject(HttpClient);
  private readonly api = inject(ApiService);

  upload({ file, competitionId, caption = '' }: UploadRequest): Observable<MediaAsset> {
    const kind = file.type.startsWith('video/') ? 'video' : 'image';

    return this.api
      .requestUpload({
        kind,
        ...(competitionId ? { competition_id: competitionId } : {}),
        filename: file.name,
        content_type: file.type || 'application/octet-stream',
        size_bytes: file.size,
        caption,
      })
      .pipe(
        switchMap((target) =>
          from(this.putBytes(target, file)).pipe(
            // Videos are finalised by the provider's webhook, not by the client.
            switchMap(() => (kind === 'video' ? of(target.media_asset) : this.complete(target, file))),
          ),
        ),
      );
  }

  private async putBytes(target: UploadTarget, file: File): Promise<void> {
    const method = target.method || 'PUT';
    // Direct-creator video uploads take a multipart form on POST.
    const body: BodyInit = method === 'POST' ? this.asForm(file) : file;
    const response = await fetch(target.upload_url, {
      method,
      headers: method === 'POST' ? target.headers ?? {} : target.headers ?? { 'Content-Type': file.type },
      body,
    });

    if (!response.ok) {
      throw new Error(`Upload failed with status ${response.status}`);
    }
  }

  private asForm(file: File): FormData {
    const form = new FormData();
    form.append('file', file);
    return form;
  }

  private complete(target: UploadTarget, file: File): Observable<MediaAsset> {
    return this.api.completeUpload(target.media_asset.id, {
      size_bytes: file.size,
      content_type: file.type,
    });
  }

  /** Poll until a video finishes transcoding, or give up after ~2 minutes. */
  waitUntilReady(mediaId: string, intervalMs = 4000, attempts = 30): Observable<MediaAsset> {
    return new Observable<MediaAsset>((subscriber) => {
      let remaining = attempts;
      let timer: ReturnType<typeof setTimeout>;

      const poll = () => {
        this.api.getMediaAsset(mediaId).subscribe({
          next: (asset) => {
            if (asset.status === 'ready' || asset.status === 'failed') {
              subscriber.next(asset);
              subscriber.complete();
              return;
            }
            remaining -= 1;
            if (remaining <= 0) {
              subscriber.next(asset);
              subscriber.complete();
              return;
            }
            timer = setTimeout(poll, intervalMs);
          },
          error: (error: unknown) => subscriber.error(error),
        });
      };

      poll();
      return () => clearTimeout(timer);
    });
  }
}
