import { ChangeDetectionStrategy, Component, HostListener, input, signal } from '@angular/core';
import { IonIcon, IonSpinner } from '@ionic/angular/standalone';

import type { MediaAsset, PostMedia } from '../core/models';

@Component({
  selector: 'fm-media-gallery',
  standalone: true,
  imports: [IonIcon, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (items().length) {
      <div class="gallery" [class.compact]="compact()" [attr.data-count]="items().length">
        @for (item of items(); track item.id; let index = $index) {
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
                  @if (item.media_asset.status === 'failed') {
                    <ion-icon name="alert-circle" aria-hidden="true" />
                  } @else {
                    <ion-spinner name="crescent" />
                  }
                  <span>{{ processingLabel(item.media_asset) }}</span>
                </div>
              }
            } @else {
              <button type="button" class="zoom" (click)="open(index)" aria-label="View photo">
                <img [src]="item.media_asset.url" [alt]="item.media_asset.caption" loading="lazy" />
              </button>
            }
          </figure>
        }
      </div>
    }

    @if (viewing(); as item) {
      <div class="lightbox" role="dialog" aria-label="Photo" (click)="close()">
        <button type="button" class="close" aria-label="Close photo" (click)="close()">
          <ion-icon name="close" />
        </button>
        <img
          [src]="item.media_asset.url"
          [alt]="item.media_asset.caption"
          (click)="$event.stopPropagation()"
        />
        @if (item.media_asset.caption) {
          <p class="caption">{{ item.media_asset.caption }}</p>
        }
      </div>
    }
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .gallery {
        display: grid;
        gap: 2px;
        margin-top: 10px;
        grid-template-columns: 1fr 1fr;

        &[data-count='1'] {
          grid-template-columns: 1fr;
        }

        &[data-count='3'] figure:first-child {
          grid-column: span 2;
        }

        figure {
          margin: 0;
          background: #000;
          aspect-ratio: 4 / 3;
          overflow: hidden;
        }

        img,
        video {
          display: block;
          width: 100%;
          height: 100%;
          object-fit: cover;
        }

        &.compact {
          gap: 4px;
          margin-top: 6px;
          max-width: 320px;

          figure {
            border-radius: 10px;
          }
        }
      }

      .zoom {
        display: block;
        width: 100%;
        height: 100%;
        padding: 0;
        border: none;
        background: none;
        cursor: zoom-in;

        img {
          transition: transform 0.25s ease;
        }

        &:hover img {
          transform: scale(1.03);
        }
      }

      .processing {
        display: grid;
        place-items: center;
        align-content: center;
        gap: 8px;
        width: 100%;
        height: 100%;
        color: #fff;
        font-size: 0.8rem;
        background: var(--ion-color-step-800, #2b2f36);
      }

      .lightbox {
        position: fixed;
        inset: 0;
        z-index: 1000;
        display: grid;
        place-items: center;
        align-content: center;
        gap: 12px;
        padding: 24px;
        background: rgb(0 0 0 / 0.9);
        animation: fade-in 0.18s ease both;

        img {
          max-width: 100%;
          max-height: 82vh;
          border-radius: 8px;
          animation: zoom-in 0.22s cubic-bezier(0.2, 0.8, 0.2, 1) both;
        }

        .caption {
          margin: 0;
          color: #fff;
          font-size: 0.88rem;
          text-align: center;
        }

        .close {
          position: absolute;
          top: calc(12px + var(--ion-safe-area-top, 0px));
          right: 12px;
          display: grid;
          place-items: center;
          width: 40px;
          height: 40px;
          border: none;
          border-radius: 50%;
          background: rgb(255 255 255 / 0.14);
          color: #fff;
          font-size: 1.3rem;
          cursor: pointer;
        }
      }

      @keyframes fade-in {
        from {
          opacity: 0;
        }
      }

      @keyframes zoom-in {
        from {
          opacity: 0;
          transform: scale(0.92);
        }
      }

      @media (prefers-reduced-motion: reduce) {
        .lightbox,
        .lightbox img {
          animation: none;
        }
      }
    `,
  ],
})
export class MediaGalleryComponent {
  readonly items = input.required<PostMedia[]>();
  readonly compact = input(false);

  readonly viewing = signal<PostMedia | null>(null);

  processingLabel(asset: MediaAsset): string {
    return asset.status === 'failed' ? 'Video could not be processed' : 'Video is processing…';
  }

  open(index: number): void {
    this.viewing.set(this.items()[index] ?? null);
  }

  close(): void {
    this.viewing.set(null);
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    this.close();
  }
}
