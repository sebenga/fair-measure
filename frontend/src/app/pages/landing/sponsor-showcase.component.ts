import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  afterNextRender,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';

import type { MarketingPlacement } from '../../core/models';

const ROTATE_MS = 5000;
const TINTS = ['#0f766e', '#ea580c', '#2563eb', '#7c3aed', '#0891b2'];

/** Sponsors and partners, one at a time: photo, name and pitch, cross-fading to the next. */
@Component({
  selector: 'fm-sponsor-showcase',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[class.compact]': 'compact()' },
  template: `
    <div
      class="stage"
      role="region"
      aria-roledescription="carousel"
      aria-label="Sponsors and partners"
      (mouseenter)="hovered.set(true)"
      (mouseleave)="hovered.set(false)"
      (focusin)="hovered.set(true)"
      (focusout)="hovered.set(false)"
    >
      @for (sponsor of sponsors(); track sponsor.id; let i = $index) {
        <article
          class="slide"
          [class.on]="i === index()"
          [attr.aria-hidden]="i !== index()"
          aria-roledescription="slide"
          [attr.aria-label]="(i + 1) + ' of ' + sponsors().length + ': ' + sponsor.name"
          [style.--tint]="tint(i)"
        >
          @if (sponsor.image_url) {
            <img [src]="sponsor.image_url" alt="" [attr.loading]="i === 0 ? 'eager' : 'lazy'" decoding="async" />
          }
          <div class="copy">
            @if (sponsor.logo_url) {
              <img class="logo" [src]="sponsor.logo_url" [alt]="sponsor.name + ' logo'" />
            }
            @if (sponsor.tagline) {
              <span class="tag">{{ sponsor.tagline }}</span>
            }
            <h3>{{ sponsor.name }}</h3>
            @if (sponsor.body) {
              <p>{{ sponsor.body }}</p>
            }
            @if (sponsor.cta_label) {
              <button type="button" [tabindex]="i === index() ? 0 : -1" (click)="open.emit(sponsor)">
                {{ sponsor.cta_label }} →
              </button>
            }
          </div>
        </article>
      }
      @if (rotating() && sponsors().length > 1) {
        <span class="progress" aria-hidden="true">
          @for (tick of [index()]; track tick) {
            <span [class.paused]="hovered()"></span>
          }
        </span>
      }
    </div>
    @if (sponsors().length > 1 && compact()) {
      <div class="dots" role="group" aria-label="Choose a sponsor">
        @for (sponsor of sponsors(); track sponsor.id; let i = $index) {
          <button
            type="button"
            [class.on]="i === index()"
            [attr.aria-label]="'Show ' + sponsor.name"
            [attr.aria-current]="i === index() ? 'true' : null"
            (click)="show(i)"
          ></button>
        }
      </div>
    } @else if (sponsors().length > 1) {
      <div class="picker" role="group" aria-label="Choose a sponsor">
        @for (sponsor of sponsors(); track sponsor.id; let i = $index) {
          <button
            type="button"
            [class.on]="i === index()"
            [attr.aria-current]="i === index() ? 'true' : null"
            (click)="show(i)"
          >
            {{ sponsor.name }}
          </button>
        }
      </div>
    }
  `,
  styles: `
    :host {
      display: block;
      margin-top: 16px;
    }
    .stage {
      position: relative;
      overflow: hidden;
      min-height: 320px;
      border-radius: 22px;
      background: #0b1220;
      box-shadow: 0 12px 30px rgb(15 23 42 / 12%);
    }
    .slide {
      position: absolute;
      inset: 0;
      display: grid;
      align-items: end;
      opacity: 0;
      visibility: hidden;
      background: linear-gradient(135deg, var(--tint), #0b1220);
      transition:
        opacity 0.9s ease,
        visibility 0s linear 0.9s;
    }
    .slide.on {
      opacity: 1;
      visibility: visible;
      transition: opacity 0.9s ease;
    }
    .slide > img {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: cover;
      transform: scale(1.06);
      transition: transform 6s ease-out;
    }
    .slide.on > img {
      transform: scale(1);
    }
    .slide::after {
      content: '';
      position: absolute;
      inset: 0;
      background: linear-gradient(0deg, rgb(4 10 22 / 88%) 0%, rgb(4 10 22 / 35%) 55%, transparent 100%);
    }
    .copy {
      position: relative;
      z-index: 1;
      display: grid;
      gap: 6px;
      max-width: 560px;
      padding: 22px 20px 26px;
      color: #fff;
      transform: translateY(10px);
      transition: transform 0.9s ease;
    }
    .slide.on .copy {
      transform: none;
    }
    .logo {
      width: auto;
      max-width: 140px;
      max-height: 44px;
      object-fit: contain;
    }
    .tag {
      justify-self: start;
      padding: 3px 9px;
      border-radius: 999px;
      background: var(--tint);
      font-size: 0.68rem;
      font-weight: 800;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    h3 {
      margin: 0;
      font-size: clamp(1.4rem, 3.5vw, 2rem);
      letter-spacing: -0.02em;
    }
    p {
      margin: 0;
      color: rgb(255 255 255 / 85%);
      line-height: 1.5;
    }
    .copy button {
      justify-self: start;
      margin-top: 6px;
      padding: 8px 14px;
      border: 0;
      border-radius: 999px;
      background: #fff;
      color: #0f172a;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }
    .progress {
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      z-index: 2;
      height: 3px;
      background: rgb(255 255 255 / 18%);
    }
    .progress span {
      display: block;
      height: 100%;
      background: #fff;
      transform-origin: left;
      animation: fill ${ROTATE_MS}ms linear forwards;
    }
    .progress span.paused {
      animation-play-state: paused;
    }
    @keyframes fill {
      from {
        transform: scaleX(0);
      }
      to {
        transform: scaleX(1);
      }
    }
    .picker {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }
    .picker button {
      padding: 8px 14px;
      border: 1px solid var(--fm-line, #e2e8f0);
      border-radius: 999px;
      background: var(--fm-surface, #fff);
      color: var(--fm-ink, #0f172a);
      font: inherit;
      font-size: 0.86rem;
      font-weight: 700;
      cursor: pointer;
    }
    .picker button.on {
      border-color: #0f766e;
      background: #0f766e;
      color: #fff;
    }
    @media (min-width: 880px) {
      .stage {
        min-height: 420px;
      }
      .copy {
        padding: 32px 36px 40px;
      }
    }
    :host(.compact) {
      margin-top: 0;
    }
    :host(.compact) .stage {
      min-height: 240px;
      border-radius: 18px;
    }
    :host(.compact) .copy {
      gap: 4px;
      padding: 14px 14px 18px;
    }
    :host(.compact) h3 {
      font-size: 1.1rem;
    }
    :host(.compact) p {
      font-size: 0.8rem;
      line-height: 1.4;
    }
    .dots {
      display: flex;
      justify-content: center;
      gap: 6px;
      margin-top: 10px;
    }
    .dots button {
      width: 8px;
      height: 8px;
      padding: 0;
      border: 0;
      border-radius: 50%;
      background: var(--fm-line, #cbd5e1);
      cursor: pointer;
    }
    .dots button.on {
      width: 20px;
      border-radius: 999px;
      background: #0f766e;
    }
    @media (prefers-reduced-motion: reduce) {
      .slide,
      .slide.on,
      .slide > img,
      .copy {
        transition: none;
        transform: none;
      }
    }
  `,
})
export class SponsorShowcaseComponent {
  private readonly destroyRef = inject(DestroyRef);

  readonly sponsors = input.required<MarketingPlacement[]>();
  /** Narrow sidebars: a shorter stage and dots instead of name chips. */
  readonly compact = input(false, { transform: (value: boolean | string) => value !== false });
  readonly open = output<MarketingPlacement>();

  private readonly position = signal(0);
  readonly hovered = signal(false);
  /** Off for visitors who ask for reduced motion; the picker still works. */
  readonly rotating = signal(false);
  readonly index = computed(() => {
    const count = this.sponsors().length;
    return count ? this.position() % count : 0;
  });

  constructor() {
    afterNextRender(() => {
      if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;
      this.rotating.set(true);
      // Count real time, not ticks: browsers slow timers down on busy or background pages.
      let elapsed = 0;
      let previous = performance.now();
      const timer = setInterval(() => {
        const now = performance.now();
        const delta = now - previous;
        previous = now;
        if (this.hovered() || document.hidden || this.sponsors().length < 2) return;
        elapsed += Math.min(delta, ROTATE_MS);
        if (elapsed >= ROTATE_MS) {
          elapsed = 0;
          this.position.update((value) => value + 1);
        }
      }, 250);
      this.restart = () => (elapsed = 0);
      this.destroyRef.onDestroy(() => clearInterval(timer));
    });
  }

  private restart = () => undefined as unknown;

  tint(index: number): string {
    return TINTS[index % TINTS.length];
  }

  show(index: number): void {
    this.position.set(index);
    this.restart();
  }
}
