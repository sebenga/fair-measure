import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { IonIcon } from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import {
  briefcaseOutline,
  chatbubblesOutline,
  footballOutline,
  radioOutline,
} from 'ionicons/icons';

@Component({
  selector: 'fm-auth-shell',
  standalone: true,
  imports: [IonIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './auth-shell.component.scss',
  template: `
    <div class="auth-page">
      <div class="wash" aria-hidden="true">
        <span class="glow glow-a"></span>
        <span class="glow glow-b"></span>
      </div>

      <div class="ticker" aria-hidden="true">
        <div class="ticker-track">
          @for (pass of [0, 1]; track pass) {
            <span><ion-icon name="radio-outline" /> Live Chiefs 2–1 Pirates</span>
            <span>128 people on last night’s feed</span>
            <span>Q3 board pack ready to export</span>
            <span><ion-icon name="football-outline" /> League table updated</span>
            <span>Three rating amendments logged</span>
          }
        </div>
      </div>

      <div class="auth-card">
        <aside class="brand">
          <div class="brand-top">
            <span class="logo" aria-hidden="true"><span></span></span>
            <span class="wordmark">Fair Measure</span>
          </div>
          <div class="brand-copy">
            <p class="eyebrow">{{ eyebrow() }}</p>
            <h1>{{ title() }}</h1>
            <p>{{ subtitle() }}</p>
          </div>
          <ul class="audiences">
            <li>
              <ion-icon name="football-outline" aria-hidden="true" />
              <strong>Sport</strong>
              <span>Live scores, tables and team sheets</span>
            </li>
            <li>
              <ion-icon name="chatbubbles-outline" aria-hidden="true" />
              <strong>Social</strong>
              <span>A feed for every result and rating</span>
            </li>
            <li>
              <ion-icon name="briefcase-outline" aria-hidden="true" />
              <strong>Work</strong>
              <span>Admin, reports and an audit trail</span>
            </li>
          </ul>
        </aside>
        <section class="panel">
          <ng-content />
        </section>
      </div>
    </div>
  `,
})
export class AuthShellComponent {
  readonly eyebrow = input('Sport · Social · Work');
  readonly title = input('Compete. Share. Run it properly.');
  readonly subtitle = input(
    'One workspace for match days, the conversation around them, and the people who administer both.',
  );

  constructor() {
    addIcons({ briefcaseOutline, chatbubblesOutline, footballOutline, radioOutline });
  }
}
