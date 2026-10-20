import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
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
import type { CompareResponse } from '../../core/scouting.models';
import { ScoutingService } from '../../core/scouting.service';

const COLOURS = ['#0f766e', '#c2410c', '#4338ca', '#b91c1c'];
const SIZE = 260;
const CENTRE = SIZE / 2;
const RADIUS = 96;

/** 2 to 4 players side by side: a radar of the five areas, key stats and test bests. */
@Component({
  selector: 'fm-compare',
  standalone: true,
  imports: [IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonButton, IonIcon, IonContent, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './scouting.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button defaultHref="/tabs/scouting/search" /></ion-buttons>
        <ion-title>Compare</ion-title>
        <ion-buttons slot="end">
          @if (data()) {
            <ion-button (click)="openReport()">
              <ion-icon slot="start" name="document-text-outline" aria-hidden="true" />
              Report
            </ion-button>
          }
        </ion-buttons>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (error()) {
        <p class="lede">{{ error() }}</p>
      } @else if (data(); as d) {
        <div class="legend section">
          @for (player of d.players; track player.id; let index = $index) {
            <button type="button" class="key" (click)="open(player.id)">
              <span class="swatch" [style.background]="colour(index)"></span>
              <span><strong>{{ player.name }}</strong><small>{{ player.sport?.primary_position_label ?? '' }}{{ player.age_group ? ' · ' + player.age_group : '' }}</small></span>
            </button>
          }
        </div>

        <section class="fm-card section">
          <h3>The five areas <small class="muted">your organisation's ratings</small></h3>
          <svg class="radar" [attr.viewBox]="'-48 -14 ' + (size + 96) + ' ' + (size + 28)" role="img" aria-label="Radar chart of the five areas">
            @for (ring of rings; track ring) {
              <polygon class="ring" [attr.points]="ringPoints(ring, d.areas.length)" />
            }
            @for (area of d.areas; track area.key; let index = $index) {
              <line class="spoke" [attr.x1]="centre" [attr.y1]="centre" [attr.x2]="point(index, d.areas.length, 10).x" [attr.y2]="point(index, d.areas.length, 10).y" />
              <text class="axis" [attr.x]="point(index, d.areas.length, 12.4).x" [attr.y]="point(index, d.areas.length, 12.4).y" text-anchor="middle" dominant-baseline="middle">{{ area.label }}</text>
            }
            @for (player of d.players; track player.id; let index = $index) {
              <polygon class="shape" [attr.points]="shape(player.areas, d)" [style.stroke]="colour(index)" [style.fill]="colour(index)" />
            }
          </svg>
          <table class="compare">
            <thead>
              <tr><th></th>@for (player of d.players; track player.id; let index = $index) {<th [style.color]="colour(index)">{{ first(player.name) }}</th>}</tr>
            </thead>
            <tbody>
              @for (area of d.areas; track area.key) {
                <tr><td>{{ area.label }}</td>@for (player of d.players; track player.id) {<td>{{ player.areas[area.key] ?? '–' }}</td>}</tr>
              }
              <tr class="strong"><td>Current ability</td>@for (player of d.players; track player.id) {<td>{{ player.current_ability ?? '–' }}</td>}</tr>
              <tr class="strong"><td>Potential</td>@for (player of d.players; track player.id) {<td>{{ player.potential ?? '–' }}</td>}</tr>
            </tbody>
          </table>
        </section>

        @if (d.stats.length) {
          <section class="fm-card section">
            <h3>Key stats <small class="muted">latest season, percentile bars</small></h3>
            @for (stat of d.stats; track stat.key) {
              <p class="sub">{{ stat.label }}{{ stat.unit ? ' (' + stat.unit + ')' : '' }}{{ stat.better === 'lower' ? ' · lower is better' : '' }}</p>
              @for (player of d.players; track player.id; let index = $index) {
                <div class="metric">
                  <span class="who" [style.color]="colour(index)">{{ first(player.name) }}</span>
                  <span class="bar"><span [style.width.%]="player.stats[stat.key]?.percentile ?? 0" [style.background]="colour(index)"></span></span>
                  <strong>{{ format(player.stats[stat.key]?.value) }}</strong>
                </div>
              }
            }
            <p class="hint flush">Bars show the percentile within sport, position, age group and gender; no bar means fewer than 20 to compare with.</p>
          </section>
        }

        @if (d.tests.length) {
          <section class="fm-card section">
            <h3>Physical tests <small class="muted">best result</small></h3>
            @for (test of d.tests; track test.key) {
              <p class="sub">{{ test.label }} ({{ test.unit }}) · {{ test.better === 'lower' ? 'lower is better' : 'higher is better' }}</p>
              @for (player of d.players; track player.id; let index = $index) {
                <div class="metric">
                  <span class="who" [style.color]="colour(index)">{{ first(player.name) }}</span>
                  <span class="bar"><span [style.width.%]="player.tests[test.key]?.percentile ?? 0" [style.background]="colour(index)"></span></span>
                  <strong>{{ format(player.tests[test.key]?.best) }}@if (player.tests[test.key] && !player.tests[test.key].verified) {<sup title="Self-reported">*</sup>}</strong>
                </div>
              }
            }
            <p class="hint flush">* self-reported, not verified by a coach or official.</p>
          </section>
        }
      }
      <div style="height: 32px"></div>
    </ion-content>
  `,
  styles: [
    `
      .legend {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 8px;
      }
      .key {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px;
        border: 1px solid var(--ion-color-step-100, #e6e7ea);
        border-radius: 12px;
        background: var(--ion-background-color, #fff);
        color: inherit;
        font: inherit;
        text-align: left;
      }
      .key span:last-child {
        display: grid;
      }
      .key small,
      .muted {
        color: var(--ion-color-medium);
        font-size: 0.75rem;
        font-weight: 500;
      }
      .swatch {
        width: 14px;
        height: 14px;
        border-radius: 4px;
        flex: none;
      }
      .radar {
        display: block;
        width: 100%;
        max-width: 360px;
        margin: 0 auto;
      }
      .ring {
        fill: none;
        stroke: var(--ion-color-step-100, #e6e7ea);
      }
      .spoke {
        stroke: var(--ion-color-step-150, #dfe2e6);
      }
      .axis {
        font-size: 10px;
        fill: var(--ion-color-medium);
      }
      .shape {
        fill-opacity: 0.12;
        stroke-width: 2;
      }
      .compare {
        width: 100%;
        margin-top: 10px;
        border-collapse: collapse;
        font-size: 0.85rem;
      }
      .compare th,
      .compare td {
        padding: 6px 4px;
        border-bottom: 1px solid var(--ion-color-step-50, #f1f2f4);
        text-align: center;
      }
      .compare td:first-child {
        text-align: left;
        color: var(--ion-color-medium);
      }
      .compare .strong td {
        font-weight: 700;
      }
      .sub {
        margin: 12px 0 4px;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: var(--ion-color-medium);
      }
      .metric {
        display: grid;
        grid-template-columns: 70px 1fr 56px;
        align-items: center;
        gap: 8px;
        margin: 4px 0;
        font-size: 0.85rem;
      }
      .metric strong {
        text-align: right;
        font-variant-numeric: tabular-nums;
      }
      .who {
        font-weight: 700;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
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
      }
      .hint.flush {
        margin: 10px 0 0;
      }
    `,
  ],
})
export class ComparePage {
  private readonly scouting = inject(ScoutingService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  readonly size = SIZE;
  readonly centre = CENTRE;
  readonly rings = [2, 4, 6, 8, 10];
  readonly data = signal<CompareResponse | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');
  readonly count = computed(() => this.data()?.players.length ?? 0);

  ionViewWillEnter(): void {
    const query = this.route.snapshot.queryParamMap;
    const ids = (query.get('profiles') ?? '').split(',').filter(Boolean);
    this.scouting.compare(ids, query.get('sport') ?? undefined).subscribe({
      next: (data) => {
        this.data.set(data);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(extractErrorMessage(err, 'Choose 2 to 4 players to compare.'));
      },
    });
  }

  colour(index: number): string {
    return COLOURS[index % COLOURS.length];
  }

  openReport(): void {
    const data = this.data();
    if (!data) return;
    void this.router.navigate(['/tabs/scouting/reports/compare'], {
      queryParams: { profiles: data.players.map((player) => player.id).join(','), sport: data.sport },
    });
  }

  point(index: number, count: number, value: number): { x: number; y: number } {
    const angle = -Math.PI / 2 + (index * 2 * Math.PI) / count;
    const length = (Math.max(0, Math.min(value, 12.5)) / 10) * RADIUS;
    return { x: CENTRE + Math.cos(angle) * length, y: CENTRE + Math.sin(angle) * length };
  }

  ringPoints(value: number, count: number): string {
    return Array.from({ length: count }, (_, index) => this.point(index, count, value))
      .map((point) => `${point.x},${point.y}`)
      .join(' ');
  }

  shape(areas: Record<string, number | null | undefined>, data: CompareResponse): string {
    return data.areas
      .map((area, index) => this.point(index, data.areas.length, areas[area.key] ?? 0))
      .map((point) => `${point.x},${point.y}`)
      .join(' ');
  }

  first(name: string): string {
    return name.split(' ')[0];
  }

  format(value: number | null | undefined): string {
    if (value === null || value === undefined) return '–';
    return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/\.?0+$/, '');
  }

  open(id: string): void {
    void this.router.navigate(['/tabs/scouting/players', id]);
  }
}
