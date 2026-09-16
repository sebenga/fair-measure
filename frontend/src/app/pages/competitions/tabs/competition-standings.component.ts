import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  inject,
  input,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { debounceTime } from 'rxjs';
import {
  IonButton,
  IonIcon,
  IonSelect,
  IonSelectOption,
  IonSpinner,
} from '@ionic/angular/standalone';

import { ApiService } from '../../../core/api.service';
import { extractErrorMessage } from '../../../core/error-message';
import type { CompetitionDetail, StandingRow } from '../../../core/models';
import { RealtimeService } from '../../../core/realtime.service';

@Component({
  selector: 'fm-competition-standings',
  standalone: true,
  imports: [IonSpinner, IonIcon, IonButton, IonSelect, IonSelectOption],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (competition().stages.length > 1) {
      <div class="stage-picker">
        <ion-select
          label="Stage"
          labelPlacement="stacked"
          interface="popover"
          [value]="stageId()"
          (ionChange)="selectStage($any($event).detail.value)"
        >
          <ion-select-option [value]="null">All stages</ion-select-option>
          @for (stage of competition().stages; track stage.id) {
            <ion-select-option [value]="stage.id">{{ stage.name }}</ion-select-option>
          }
        </ion-select>
      </div>
    }

    @if (loading()) {
      <div class="centered"><ion-spinner name="crescent" /></div>
    } @else if (error()) {
      <div class="fm-empty">
        <ion-icon name="alert-circle-outline" aria-hidden="true" />
        <h3>Table unavailable</h3>
        <p>{{ error() }}</p>
        <ion-button fill="clear" (click)="load()">Try again</ion-button>
      </div>
    } @else if (rows().length === 0) {
      <div class="fm-empty">
        <ion-icon name="podium-outline" aria-hidden="true" />
        <h3>No results yet</h3>
        <p>The table fills in as fixtures are completed.</p>
      </div>
    } @else {
      <div class="table-wrap fm-card">
        <table>
          <thead>
            <tr>
              <th class="pos">#</th>
              <th class="team">Team</th>
              <th>P</th>
              <th>W</th>
              <th>D</th>
              <th>L</th>
              <th>F</th>
              <th>A</th>
              <th>+/-</th>
              <th class="pts">Pts</th>
            </tr>
          </thead>
          <tbody>
            @for (row of rows(); track row.participant.id) {
              <tr [class.promoted]="row.position <= advancesCount()">
                <td class="pos">{{ row.position }}</td>
                <td class="team">
                  <span class="name">{{ row.participant.short_name || row.participant.name }}</span>
                  @if (row.form.length) {
                    <span class="form">
                      @for (result of row.form; track $index) {
                        <i [class]="'dot ' + result.toLowerCase()" [title]="result">{{ result }}</i>
                      }
                    </span>
                  }
                </td>
                <td>{{ row.played }}</td>
                <td>{{ row.wins }}</td>
                <td>{{ row.draws }}</td>
                <td>{{ row.losses }}</td>
                <td>{{ trim(row.score_for) }}</td>
                <td>{{ trim(row.score_against) }}</td>
                <td [class.negative]="isNegative(row.score_difference)">
                  {{ signed(row.score_difference) }}
                </td>
                <td class="pts">{{ trim(row.points) }}</td>
              </tr>
            }
          </tbody>
        </table>
      </div>

      <p class="legend">
        Tie-breakers in order:
        {{ tiebreakerLabels() }}
      </p>
    }
  `,
  styles: [
    `
      .stage-picker {
        margin: 12px 16px 0;
      }

      .centered {
        display: grid;
        place-items: center;
        padding: 64px 0;
      }

      .table-wrap {
        padding: 4px 0;
        overflow-x: auto;
      }

      table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.82rem;
        font-variant-numeric: tabular-nums;
      }

      th {
        padding: 10px 6px;
        font-weight: 600;
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--ion-color-medium);
        text-align: center;
        border-bottom: 1px solid var(--ion-color-step-100, #eee);
      }

      td {
        padding: 11px 6px;
        text-align: center;
        border-bottom: 1px solid var(--ion-color-step-50, #f5f5f5);
      }

      tbody tr:last-child td {
        border-bottom: none;
      }

      .pos {
        width: 34px;
        color: var(--ion-color-medium);
      }

      .team {
        text-align: left;
        padding-left: 4px;
        min-width: 140px;

        .name {
          display: block;
          font-weight: 600;
          color: var(--ion-text-color);
        }
      }

      .form {
        display: inline-flex;
        gap: 3px;
        margin-top: 4px;

        .dot {
          width: 15px;
          height: 15px;
          border-radius: 50%;
          display: grid;
          place-items: center;
          font-size: 0.58rem;
          font-style: normal;
          font-weight: 700;
          color: #fff;
        }

        .dot.w {
          background: var(--ion-color-success);
        }
        .dot.d {
          background: var(--ion-color-medium);
        }
        .dot.l {
          background: var(--ion-color-danger);
        }
      }

      .pts {
        font-weight: 700;
        color: var(--ion-text-color);
      }

      .negative {
        color: var(--ion-color-danger);
      }

      .promoted .pos {
        position: relative;
        font-weight: 700;
        color: var(--ion-color-success);
      }

      .legend {
        margin: 14px 20px 32px;
        font-size: 0.74rem;
        color: var(--ion-color-medium);
        line-height: 1.5;
      }
    `,
  ],
})
export class CompetitionStandingsComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly realtime = inject(RealtimeService);

  readonly competition = input.required<CompetitionDetail>();

  readonly rows = signal<StandingRow[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly stageId = signal<string | null>(null);

  ngOnInit(): void {
    this.load();

    // Standings are recomputed by a worker, so the table can lag a completed
    // fixture by a moment. Debounce so a burst of events causes one refetch.
    this.realtime
      .onAny(['standings.updated', 'standings.stale'])
      .pipe(debounceTime(400), takeUntilDestroyed())
      .subscribe(() => this.load(false));
  }

  load(showSpinner = true): void {
    if (showSpinner) this.loading.set(true);
    this.error.set(null);

    this.api
      .getStandings(this.competition().id, { stage: this.stageId() })
      .subscribe({
        next: (response) => {
          this.rows.set(response.rows);
          this.loading.set(false);
        },
        error: (err: unknown) => {
          this.error.set(extractErrorMessage(err));
          this.loading.set(false);
        },
      });
  }

  selectStage(value: string | null): void {
    this.stageId.set(value ?? null);
    this.load();
  }

  advancesCount(): number {
    const stage = this.competition().stages.find((candidate) => candidate.id === this.stageId());
    return stage?.advances_count ?? 0;
  }

  tiebreakerLabels(): string {
    const labels: Record<string, string> = {
      points: 'points',
      score_difference: 'score difference',
      score_for: 'score for',
      wins: 'wins',
      head_to_head: 'head-to-head',
      played: 'fewest played',
      name: 'name',
    };
    return this.competition()
      .points_policy.tiebreakers.map((key) => labels[key] ?? key)
      .join(', ');
  }

  /** Decimals arrive as strings so precision survives; most are whole numbers. */
  trim(value: string): string {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? String(parsed) : value;
  }

  signed(value: string): string {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return value;
    return parsed > 0 ? `+${parsed}` : String(parsed);
  }

  isNegative(value: string): boolean {
    return Number(value) < 0;
  }
}
