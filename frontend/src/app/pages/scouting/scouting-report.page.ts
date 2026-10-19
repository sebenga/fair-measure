import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import {
  IonBackButton,
  IonButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonSpinner,
  IonTitle,
  IonToolbar,
} from '@ionic/angular/standalone';

import { extractErrorMessage } from '../../core/error-message';
import type { ReportLeague, ScoutingCatalog, ScoutingReport } from '../../core/scouting.models';
import { ScoutingService } from '../../core/scouting.service';

@Component({
  selector: 'fm-scouting-report',
  standalone: true,
  imports: [
    DatePipe,
    IonHeader,
    IonToolbar,
    IonTitle,
    IonButtons,
    IonBackButton,
    IonButton,
    IonContent,
    IonIcon,
    IonSpinner,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './scouting.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button [defaultHref]="backHref()" /></ion-buttons>
        <ion-title>Scouting report</ion-title>
        <ion-buttons slot="end">
          <ion-button [disabled]="!report() || exporting()" (click)="savePdf()">
            <ion-icon slot="start" name="print-outline" aria-hidden="true" />
            Save as PDF
          </ion-button>
        </ion-buttons>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (error()) {
        <div class="fm-empty">
          <ion-icon name="eye-off-outline" aria-hidden="true" />
          <h3>Report not available</h3>
          <p>{{ error() }}</p>
        </div>
      } @else if (report(); as r) {
        <article class="report fm-enter">
          <header class="masthead">
            <div>
              <p class="kicker">Fair Measure · Player scouting report</p>
              <h1>{{ r.profile.first_name }} {{ r.profile.last_name }}</h1>
              <p class="meta">
                @if (r.profile.age !== undefined && r.profile.age !== null) {
                  {{ r.profile.age }} years ·
                }
                {{ r.profile.age_group?.label ?? 'Age group unknown' }}
                @if (regionLabel(r.profile.region)) {
                  · {{ regionLabel(r.profile.region) }}
                }
                @if (r.profile.nationality) {
                  · {{ r.profile.nationality }}
                }
              </p>
              @if (r.profile.teams.length) {
                <div class="chips">
                  @for (team of r.profile.teams; track team.id) {
                    <span class="badge">{{ team.name }} · {{ team.competition }}</span>
                  }
                </div>
              }
            </div>
            <span class="avatar large">
              @if (r.profile.photo_url) {
                <img [src]="r.profile.photo_url" alt="" />
              } @else {
                {{ r.profile.first_name.charAt(0) }}{{ r.profile.last_name.charAt(0) }}
              }
            </span>
          </header>

          <p class="stamp">
            Generated {{ r.generated_at | date: 'd MMM y, HH:mm' }} from data stored on Fair Measure.
            @if (r.access === 'owner' || r.access === 'guardian') {
              This is exactly what a scout's report shows.
            }
            Contact details are never included.
          </p>

          @if (r.headline.length) {
            <section class="fm-card section">
              <h3>Key facts</h3>
              <ul class="facts">
                @for (line of r.headline; track line) {
                  <li>{{ line }}</li>
                }
              </ul>
            </section>
          }

          <section class="fm-card section">
            <h3>Sport and positions</h3>
            @for (sport of r.profile.sports; track sport.id) {
              <p class="line">
                <strong>{{ sport.sport_label }}</strong>
                {{ sport.primary_position_label ? '· ' + sport.primary_position_label : '· No main position' }}
                @if (sport.secondary_positions.length) {
                  <span class="muted">· also {{ secondaryLabels(sport.sport, sport.secondary_positions) }}</span>
                }
              </p>
            } @empty {
              <p class="muted">No sport on the profile yet.</p>
            }
            @if (r.profile.availability; as availability) {
              <p class="line">
                <strong>Availability:</strong> {{ availabilityLabel(availability.status) }}
                @if (availability.note) {
                  <span class="muted">· {{ availability.note }}</span>
                }
              </p>
            }
          </section>

          @if (r.profile.bio) {
            <section class="fm-card section">
              <h3>About</h3>
              <p class="line">{{ r.profile.bio }}</p>
            </section>
          }

          <section class="fm-card section">
            <h3>Physical</h3>
            @if (r.profile.measurements.length) {
              <table>
                <thead>
                  <tr><th>Measure</th><th>Value</th><th>Measured</th><th>Source</th></tr>
                </thead>
                <tbody>
                  @for (item of r.profile.measurements; track item.id) {
                    <tr>
                      <td>{{ item.label }}</td>
                      <td>{{ item.value !== null ? trim(item.value) + ' ' + item.unit : item.text_value }}</td>
                      <td>{{ item.measured_on | date: 'd MMM y' }}</td>
                      <td>
                        <span class="badge" [class.ok]="item.verified">
                          {{ item.verified ? 'Verified · ' + item.verified_by_name : 'Self-reported' }}
                        </span>
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            } @else {
              <p class="muted">No measurements shared.</p>
            }
          </section>

          <h3 class="fm-section-title">League record</h3>
          @for (league of r.leagues; track league.competition_id) {
            <section class="fm-card section league">
              <header class="league-head">
                <div>
                  <h3>{{ league.competition }}</h3>
                  <p class="muted">
                    {{ league.team }}{{ league.position ? ' · ' + league.position : '' }}{{
                      league.number !== null ? ' · #' + league.number : ''
                    }}
                  </p>
                </div>
                @if (league.selection; as selection) {
                  <span class="badge" [class.ok]="selection.status === 'published'" [class.warn]="selection.status === 'draft'">
                    <ion-icon name="shirt-outline" aria-hidden="true" />
                    {{ selection.status === 'published' ? 'In the league squad' : 'In the draft squad' }}
                  </span>
                }
              </header>

              <div class="numbers">
                <div><strong>{{ league.games }}</strong><small>Team games</small></div>
                <div>
                  <strong>W{{ league.record.won }} D{{ league.record.drawn }} L{{ league.record.lost }}</strong>
                  <small>Team record</small>
                </div>
                <div><strong>{{ league.avg_rating ?? '–' }}</strong><small>Avg rating</small></div>
                <div><strong>{{ league.ratings.length }}</strong><small>Rated games</small></div>
              </div>

              @if (league.ratings.length) {
                <p class="sub-title">Rating history</p>
                <div class="bars" role="img" [attr.aria-label]="'Ratings: ' + ratingList(league)">
                  @for (item of league.ratings; track $index) {
                    <div class="bar">
                      <span class="fill" [style.height.%]="+item.rating * 10"></span>
                      <strong>{{ item.rating }}</strong>
                      <small>{{ item.date | date: 'd MMM' }}</small>
                    </div>
                  }
                </div>
              }

              @if (league.stats.length) {
                <p class="sub-title">Recorded for this player</p>
                <table>
                  <thead>
                    <tr><th>Event</th><th>Count</th><th>Points</th><th>Period</th></tr>
                  </thead>
                  <tbody>
                    @for (stat of league.stats; track stat.key) {
                      <tr>
                        <td>{{ stat.label }}</td>
                        <td>{{ stat.count }}</td>
                        <td>{{ stat.points }}</td>
                        <td>{{ stat.first | date: 'd MMM y' }}{{ sameDay(stat.first, stat.last) ? '' : ' – ' + (stat.last | date: 'd MMM y') }}</td>
                      </tr>
                    }
                  </tbody>
                </table>
              } @else {
                <p class="muted">No score events tagged to this player in this league yet.</p>
              }

              @if (league.selection; as selection) {
                <p class="sub-title">Why they were picked</p>
                <ul class="facts">
                  @for (line of selection.summary; track line) {
                    <li>{{ line }}</li>
                  }
                </ul>
              }
            </section>
          } @empty {
            <div class="fm-card section">
              <p class="muted">Not on a team in any league you can see.</p>
            </div>
          }

          @if (r.profile.videos.length) {
            <section class="fm-card section">
              <h3>Highlight videos</h3>
              <ul class="facts">
                @for (video of r.profile.videos; track video.id) {
                  <li>
                    @if (video.url || video.playback_url) {
                      <a [href]="video.url || video.playback_url" target="_blank" rel="noopener">{{ video.title }}</a>
                    } @else {
                      {{ video.title }} <span class="muted">({{ video.status }})</span>
                    }
                  </li>
                }
              </ul>
            </section>
          }

          <section class="fm-card section">
            <h3>What this report is based on</h3>
            <ul class="coverage">
              @for (item of r.coverage; track item.key) {
                <li [class.have]="item.available">
                  <ion-icon [name]="item.available ? 'checkmark-outline' : 'remove-circle-outline'" aria-hidden="true" />
                  <span>
                    <strong>{{ item.label }}</strong>
                    @if (item.note) {
                      <small>{{ item.note }}</small>
                    }
                  </span>
                </li>
              }
            </ul>
          </section>
        </article>
      }
      <div style="height: 32px"></div>
    </ion-content>
  `,
  styles: [
    `
      .report {
        max-width: 860px;
        margin: 0 auto;
      }

      .masthead {
        display: flex;
        justify-content: space-between;
        gap: 16px;
        margin: 16px;
        padding: 18px;
        border-radius: 20px;
        color: #fff;
        background: linear-gradient(135deg, var(--ion-color-primary), var(--ion-color-secondary));

        h1 {
          margin: 2px 0 4px;
          font-size: 1.6rem;
          font-weight: 800;
        }

        .kicker {
          margin: 0;
          font-size: 0.72rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          opacity: 0.85;
        }

        .meta {
          margin: 0 0 10px;
          opacity: 0.92;
        }

        .badge {
          background: rgb(255 255 255 / 0.2);
          color: #fff;
        }

        .avatar {
          border: 3px solid rgb(255 255 255 / 0.6);
        }
      }

      .stamp {
        margin: 0 20px 6px;
        color: var(--ion-color-medium);
        font-size: 0.78rem;
      }

      .line {
        margin: 0 0 6px;
        line-height: 1.5;
      }

      .muted {
        color: var(--ion-color-medium);
      }

      .facts {
        margin: 0;
        padding-left: 18px;
        line-height: 1.6;
      }

      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.86rem;

        th,
        td {
          padding: 7px 6px;
          border-bottom: 1px solid var(--ion-color-step-100, #eceff3);
          text-align: left;
          vertical-align: top;
        }

        th {
          color: var(--ion-color-medium);
          font-size: 0.72rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.04em;
        }
      }

      .league-head {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 10px;

        h3 {
          margin: 0;
        }

        p {
          margin: 2px 0 0;
        }
      }

      .numbers {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 8px;
        margin: 12px 0;

        div {
          display: grid;
          gap: 2px;
          padding: 10px;
          border-radius: 12px;
          background: var(--ion-color-light);
          text-align: center;
        }

        strong {
          font-size: 1.05rem;
        }

        small {
          color: var(--ion-color-medium);
          font-size: 0.7rem;
        }
      }

      .sub-title {
        margin: 12px 0 6px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: var(--ion-color-medium);
      }

      .bars {
        display: flex;
        align-items: flex-end;
        gap: 8px;
        height: 130px;
        padding: 6px 2px 0;
        overflow-x: auto;
      }

      .bar {
        flex: 0 0 40px;
        display: grid;
        grid-template-rows: 1fr auto auto;
        justify-items: center;
        height: 100%;
        font-size: 0.7rem;

        .fill {
          align-self: end;
          width: 22px;
          border-radius: 6px 6px 2px 2px;
          background: linear-gradient(180deg, var(--ion-color-secondary), var(--ion-color-primary));
          animation: grow 0.5s cubic-bezier(0.2, 0.8, 0.2, 1) both;
          transform-origin: bottom;
        }

        small {
          color: var(--ion-color-medium);
        }
      }

      .coverage {
        display: grid;
        gap: 8px;
        margin: 0;
        padding: 0;
        list-style: none;

        li {
          display: flex;
          gap: 10px;
          align-items: flex-start;
          color: var(--ion-color-medium);

          &.have {
            color: var(--ion-text-color);

            ion-icon {
              color: var(--ion-color-success);
            }
          }
        }

        span {
          display: grid;
        }

        small {
          color: var(--ion-color-medium);
        }

        ion-icon {
          flex: 0 0 auto;
          margin-top: 2px;
          font-size: 1.1rem;
        }
      }

      @keyframes grow {
        from {
          transform: scaleY(0);
        }
      }

      @media (max-width: 520px) {
        .numbers {
          grid-template-columns: repeat(2, 1fr);
        }
      }

      @media print {
        .masthead {
          color: #000;
          background: none;
          border: 2px solid #222;
          -webkit-print-color-adjust: exact;
          print-color-adjust: exact;

          .badge {
            color: #000;
            border: 1px solid #999;
          }
        }

        .bar .fill {
          -webkit-print-color-adjust: exact;
          print-color-adjust: exact;
        }

        .section {
          break-inside: avoid;
        }
      }
    `,
  ],
})
export class ScoutingReportPage {
  private readonly scouting = inject(ScoutingService);
  private readonly route = inject(ActivatedRoute);

  readonly catalog = signal<ScoutingCatalog | null>(null);
  readonly report = signal<ScoutingReport | null>(null);
  readonly loading = signal(true);
  readonly exporting = signal(false);
  readonly error = signal('');

  private readonly profileId = computed(() => this.route.snapshot.paramMap.get('id') ?? '');
  readonly backHref = computed(() => `/tabs/scouting/players/${this.profileId()}`);

  ionViewWillEnter(): void {
    this.scouting.catalog().subscribe((catalog) => this.catalog.set(catalog));
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.scouting.report(this.profileId()).subscribe({
      next: (report) => {
        this.report.set(report);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err, 'You cannot see this player.'));
        this.loading.set(false);
      },
    });
  }

  /** Logs the export, refreshes the numbers, then opens the browser's print / save-as-PDF. */
  savePdf(): void {
    this.exporting.set(true);
    this.scouting.report(this.profileId(), true).subscribe({
      next: (report) => {
        this.report.set(report);
        this.exporting.set(false);
        setTimeout(() => window.print(), 50);
      },
      error: () => this.exporting.set(false),
    });
  }

  regionLabel(key: string): string {
    return (this.catalog()?.regions ?? []).find((region) => region.key === key)?.label ?? '';
  }

  secondaryLabels(sportKey: string, keys: string[]): string {
    const positions = (this.catalog()?.sports ?? []).find((sport) => sport.key === sportKey)?.positions ?? [];
    return keys.map((key) => positions.find((position) => position.key === key)?.label ?? key).join(', ');
  }

  availabilityLabel(status: string): string {
    return (
      { available: 'Available', limited: 'Limited availability', unavailable: 'Not available', injured: 'Injured' }[
        status
      ] ?? status
    );
  }

  ratingList(league: ReportLeague): string {
    return league.ratings.map((item) => item.rating).join(', ');
  }

  sameDay(a: string, b: string): boolean {
    return a.slice(0, 10) === b.slice(0, 10);
  }

  trim(value: string): string {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? String(parsed) : value;
  }
}
