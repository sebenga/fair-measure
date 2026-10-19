import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { IonIcon, IonSpinner } from '@ionic/angular/standalone';

import type { AttachmentQueue } from './attachment-queue';

/** Thumbnails of picked files with upload state and a remove button. */
@Component({
  selector: 'fm-attachment-tray',
  standalone: true,
  imports: [IonIcon, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (queue().items().length) {
      <div class="attachments" [class.small]="small()">
        @for (item of queue().items(); track item.previewUrl) {
          <div class="thumb" [class.failed]="item.failed" [class.done]="item.asset">
            @if (item.isVideo) {
              <video [src]="item.previewUrl" muted playsinline preload="metadata"></video>
              <ion-icon name="videocam" class="kind" aria-hidden="true" />
            } @else {
              <img [src]="item.previewUrl" alt="" />
            }

            @if (!item.asset && !item.failed) {
              <div class="veil" aria-label="Uploading"><ion-spinner name="crescent" /></div>
            }
            @if (item.failed) {
              <div class="veil"><ion-icon name="alert-circle" aria-label="Upload failed" /></div>
            }

            <button
              type="button"
              class="remove"
              (click)="queue().remove(item)"
              [attr.aria-label]="'Remove ' + item.file.name"
            >
              <ion-icon name="close" />
            </button>
          </div>
        }
      </div>
    }
  `,
  styles: [
    `
      .attachments {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 8px 0 4px;

        &.small .thumb {
          width: 56px;
          height: 56px;
        }
      }

      .thumb {
        position: relative;
        width: 72px;
        height: 72px;
        border-radius: 10px;
        overflow: hidden;
        background: var(--ion-color-step-100, #eceff3);
        animation: pop-in 0.22s cubic-bezier(0.2, 0.8, 0.2, 1) both;

        img,
        video {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }

        .kind {
          position: absolute;
          left: 5px;
          bottom: 5px;
          color: #fff;
          font-size: 0.85rem;
          filter: drop-shadow(0 1px 2px rgb(0 0 0 / 0.6));
        }

        .veil {
          position: absolute;
          inset: 0;
          display: grid;
          place-items: center;
          background: rgb(0 0 0 / 0.42);
          color: #fff;

          ion-icon {
            font-size: 1.4rem;
          }
        }

        .remove {
          position: absolute;
          top: 3px;
          right: 3px;
          width: 20px;
          height: 20px;
          display: grid;
          place-items: center;
          padding: 0;
          border: none;
          border-radius: 50%;
          background: rgb(0 0 0 / 0.62);
          color: #fff;
          cursor: pointer;

          ion-icon {
            font-size: 0.8rem;
          }
        }

        &.failed {
          outline: 2px solid var(--ion-color-danger);
        }
      }

      @keyframes pop-in {
        from {
          opacity: 0;
          transform: scale(0.8);
        }
      }

      @media (prefers-reduced-motion: reduce) {
        .thumb {
          animation: none;
        }
      }
    `,
  ],
})
export class AttachmentTrayComponent {
  readonly queue = input.required<AttachmentQueue>();
  readonly small = input(false);
}
