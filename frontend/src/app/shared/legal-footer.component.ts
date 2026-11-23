import { ChangeDetectionStrategy, Component, OnInit, computed, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { CompanyLegalService } from '../core/company-legal.service';

/** The short legal footer: copyright, ownership and links to the notices. */
@Component({
  selector: 'fm-legal-footer',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <footer>
      <p>
        {{ copyrightLine() }}
        @if (legalName()) {
          {{ legalName() }}
          @if (registrationNumber()) {
            (Reg. {{ registrationNumber() }})
          }
          @if (vatNumber()) {
            · VAT {{ vatNumber() }}
          }.
        }
        {{ product() }} is owned and operated in South Africa. Not affiliated with any sports federation.
        Results are for information only.
      </p>
      <nav aria-label="Legal">
        <a routerLink="/legal">Terms</a>
        <span aria-hidden="true">·</span>
        <a routerLink="/legal" fragment="privacy">Privacy (POPIA)</a>
        <span aria-hidden="true">·</span>
        <a routerLink="/legal" fragment="ownership">Legal Notice</a>
        <span aria-hidden="true">·</span>
        <a routerLink="/tabs/commercial">Costs and earnings</a>
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
export class LegalFooterComponent implements OnInit {
  private readonly companyLegal = inject(CompanyLegalService);

  readonly copyrightLine = this.companyLegal.copyrightLine;
  readonly product = computed(() => this.companyLegal.company().product || 'Fair Measure');
  readonly legalName = computed(() => this.companyLegal.company().legal_name || '');
  readonly registrationNumber = computed(
    () => this.companyLegal.company().registration_number || '',
  );
  readonly vatNumber = computed(() => this.companyLegal.company().vat_number || '');

  ngOnInit(): void {
    this.companyLegal.ensureLoaded();
  }
}
