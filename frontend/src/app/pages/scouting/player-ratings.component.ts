import { ChangeDetectionStrategy, Component, inject, input, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Router } from '@angular/router';
import { IonIcon, IonSpinner } from '@ionic/angular/standalone';

import { extractErrorMessage } from '../../core/error-message';
import type { ProfileRatings } from '../../core/scouting.models';
import { ScoutingService } from '../../core/scouting.service';

const RECOMMENDATION: Record<string, string> = { monitor: 'Monitor', trial: 'Trial', sign: 'Sign', not_for_us: 'Not for us' };

/** A scout's Ratings tab: their organisation's weighted view and every dated rating. */
@Component({
  selector: 'fm-player-ratings',
  standalone: true,
  imports: [DatePipe, IonIcon, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './scouting.scss',
  template: `
    <div class="section">
      <button type="button" class="btn block" (click)="rate()">
        <ion-icon name="star-outline" aria-hidden="true" />
        Rate this player
      </button>
    </div>

    @if (loading()) {
      <div class="centered"><ion-spinner name="crescent" /></div>
    } @else if (error()) {
      <p class="lede">{{ error() }}</p>
    } @else if (data(); as d) {
      @if (d.organisations.length > 1) {
        <div class="chips section">
          @for (row of d.organisations; track row.id) {
            <button type="button" class="chip" [class.on]="row.id === d.summary.organisation.id" (click)="load(row.id)">{{ row.name }}</button>
          }
        </div>
      }
      <section class="fm-card section">
        <h3>{{ d.summary.organisation.name }}</h3>
        @if (!d.summary.ratings) {
          <p class="hint flush">No one in your organisation has rated this player yet.</p>
        } @else {
          <p class="hint flush">
            {{ d.summary.scouts }} scout(s), {{ d.summary.ratings }} rating(s). Each scout's latest rating counts, weighted by confidence (high 3, medium 2, low 1).
          </p>
          <ul class="list">
            @for (area of d.summary.areas; track area.key) {
              <li class="area-row">
                <span>{{ area.label }}</span>
                <span class="bar"><span [style.width.%]="(area.average ?? 0) * 10"></span></span>
                <strong>{{ area.average ?? '–' }}</strong>
              </li>
            }
          </ul>
          <div class="grades">
            <div><strong>{{ d.summary.current_ability ?? '–' }}</strong><small>current ability</small></div>
            <div><strong>{{ d.summary.potential ?? '–' }}</strong><small>potential</small></div>
            <div>
              <strong>{{ topRecommendation(d) }}</strong>
              <small>most recommended</small>
            </div>
          </div>
        }
      </section>

      @if (d.ratings.length) {
        <h3 class="fm-section-title">Ratings over time</h3>
        @for (row of d.ratings; track row.id) {
          <details class="fm-card section rating">
            <summary>
              <span class="grow">
                <strong>{{ row.observed_at | date: 'd MMM y, HH:mm' }} · {{ row.scout.name }}</strong>
                <small>
                  {{ row.mode === 'quick' ? 'Quick' : 'Full' }} · {{ row.watched === 'live' ? 'live' : 'video' }} · {{ row.confidence }} confidence{{ row.fixture ? ' · ' + row.fixture.label : '' }}
                </small>
              </span>
              @if (row.recommendation) {
                <span class="badge info">{{ recommendationLabel(row.recommendation) }}</span>
              }
            </summary>
            <div class="chips">
              @for (entry of areaEntries(row.areas); track entry[0]) {
                <span class="badge">{{ entry[0] }} {{ entry[1] }}</span>
              }
              @if (row.current_ability) {
                <span class="badge ok">Current {{ row.current_ability }}</span>
              }
              @if (row.potential) {
                <span class="badge ok">Potential {{ row.potential }}</span>
              }
            </div>
            @if (attributeCount(row) ) {
              <p class="hint flush">{{ attributeCount(row) }} attribute(s) rated in full mode.</p>
            }
            @if (row.notes) {
              <p class="body">{{ row.notes }}</p>
            }
            @for (clip of row.clips; track $index) {
              <p class="hint flush">Clip: {{ clip.title || clip.url }} at {{ clock(clip.at_seconds) }}{{ clip.note ? ' · ' + clip.note : '' }}</p>
            }
          </details>
        }
      }

      <section class="fm-card section qr">
        <img [src]="qr()" alt="QR code to rate this player" width="132" height="132" />
        <span>
          <strong>Their rating code</strong>
          <small>Scan it with the Rate screen, or type the code shown in their profile.</small>
        </span>
      </section>
    }
  `,
  styles: [
    `
      .area-row {
        display: grid;
        grid-template-columns: 90px 1fr 36px;
        align-items: center;
        gap: 8px;
        font-size: 0.88rem;
      }
      .bar {
        display: block;
        height: 8px;
        border-radius: 4px;
        background: var(--ion-color-light);
        color: var(--ion-color-light-contrast);
        overflow: hidden;
      }
      .bar span {
        display: block;
        height: 100%;
        background: var(--ion-color-primary);
      }
      .grades {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 8px;
        margin-top: 12px;
        text-align: center;
      }
      .grades strong {
        display: block;
        font-size: 1.25rem;
      }
      .grades small {
        color: var(--ion-color-medium);
        font-size: 0.72rem;
      }
      .rating summary {
        display: flex;
        align-items: center;
        gap: 8px;
        cursor: pointer;
      }
      .rating .grow {
        flex: 1;
        display: grid;
        gap: 2px;
      }
      .rating small {
        color: var(--ion-color-medium);
      }
      .rating .chips {
        margin-top: 8px;
      }
      .body {
        margin: 8px 0 0;
        line-height: 1.5;
      }
      .hint.flush {
        margin: 6px 0 0;
      }
      .qr {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .qr span {
        display: grid;
        gap: 2px;
      }
      .qr small {
        color: var(--ion-color-medium);
      }
    `,
  ],
})
export class PlayerRatingsComponent {
  private readonly scouting = inject(ScoutingService);
  private readonly router = inject(Router);

  readonly profileId = input.required<string>();
  readonly data = signal<ProfileRatings | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');

  ngOnInit(): void {
    this.load();
  }

  load(organisation?: string): void {
    this.loading.set(true);
    this.scouting.profileRatings(this.profileId(), organisation).subscribe({
      next: (data) => {
        this.data.set(data);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(extractErrorMessage(err, 'Ratings are only for scouts in an organisation.'));
      },
    });
  }

  qr(): string {
    return this.scouting.qrUrl(this.profileId());
  }

  rate(): void {
    void this.router.navigate(['/tabs/scouting/rate'], { queryParams: { profile: this.profileId() } });
  }

  areaEntries(areas: Record<string, number>): Array<[string, number]> {
    return Object.entries(areas).map(([key, value]) => [key.charAt(0).toUpperCase() + key.slice(1), value]);
  }

  attributeCount(row: { attribute_scores: Record<string, number> }): number {
    return Object.keys(row.attribute_scores).length;
  }

  recommendationLabel(key: string): string {
    return RECOMMENDATION[key] ?? key;
  }

  topRecommendation(data: ProfileRatings): string {
    const best = [...data.summary.recommendations].sort((a, b) => b.count - a.count)[0];
    return best?.count ? best.label : '–';
  }

  clock(seconds: number): string {
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
  }
}
