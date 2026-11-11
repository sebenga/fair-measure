import { Location, NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, DestroyRef, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { IonContent, IonIcon } from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import { arrowBackOutline } from 'ionicons/icons';

import { LEGAL, LEGAL_SECTIONS, type LegalPoint, legalPieces } from '../../core/legal';
import { LegalFooterComponent } from '../../shared/legal-footer.component';

/** Legal notices, disclaimers, privacy and terms for Fair Measure. Open to everyone. */
@Component({
  selector: 'fm-legal',
  standalone: true,
  imports: [IonContent, IonIcon, LegalFooterComponent, NgTemplateOutlet],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'ion-page' },
  template: `
    <ion-content [fullscreen]="true">
      <div class="legal">
        <header class="nav">
          <button type="button" class="brand" (click)="home()">
            <span class="logo" aria-hidden="true"><span></span></span>
            {{ legal.product }}
          </button>
          <button type="button" class="back" (click)="back()">
            <ion-icon name="arrow-back-outline" aria-hidden="true" />
            Back
          </button>
        </header>

        <section class="head">
          <p class="eyebrow">Legal</p>
          <h1>{{ legal.product }} — Legal Notices &amp; Disclaimers</h1>
          <dl>
            <div>
              <dt>Owner</dt>
              <dd>{{ legal.owner }} ("we", "us", "our")</dd>
            </div>
            <div>
              <dt>Website</dt>
              <dd>
                <a [href]="legal.website" target="_blank" rel="noopener">{{ legal.website }}</a>
              </dd>
            </div>
            <div>
              <dt>Last updated</dt>
              <dd>{{ legal.lastUpdated }}</dd>
            </div>
          </dl>
        </section>

        <nav class="contents" aria-label="Sections">
          @for (section of sections; track section.id; let index = $index) {
            <button type="button" (click)="jump(section.id)">
              <b>{{ index + 1 }}</b>
              {{ section.title }}
            </button>
          }
        </nav>

        @for (section of sections; track section.id; let index = $index) {
          <article class="section" [id]="section.id">
            <h2>
              <span class="number">{{ index + 1 }}</span>
              {{ section.title }}
            </h2>
            @for (block of section.body; track $index) {
              @if (isList(block)) {
                <ul>
                  @for (point of block; track $index) {
                    <li>
                      @if (point.label) {
                        <strong>{{ point.label }}:&nbsp;</strong>
                      }
                      <ng-container *ngTemplateOutlet="line; context: { $implicit: point.text }" />
                    </li>
                  }
                </ul>
              } @else {
                <p><ng-container *ngTemplateOutlet="line; context: { $implicit: block }" /></p>
              }
            }
          </article>
        }

        <!-- Kept on one line: line breaks here would show as spaces around links and placeholders. -->
        <ng-template #line let-text>@for (piece of pieces(text); track $index) {@switch (piece.kind) {@case ('blank') {<mark title="To be filled in">{{ piece.value }}</mark>}@case ('link') {<a [href]="piece.value" target="_blank" rel="noopener">{{ piece.value }}</a>}@default {{{ piece.value }}}}}</ng-template>

        <fm-legal-footer />
      </div>
    </ion-content>
  `,
  styles: `
    ion-content {
      --background: var(--ion-background-color, #f6f7f8);
    }
    .legal {
      display: grid;
      gap: 14px;
      width: min(880px, 100%);
      margin: 0 auto;
      padding: 16px 16px 0;
      box-sizing: border-box;
      color: var(--fm-ink);
    }
    .nav {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      padding: 8px 10px 8px 12px;
      border-radius: 999px;
      background: var(--fm-surface);
      box-shadow: 0 8px 24px rgb(15 23 42 / 6%);
    }
    .brand,
    .back {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 0;
      background: none;
      color: var(--fm-ink);
      font: inherit;
      cursor: pointer;
    }
    .brand {
      font-weight: 750;
    }
    .back {
      min-height: 36px;
      padding: 0 12px;
      border: 1px solid var(--fm-line);
      border-radius: 999px;
      font-size: 0.86rem;
      font-weight: 700;
    }
    .logo {
      display: grid;
      place-items: center;
      width: 26px;
      height: 26px;
      border-radius: 8px;
      background: var(--fm-gradient);
    }
    .logo span {
      width: 9px;
      height: 9px;
      border: 2px solid #fff;
      border-radius: 50%;
    }
    .head {
      padding: 22px 20px;
      border-radius: 24px;
      background: var(--fm-gradient);
      color: #fff;
      box-shadow: 0 12px 28px rgb(14 116 144 / 22%);
      animation: rise 0.45s var(--fm-ease-out, ease-out) backwards;
    }
    .eyebrow {
      margin: 0 0 6px;
      color: rgb(255 255 255 / 80%);
      font-size: 0.72rem;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    h1 {
      margin: 0 0 14px;
      font-size: clamp(1.4rem, 4vw, 2rem);
      font-weight: 800;
      line-height: 1.12;
      letter-spacing: -0.02em;
    }
    .head dl {
      display: grid;
      gap: 6px;
      margin: 0;
      font-size: 0.86rem;
    }
    .head dl div {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .head dt {
      font-weight: 800;
    }
    .head dt::after {
      content: ':';
    }
    .head dd {
      margin: 0;
      overflow-wrap: anywhere;
    }
    .head a {
      color: #fff;
    }
    .contents {
      display: grid;
      gap: 4px;
      padding: 10px;
      border-radius: 18px;
      background: var(--fm-surface);
      box-shadow: var(--fm-shadow);
    }
    .contents button {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px;
      border: 0;
      border-radius: 10px;
      background: none;
      color: var(--fm-ink);
      font: inherit;
      font-size: 0.88rem;
      font-weight: 600;
      text-align: left;
      cursor: pointer;
    }
    .contents button:hover,
    .contents button:focus-visible {
      background: var(--fm-chip-selected);
    }
    .contents b,
    .number {
      flex: 0 0 auto;
      display: inline-grid;
      place-items: center;
      width: 24px;
      height: 24px;
      border-radius: 50%;
      background: var(--fm-gradient);
      color: #fff;
      font-size: 0.74rem;
      font-weight: 800;
    }
    .section {
      padding: 18px 18px 8px;
      border-radius: 18px;
      background: var(--fm-surface);
      box-shadow: var(--fm-shadow);
      scroll-margin-top: 12px;
    }
    .section h2 {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      margin: 0 0 10px;
      font-size: 1.05rem;
      font-weight: 800;
      line-height: 1.3;
    }
    .section p,
    .section li {
      color: var(--fm-ink);
      font-size: 0.92rem;
      line-height: 1.6;
      overflow-wrap: anywhere;
    }
    .section p {
      margin: 0 0 12px;
    }
    .section ul {
      display: grid;
      gap: 6px;
      margin: 0 0 12px;
      padding-left: 18px;
    }
    .section a {
      color: var(--fm-accent);
      font-weight: 700;
    }
    mark {
      padding: 0 4px;
      border-radius: 4px;
      background: #fef3c7;
      color: #92400e;
      font-weight: 700;
    }
    @keyframes rise {
      from {
        opacity: 0;
        transform: translateY(10px);
      }
    }
    @media (min-width: 760px) {
      .legal {
        padding: 20px 24px 0;
      }
      .head {
        padding: 30px 32px;
      }
      .contents {
        grid-template-columns: 1fr 1fr;
      }
      .section {
        padding: 24px 28px 12px;
      }
    }
  `,
})
export class LegalPage {
  private readonly router = inject(Router);
  private readonly location = inject(Location);
  private readonly route = inject(ActivatedRoute);

  readonly legal = LEGAL;
  readonly sections = LEGAL_SECTIONS;

  constructor() {
    addIcons({ arrowBackOutline });
    this.route.fragment.pipe(takeUntilDestroyed(inject(DestroyRef))).subscribe((fragment) => {
      if (fragment) setTimeout(() => this.jump(fragment), 350);
    });
  }

  isList(block: string | LegalPoint[]): block is LegalPoint[] {
    return Array.isArray(block);
  }

  pieces(text: string) {
    return legalPieces(text);
  }

  jump(id: string): void {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  home(): void {
    void this.router.navigateByUrl('/');
  }

  back(): void {
    if (window.history.length > 1) this.location.back();
    else this.home();
  }
}
