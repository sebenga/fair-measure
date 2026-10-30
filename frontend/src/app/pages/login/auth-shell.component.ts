import { ChangeDetectionStrategy, Component, DestroyRef, afterNextRender, inject, input, signal } from '@angular/core';
import { Router } from '@angular/router';
import { IonIcon } from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import { arrowBackOutline, briefcaseOutline, chatbubblesOutline, footballOutline } from 'ionicons/icons';

const MEDIA = 'assets/landing';
const FADE_EVERY_MS = 5000;

/** Sign-in and registration frame, in the landing page's style: match-day photos beside the form. */
@Component({
  selector: 'fm-auth-shell',
  standalone: true,
  imports: [IonIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './auth-shell.component.scss',
  template: `
    <div class="auth-page">
      <header class="nav">
        <button type="button" class="brand" (click)="home()">
          <span class="logo" aria-hidden="true"><span></span></span>
          Fair Measure
        </button>
        <button type="button" class="back" (click)="home()">
          <ion-icon name="arrow-back-outline" aria-hidden="true" />
          Back to home
        </button>
      </header>

      <div class="auth-card">
        <aside class="story">
          @for (photo of photos(); track photo; let i = $index) {
            <img [src]="photo" alt="" [class.on]="i === shown()" [attr.loading]="i === 0 ? 'eager' : 'lazy'" />
          }
          <div class="story-copy">
            <p class="eyebrow">{{ eyebrow() }}</p>
            <h1>{{ title() }}</h1>
            <p class="lede">{{ subtitle() }}</p>
            <ul class="perks">
              <li>
                <span class="icon"><ion-icon name="football-outline" aria-hidden="true" /></span>
                <span><strong>Sport</strong><small>Live scores, tables and team sheets</small></span>
              </li>
              <li>
                <span class="icon"><ion-icon name="chatbubbles-outline" aria-hidden="true" /></span>
                <span><strong>Social</strong><small>A feed for every result and rating</small></span>
              </li>
              <li>
                <span class="icon"><ion-icon name="briefcase-outline" aria-hidden="true" /></span>
                <span><strong>Work</strong><small>KPI leagues, reports and an audit trail</small></span>
              </li>
            </ul>
          </div>
        </aside>
        <section class="panel">
          <ng-content />
        </section>
      </div>
    </div>
  `,
})
export class AuthShellComponent {
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  readonly eyebrow = input('Sport · Social · Work');
  readonly title = input('Compete. Share. Run it properly.');
  readonly subtitle = input(
    'One workspace for match days, the conversation around them, and the people who administer both.',
  );
  /** Photos that fade behind the copy; the first loads straight away. */
  readonly photos = input<string[]>([
    `${MEDIA}/moment-fans.jpg`,
    `${MEDIA}/hero.jpg`,
    `${MEDIA}/moment-office.jpg`,
  ]);
  readonly shown = signal(0);

  constructor() {
    addIcons({ arrowBackOutline, briefcaseOutline, chatbubblesOutline, footballOutline });
    afterNextRender(() => {
      if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return;
      const timer = setInterval(() => {
        const count = this.photos().length;
        if (!document.hidden && count > 1) this.shown.update((index) => (index + 1) % count);
      }, FADE_EVERY_MS);
      this.destroyRef.onDestroy(() => clearInterval(timer));
    });
  }

  home(): void {
    void this.router.navigateByUrl('/');
  }
}
