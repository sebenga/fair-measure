import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';
import { IonIcon } from '@ionic/angular/standalone';

@Component({
  selector: 'fm-promo-slot',
  standalone: true,
  imports: [IonIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button type="button" class="slot" [attr.data-kind]="kind()" (click)="open.emit()">
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

      :host-context(.market-strip) {
        margin: 0;
        flex: 0 0 min(260px, 78vw);
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
  readonly open = output<void>();
}
