import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

import type { Competition } from '../core/models';

const TINTS = [
  'linear-gradient(135deg, #0f766e, #14b8a6)',
  'linear-gradient(135deg, #1d4ed8, #60a5fa)',
  'linear-gradient(135deg, #7c3aed, #c084fc)',
  'linear-gradient(135deg, #b45309, #f59e0b)',
  'linear-gradient(135deg, #be123c, #fb7185)',
];

/**
 * Competitions in one swipeable row, for the top of a page: they are what people
 * came for, so they are on screen before any scrolling.
 */
@Component({
  selector: 'fm-competition-strip',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (competitions().length) {
      <section class="strip" [attr.aria-label]="title()">
        <div class="head">
          <h2>{{ title() }}</h2>
          <span class="count">{{ competitions().length }}</span>
        </div>
        <div class="row">
          @for (competition of competitions(); track competition.id; let i = $index) {
            <button type="button" class="tile" (click)="open.emit(competition)">
              @if (competition.logo_url) {
                <img class="badge" [src]="competition.logo_url" alt="" />
              } @else {
                <span class="badge" [style.background]="tint(i)">{{ initials(competition.name) }}</span>
              }
              <span class="copy">
                <strong>{{ competition.name }}</strong>
                <small>
                  <span class="sport">{{ competition.sport || 'Competition' }}</span> ·
                  {{ competition.participant_count }}
                  {{ competition.participant_count === 1 ? 'entrant' : 'entrants' }}
                </small>
                @if (competition.my_role) {
                  <em class="mine">Yours</em>
                } @else if (competition.status === 'active') {
                  <em class="on">In play</em>
                }
              </span>
            </button>
          }
        </div>
      </section>
    }
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .strip {
        margin: 10px 0 4px;
      }

      .head {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 0 16px 8px;
      }

      h2 {
        margin: 0;
        font-size: 1rem;
        font-weight: 700;
      }

      .count {
        padding: 1px 8px;
        border-radius: 999px;
        background: var(--ion-color-step-100, #e9ecf1);
        font-size: 0.75rem;
        font-weight: 700;
      }

      .row {
        display: flex;
        gap: 10px;
        overflow-x: auto;
        padding: 2px 16px 8px;
        scroll-snap-type: x proximity;
        scroll-padding-inline: 16px;
        scrollbar-width: none;
        -webkit-overflow-scrolling: touch;
      }

      .row::-webkit-scrollbar {
        display: none;
      }

      .tile {
        flex: 0 0 auto;
        display: flex;
        align-items: center;
        gap: 10px;
        width: min(72vw, 260px);
        padding: 10px 12px;
        border: 1px solid var(--ion-color-step-150, #e3e6eb);
        border-radius: 16px;
        background: var(--ion-card-background, #fff);
        color: var(--ion-text-color);
        font: inherit;
        text-align: left;
        cursor: pointer;
        scroll-snap-align: start;
      }

      .badge {
        flex: 0 0 auto;
        display: grid;
        place-items: center;
        width: 44px;
        height: 44px;
        border-radius: 12px;
        object-fit: cover;
        color: #fff;
        font-weight: 800;
        font-size: 0.95rem;
      }

      .copy {
        display: grid;
        gap: 2px;
        min-width: 0;
      }

      strong {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      small {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        color: var(--ion-color-medium);
      }

      .sport {
        text-transform: capitalize;
      }

      em {
        justify-self: start;
        padding: 0 7px;
        border-radius: 999px;
        font-size: 0.7rem;
        font-style: normal;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }

      em.on {
        background: rgba(var(--ion-color-success-rgb), 0.14);
        color: var(--ion-color-success-shade);
      }

      em.mine {
        background: rgba(var(--ion-color-primary-rgb), 0.12);
        color: var(--ion-color-primary);
      }
    `,
  ],
})
export class CompetitionStripComponent {
  readonly competitions = input.required<Competition[]>();
  readonly title = input('Competitions');
  readonly open = output<Competition>();

  tint(index: number): string {
    return TINTS[index % TINTS.length];
  }

  initials(name: string): string {
    const words = name.trim().split(/\s+/).filter(Boolean);
    return ((words[0]?.[0] ?? '') + (words[1]?.[0] ?? '')).toUpperCase() || 'FM';
  }
}
