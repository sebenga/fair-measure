import { NgTemplateOutlet } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  TemplateRef,
  afterNextRender,
  contentChild,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { interval } from 'rxjs';

/** How long a touch, hover or tap on a dot holds the slides still. */
const HOLD_MS = 4000;
const SWIPE_PX = 48;

/**
 * Rotating slides for marketing: one item at a time, swipe or dots to move, and
 * auto-advance that pauses while touched, hovered, off screen or in a hidden tab.
 * Reduced-motion users get the dots only.
 *
 *   <fm-carousel [items]="ads" label="Partners">
 *     <ng-template let-ad> <fm-promo-slot [title]="ad.name" /> </ng-template>
 *   </fm-carousel>
 */
@Component({
  selector: 'fm-carousel',
  standalone: true,
  imports: [NgTemplateOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div
      class="viewport"
      role="region"
      aria-roledescription="carousel"
      [attr.aria-label]="label()"
      (pointerdown)="onPointerDown($event)"
      (pointerup)="onPointerUp($event)"
      (pointercancel)="hold()"
      (mouseenter)="hovering = true"
      (mouseleave)="hovering = false; hold()"
    >
      <div class="track" [style.transform]="'translateX(' + -index() * 100 + '%)'">
        @for (item of items(); track $index; let i = $index) {
          <div
            class="slide"
            role="group"
            aria-roledescription="slide"
            [attr.aria-label]="i + 1 + ' of ' + items().length"
            [attr.aria-hidden]="i !== index() ? 'true' : null"
            [attr.inert]="i !== index() ? '' : null"
          >
            <ng-container *ngTemplateOutlet="slide(); context: { $implicit: item, index: i }" />
          </div>
        }
      </div>
    </div>
    @if (items().length > 1) {
      <div class="dots" role="group" [attr.aria-label]="'Choose ' + label()">
        @for (item of items(); track $index; let i = $index) {
          <button
            type="button"
            [class.on]="index() === i"
            [attr.aria-label]="'Show slide ' + (i + 1)"
            [attr.aria-current]="index() === i ? 'true' : null"
            (click)="go(i)"
          ></button>
        }
      </div>
    }
  `,
  styles: [
    `
      :host {
        display: block;
        min-width: 0;
      }

      .viewport {
        overflow: hidden;
        touch-action: pan-y;
      }

      .track {
        display: flex;
        transition: transform 480ms ease;
      }

      .slide {
        flex: 0 0 100%;
        min-width: 0;
        box-sizing: border-box;
      }

      .dots {
        display: flex;
        justify-content: center;
        gap: 6px;
        padding: 8px 0 2px;
      }

      .dots button {
        width: 7px;
        height: 7px;
        padding: 0;
        border: 0;
        border-radius: 99px;
        background: var(--fm-line, #cbd5e1);
        transition: width 0.25s ease;
        cursor: pointer;
      }

      .dots button.on {
        width: 18px;
        background: var(--fm-accent, #0f766e);
      }

      @media (prefers-reduced-motion: reduce) {
        .track,
        .dots button {
          transition: none;
        }
      }
    `,
  ],
})
export class CarouselComponent<T = unknown> {
  readonly items = input.required<T[]>();
  readonly label = input('Slides');
  /** Which slide to open on, so several carousels of the same ads do not match. */
  readonly start = input(0);
  readonly every = input(4500);

  readonly slide = contentChild.required(TemplateRef);
  readonly index = signal(0);

  hovering = false;
  private touching = false;
  private holdUntil = 0;
  private startX = 0;
  private suppressClickUntil = 0;
  private onScreen = true;
  private shownKey = '';
  private shownAt = Date.now();

  private readonly host = inject(ElementRef<HTMLElement>);
  private readonly destroyRef = inject(DestroyRef);

  constructor() {
    effect(() => {
      const items = this.items();
      const key = `${items.length}:${this.start()}`;
      if (key === this.shownKey) return;
      this.shownKey = key;
      untracked(() => this.show(items.length ? this.start() % items.length : 0));
    });

    interval(500)
      .pipe(takeUntilDestroyed())
      .subscribe(() => this.advance());

    afterNextRender(() => {
      const element = this.host.nativeElement as HTMLElement;
      // A swipe ends in a click on the slide underneath; that click must not open it.
      const swallow = (event: Event) => {
        if (Date.now() < this.suppressClickUntil) {
          event.preventDefault();
          event.stopPropagation();
        }
      };
      element.addEventListener('click', swallow, true);
      let observer: IntersectionObserver | undefined;
      if ('IntersectionObserver' in window) {
        observer = new IntersectionObserver((entries) => {
          this.onScreen = entries.some((entry) => entry.isIntersecting);
        });
        observer.observe(element);
      }
      this.destroyRef.onDestroy(() => {
        element.removeEventListener('click', swallow, true);
        observer?.disconnect();
      });
    });
  }

  go(index: number): void {
    this.holdUntil = Date.now() + HOLD_MS;
    this.show(index);
  }

  hold(): void {
    this.touching = false;
    this.holdUntil = Date.now() + HOLD_MS;
  }

  onPointerDown(event: PointerEvent): void {
    this.startX = event.clientX;
    this.touching = true;
  }

  onPointerUp(event: PointerEvent): void {
    const distance = event.clientX - this.startX;
    const count = this.items().length;
    if (count > 1 && Math.abs(distance) > SWIPE_PX) {
      this.suppressClickUntil = Date.now() + 500;
      const step = distance < 0 ? 1 : -1;
      this.show((this.index() + step + count) % count);
    }
    this.hold();
  }

  private show(index: number): void {
    this.shownAt = Date.now();
    this.index.set(index);
  }

  private advance(): void {
    const count = this.items().length;
    if (count < 2 || this.touching || this.hovering || !this.onScreen) return;
    const now = Date.now();
    if (now < this.holdUntil || now - this.shownAt < this.every() || document.hidden) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    this.show((this.index() + 1) % count);
  }
}
