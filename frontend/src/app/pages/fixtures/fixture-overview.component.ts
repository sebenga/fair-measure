import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { IonIcon } from '@ionic/angular/standalone';

import type { FixtureDetail, ScoringCategory } from '../../core/models';

type Moment = {
  id: string;
  minute: number | null;
  kind: 'score' | 'yellow' | 'red' | 'card';
  label: string;
  player: string;
  home: boolean;
};

/** The fixture's first tab: when and where, who officiates, and the moments that decided it. */
@Component({
  selector: 'fm-fixture-overview',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, IonIcon, NgTemplateOutlet, RouterLink],
  template: `
    @if (finished()) {
      <a class="fm-card report-link" [routerLink]="['/tabs/competitions', competitionId(), 'fixtures', fixture().id, 'report']">
        <ion-icon name="document-text-outline" aria-hidden="true" />
        <span>
          <strong>Post-match report</strong>
          <em>Result, line-ups, goals, cards, substitutions and the officials' notes. Printable.</em>
        </span>
        <ion-icon name="chevron-forward-outline" aria-hidden="true" />
      </a>
    }

    <h3 class="fm-section-title">Key moments</h3>
    @if (moments().length) {
      <div class="fm-card moments">
        <div class="moment heads">
          <span class="home">{{ teamName(0) }}</span>
          <span></span>
          <span>{{ teamName(1) }}</span>
        </div>
        @for (moment of moments(); track moment.id) {
          <div class="moment">
            <span class="home">
              @if (moment.home) {
                <ng-container *ngTemplateOutlet="what; context: { $implicit: moment }" />
              }
            </span>
            <span class="minute">{{ moment.minute !== null ? moment.minute + "'" : '' }}</span>
            <span>
              @if (!moment.home) {
                <ng-container *ngTemplateOutlet="what; context: { $implicit: moment }" />
              }
            </span>
          </div>
        }
      </div>
      <ng-template #what let-moment>
        <span class="what">
          @if (moment.kind === 'score') {
            <ion-icon name="football-outline" aria-hidden="true" />
          } @else {
            <i class="card" [attr.data-kind]="moment.kind" aria-hidden="true"></i>
          }
          <strong>{{ moment.player || moment.label }}</strong>
          @if (moment.player) {
            <em>{{ moment.label }}</em>
          }
        </span>
      </ng-template>
    } @else {
      <div class="fm-empty compact"><p>No goals or cards yet.</p></div>
    }

    <h3 class="fm-section-title">Match info</h3>
    <dl class="fm-card info">
      <dt>Competition</dt>
      <dd>{{ competitionName() }}{{ fixture().label ? ' · ' + fixture().label : '' }}</dd>
      @if (fixture().scheduled_at) {
        <dt>Kickoff</dt>
        <dd>{{ fixture().scheduled_at | date: 'EEEE d MMMM y, HH:mm' }}</dd>
      }
      @if (fixture().location) {
        <dt>Venue</dt>
        <dd>{{ fixture().location }}</dd>
      }
      <dt>Game time</dt>
      <dd>{{ gameTime() }}</dd>
      <dt>Referee</dt>
      <dd>
        @for (referee of fixture().referees; track referee.id; let last = $last) {
          {{ referee.display_name || referee.email }}{{ last ? '' : ', ' }}
        } @empty {
          <span class="muted">Not assigned</span>
        }
      </dd>
      @if (fixture().notes) {
        <dt>Notes</dt>
        <dd class="pre">{{ fixture().notes }}</dd>
      }
    </dl>
  `,
  styles: [
    `
      .report-link {
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 0 16px 16px;
        padding: 14px 16px;
        color: inherit;
        text-decoration: none;
      }
      .report-link > ion-icon:first-child {
        font-size: 1.6rem;
        color: var(--ion-color-primary);
      }
      .report-link span {
        flex: 1 1 auto;
        display: grid;
        gap: 2px;
      }
      .report-link em {
        font-style: normal;
        font-size: 0.78rem;
        color: var(--ion-color-medium);
      }
      .moments {
        display: grid;
        gap: 8px;
        margin: 0 16px 16px;
        padding: 12px 14px;
      }
      .moment {
        display: grid;
        grid-template-columns: minmax(0, 1fr) 44px minmax(0, 1fr);
        align-items: center;
        gap: 6px;
        font-size: 0.88rem;
      }
      .moment.heads {
        padding-bottom: 6px;
        border-bottom: 1px solid var(--ion-color-step-100, #eef0f3);
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: var(--ion-color-primary);
      }
      .moment .home {
        text-align: right;
      }
      .moment .minute {
        text-align: center;
        font-weight: 800;
        color: var(--ion-color-medium);
      }
      .moment .what {
        display: inline-flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 4px 6px;
      }
      .moment .home .what {
        flex-direction: row-reverse;
      }
      .moment em {
        font-style: normal;
        font-size: 0.76rem;
        color: var(--ion-color-medium);
      }
      .card {
        display: inline-block;
        width: 10px;
        height: 14px;
        border-radius: 2px;
        background: var(--ion-color-medium);
      }
      .card[data-kind='yellow'] {
        background: #facc15;
      }
      .card[data-kind='red'] {
        background: #dc2626;
      }
      .info {
        display: grid;
        grid-template-columns: max-content 1fr;
        gap: 8px 14px;
        margin: 0 16px 16px;
        padding: 14px 16px;
        font-size: 0.9rem;
      }
      .info dt {
        font-weight: 700;
        color: var(--ion-color-medium);
      }
      .info dd {
        margin: 0;
      }
      .muted {
        color: var(--ion-color-medium);
      }
      .pre {
        white-space: pre-wrap;
      }
    `,
  ],
})
export class FixtureOverviewComponent {
  readonly fixture = input.required<FixtureDetail>();
  readonly categories = input<ScoringCategory[]>([]);
  readonly competitionId = input.required<string>();
  readonly competitionName = input('');
  readonly gameTime = input('');

  teamName(index: number): string {
    const side = this.fixture().sides[index];
    return side?.participant.short_name || side?.participant.name || '';
  }

  readonly finished = computed(() => ['completed', 'forfeit'].includes(this.fixture().status));

  readonly moments = computed<Moment[]>(() => {
    const fixture = this.fixture();
    const byId = new Map(this.categories().map((category) => [category.id, category]));
    const home = fixture.sides[0]?.id;
    const rows: Moment[] = [];
    for (const event of fixture.events) {
      const category = byId.get(event.scoring_category);
      const code = (category?.code ?? '').toLowerCase();
      let kind: Moment['kind'] | null = null;
      if (code.endsWith('-card')) {
        const colour = code.replace(/-card$/, '');
        kind = colour === 'yellow' || colour === 'red' ? colour : 'card';
      } else if (category?.affects_score && Number(event.points) !== 0) {
        kind = 'score';
      }
      if (!kind) continue;
      rows.push({
        id: event.id,
        minute: event.minute,
        kind,
        label: event.scoring_category_name,
        player: event.player_name,
        home: event.side === home,
      });
    }
    return rows.sort(
      (a, b) => (a.minute ?? Number.MAX_SAFE_INTEGER) - (b.minute ?? Number.MAX_SAFE_INTEGER),
    );
  });
}
