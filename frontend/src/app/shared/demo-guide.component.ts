import { NgTemplateOutlet } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  HostListener,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';

import { DemoGuideService } from '../core/demo-guide.service';

const TYPE_EVERY_MS = 16;

/** Coach Kaya: the animated guide that walks a demo competition feature by feature. */
@Component({
  selector: 'fm-demo-guide',
  standalone: true,
  imports: [NgTemplateOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './demo-guide.component.scss',
  template: `
    @if (guide.driving()) {
      <div class="shield" aria-hidden="true"></div>
      <div class="drive-bar" role="status">
        <span class="rec" aria-hidden="true"></span>
        <span>
          Coach Kaya is showing you
          @if (guide.progress(); as progress) {
            · {{ progress.done }} of {{ progress.total }}
          }
        </span>
        @if (guide.voice.supported) {
          <button
            type="button"
            class="voice"
            [attr.aria-label]="guide.voice.on() ? 'Turn the voice off' : 'Turn the voice on'"
            [attr.aria-pressed]="guide.voice.on()"
            (click)="guide.voice.toggle()"
          >
            <ng-container *ngTemplateOutlet="speaker" />
          </button>
        }
        <button type="button" (click)="guide.halt()">Stop</button>
      </div>
    }
    @if (guide.cursor(); as cursor) {
      <div
        class="cursor"
        [class.pressing]="cursor.pressing"
        [class.flip]="cursor.x > viewportWidth() - 260"
        [style.transform]="'translate(' + cursor.x + 'px, ' + cursor.y + 'px)'"
        aria-hidden="true"
      >
        <span class="ripple"></span>
        <svg class="hand" viewBox="0 0 32 32" width="34" height="34">
          <path
            d="M11 3.5a2.5 2.5 0 0 1 5 0V13l1-.2a2.4 2.4 0 0 1 2.8 1.6l.2.6.6-.1a2.4 2.4 0 0 1 2.8 1.7l.1.4h.3a2.4 2.4 0 0 1 2.7 2.4V23c0 3.9-3.1 7-7 7h-2.3a7 7 0 0 1-5.6-2.8L6.2 21a2.4 2.4 0 0 1 3.4-3.3l1.4 1.2Z"
          />
        </svg>
        <span class="say">{{ cursor.say }}</span>
      </div>
    }
    @if (guide.open() && !guide.driving() && guide.step(); as step) {
      <aside class="guide" [class.min]="guide.minimized()" role="dialog" aria-label="Guided tour">
        <button
          type="button"
          class="coach"
          [attr.data-pose]="step.pose"
          [class.talking]="typing() || guide.voice.speaking()"
          [attr.aria-label]="guide.minimized() ? 'Open the guided tour' : 'Coach Kaya'"
          (click)="guide.minimized() ? guide.toggleMinimized() : finishTyping()"
        >
          <span class="shadow" aria-hidden="true"></span>
          <span class="figure" aria-hidden="true">
            <span class="arm left"></span>
            <span class="arm right"><span class="hand"></span></span>
            <span class="torso"><span class="badge">FM</span><span class="whistle"></span></span>
            <span class="head">
              <span class="cap"><span class="brim"></span></span>
              <span class="eye l"></span>
              <span class="eye r"></span>
              <span class="cheek l"></span>
              <span class="cheek r"></span>
              <span class="mouth"></span>
            </span>
          </span>
        </button>

        @if (!guide.minimized()) {
          <section class="bubble" aria-live="polite">
            <header>
              <span class="count">{{ guide.index() + 1 }} / {{ guide.steps().length }}</span>
              <span class="who">{{ guide.tourLabel() }}</span>
              @if (guide.voice.supported) {
                <button
                  type="button"
                  class="icon voice"
                  [class.off]="!guide.voice.on()"
                  [attr.aria-label]="guide.voice.on() ? 'Turn the voice off' : 'Turn the voice on'"
                  [attr.aria-pressed]="guide.voice.on()"
                  (click)="toggleVoice(step.body)"
                >
                  <ng-container *ngTemplateOutlet="speaker" />
                </button>
              }
              <button type="button" class="icon" aria-label="Minimise the tour" (click)="guide.toggleMinimized()">–</button>
              <button type="button" class="icon" aria-label="Close the tour" (click)="guide.close()">×</button>
            </header>
            <h3>{{ step.title }}</h3>
            <p (click)="finishTyping()">{{ typed() }}<span class="caret" [class.on]="typing()"></span></p>
            <div class="dots" role="tablist" aria-label="Tour steps">
              @for (item of guide.steps(); track item.key; let i = $index) {
                <button
                  type="button"
                  class="dot"
                  role="tab"
                  [class.on]="i === guide.index()"
                  [class.done]="i < guide.index()"
                  [attr.aria-label]="'Step ' + (i + 1) + ': ' + item.title"
                  [attr.aria-selected]="i === guide.index()"
                  (click)="guide.goTo(i)"
                ></button>
              }
            </div>
            <footer>
              <button type="button" class="ghost" [disabled]="guide.isFirst()" (click)="guide.back()">Back</button>
              @if (step.actions?.length) {
                <button type="button" class="ghost show-me" (click)="guide.demonstrate()">Show me again</button>
              }
              <button type="button" class="go" (click)="guide.next()">
                {{ guide.isLast() ? 'Finish' : 'Next' }}
              </button>
            </footer>
          </section>
        }
      </aside>
    }

    <ng-template #speaker>
      <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
        <path d="M4 9v6h4l5 4V5L8 9H4Z" fill="currentColor" />
        @if (guide.voice.on()) {
          <path d="M16 8.5a5 5 0 0 1 0 7M18.5 6a8.5 8.5 0 0 1 0 12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        } @else {
          <path d="m16 9 5 6m0-6-5 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        }
      </svg>
    </ng-template>
  `,
})
export class DemoGuideComponent {
  readonly guide = inject(DemoGuideService);

  readonly typed = signal('');
  readonly viewportWidth = signal(window.innerWidth);
  readonly typing = signal(false);
  private full = '';
  private timer: ReturnType<typeof setInterval> | null = null;
  private readonly calm =
    typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;

  constructor() {
    effect(() => {
      const step = this.guide.step();
      const open = this.guide.open();
      untracked(() => this.type(open && step ? step.body : ''));
    });
    inject(DestroyRef).onDestroy(() => this.stop());
  }

  @HostListener('window:resize')
  onResize(): void {
    this.viewportWidth.set(window.innerWidth);
  }

  /** Turning the voice on reads the current step aloud straight away. */
  toggleVoice(body: string): void {
    this.guide.voice.toggle();
    if (this.guide.voice.on() && !this.guide.driving()) void this.guide.voice.say(body);
  }

  finishTyping(): void {
    this.stop();
    this.typed.set(this.full);
  }

  private type(text: string): void {
    this.stop();
    this.full = text;
    if (!text || this.calm) {
      this.typed.set(text);
      return;
    }
    let shown = 0;
    this.typed.set('');
    this.typing.set(true);
    this.timer = setInterval(() => {
      shown = Math.min(text.length, shown + 2);
      this.typed.set(text.slice(0, shown));
      if (shown >= text.length) this.stop();
    }, TYPE_EVERY_MS);
  }

  private stop(): void {
    if (this.timer !== null) clearInterval(this.timer);
    this.timer = null;
    this.typing.set(false);
  }
}
