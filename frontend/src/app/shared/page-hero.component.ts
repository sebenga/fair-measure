import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/**
 * The landing page banner for app pages: a match-day photo under the teal
 * overlay, with an eyebrow, a headline and room for buttons (projected).
 */
@Component({
  selector: 'fm-page-hero',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <img [src]="image()" alt="" decoding="async" />
    <div class="copy">
      @if (eyebrow()) {
        <p class="eyebrow">{{ eyebrow() }}</p>
      }
      <h1>{{ title() }}</h1>
      @if (subtitle()) {
        <p class="lede">{{ subtitle() }}</p>
      }
      <div class="actions"><ng-content /></div>
    </div>
  `,
  styles: `
    :host {
      position: relative;
      display: block;
      overflow: hidden;
      margin: 12px 16px 4px;
      border-radius: 24px;
      background: #0b1220;
      color: #fff;
      box-shadow: 0 14px 36px rgb(15 23 42 / 12%);
      animation: fm-rise 0.45s var(--fm-ease-out, ease) backwards;
    }
    img {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    :host::after {
      content: '';
      position: absolute;
      inset: 0;
      background:
        linear-gradient(160deg, rgb(15 118 110 / 80%) 0%, rgb(4 10 22 / 84%) 72%),
        linear-gradient(0deg, rgb(4 10 22 / 40%), transparent);
    }
    .copy {
      position: relative;
      z-index: 1;
      display: grid;
      gap: 8px;
      padding: 26px 20px 22px;
    }
    .eyebrow {
      margin: 0;
      color: #5eead4;
      font-size: 0.72rem;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    h1 {
      margin: 0;
      max-width: 22ch;
      font-size: clamp(1.45rem, 3.6vw, 2.2rem);
      font-weight: 750;
      line-height: 1.08;
      letter-spacing: -0.03em;
    }
    .lede {
      margin: 0;
      max-width: 56ch;
      color: rgb(255 255 255 / 82%);
      line-height: 1.5;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 6px;
    }
    .actions:empty {
      display: none;
    }
    @media (min-width: 880px) {
      :host {
        margin: 16px 24px 6px;
      }
      .copy {
        padding: 40px 36px 34px;
      }
    }
  `,
})
export class PageHeroComponent {
  readonly eyebrow = input('');
  readonly title = input.required<string>();
  readonly subtitle = input('');
  readonly image = input('assets/landing/moment-fans.jpg');
}
