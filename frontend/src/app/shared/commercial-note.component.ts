import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

import { COMMERCIAL } from '../core/commercial';

/**
 * Short commercial terms for organisers: create, setup and the competition
 * page itself, with a link to the full Costs and earnings page.
 */
@Component({
  selector: 'fm-commercial-note',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <aside [class.compact]="compact()" aria-label="Commercial opportunities for organisers">
      <p class="kicker">{{ compact() ? 'For organisers' : 'Commercial opportunities' }}</p>
      <p class="copy">
        @if (compact()) {
          The marketplace is live: you keep {{ 100 - commission }}% of sponsorships. Running
          competitions is free in year one.
        } @else {
          The marketing marketplace is live from day one — Fair Measure keeps
          {{ commission }}% of sponsorships. Competitions stay free to run in year one; paid
          plans after that are proposed starting points only.
        }
      </p>
      <a routerLink="/tabs/commercial">See costs, earnings and plans →</a>
    </aside>
  `,
  styles: `
    :host {
      display: block;
      margin: 16px 0;
    }
    :host:has(aside.compact) {
      margin: 10px 16px;
    }
    aside {
      display: grid;
      gap: 6px;
      padding: 14px 16px;
      border: 1px solid color-mix(in srgb, var(--ion-color-primary) 30%, var(--fm-line, #e3e6eb));
      border-radius: 16px;
      background: var(--fm-chip-selected, color-mix(in srgb, var(--ion-color-primary) 8%, #fff));
      color: var(--fm-ink, var(--ion-text-color));
    }
    aside.compact {
      padding: 12px 14px;
      border-radius: 14px;
    }
    .kicker {
      margin: 0;
      color: var(--fm-accent, var(--ion-color-primary));
      font-size: 0.7rem;
      font-weight: 800;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }
    .copy {
      margin: 0;
      font-size: 0.9rem;
      line-height: 1.5;
    }
    aside.compact .copy {
      font-size: 0.86rem;
    }
    a {
      justify-self: start;
      color: var(--fm-accent, var(--ion-color-primary));
      font-size: 0.88rem;
      font-weight: 700;
      text-decoration: none;
    }
    a:hover,
    a:focus-visible {
      text-decoration: underline;
    }
  `,
})
export class CommercialNoteComponent {
  readonly compact = input(false);
  readonly commission = COMMERCIAL.sponsorshipCommission;
}
