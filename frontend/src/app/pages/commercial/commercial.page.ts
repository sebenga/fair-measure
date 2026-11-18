import { ChangeDetectionStrategy, Component } from '@angular/core';
import {
  IonBackButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonTitle,
  IonToolbar,
} from '@ionic/angular/standalone';

import {
  COMMERCIAL,
  COMMERCIAL_EXAMPLE,
  COMMERCIAL_FREE_TIER,
  COMMERCIAL_KEY_POINTS,
  COMMERCIAL_MOVING,
  COMMERCIAL_PAYOUTS,
  COMMERCIAL_PLANS,
  COMMERCIAL_SPLITS,
  randAmount,
} from '../../core/commercial';
import { LegalFooterComponent } from '../../shared/legal-footer.component';
import { PageHeroComponent } from '../../shared/page-hero.component';

/** What running a competition costs and earns: the proposed commercial terms for organisers. */
@Component({
  selector: 'fm-commercial',
  standalone: true,
  imports: [
    IonHeader,
    IonToolbar,
    IonTitle,
    IonButtons,
    IonBackButton,
    IonContent,
    PageHeroComponent,
    LegalFooterComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start">
          <ion-back-button defaultHref="/tabs/competitions" />
        </ion-buttons>
        <ion-title>Costs and earnings</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      <div class="page">
        <fm-page-hero
          eyebrow="For organisers"
          title="What running a competition costs and earns"
          subtitle="Free in year one, with a commission on sponsorships. This page sets out what is proposed after that, so there are no surprises."
          image="assets/landing/moment-touchline.jpg"
        />

        <div class="body">
          <p class="notice" role="note">
            <strong>Proposed terms.</strong>
            The rand amounts on this page are starting points and may change before any paid plan
            begins. Last updated {{ commercial.lastUpdated }}.
          </p>

          <section class="card" aria-labelledby="know">
            <h2 id="know">Before you create a competition</h2>
            <ol class="points">
              @for (point of keyPoints; track point.title; let index = $index) {
                <li>
                  <span class="number" aria-hidden="true">{{ index + 1 }}</span>
                  <div>
                    <strong>{{ point.title }}</strong>
                    <p>{{ point.text }}</p>
                  </div>
                </li>
              }
            </ol>
          </section>

          <section class="card" aria-labelledby="visibility">
            <h2 id="visibility">Visibility upgrades (test)</h2>
            <p class="lede">
              Running a competition stays free in year one. These Paystack test charges unlock
              private competitions and landing-page placement when payment keys are configured.
            </p>
            <ul class="plans">
              <li>
                <strong>Private competition</strong>
                <span>{{ privatePrice }} · Paystack</span>
              </li>
              <li>
                <strong>Landing page placement</strong>
                <span>{{ landingPrice }} · Paystack</span>
              </li>
            </ul>
          </section>

          <section class="card" aria-labelledby="splits">
            <h2 id="splits">How income is shared</h2>
            <p class="lede">
              The sponsorship split applies now. The other splits apply once those ways of earning
              are switched on.
            </p>
            <table>
              <thead>
                <tr>
                  <th scope="col">Income</th>
                  <th scope="col">You keep</th>
                  <th scope="col">Fair Measure keeps</th>
                </tr>
              </thead>
              <tbody>
                @for (split of splits; track split.source) {
                  <tr>
                    <th scope="row">{{ split.source }}</th>
                    <td>{{ split.organiser }}</td>
                    <td>{{ split.fairMeasure }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </section>

          <section class="card" aria-labelledby="plans">
            <h2 id="plans">Plans after year one</h2>
            <p class="proposed">Proposed prices</p>
            <p class="lede">{{ freeTier.detail }}</p>
            <ul class="plans">
              <li class="free">
                <strong>{{ freeTier.name }}</strong>
                <span>{{ freeTier.price }}</span>
              </li>
              @for (plan of plans; track plan.name) {
                <li>
                  <strong>{{ plan.name }}</strong>
                  <span>{{ plan.price }}</span>
                </li>
              }
            </ul>
          </section>

          <section class="card" aria-labelledby="sponsor-paid">
            <h2 id="sponsor-paid">When sponsors pay for your plan</h2>
            <p class="lede">
              A plan comes out of your sponsor earnings first, so you only pay from your own pocket
              if sponsorship does not cover it.
            </p>
            <div class="example">
              <p class="example-title">Example: a school with R11,500 of sponsors</p>
              <dl>
                @for (line of example; track line.label) {
                  <div [class.total]="line.total">
                    <dt>{{ line.label }}</dt>
                    <dd>{{ line.amount }}</dd>
                  </div>
                }
              </dl>
            </div>
          </section>

          <div class="pair">
            <section class="card" aria-labelledby="moving">
              <h2 id="moving">Moving to paid plans</h2>
              <dl class="facts">
                @for (point of moving; track point.title) {
                  <div>
                    <dt>{{ point.title }}</dt>
                    <dd>{{ point.text }}</dd>
                  </div>
                }
              </dl>
            </section>

            <section class="card" aria-labelledby="payouts">
              <h2 id="payouts">Payouts to organisers</h2>
              <dl class="facts">
                @for (point of payouts; track point.title) {
                  <div>
                    <dt>{{ point.title }}</dt>
                    <dd>{{ point.text }}</dd>
                  </div>
                }
              </dl>
            </section>
          </div>
        </div>

        <fm-legal-footer />
      </div>
    </ion-content>
  `,
  styles: `
    ion-content {
      --background: var(--ion-background-color, #f6f7f8);
    }
    .page {
      width: min(880px, 100%);
      margin: 0 auto;
      color: var(--fm-ink);
    }
    .body {
      display: grid;
      gap: 14px;
      padding: 10px 16px 0;
    }
    .notice {
      margin: 0;
      padding: 12px 16px;
      border: 1px solid #fcd34d;
      border-radius: 14px;
      background: #fffbeb;
      color: #78350f;
      font-size: 0.9rem;
      line-height: 1.5;
    }
    .card {
      padding: 18px 18px 16px;
      border-radius: 18px;
      background: var(--fm-surface);
      box-shadow: var(--fm-shadow);
    }
    h2 {
      margin: 0 0 10px;
      font-size: 1.08rem;
      font-weight: 800;
      letter-spacing: -0.01em;
    }
    .lede {
      margin: 0 0 14px;
      max-width: 62ch;
      color: var(--ion-color-medium-shade);
      font-size: 0.92rem;
      line-height: 1.55;
    }
    .points {
      display: grid;
      gap: 14px;
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .points li {
      display: flex;
      gap: 12px;
    }
    .number {
      flex: 0 0 auto;
      display: grid;
      place-items: center;
      width: 26px;
      height: 26px;
      border-radius: 50%;
      background: var(--fm-gradient);
      color: #fff;
      font-size: 0.78rem;
      font-weight: 800;
    }
    .points strong {
      font-size: 0.96rem;
    }
    .points p {
      margin: 2px 0 0;
      color: var(--ion-color-medium-shade);
      font-size: 0.9rem;
      line-height: 1.5;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9rem;
    }
    thead th {
      padding: 0 8px 8px 0;
      color: var(--ion-color-medium-shade);
      font-size: 0.72rem;
      font-weight: 800;
      letter-spacing: 0.06em;
      text-align: left;
      text-transform: uppercase;
    }
    tbody th,
    tbody td {
      padding: 10px 8px 10px 0;
      border-top: 1px solid var(--fm-line);
      text-align: left;
      vertical-align: top;
    }
    tbody th {
      font-weight: 600;
    }
    tbody td {
      font-weight: 700;
      white-space: nowrap;
    }
    .plans {
      display: grid;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .plans li {
      display: flex;
      flex-wrap: wrap;
      align-items: baseline;
      justify-content: space-between;
      gap: 4px 12px;
      padding: 12px 14px;
      border: 1px solid var(--fm-line);
      border-radius: 12px;
      font-size: 0.94rem;
    }
    .plans li.free {
      border-color: transparent;
      background: var(--fm-chip-selected);
    }
    .plans span {
      font-weight: 700;
    }
    .proposed {
      margin: -4px 0 8px;
      color: #92400e;
      font-size: 0.72rem;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .example {
      padding: 14px;
      border-radius: 14px;
      background: var(--fm-chip-selected);
    }
    .example-title {
      margin: 0 0 8px;
      font-size: 0.9rem;
      font-weight: 700;
    }
    .example dl,
    .facts {
      display: grid;
      margin: 0;
    }
    .example dl div {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 6px 0;
      font-size: 0.92rem;
    }
    .example dd {
      margin: 0;
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }
    .example .total {
      margin-top: 4px;
      padding-top: 10px;
      border-top: 1px solid color-mix(in srgb, var(--fm-ink) 20%, transparent);
      font-weight: 800;
    }
    .facts {
      gap: 12px;
    }
    .facts dt {
      color: var(--ion-color-medium-shade);
      font-size: 0.72rem;
      font-weight: 800;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .facts dd {
      margin: 2px 0 0;
      font-size: 0.94rem;
      line-height: 1.5;
    }
    .pair {
      display: grid;
      gap: 14px;
    }
    @media (min-width: 760px) {
      .body {
        padding: 12px 24px 0;
      }
      .card {
        padding: 24px 26px 22px;
      }
      .pair {
        grid-template-columns: 1fr 1fr;
      }
      .plans {
        grid-template-columns: 1fr 1fr;
      }
    }
    @media (prefers-color-scheme: dark) {
      .notice {
        border-color: #92400e;
        background: #2a1c05;
        color: #fde68a;
      }
      .proposed {
        color: #fbbf24;
      }
    }
  `,
})
export class CommercialPage {
  readonly commercial = COMMERCIAL;
  readonly keyPoints = COMMERCIAL_KEY_POINTS;
  readonly freeTier = COMMERCIAL_FREE_TIER;
  readonly plans = COMMERCIAL_PLANS;
  readonly splits = COMMERCIAL_SPLITS;
  readonly example = COMMERCIAL_EXAMPLE;
  readonly moving = COMMERCIAL_MOVING;
  readonly payouts = COMMERCIAL_PAYOUTS;
  readonly privatePrice = randAmount(COMMERCIAL.payments.privateCents);
  readonly landingPrice = randAmount(COMMERCIAL.payments.landingCents);
}
