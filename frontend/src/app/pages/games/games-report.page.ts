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
import type { GamesReport, ReportKind } from '../../core/games.service';
import { GamesService } from '../../core/games.service';

const KINDS: ReportKind[] = ['medal-table', 'results-book', 'noc-summary', 'daily'];

/** A printable Games report: print or save as PDF, or download the same data as CSV. */
@Component({
  selector: 'fm-games-report',
  standalone: true,
  imports: [DatePipe, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonButton, IonContent, IonIcon, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './games.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button [defaultHref]="backHref()" /></ion-buttons>
        <ion-title>Report</ion-title>
        <ion-buttons slot="end">
          <ion-button [disabled]="!report() || busy()" (click)="downloadCsv()">
            <ion-icon slot="start" name="download-outline" aria-hidden="true" />
            CSV
          </ion-button>
          <ion-button [disabled]="!report()" (click)="print()">
            <ion-icon slot="start" name="print-outline" aria-hidden="true" />
            Print / PDF
          </ion-button>
        </ion-buttons>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (report(); as r) {
        <article class="report">
          <header>
            <h1>{{ r.title }}</h1>
            <p>{{ r.subtitle }} · produced {{ now | date: 'd MMM y, HH:mm' }}</p>
          </header>
          @for (section of r.sections; track $index) {
            <section>
              <h2>{{ section.heading }}</h2>
              @if (section.rows.length) {
                <table>
                  <thead>
                    <tr>
                      @for (column of section.columns; track $index) {
                        <th>{{ column }}</th>
                      }
                    </tr>
                  </thead>
                  <tbody>
                    @for (row of section.rows; track $index) {
                      <tr>
                        @for (cell of row; track $index) {
                          <td>{{ cell }}</td>
                        }
                      </tr>
                    }
                  </tbody>
                </table>
              } @else {
                <p class="empty">Nothing to report.</p>
              }
            </section>
          } @empty {
            <p class="empty">Nothing to report yet.</p>
          }
          <footer>Fair Measure · results confirmed by the event officials</footer>
        </article>
      } @else {
        <p class="hint">{{ error() || 'This report is not available.' }}</p>
      }
    </ion-content>
  `,
  styles: [
    `
      .report {
        max-width: 960px;
        margin: 0 auto;
        padding: 18px 16px 40px;
        color: var(--ion-text-color);
      }
      header h1 {
        margin: 0;
        font-size: 1.4rem;
      }
      header p,
      footer,
      .empty {
        color: var(--ion-color-medium);
        font-size: 0.85rem;
      }
      section {
        margin-top: 18px;
        break-inside: avoid;
      }
      h2 {
        margin: 0 0 6px;
        font-size: 1rem;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.86rem;
      }
      th,
      td {
        padding: 6px 8px;
        border-bottom: 1px solid var(--ion-color-step-100, #e6e7ea);
        text-align: left;
      }
      th {
        font-size: 0.7rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: var(--ion-color-medium);
      }
      footer {
        margin-top: 24px;
      }
      @media print {
        .report {
          max-width: none;
          padding: 0;
          color: #000;
        }
        th,
        td {
          border-bottom-color: #ccc;
        }
      }
    `,
  ],
})
export class GamesReportPage {
  private readonly service = inject(GamesService);
  private readonly route = inject(ActivatedRoute);
  private readonly toasts = inject(ToastController);

  readonly report = signal<GamesReport | null>(null);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly now = new Date();
  private readonly gamesId = computed(() => this.route.snapshot.paramMap.get('id') ?? '');
  private readonly kind = computed(() => this.route.snapshot.paramMap.get('kind') as ReportKind);
  readonly backHref = computed(() => `/tabs/games/${this.gamesId()}`);

  private params(): Record<string, string> {
    const query = this.route.snapshot.queryParamMap;
    const params: Record<string, string> = {};
    for (const key of ['sport', 'noc', 'date']) {
      const value = query.get(key);
      if (value) params[key] = value;
    }
    return params;
  }

  ionViewWillEnter(): void {
    if (!KINDS.includes(this.kind())) {
      this.loading.set(false);
      return;
    }
    this.service.report(this.gamesId(), this.kind(), this.params()).subscribe({
      next: (report) => {
        this.report.set(report);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err, 'This report is not available.'));
        this.loading.set(false);
      },
    });
  }

  print(): void {
    setTimeout(() => window.print(), 50);
  }

  downloadCsv(): void {
    const report = this.report();
    if (!report) return;
    this.busy.set(true);
    this.service.reportCsv(this.gamesId(), this.kind(), this.params()).subscribe({
      next: (blob) => {
        this.busy.set(false);
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${report.title.replace(/[^\w\- ]+/g, '').trim() || 'report'}.csv`;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        const toast = await this.toasts.create({
          message: extractErrorMessage(err, 'Could not download the CSV.'),
          color: 'danger',
          duration: 2400,
          position: 'top',
        });
        await toast.present();
      },
    });
  }
}
