import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import {
  IonBackButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonSpinner,
  IonTitle,
  IonToolbar,
} from '@ionic/angular/standalone';

import type { CatalogAttribute, CatalogSport, RatingArea, SportCatalogue } from '../../core/scouting.models';
import { ScoutingService } from '../../core/scouting.service';

const ANCHORS: Array<'2' | '5' | '8' | '10'> = ['2', '5', '8', '10'];
const PER: Record<string, string> = { match: 'per match', '90min': 'per 90 minutes', game: 'per game' };

/** The rating guide: what each sport's attributes, tests and stats mean. */
@Component({
  selector: 'fm-rating-guide',
  standalone: true,
  imports: [IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonIcon, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './scouting.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button [defaultHref]="sportKey() ? '/tabs/scouting/guide' : '/tabs/scouting'" /></ion-buttons>
        <ion-title>{{ sport()?.label ?? 'Rating guide' }}</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (sportKey() && sport(); as s) {
        <p class="lede">
          Rate each attribute from {{ s.scale.min }} to {{ s.scale.max }}. Every sport uses the same five areas, so
          ratings compare fairly across sports. Tap an area to see what 2, 5, 8 and 10 look like.
        </p>

        @if (s.positions.length > 1) {
          <div class="section">
            <p class="sub">Show attributes for</p>
            <div class="chips">
              <button type="button" class="chip" [class.on]="!position()" (click)="position.set('')">All positions</button>
              @for (item of s.positions; track item.key) {
                <button type="button" class="chip" [class.on]="position() === item.key" (click)="position.set(item.key)">{{ item.label }}</button>
              }
            </div>
          </div>
        }

        @for (area of s.areas; track area.key) {
          <details class="fm-card section area" [open]="area.key === 'technical'">
            <summary>
              <span class="grow">
                <strong>{{ area.label }}</strong>
                <small>{{ area.description }}</small>
              </span>
              <span class="badge info">{{ visible(area.attributes).length }}</span>
            </summary>
            <ol class="anchors" aria-label="What the ratings look like">
              @for (point of anchors; track point) {
                <li><strong>{{ point }}</strong><span>{{ area.anchors[point] }}</span></li>
              }
            </ol>
            <ul class="list">
              @for (item of visible(area.attributes); track item.key) {
                <li class="list-row">
                  <span class="grow">
                    <strong>{{ item.label }}</strong>
                    <small>{{ item.description }}</small>
                    @if (item.applies_to_positions?.length) {
                      <small class="only">Only for: {{ positionLabels(s, item.applies_to_positions ?? []) }}</small>
                    }
                  </span>
                  @if (item.universal) {
                    <span class="badge">Every sport</span>
                  }
                </li>
              }
            </ul>
          </details>
        }

        @if (s.physical_tests.length) {
          <h3 class="fm-section-title">Physical tests</h3>
          <section class="fm-card section">
            <ul class="list">
              @for (item of s.physical_tests; track item.key) {
                <li class="list-row">
                  <span class="grow"><strong>{{ item.label }}</strong><small>{{ item.description }}</small></span>
                  <span class="badge">{{ item.unit }} · {{ item.better === 'lower' ? 'lower is better' : 'higher is better' }}</span>
                </li>
              }
            </ul>
          </section>
        }

        @if (s.match_stats.length) {
          <h3 class="fm-section-title">Match stats</h3>
          <section class="fm-card section">
            <p class="hint flush">Worked out from what scorers record in matches. A formula combines other stats.</p>
            <ul class="list">
              @for (item of s.match_stats; track item.key) {
                <li class="list-row">
                  <span class="grow">
                    <strong>{{ item.label }}{{ item.unit ? ' (' + item.unit + ')' : '' }}</strong>
                    <small>
                      @if (item.formula) {
                        <code>{{ item.formula }}</code>
                      } @else {
                        {{ item.source_label || 'Recorded as "' + item.source + '"' }}
                      }
                    </small>
                  </span>
                  <span class="badge">{{ per(item.per) }}</span>
                </li>
              }
            </ul>
          </section>
        }
      } @else {
        <p class="lede">
          How Fair Measure rates players. Every sport uses the same five areas, each rated from 1 to 10; each sport adds
          its own skills, physical tests and the match stats worked out from its scoring.
        </p>
        <div class="section">
          <div class="chips">
            @for (area of areas(); track area.key) {
              <span class="badge info">{{ area.label }}</span>
            }
          </div>
        </div>
        <ul class="list section">
          @for (row of sports(); track row.key) {
            <li>
              <button type="button" class="fm-card sport-row" (click)="open(row.key)">
                <span class="grow">
                  <strong>{{ row.label }}</strong>
                  <small>{{ row.attribute_count }} attributes · {{ row.physical_test_count }} tests · {{ row.match_stat_count }} match stats</small>
                </span>
                <ion-icon name="chevron-forward-outline" aria-hidden="true" />
              </button>
            </li>
          }
        </ul>
      }
      <div style="height: 32px"></div>
    </ion-content>
  `,
  styles: [
    `
      .sub {
        margin: 0 0 6px;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--ion-color-medium);
      }
      .area summary {
        display: flex;
        align-items: center;
        gap: 10px;
        cursor: pointer;
      }
      .area summary .grow {
        flex: 1;
        display: grid;
        gap: 2px;
      }
      .area summary small,
      .only {
        color: var(--ion-color-medium);
        font-size: 0.8rem;
      }
      .only {
        display: block;
        margin-top: 2px;
        font-style: italic;
      }
      .anchors {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 8px;
        margin: 12px 0;
        padding: 0;
        list-style: none;
      }
      .anchors li {
        display: grid;
        gap: 2px;
        padding: 8px 10px;
        border-radius: 12px;
        background: var(--ion-color-light);
        color: var(--ion-color-light-contrast);
        font-size: 0.8rem;
      }
      .anchors strong {
        font-size: 1.1rem;
        color: var(--ion-color-primary);
      }
      .sport-row {
        display: flex;
        align-items: center;
        gap: 10px;
        width: 100%;
        padding: 12px 14px;
        border: 0;
        color: var(--ion-text-color);
        font: inherit;
        text-align: left;
        cursor: pointer;
      }
      .sport-row .grow {
        flex: 1;
        display: grid;
        gap: 2px;
      }
      .sport-row small {
        color: var(--ion-color-medium);
      }
      .hint.flush {
        margin: 0 0 8px;
      }
      code {
        font-size: 0.78rem;
      }
    `,
  ],
})
export class RatingGuidePage {
  private readonly service = inject(ScoutingService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  readonly anchors = ANCHORS;
  readonly sports = signal<CatalogSport[]>([]);
  readonly areas = signal<RatingArea[]>([]);
  readonly sport = signal<SportCatalogue | null>(null);
  readonly position = signal('');
  readonly loading = signal(true);
  readonly sportKey = computed(() => this.route.snapshot.paramMap.get('sport') ?? '');

  ionViewWillEnter(): void {
    const key = this.sportKey();
    if (key) {
      this.service.sportCatalogue(key).subscribe({
        next: (row) => {
          this.sport.set(row);
          this.loading.set(false);
        },
        error: () => this.loading.set(false),
      });
      return;
    }
    this.service.catalog().subscribe({
      next: (catalog) => {
        this.sports.set(catalog.sports);
        this.areas.set(catalog.areas ?? []);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  visible(rows: CatalogAttribute[]): CatalogAttribute[] {
    const position = this.position();
    if (!position) return rows;
    return rows.filter((row) => !row.applies_to_positions?.length || row.applies_to_positions.includes(position));
  }

  positionLabels(sport: SportCatalogue, keys: string[]): string {
    return keys.map((key) => sport.positions.find((item) => item.key === key)?.label ?? key).join(', ');
  }

  per(value: string): string {
    return PER[value] ?? value;
  }

  open(key: string): void {
    void this.router.navigateByUrl(`/tabs/scouting/guide/${key}`);
  }
}
