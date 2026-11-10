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
  ToastController,
} from '@ionic/angular/standalone';

import { extractErrorMessage } from '../../core/error-message';
import type { ReportSection, TalentReport, TalentReportKind } from '../../core/scouting.models';
import { ScoutingService } from '../../core/scouting.service';

const KINDS: TalentReportKind[] = ['player', 'progress', 'compare', 'shortlist', 'competition', 'activity'];
const COLOURS = ['#0f766e', '#c2410c', '#4338ca', '#a16207'];
const SIZE = 240;
const CENTRE = SIZE / 2;
const RADIUS = 86;

/** Any of the six talent reports: the on-screen view, and its logged PDF export. */
@Component({
  selector: 'fm-talent-report',
  standalone: true,
  imports: [DatePipe, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonButton, IonIcon, IonContent, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrls: ['./scouting.scss', './talent-report.page.scss'],
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button defaultHref="/tabs/scouting" /></ion-buttons>
        <ion-title>{{ report()?.title ?? 'Report' }}</ion-title>
        <ion-buttons slot="end">
          <ion-button [disabled]="!report() || exporting()" (click)="downloadPdf()">
            <ion-icon slot="start" name="download-outline" aria-hidden="true" />
            PDF
          </ion-button>
        </ion-buttons>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (error()) {
        <p class="lede">{{ error() }}</p>
      } @else if (report(); as r) {
        <section class="section report-head">
          @if (r.organisation?.logo_url) {
            <img class="report-logo" [src]="r.organisation!.logo_url" [alt]="r.organisation!.name + ' logo'" />
          }
          <div>
            <p class="kicker">{{ r.organisation?.name ?? 'Fair Measure' }}</p>
            <h2>{{ r.subtitle }}</h2>
            <p class="muted">Built from stored data · {{ r.generated_at | date: 'd MMM y, HH:mm' }}. Every PDF export is logged.</p>
          </div>
        </section>

        @for (section of r.sections; track $index) {
          <section class="section">
            <h3 class="fm-section-title">{{ section.heading }}</h3>
            @switch (section.type) {
              @case ('facts') {
                <dl class="report-facts">
                  @for (row of facts(section); track row.label) {
                    <div>
                      <dt>{{ row.label }}</dt>
                      <dd>
                        {{ row.value }}
                        @if (row.date || row.verified !== null || row.source) {
                          <small>
                            {{ row.date ?? '' }}
                            @if (row.verified !== null) {
                              · {{ row.verified ? 'verified' : 'self-reported' }}
                            }
                            {{ row.source ? '· ' + row.source : '' }}
                          </small>
                        }
                      </dd>
                    </div>
                  }
                </dl>
              }
              @case ('table') {
                <div class="report-table">
                  <table>
                    <thead>
                      <tr>
                        @for (column of tableOf(section).columns; track $index) {
                          <th>{{ column }}</th>
                        }
                      </tr>
                    </thead>
                    <tbody>
                      @for (row of tableOf(section).rows; track $index; let index = $index) {
                        <tr [class.mark]="tableOf(section).highlight.includes(index)">
                          @for (cell of row; track $index) {
                            <td>{{ cell }}</td>
                          }
                        </tr>
                      } @empty {
                        <tr><td [attr.colspan]="tableOf(section).columns.length">Nothing to show yet.</td></tr>
                      }
                    </tbody>
                  </table>
                </div>
              }
              @case ('radar') {
                <svg class="radar" [attr.viewBox]="'-40 -10 ' + (size + 80) + ' ' + (size + 20)" role="img" [attr.aria-label]="section.heading">
                  @for (ring of [0.25, 0.5, 0.75, 1]; track ring) {
                    <polygon class="ring" [attr.points]="ringPoints(radarOf(section).axes.length, ring)" />
                  }
                  @for (axis of radarOf(section).axes; track axis; let index = $index) {
                    <text class="axis" [attr.x]="axisPoint(index, radarOf(section).axes.length, 1.18).x" [attr.y]="axisPoint(index, radarOf(section).axes.length, 1.18).y" text-anchor="middle">{{ axis }}</text>
                  }
                  @for (series of radarOf(section).series; track series.name; let index = $index) {
                    <polygon class="series" [attr.points]="seriesPoints(series.values, radarOf(section).max)" [attr.stroke]="colour(index)" [attr.fill]="colour(index)" />
                  }
                </svg>
                <div class="legend-row">
                  @for (series of radarOf(section).series; track series.name; let index = $index) {
                    <span><i [style.background]="colour(index)"></i>{{ series.name }}</span>
                  }
                </div>
              }
              @case ('line') {
                @if (lineOf(section).points.length > 1) {
                  <svg class="history" viewBox="0 0 320 140" role="img" [attr.aria-label]="section.heading">
                    <polyline [attr.points]="linePoints(lineOf(section))" />
                    @for (point of lineOf(section).points; track $index; let index = $index) {
                      <circle [attr.cx]="lineX(index, lineOf(section).points.length)" [attr.cy]="lineY(point.value, lineOf(section).max)" r="3" />
                    }
                  </svg>
                }
                <p class="muted">
                  @for (point of lineOf(section).points; track $index) {
                    <span class="chip">{{ point.date }} · {{ point.value }}{{ point.label ? ' · ' + point.label : '' }}</span>
                  }
                </p>
              }
              @case ('notes') {
                @for (item of listOf(section); track $index) {
                  <p class="note-row"><strong>{{ item.date }} · {{ item.author }}</strong> {{ item.text }}</p>
                } @empty {
                  <p class="muted">No notes.</p>
                }
              }
              @case ('links') {
                @for (item of listOf(section); track $index) {
                  <p><a [href]="item.url" target="_blank" rel="noopener">{{ item.label }}</a></p>
                }
              }
              @case ('highlights') {
                <ul class="highlights">
                  @for (item of stringsOf(section); track $index) {
                    <li>{{ item }}</li>
                  }
                </ul>
              }
            }
            @if (section.note) {
              <p class="muted small">{{ section.note }}</p>
            }
          </section>
        }
      }
    </ion-content>
  `,
})
export class TalentReportPage {
  private readonly route = inject(ActivatedRoute);
  private readonly scouting = inject(ScoutingService);
  private readonly toasts = inject(ToastController);

  readonly size = SIZE;
  readonly report = signal<TalentReport | null>(null);
  readonly loading = signal(true);
  readonly exporting = signal(false);
  readonly error = signal<string | null>(null);

  private readonly kind = computed(() => this.route.snapshot.paramMap.get('kind') as TalentReportKind);
  private readonly params = computed(() => {
    const query = this.route.snapshot.queryParamMap;
    return Object.fromEntries(query.keys.map((key) => [key, query.get(key) ?? '']));
  });

  ionViewWillEnter(): void {
    if (!KINDS.includes(this.kind())) {
      this.error.set('Unknown report.');
      this.loading.set(false);
      return;
    }
    this.scouting.talentReport(this.kind(), this.params()).subscribe({
      next: (report) => {
        this.report.set(report);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err, 'This report is not available to you.'));
        this.loading.set(false);
      },
    });
  }

  downloadPdf(): void {
    this.exporting.set(true);
    this.scouting.talentReportPdf(this.kind(), this.params()).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `fair-measure-${this.kind()}-report.pdf`;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        this.exporting.set(false);
      },
      error: async (err: unknown) => {
        this.exporting.set(false);
        const toast = await this.toasts.create({
          message: extractErrorMessage(err, 'The PDF could not be made.'),
          color: 'danger',
          duration: 2500,
        });
        await toast.present();
      },
    });
  }

  // Narrow a section for the template.
  facts(section: ReportSection) {
    return section.type === 'facts' ? section.rows : [];
  }

  tableOf(section: ReportSection) {
    return section.type === 'table' ? section : { columns: [], rows: [], highlight: [] as number[] };
  }

  radarOf(section: ReportSection) {
    return section.type === 'radar' ? section : { axes: [], series: [], max: 10 };
  }

  lineOf(section: ReportSection) {
    return section.type === 'line' ? section : { points: [], max: 10 };
  }

  listOf(section: ReportSection): Array<{ author?: string; date?: string; text?: string; label?: string; url?: string }> {
    return section.type === 'notes' || section.type === 'links' ? section.items : [];
  }

  stringsOf(section: ReportSection): string[] {
    return section.type === 'highlights' ? section.items : [];
  }

  colour(index: number): string {
    return COLOURS[index % COLOURS.length];
  }

  axisPoint(index: number, count: number, scale: number): { x: number; y: number } {
    const angle = (Math.PI * 2 * index) / count - Math.PI / 2;
    return { x: CENTRE + Math.cos(angle) * RADIUS * scale, y: CENTRE + Math.sin(angle) * RADIUS * scale };
  }

  ringPoints(count: number, scale: number): string {
    return Array.from({ length: count }, (_, index) => {
      const point = this.axisPoint(index, count, scale);
      return `${point.x},${point.y}`;
    }).join(' ');
  }

  seriesPoints(values: Array<number | null>, max: number): string {
    return values
      .map((value, index) => {
        const point = this.axisPoint(index, values.length, Math.max(0, Math.min(1, (value ?? 0) / (max || 10))));
        return `${point.x},${point.y}`;
      })
      .join(' ');
  }

  lineX(index: number, count: number): number {
    return 20 + (280 * index) / Math.max(count - 1, 1);
  }

  lineY(value: number, max: number): number {
    return 120 - (100 * value) / (max || 10);
  }

  linePoints(section: { points: Array<{ value: number }>; max: number }): string {
    return section.points
      .map((point, index) => `${this.lineX(index, section.points.length)},${this.lineY(point.value, section.max)}`)
      .join(' ');
  }
}
