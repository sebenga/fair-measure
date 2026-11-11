import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

import { LEGAL } from '../core/legal';

/** The short legal footer: copyright, ownership and links to the notices. */
@Component({
  selector: 'fm-legal-footer',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <footer>
      <p>
        © {{ legal.year }} {{ legal.owner }}. All rights reserved. {{ legal.product }} is owned and operated by
        {{ legal.owner }}, South Africa. Not affiliated with any sports federation. Results are for information only.
      </p>
      <nav aria-label="Legal">
        <a routerLink="/legal">Terms</a>
        <span aria-hidden="true">·</span>
        <a routerLink="/legal" fragment="privacy">Privacy (POPIA)</a>
        <span aria-hidden="true">·</span>
        <a routerLink="/legal" fragment="ownership">Legal Notice</a>
      </nav>
    </footer>
  `,
  styles: `
    :host {
      display: block;
    }
    footer {
      display: grid;
      gap: 8px;
      padding: 18px 16px calc(18px + env(safe-area-inset-bottom));
      color: var(--ion-color-medium);
      font-size: 0.76rem;
      line-height: 1.5;
      text-align: center;
    }
    p {
      max-width: 72ch;
      margin: 0 auto;
    }
    nav {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 6px;
    }
    a {
      color: var(--fm-accent);
      font-weight: 700;
      text-decoration: none;
    }
    a:hover,
    a:focus-visible {
      text-decoration: underline;
    }
  `,
})
export class LegalFooterComponent {
  readonly legal = LEGAL;
}
