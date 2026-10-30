import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { IonIcon } from '@ionic/angular/standalone';

@Component({
  selector: 'fm-promo-slot',
  standalone: true,
  imports: [IonIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button type="button" class="slot" [class.photo]="!!image()" [attr.data-kind]="kind()" (click)="open.emit()">
      @if (image()) {
        <img class="bg" [src]="image()" alt="" loading="lazy" decoding="async" />
      }
      <span class="eyebrow">{{ eyebrow() }}</span>
      <span class="row">
        @if (logo()) {
          <img class="logo" [src]="logo()" alt="" />
        } @else if (icon()) {
          <ion-icon [name]="icon()" aria-hidden="true" />
        }
        <span class="copy">
          <strong>{{ title() }}</strong>
          <small>{{ body() }}</small>
        </span>
        <ion-icon name="chevron-forward-outline" aria-hidden="true" />
      </span>
      @if (action()) {
        <span class="cta">{{ action() }}</span>
      }
    </button>
  `,
  styles: [
    `
      :host {
        display: block;
        margin: 12px 16px 0;
      }

      :host-context(.sponsored-rail) {
        margin: 0 0 12px;
      }

      :host-context(.sponsored-rail) .slot {
        padding: 12px 10px 10px;
      }

      :host-context(.sponsored-rail) .row {
        flex-wrap: wrap;
      }

      :host-context(.sponsored-rail) ion-icon[name='chevron-forward-outline'] {
        display: none;
      }

      :host-context(.market-slide) {
        margin: 0;
        width: 100%;
      }

      .slot {
        display: grid;
        gap: 8px;
        width: 100%;
        padding: 14px 14px 12px;
        border: 0;
        border-radius: 16px;
        background: var(--ion-card-background, #fff);
        box-shadow: var(--fm-shadow);
        color: inherit;
        font: inherit;
        text-align: left;
        cursor: pointer;
      }

      .slot[data-kind='banner'] {
        color: var(--fm-on-fill);
        background: linear-gradient(135deg, var(--ion-color-primary-shade), #1d4ed8);
      }

      .slot[data-kind='sponsored'] {
        box-shadow:
          var(--fm-shadow),
          inset 3px 0 0 var(--ion-color-warning);
      }

      .slot[data-kind='corporate'] {
        color: var(--fm-on-light);
        background: linear-gradient(160deg, #ccfbf1, #ffffff 58%);
        box-shadow:
          var(--fm-shadow),
          inset 3px 0 0 #0f766e;
      }

      .slot[data-kind='government'] {
        color: var(--fm-on-fill);
        background: linear-gradient(160deg, #1e3a5f, #0f172a);
      }

      .slot[data-kind='competition'] {
        color: var(--fm-on-light);
        box-shadow:
          var(--fm-shadow),
          inset 3px 0 0 #ea580c;
        background: linear-gradient(160deg, #fff7ed, #ffffff 62%);
      }

      .logo {
        width: 36px;
        height: 36px;
        border-radius: 10px;
        object-fit: cover;
        flex: 0 0 auto;
        background: #fff;
      }

      .eyebrow {
        font-size: 0.68rem;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        opacity: 0.75;
      }

      .row {
        display: flex;
        align-items: center;
        gap: 10px;
      }

      .copy {
        flex: 1 1 auto;
        display: grid;
        gap: 2px;
        min-width: 0;
      }

      small {
        opacity: 0.82;
        line-height: 1.4;
      }

      ion-icon {
        font-size: 1.35rem;
        flex: 0 0 auto;
      }

      .cta {
        font-size: 0.8rem;
        font-weight: 700;
      }

      /* Photo cards: the landing page treatment, a picture under a teal-to-dark wash. */
      .slot.photo {
        position: relative;
        isolation: isolate;
        overflow: hidden;
        align-content: end;
        min-height: 190px;
        padding: 16px;
        border-radius: 18px;
        background: #0b1220;
        color: #fff;
        box-shadow: 0 12px 28px rgb(15 23 42 / 14%);
      }

      .slot.photo .bg {
        position: absolute;
        inset: 0;
        z-index: -2;
        width: 100%;
        height: 100%;
        object-fit: cover;
        transition: transform 0.6s ease;
      }

      .slot.photo::after {
        content: '';
        position: absolute;
        inset: 0;
        z-index: -1;
        background: linear-gradient(0deg, rgb(4 10 22 / 90%) 0%, rgb(4 10 22 / 45%) 55%, rgb(15 118 110 / 35%) 100%);
      }

      .slot.photo[data-kind='government']::after {
        background: linear-gradient(0deg, rgb(4 10 22 / 92%) 0%, rgb(15 30 60 / 55%) 55%, rgb(30 58 95 / 40%) 100%);
      }

      .slot.photo[data-kind='competition']::after {
        background: linear-gradient(0deg, rgb(4 10 22 / 90%) 0%, rgb(4 10 22 / 45%) 55%, rgb(234 88 12 / 30%) 100%);
      }

      @media (hover: hover) {
        .slot.photo:hover .bg {
          transform: scale(1.04);
        }
      }

      .slot.photo .eyebrow {
        justify-self: start;
        padding: 3px 9px;
        border-radius: 999px;
        background: rgb(15 118 110 / 92%);
        opacity: 1;
        letter-spacing: 0.08em;
      }

      .slot.photo[data-kind='government'] .eyebrow {
        background: rgb(37 99 235 / 88%);
      }

      .slot.photo[data-kind='competition'] .eyebrow {
        background: rgb(234 88 12 / 92%);
      }

      .slot.photo strong {
        font-size: 1.05rem;
        line-height: 1.25;
      }

      .slot.photo small {
        opacity: 0.86;
      }

      .slot.photo .cta {
        justify-self: start;
        margin-top: 2px;
        padding: 7px 13px;
        border-radius: 999px;
        background: #fff;
        color: #0f172a;
      }
    `,
  ],
})
export class PromoSlotComponent {
  readonly kind = input<'banner' | 'sponsored' | 'suggested' | 'corporate' | 'government' | 'competition'>(
    'suggested',
  );
  readonly eyebrow = input('Suggested');
  readonly title = input.required<string>();
  readonly body = input('');
  readonly action = input('');
  readonly icon = input('');
  readonly logo = input('');
  /** Optional photo; turns the card into a landing-style picture card. */
  readonly image = input('');
  readonly open = output<void>();
}
