import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { TitleCasePipe } from '@angular/common';
import { IonBadge, IonButton, IonIcon } from '@ionic/angular/standalone';

import type { Competition } from '../core/models';

export type CompetitionCardPromo = {
  kind: 'corporate' | 'government' | 'competition' | 'featured';
  eyebrow: string;
  title: string;
};

@Component({
  selector: 'fm-competition-card',
  standalone: true,
  imports: [TitleCasePipe, IonBadge, IonButton, IonIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="card" [attr.data-size]="size()" [attr.data-promo]="promo()?.kind || null">
      <button type="button" class="card-main" (click)="open.emit()">
        <div class="crest" [style.background]="crestColour()">
          @if (competition().logo_url) {
            <img [src]="competition().logo_url" alt="" />
          } @else {
            <span>{{ initials() }}</span>
          }
        </div>

        <div class="body">
          <div class="title-row">
            <h2>{{ competition().name }}</h2>
            @if (competition().is_private) {
              <ion-icon name="lock-closed-outline" aria-label="Private" />
            }
          </div>

          <div class="meta">
            @if (competition().sport) {
              <span>{{ competition().sport }}</span>
            }
            <span>{{ competition().participant_count }} entrants</span>
            <span>{{ formatLabel() }}</span>
          </div>

          <div class="tags">
            <ion-badge [color]="statusColour()">{{ competition().status | titlecase }}</ion-badge>
            @if (competition().show_on_landing) {
              <ion-badge color="warning">On landing page</ion-badge>
            }
            @if (competition().open_to_scouts) {
              <ion-badge color="tertiary">Open to scouts</ion-badge>
            }
            @if (competition().my_role) {
              <ion-badge color="light">{{ competition().my_role | titlecase }}</ion-badge>
            }
          </div>
        </div>

        @if (!canDelete()) {
          <ion-icon name="chevron-forward-outline" class="chevron" aria-hidden="true" />
        }
      </button>

      @if (promo(); as ad) {
        <button type="button" class="promo" [attr.data-kind]="ad.kind" (click)="onPromo($event)">
          <span>{{ ad.eyebrow }}</span>
          <strong>{{ ad.title }}</strong>
        </button>
      }

      @if (canDelete()) {
        <ion-button
          fill="clear"
          color="danger"
          size="small"
          type="button"
          (click)="onDelete($event)"
        >
          <ion-icon slot="icon-only" name="trash-outline" aria-label="Delete competition" />
        </ion-button>
      }
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
        animation: fm-rise 0.5s var(--fm-ease-out) backwards;
        animation-delay: calc(min(var(--i, 0), 10) * 60ms);
      }

      .card {
        display: flex;
        flex-wrap: wrap;
        transition:
          transform 0.25s var(--fm-ease-out),
          box-shadow 0.25s var(--fm-ease-out);
        align-items: center;
        gap: 8px;
        width: calc(100% - 32px);
        margin: 12px 16px;
        padding: 0;
        background: var(--ion-card-background, #fff);
        border-radius: var(--fm-radius);
        box-shadow: var(--fm-shadow);
      }

      .card-main {
        display: flex;
        align-items: center;
        gap: 14px;
        flex: 1 1 auto;
        min-width: 0;
        padding: 14px;
        text-align: left;
        background: transparent;
        border: none;
        cursor: pointer;
        transition: transform 120ms ease;
      }

      .card:active {
        transform: scale(0.985);
      }

      @media (hover: hover) {
        .card:hover {
          transform: translateY(-2px);
          box-shadow: 0 12px 28px rgba(0, 0, 0, 0.12);
        }

        .card:hover .chevron {
          transform: translateX(3px);
        }
      }

      .card[data-promo='corporate'] {
        box-shadow:
          var(--fm-shadow),
          inset 3px 0 0 #0f766e;
      }

      .card[data-promo='government'] {
        box-shadow:
          var(--fm-shadow),
          inset 3px 0 0 #1e3a5f;
      }

      .card[data-promo='competition'],
      .card[data-promo='featured'] {
        box-shadow:
          var(--fm-shadow),
          inset 3px 0 0 #ea580c;
      }

      .card[data-size='large'] {
        width: calc(100% - 24px);
        margin: 16px 12px;
      }

      .card[data-size='large'] .card-main {
        padding: 20px 16px;
        gap: 16px;
      }

      .card[data-size='large'] .crest {
        width: 72px;
        height: 72px;
        border-radius: 18px;
        font-size: 1.25rem;
      }

      .card[data-size='large'] .title-row h2 {
        font-size: 1.22rem;
      }

      .card[data-size='large'] .meta {
        font-size: 0.88rem;
        margin-top: 6px;
      }

      .crest {
        flex: 0 0 auto;
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: grid;
        place-items: center;
        color: #fff;
        font-weight: 700;
        font-size: 1rem;
        overflow: hidden;

        img {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }
      }

      .body {
        flex: 1 1 auto;
        min-width: 0;
      }

      .title-row {
        display: flex;
        align-items: center;
        gap: 6px;

        h2 {
          margin: 0;
          font-size: 1rem;
          font-weight: 650;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          color: var(--ion-text-color);
        }

        ion-icon {
          font-size: 0.85rem;
          color: var(--ion-color-medium);
        }
      }

      .meta {
        display: flex;
        flex-wrap: wrap;
        gap: 4px 10px;
        margin-top: 3px;
        font-size: 0.8rem;
        color: var(--ion-color-medium);

        span:not(:last-child)::after {
          content: '·';
          margin-left: 10px;
        }
      }

      .tags {
        display: flex;
        gap: 6px;
        margin-top: 8px;

        ion-badge {
          font-size: 0.65rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }
      }

      ion-button {
        flex: 0 0 auto;
        margin: 0 8px 0 0;
      }

      .chevron {
        flex: 0 0 auto;
        color: var(--ion-color-medium);
        font-size: 1.1rem;
        transition: transform 0.25s var(--fm-ease-out);
      }

      .promo {
        flex: 1 1 100%;
        display: flex;
        align-items: baseline;
        gap: 8px;
        margin: -4px 14px 12px;
        padding: 8px 10px;
        border: 0;
        border-radius: 10px;
        background: var(--fm-chip-bg);
        color: var(--fm-ink);
        font: inherit;
        text-align: left;
        cursor: pointer;
      }

      .promo span {
        font-size: 0.66rem;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--ion-color-medium);
      }

      .promo strong {
        font-size: 0.8rem;
        font-weight: 650;
      }

      .promo[data-kind='corporate'] {
        background: #ccfbf1;
        color: var(--fm-on-light);
      }

      .promo[data-kind='government'] {
        background: #1e3a5f;
        color: var(--fm-on-fill);
      }

      .promo[data-kind='government'] span {
        color: #94a3b8;
      }

      .promo[data-kind='competition'],
      .promo[data-kind='featured'] {
        background: #ffedd5;
        color: var(--fm-on-light);
      }
    `,
  ],
})
export class CompetitionCardComponent {
  readonly competition = input.required<Competition>();
  readonly size = input<'default' | 'large'>('default');
  readonly canDelete = input(false);
  readonly promo = input<CompetitionCardPromo | null>(null);
  readonly open = output<void>();
  readonly promoClick = output<void>();
  readonly deleteClick = output<void>();

  onPromo(event: Event): void {
    event.preventDefault();
    event.stopPropagation();
    this.promoClick.emit();
  }

  onDelete(event: Event): void {
    event.preventDefault();
    event.stopPropagation();
    this.deleteClick.emit();
  }

  initials(): string {
    return this.competition()
      .name.split(/\s+/)
      .slice(0, 2)
      .map((word) => word.charAt(0).toUpperCase())
      .join('');
  }

  /** A stable colour per competition so cards stay recognisable between visits. */
  crestColour(): string {
    const name = this.competition().name;
    let hash = 0;
    for (let index = 0; index < name.length; index += 1) {
      hash = name.charCodeAt(index) + ((hash << 5) - hash);
    }
    const hue = Math.abs(hash) % 360;
    return `linear-gradient(135deg, hsl(${hue} 55% 42%), hsl(${(hue + 40) % 360} 60% 52%))`;
  }

  statusColour(): string {
    switch (this.competition().status) {
      case 'active':
        return 'success';
      case 'completed':
        return 'medium';
      case 'archived':
        return 'medium';
      default:
        return 'warning';
    }
  }

  formatLabel(): string {
    const competition = this.competition();
    const basis =
      competition.scoring_basis ??
      (competition.settings_json?.['scoring_basis'] as string | undefined) ??
      (competition.settings_json?.['table_mode'] === 'points' ? 'criteria' : undefined);
    if (basis === 'criteria') return 'Points accumulation';
    if (basis === 'results' && (competition.format === 'league' || competition.format === 'freeform')) {
      return 'Versus league';
    }
    const labels: Record<string, string> = {
      league: 'League',
      knockout: 'Knockout',
      group_knockout: 'Groups + knockout',
      ladder: 'Ladder',
      freeform: 'Freeform',
    };
    return labels[competition.format] ?? competition.format;
  }
}
