import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  OnDestroy,
  OnInit,
  computed,
  inject,
  input,
  output,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { interval } from 'rxjs';
import { take } from 'rxjs/operators';

import {
  HOUSE_COMPETITION_AD,
  adDurationSeconds,
  formatAdCountdown,
  type AdCreative,
} from '../core/ad-break';

const RING = 94.2;
const AD_FALLBACK = 30;

function prefersReducedMotion(): boolean {
  if (typeof window.matchMedia !== 'function') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Full-screen pre-roll. The parent decides when it is on screen.
 * There is no skip control: the break ends only when the clock runs out.
 * Image and video creatives replace the house backdrop; the countdown stays.
 */
@Component({
  selector: 'fm-ad-break',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section
      class="shell"
      [class.has-media]="!!media()"
      role="dialog"
      aria-modal="true"
      aria-labelledby="ad-title"
      data-ad-break
      tabindex="-1"
    >
      <div class="bg">
        @if (media(); as item) {
          @if (item.type === 'video') {
            <video
              [src]="item.src"
              [attr.poster]="item.poster || null"
              autoplay
              muted
              playsinline
              loop
              [muted]="true"
              aria-hidden="true"
            ></video>
          } @else {
            <img [src]="item.src" [alt]="item.alt" />
          }
        } @else {
          <span class="orb one" aria-hidden="true"></span>
          <span class="orb two" aria-hidden="true"></span>
        }
      </div>

      <header class="top">
        <span class="pill">{{ creative().label }}</span>
        <span class="clock" aria-hidden="true">
          <svg viewBox="0 0 36 36" focusable="false">
            <circle class="track" cx="18" cy="18" r="15" />
            <circle class="value" cx="18" cy="18" r="15" [style.strokeDashoffset]="ringOffset()" />
          </svg>
          <strong>{{ clock() }}</strong>
        </span>
      </header>

      <div class="copy">
        @if (!media()) {
          <div class="brand">
            <span class="mark" aria-hidden="true"><span></span></span>
            <span class="word">{{ creative().sponsor }}</span>
          </div>
        } @else {
          <p class="sponsor">{{ creative().sponsor }}</p>
        }
        <h1 id="ad-title">{{ creative().title }}</h1>
        @if (creative().message) {
          <p class="message">{{ creative().message }}</p>
        }
        @if (!media() && creative().highlights?.length) {
          <ul class="highlights">
            @for (item of creative().highlights; track item) {
              <li>{{ item }}</li>
            }
          </ul>
        }
      </div>

      <footer class="dock">
        <div class="meter" aria-hidden="true"><span [style.width.%]="percentLeft()"></span></div>
        <p class="status">Competition opens in <strong>{{ clock() }}</strong></p>
        @if (creative().href) {
          <a [href]="creative().href" target="_blank" rel="noopener noreferrer">{{
            creative().ctaLabel || 'Learn more'
          }}</a>
        }
      </footer>

      <p class="sr-only" aria-live="polite">{{ announcement() }}</p>
    </section>
  `,
  styles: [
    `
      :host {
        position: fixed;
        inset: 0;
        z-index: 200000;
        display: block;
        color: #f8fafc;
        background: #061018;
        color-scheme: dark;
        font-family: var(--ion-font-family, system-ui, sans-serif);
      }

      .shell {
        position: relative;
        display: flex;
        flex-direction: column;
        height: 100%;
        padding: max(16px, env(safe-area-inset-top)) 22px max(18px, env(safe-area-inset-bottom));
        overflow: hidden;
        outline: none;
      }

      .bg {
        position: absolute;
        inset: 0;
        pointer-events: none;
        background:
          radial-gradient(circle at 12% 0%, rgb(14 165 233 / 32%), transparent 34%),
          radial-gradient(circle at 100% 88%, rgb(15 118 110 / 42%), transparent 38%),
          linear-gradient(165deg, #07141c, #0c1c24 52%, #071018);
      }

      .bg img,
      .bg video {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        object-fit: cover;
      }

      .shell.has-media .bg::after {
        content: '';
        position: absolute;
        inset: 0;
        background: linear-gradient(180deg, rgb(4 10 16 / 20%), rgb(4 10 16 / 88%) 74%);
      }

      .orb {
        position: absolute;
        border-radius: 50%;
        animation: drift 9s ease-in-out infinite;
      }

      .orb.one {
        width: 240px;
        height: 240px;
        top: -50px;
        left: -40px;
        background: radial-gradient(circle, rgb(14 165 233 / 55%), transparent 68%);
      }

      .orb.two {
        width: 280px;
        height: 280px;
        right: -70px;
        bottom: 8%;
        background: radial-gradient(circle, rgb(15 118 110 / 60%), transparent 68%);
        animation-delay: -4s;
      }

      .top,
      .copy,
      .dock {
        position: relative;
        z-index: 1;
        width: min(480px, 100%);
        margin-inline: auto;
      }

      .top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
      }

      .pill {
        padding: 6px 10px;
        border-radius: 999px;
        background: rgb(255 255 255 / 12%);
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.12em;
        text-transform: uppercase;
      }

      .clock {
        position: relative;
        display: grid;
        width: 68px;
        height: 68px;
        place-items: center;
        flex: 0 0 auto;
      }

      .clock svg {
        position: absolute;
        inset: 0;
      }

      .clock circle {
        fill: none;
        stroke-width: 2.4;
      }

      .clock .track {
        stroke: rgb(255 255 255 / 18%);
      }

      .clock .value {
        stroke: #5eead4;
        stroke-linecap: round;
        stroke-dasharray: 94.2;
        transform: rotate(-90deg);
        transform-origin: 50% 50%;
        transition: stroke-dashoffset 1s linear;
      }

      .clock strong {
        font-size: 0.78rem;
        font-variant-numeric: tabular-nums;
        letter-spacing: -0.03em;
      }

      .copy {
        flex: 1 1 auto;
        display: flex;
        flex-direction: column;
        justify-content: center;
        min-height: 0;
        overflow: auto;
        padding: 20px 0;
      }

      .shell.has-media .copy {
        justify-content: flex-end;
      }

      .brand {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 18px;
      }

      .mark {
        display: grid;
        width: 54px;
        height: 54px;
        place-items: center;
        border-radius: 16px;
        background: linear-gradient(135deg, #0d6861, #0ea5e9);
        box-shadow: 0 10px 24px rgb(14 116 144 / 28%);
        animation: glow 3.4s ease-in-out infinite;
      }

      .mark span {
        width: 16px;
        height: 16px;
        border: 3px solid #fff;
        border-radius: 50%;
      }

      .word,
      .sponsor {
        margin: 0;
        font-size: 0.95rem;
        font-weight: 800;
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }

      h1 {
        margin: 0;
        max-width: 16ch;
        font-size: clamp(1.85rem, 6vw, 2.7rem);
        font-weight: 750;
        letter-spacing: -0.035em;
        line-height: 1.05;
        text-wrap: balance;
      }

      .message {
        max-width: 38ch;
        margin: 14px 0 0;
        color: rgb(226 232 240 / 88%);
        font-size: 1.02rem;
        line-height: 1.45;
      }

      .highlights {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 20px 0 0;
        padding: 0;
        list-style: none;
      }

      .highlights li {
        padding: 7px 12px;
        border-radius: 999px;
        background: rgb(255 255 255 / 10%);
        font-size: 0.85rem;
        font-weight: 700;
        animation: rise 0.55s ease both;
      }

      .highlights li:nth-child(2) {
        animation-delay: 0.08s;
      }

      .highlights li:nth-child(3) {
        animation-delay: 0.16s;
      }

      .dock {
        display: grid;
        gap: 10px;
      }

      .meter {
        height: 4px;
        overflow: hidden;
        border-radius: 99px;
        background: rgb(255 255 255 / 16%);
      }

      .meter span {
        display: block;
        height: 100%;
        background: linear-gradient(90deg, #0f766e, #5eead4);
        transition: width 1s linear;
      }

      .status {
        margin: 0;
        font-size: 0.98rem;
      }

      .status strong {
        font-variant-numeric: tabular-nums;
      }

      a {
        justify-self: start;
        color: #99f6e4;
        font-weight: 800;
        text-underline-offset: 3px;
      }

      .sr-only {
        position: absolute;
        width: 1px;
        height: 1px;
        overflow: hidden;
        clip: rect(0 0 0 0);
      }

      @media (min-width: 800px) {
        .shell {
          padding-inline: 32px;
        }
      }

      @media (max-height: 560px) {
        .mark {
          width: 40px;
          height: 40px;
        }

        h1 {
          font-size: 1.45rem;
        }

        .copy {
          padding-block: 8px;
        }
      }

      @media (forced-colors: active) {
        .pill,
        .clock,
        a {
          border: 1px solid CanvasText;
        }
      }

      @keyframes drift {
        50% {
          transform: translate3d(14px, -18px, 0) scale(1.05);
        }
      }

      @keyframes glow {
        50% {
          box-shadow: 0 0 0 8px rgb(94 234 212 / 16%);
        }
      }

      @keyframes rise {
        from {
          opacity: 0;
          transform: translateY(8px);
        }
      }

      @media (prefers-reduced-motion: reduce) {
        :host * {
          animation: none !important;
          transition: none !important;
        }
      }

      :host(.is-reduced-motion) * {
        animation: none !important;
        transition: none !important;
      }
    `,
  ],
  host: {
    '[class.is-reduced-motion]': 'reducedMotion',
  },
})
export class AdBreakComponent implements OnInit, OnDestroy {
  private readonly host = inject(ElementRef<HTMLElement>);
  private readonly destroyRef = inject(DestroyRef);

  readonly creative = input<AdCreative>(HOUSE_COMPETITION_AD);
  readonly finished = output<void>();

  readonly reducedMotion = prefersReducedMotion();
  readonly total = signal(AD_FALLBACK);
  readonly remaining = signal(AD_FALLBACK);
  readonly announcement = signal('');

  readonly media = computed(() => this.creative().media ?? null);
  readonly clock = computed(() => formatAdCountdown(this.remaining()));
  readonly percentLeft = computed(() => {
    const total = this.total();
    if (total <= 0) return 100;
    return (this.remaining() / total) * 100;
  });
  readonly ringOffset = computed(() => {
    const total = this.total();
    const fraction = total <= 0 ? 1 : this.remaining() / total;
    return (1 - fraction) * RING;
  });

  private readonly onKeyDown = (event: KeyboardEvent): void => {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    if (event.key !== 'Tab') return;
    const root = this.host.nativeElement as HTMLElement;
    const focusable = Array.from(
      root.querySelectorAll('a[href], button:not([disabled])'),
    ) as HTMLElement[];
    const shell = root.querySelector('.shell') as HTMLElement | null;
    if (focusable.length === 0) {
      event.preventDefault();
      shell?.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;
    const inside = active instanceof Node && root.contains(active);
    if (!inside) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus();
      return;
    }
    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  };

  private previousBodyOverflow = '';
  private previousHtmlOverflow = '';
  private ended = false;

  ngOnInit(): void {
    const creative = this.creative();
    const total = adDurationSeconds(creative);
    this.total.set(total);
    this.remaining.set(total);
    this.announcement.set(
      `Advertisement from ${creative.sponsor}. The competition opens in ${total} seconds and cannot be skipped.`,
    );

    const element = this.host.nativeElement;
    if (element.parentNode !== document.body) document.body.appendChild(element);
    this.previousBodyOverflow = document.body.style.overflow;
    this.previousHtmlOverflow = document.documentElement.style.overflow;
    document.body.style.overflow = 'hidden';
    document.documentElement.style.overflow = 'hidden';
    document.addEventListener('keydown', this.onKeyDown, true);
    queueMicrotask(() => (element.querySelector('.shell') as HTMLElement | null)?.focus());

    interval(1000)
      .pipe(take(total), takeUntilDestroyed(this.destroyRef))
      .subscribe((tick) => {
        const left = total - tick - 1;
        this.remaining.set(left);
        if (left <= 0) this.finish();
      });
  }

  ngOnDestroy(): void {
    document.removeEventListener('keydown', this.onKeyDown, true);
    document.body.style.overflow = this.previousBodyOverflow;
    document.documentElement.style.overflow = this.previousHtmlOverflow;
    this.host.nativeElement.remove();
  }

  private finish(): void {
    if (this.ended) return;
    this.ended = true;
    this.finished.emit();
  }
}
