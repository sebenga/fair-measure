import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { debounceTime } from 'rxjs';
import {
  AlertController,
  IonButton,
  IonIcon,
  IonSelect,
  IonSelectOption,
  ToastController,
} from '@ionic/angular/standalone';

import { ApiService } from '../../../core/api.service';
import { extractErrorMessage } from '../../../core/error-message';
import type {
  CompetitionDetail,
  CriterionBreakdown,
  Fixture,
  PlayerStatsTable,
  StandingRow,
} from '../../../core/models';
import { isPointsTable, tableBonusEnabled, tableBonusOf } from '../../../core/models';
import { KnockoutTreeComponent } from './knockout-tree.component';
import { RealtimeService } from '../../../core/realtime.service';
import type { CombinationStatRow } from '../../../core/results.models';
import { ResultsService } from '../../../core/results.service';

@Component({
  selector: 'fm-competition-standings',
  standalone: true,
  imports: [IonIcon, IonButton, IonSelect, IonSelectOption, KnockoutTreeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (pointsTable() && scoringGuide().length) {
      <section class="scoring-guide fm-card">
        <h3>How points are earned</h3>
        <ul>
          @for (category of scoringGuide(); track category.id) {
            <li>
              <strong>{{ category.name }}: {{ trim(category.points) }} points</strong>
              @if (category.description) {
                <p>{{ category.description }}</p>
              }
            </li>
          }
        </ul>
      </section>
    }

    @if (competition().format !== 'knockout' && competition().stages.length > 1) {
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

    @if (competition().format === 'knockout') {
      <fm-knockout-tree [competitionId]="competition().id" (select)="openFixture($event)" />
    } @else if (loading()) {
      <div class="table-wrap fm-card" aria-busy="true" aria-label="Loading the table">
        @for (n of skeletonRows; track n) {
          <span class="fm-skeleton skeleton-row" [style.width.%]="100 - n * 6"></span>
        }
      </div>
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
        <p>
          @if (pointsTable()) {
            The table fills in as scoring criteria are logged.
          } @else {
            The table fills in as fixtures are completed.
          }
        </p>
      </div>
    } @else {
      <div class="table-wrap fm-card">
        <table>
          <thead>
            <tr>
              <th class="pos">#</th>
              <th class="team">{{ pointsTable() ? 'Name' : seriesTable() ? 'Entrant' : 'Team' }}</th>
              <th>{{ pointsTable() ? 'E' : seriesTable() ? 'St' : 'P' }}</th>
              @if (seriesTable()) {
                <th>1st</th>
                <th>2nd</th>
                <th>3rd</th>
              } @else if (!pointsTable()) {
                <th>W</th>
                <th>D</th>
                <th>L</th>
                <th>F</th>
                <th>A</th>
                <th>+/-</th>
                @if (headStartTable()) {
                  <th title="Goal difference without handicap goals">Net</th>
                }
                @if (showsBonus()) {
                  <th title="Bonus points">B</th>
                }
              }
              <th class="pts">Pts</th>
            </tr>
          </thead>
          <tbody>
            @for (row of rows(); track row.participant.id) {
              <tr
                class="row-in"
                [style.--i]="$index"
                [class.promoted]="row.position <= advancesCount()"
                [class.expandable]="pointsTable()"
                [class.fm-flash]="!!changes()[row.participant.id]"
                [class.leader]="row.position === 1"
                (click)="pointsTable() && toggle(row.participant.id)"
              >
                <td class="pos">
                  <span class="badge" [class]="'badge place-' + (row.position <= 3 ? row.position : 'n')">
                    {{ row.position }}
                  </span>
                  @if (changes()[row.participant.id]?.delta; as delta) {
                    <i class="move" [class.up]="delta > 0" [class.down]="delta < 0" aria-hidden="true">
                      {{ delta > 0 ? '▲' : '▼' }}
                    </i>
                  }
                </td>
                <td class="team">
                  <span class="name">{{ row.participant.short_name || row.participant.name }}</span>
                  @if (pointsTable()) {
                    <span class="form">{{ expanded() === row.participant.id ? 'Hide' : 'How' }}</span>
                  } @else if (row.form.length) {
                    <span class="form">
                      @for (result of row.form; track $index) {
                        <i [class]="'dot ' + result.toLowerCase()" [title]="result">{{ result }}</i>
                      }
                    </span>
                  }
                </td>
                <td>{{ row.played }}</td>
                @if (seriesTable()) {
                  <td>{{ row.wins }}</td>
                  <td>{{ row.detail?.seconds ?? 0 }}</td>
                  <td>{{ row.detail?.thirds ?? 0 }}</td>
                } @else if (!pointsTable()) {
                  <td>{{ row.wins }}</td>
                  <td>{{ row.draws }}</td>
                  <td>{{ row.losses }}</td>
                  <td>{{ trim(row.score_for) }}</td>
                  <td>{{ trim(row.score_against) }}</td>
                  <td [class.negative]="isNegative(row.score_difference)">
                    {{ signed(row.score_difference) }}
                  </td>
                  @if (headStartTable()) {
                    <td [class.negative]="isNegative(netDifference(row))">{{ signed(netDifference(row)) }}</td>
                  }
                  @if (showsBonus()) {
                    <td>{{ trim(row.bonus_points) }}</td>
                  }
                }
                <td class="pts">
                  <span [class.fm-bump]="changes()[row.participant.id]?.points">{{ trim(row.points) }}</span>
                </td>
              </tr>
              @if (pointsTable() && expanded() === row.participant.id) {
                <tr class="breakdown">
                  <td class="pos"></td>
                  <td class="detail" colspan="3">
                    @for (criterion of breakdownFor(row.participant.id); track criterion.id) {
                      <div class="criterion">
                        <strong>{{ criterion.name }}</strong>
                        <span>{{ trim(criterion.total) }} pts</span>
                        <p>{{ criterion.description || 'No description for these points yet.' }}</p>
                        @for (entry of criterion.entries; track $index) {
                          <p class="entry">
                            {{ trim(entry.quantity) }} × {{ trim(criterion.points_each) }}
                            = {{ trim(entry.awarded) }}.
                            {{ entry.note || 'No note on how this was accumulated.' }}
                            @if (canScore() && entry.id) {
                              <button
                                type="button"
                                class="entry-delete"
                                [disabled]="deleting()"
                                (click)="$event.stopPropagation(); confirmDeleteEntry(row.participant.name, criterion, entry)"
                                [attr.aria-label]="'Delete this ' + criterion.name + ' entry'"
                              >
                                <ion-icon name="trash-outline" aria-hidden="true" />
                              </button>
                            }
                          </p>
                        }
                      </div>
                    } @empty {
                      <p class="entry">No scoring criteria logged yet.</p>
                    }
                  </td>
                </tr>
              }
            }
          </tbody>
        </table>
      </div>

      @if (combinations()) {
        <section class="combo-stats">
          <div class="combo-tabs" role="tablist">
            @for (option of statOptions(); track option.key) {
              <button type="button" role="tab" [attr.aria-selected]="statsBy() === option.key" [class.on]="statsBy() === option.key" (click)="loadStats(option.key)">
                {{ option.label }}
              </button>
            }
          </div>
          <div class="table-wrap fm-card">
            <table>
              <thead>
                <tr>
                  <th class="team">{{ statLabel() }}</th>
                  <th>St</th>
                  <th>1st</th>
                  <th>2nd</th>
                  <th>3rd</th>
                  <th class="pts">Pts</th>
                  @if (showsPrize()) {
                    <th>Prize</th>
                  }
                </tr>
              </thead>
              <tbody>
                @for (row of stats(); track row.key) {
                  <tr>
                    <td class="team"><span class="name">{{ row.name }}</span></td>
                    <td>{{ row.starts }}</td>
                    <td>{{ row.wins }}</td>
                    <td>{{ row.seconds }}</td>
                    <td>{{ row.thirds }}</td>
                    <td class="pts">{{ trim(row.points) }}</td>
                    @if (showsPrize()) {
                      <td>{{ row.prize ?? '' }}</td>
                    }
                  </tr>
                } @empty {
                  <tr><td colspan="6" class="empty-cell">No confirmed results yet.</td></tr>
                }
              </tbody>
            </table>
          </div>
        </section>
      }

      @if (playerStats(); as table) {
        @if (table.rows.length) {
          <section class="combo-stats">
            <h3 class="fm-section-title">Players</h3>
            <div class="table-wrap fm-card">
              <table>
                <thead>
                  <tr>
                    <th class="team">Player</th>
                    @for (column of table.columns; track column.key) {
                      <th>{{ column.label }}</th>
                    }
                  </tr>
                </thead>
                <tbody>
                  @for (row of table.rows; track row.player_id) {
                    <tr>
                      <td class="team">
                        <span class="name">{{ row.name }}</span>
                        <span class="form">{{ row.team }}</span>
                      </td>
                      @for (column of table.columns; track column.key) {
                        <td>{{ row.values[column.key] }}</td>
                      }
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          </section>
        }
      }

      <p class="legend">
        @if (seriesTable()) {
          {{ seriesBlurb() }}
          Ties: {{ tiebreakerLabels() }}.
        } @else if (pointsTable()) {
          Tap a name to see each scoring criterion, what the points mean, and how they were accumulated.
        } @else {
          @if (leagueGuide(); as league) {
            League: {{ league }}.
          }
          Tie-breakers in order: {{ tiebreakerLabels() }}.
          @if (bonusGuide(); as bonus) {
            Bonus: {{ bonus }}.
          }
        }
      </p>
    }

    @if (showsRounds()) {
      <fm-knockout-tree
        [competitionId]="competition().id"
        layout="rounds"
        (select)="openFixture($event)"
      />
    }
  `,
  styles: [
    `
      .scoring-guide {
        margin: 12px 16px;
        padding: 12px 16px;
      }

      .scoring-guide h3 {
        margin: 0 0 8px;
        font-size: 0.95rem;
      }

      .scoring-guide ul {
        margin: 0;
        padding-left: 1.1rem;
      }

      .scoring-guide li + li {
        margin-top: 8px;
      }

      .scoring-guide p {
        margin: 2px 0 0;
        color: var(--ion-color-medium);
        font-size: 0.82rem;
      }

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

      .skeleton-row {
        height: 20px;
        margin: 14px 16px;
      }

      tr.row-in {
        animation: fm-slide-in 0.45s var(--fm-ease-out) both;
        animation-delay: calc(min(var(--i, 0), 14) * 45ms);
        transition: background-color 0.2s ease;
      }

      tr.expandable:hover,
      tr.expandable:active {
        background: var(--ion-color-step-50, #f7f8fa);
      }

      .badge {
        display: inline-grid;
        place-items: center;
        min-width: 24px;
        height: 24px;
        border-radius: 50%;
        font-weight: 700;
        font-size: 0.75rem;
      }

      .badge.place-1 {
        background: linear-gradient(135deg, #fde68a, #f59e0b);
        color: #4a3200;
      }

      .badge.place-2 {
        background: linear-gradient(135deg, #f1f5f9, #94a3b8);
        color: #1e293b;
      }

      .badge.place-3 {
        background: linear-gradient(135deg, #fed7aa, #c2410c);
        color: #fff;
      }

      tr.leader .name {
        background: linear-gradient(90deg, var(--ion-color-primary), var(--ion-color-tertiary, #6a64f1));
        -webkit-background-clip: text;
        background-clip: text;
        color: transparent;
      }

      .move {
        display: block;
        font-style: normal;
        font-size: 0.55rem;
        line-height: 1;
        animation: fm-rise 0.4s var(--fm-ease-out) both;
      }

      .move.up {
        color: var(--ion-color-success);
      }

      .move.down {
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

      tr.expandable {
        cursor: pointer;
      }

      tr.breakdown td {
        background: var(--ion-color-step-50, #f7f8fa);
        text-align: left;
      }

      tr.breakdown td.detail {
        padding: 8px 12px 12px 4px;
      }

      .criterion {
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 2px 8px;
        padding: 8px 0;
        border-top: 1px solid var(--ion-color-step-100, #e6e9ee);
        font-size: 0.8rem;
      }

      .combo-stats {
        margin-top: 18px;
      }

      .combo-tabs {
        display: flex;
        gap: 6px;
        margin: 0 16px 8px;

        button {
          min-height: 36px;
          padding: 6px 14px;
          border: 1.5px solid var(--ion-color-step-150, #dfe2e6);
          border-radius: 999px;
          background: var(--ion-background-color, #fff);
          color: var(--ion-text-color);
          font: inherit;
          font-size: 0.85rem;
          cursor: pointer;

          &.on {
            border-color: var(--ion-color-primary);
            background: color-mix(in srgb, var(--ion-color-primary) 12%, transparent);
            color: var(--ion-color-primary);
            font-weight: 700;
          }
        }
      }

      .empty-cell {
        color: var(--ion-color-medium);
        text-align: center;
      }

      .criterion p,
      .entry {
        grid-column: 1 / -1;
        margin: 0;
        color: var(--ion-color-medium);
        text-align: left;
      }

      .entry-delete {
        margin-left: 6px;
        padding: 2px 4px;
        border: none;
        background: transparent;
        color: var(--ion-color-danger);
        vertical-align: middle;
        cursor: pointer;
      }
    `,
  ],
})
export class CompetitionStandingsComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly realtime = inject(RealtimeService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly results = inject(ResultsService);
  private readonly alerts = inject(AlertController);
  private readonly toasts = inject(ToastController);

  readonly deleting = signal(false);

  canScore(): boolean {
    const role = this.competition().my_role;
    return role === 'owner' || role === 'admin' || role === 'scorer';
  }

  openFixture(fixture: Fixture): void {
    void this.router.navigate(['/tabs/competitions', this.competition().id, 'fixtures', fixture.id]);
  }

  /** Delete one logged entry after a confirmation; the table is worked out again. */
  async confirmDeleteEntry(
    who: string,
    criterion: CriterionBreakdown,
    entry: CriterionBreakdown['entries'][number],
  ): Promise<void> {
    const official = this.competition().settings_json?.['official_results'] === true;
    const alert = await this.alerts.create({
      header: 'Delete this score?',
      message: `${who} · ${criterion.name}: ${this.trim(entry.awarded)} pts${entry.note ? ' (' + entry.note + ')' : ''}. The table is worked out again.`,
      inputs: official
        ? [{ name: 'reason', type: 'textarea', placeholder: 'Why is it being removed? This is logged.' }]
        : [],
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        {
          text: 'Delete',
          role: 'destructive',
          handler: (values: { reason?: string } | undefined) => {
            const reason = (values?.reason ?? '').trim();
            if (official && !reason) {
              void this.notify('Give a reason; changes to an official result are logged.', 'danger');
              return false;
            }
            this.deleting.set(true);
            this.api.deleteEvent(entry.fixture_id, entry.id, reason || undefined).subscribe({
              next: () => {
                this.deleting.set(false);
                void this.notify('Score deleted. The table is updated.', 'success');
                this.load(false);
              },
              error: (err: unknown) => {
                this.deleting.set(false);
                void this.notify(extractErrorMessage(err, 'Could not delete that score.'), 'danger');
              },
            });
            return true;
          },
        },
      ],
    });
    await alert.present();
  }

  private async notify(message: string, color: string): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2200, position: 'bottom' });
    await toast.present();
  }

  readonly competition = input.required<CompetitionDetail>();
  readonly statOptions = computed(() => {
    const roles =
      (this.competition().settings_json?.['result_config'] as { roles?: Record<string, string> } | undefined)
        ?.roles ?? {};
    return [
      { key: 'horse' as const, label: roles['horse'] ?? 'Horses' },
      { key: 'rider' as const, label: roles['rider'] ?? 'Riders' },
      { key: 'trainer' as const, label: roles['trainer'] ?? 'Trainers' },
    ];
  });
  readonly statsBy = signal<'horse' | 'rider' | 'trainer'>('horse');
  readonly stats = signal<CombinationStatRow[]>([]);

  readonly rows = signal<StandingRow[]>([]);
  readonly breakdown = signal<Record<string, CriterionBreakdown[]>>({});
  readonly expanded = signal<string | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly stageId = signal<string | null>(null);

  /** Who just moved or scored, so the table can flash and show an arrow for a moment. */
  readonly changes = signal<Record<string, { delta: number; points: boolean }>>({});
  readonly skeletonRows = [0, 1, 2, 3, 4];
  private previous = new Map<string, { position: number; points: string }>();
  private clearTimer: ReturnType<typeof setTimeout> | undefined;

  readonly scoringGuide = computed(() =>
    this.competition().scoring_categories.filter((category) => category.affects_score),
  );

  ngOnInit(): void {
    this.load();

    // Standings are recomputed by a worker, so the table can lag a completed
    // fixture by a moment. Debounce so a burst of events causes one refetch.
    this.realtime
      .onAny(['standings.updated', 'standings.stale'])
      .pipe(debounceTime(400), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.load(false));
  }

  load(showSpinner = true): void {
    if (showSpinner) this.loading.set(true);
    this.error.set(null);

    this.api
      .getStandings(this.competition().id, { stage: this.stageId(), refresh: true })
      .subscribe({
        next: (response) => {
          this.noteChanges(response.rows);
          this.rows.set(response.rows);
          if (this.combinations()) this.loadStats();
          if (this.keepsPlayerStats()) this.loadPlayerStats();
          this.breakdown.set(response.breakdown ?? {});
          this.loading.set(false);
        },
        error: (err: unknown) => {
          this.error.set(extractErrorMessage(err));
          this.loading.set(false);
        },
      });
  }

  private noteChanges(next: StandingRow[]): void {
    const changed: Record<string, { delta: number; points: boolean }> = {};
    if (this.previous.size) {
      for (const row of next) {
        const before = this.previous.get(row.participant.id);
        if (!before) continue;
        const delta = before.position - row.position;
        const points = before.points !== row.points;
        if (delta !== 0 || points) changed[row.participant.id] = { delta, points };
      }
    }
    this.previous = new Map(
      next.map((row) => [row.participant.id, { position: row.position, points: row.points }]),
    );
    clearTimeout(this.clearTimer);
    this.changes.set(changed);
    if (Object.keys(changed).length) {
      this.clearTimer = setTimeout(() => this.changes.set({}), 3500);
    }
  }

  selectStage(value: string | null): void {
    this.stageId.set(value ?? null);
    this.load();
  }

  advancesCount(): number {
    const stage = this.competition().stages.find((candidate) => candidate.id === this.stageId());
    return stage?.advances_count ?? 0;
  }

  pointsTable(): boolean {
    return !this.seriesTable() && isPointsTable(this.competition());
  }

  showsRounds(): boolean {
    if (this.pointsTable() || this.seriesTable()) return false;
    const format = this.competition().format;
    return format === 'league' || format === 'ladder' || format === 'group_knockout';
  }

  showsBonus(): boolean {
    return tableBonusEnabled(this.competition()) || this.rows().some((row) => Number(row.bonus_points) !== 0);
  }

  leagueGuide(): string {
    const raw = this.competition().settings_json?.['league_points'];
    if (!raw || typeof raw !== 'object') return '';
    const points = raw as Record<string, number>;
    const parts: string[] = [];
    if (points['win'] != null) parts.push(`win ${points['win']}`);
    if (points['draw'] != null) parts.push(`draw ${points['draw']}`);
    if (points['loss'] != null) parts.push(`loss ${points['loss']}`);
    if (points['extra_time_win'] != null) parts.push(`extra-time win ${points['extra_time_win']}`);
    if (points['penalty_win'] != null) parts.push(`penalty win ${points['penalty_win']}`);
    return parts.join(', ');
  }

  bonusGuide(): string {
    const bonus = tableBonusOf(this.competition());
    if (!bonus?.enabled) return '';
    const parts: string[] = [];
    if (bonus.scoring_threshold) {
      const codes = bonus.scoring_codes?.length ? bonus.scoring_codes : bonus.scoring_code ? [bonus.scoring_code] : [];
      const names = codes
        .map((code) => this.competition().scoring_categories.find((item) => item.code === code)?.name || code)
        .filter(Boolean);
      const of = names.join(' / ') || 'match score';
      parts.push(`+${bonus.scoring_points ?? 0} for ${bonus.scoring_threshold}+ ${of}`);
    }
    if (bonus.win_margin) {
      parts.push(`+${bonus.win_points ?? 0} for winning by ${bonus.win_margin}`);
    }
    if (bonus.loss_margin) {
      parts.push(`+${bonus.loss_points ?? 0} for losing by ${bonus.loss_margin} or fewer`);
    }
    return parts.join(', ');
  }

  /** Competitions ranked per event (races, classes, rides) show a series table. */
  seriesTable(): boolean {
    return Boolean(this.competition().settings_json?.['result_type']);
  }

  combinations(): boolean {
    return this.competition().settings_json?.['participant_type'] === 'combination';
  }

  statLabel(): string {
    return this.statOptions().find((option) => option.key === this.statsBy())?.label.replace(/s$/, '') ?? '';
  }

  readonly playerStats = signal<PlayerStatsTable | null>(null);

  keepsPlayerStats(): boolean {
    const columns = this.competition().settings_json?.['player_stats'];
    return Array.isArray(columns) && columns.length > 0;
  }

  private loadPlayerStats(): void {
    this.api.playerStats(this.competition().id).subscribe({
      next: (table) => this.playerStats.set(table),
      error: () => this.playerStats.set(null),
    });
  }

  headStartTable(): boolean {
    const source = this.competition().settings_json?.['head_start'];
    return !!source && typeof source === 'object' && Object.keys(source).length > 0;
  }

  netDifference(row: StandingRow): string {
    const value = (row.detail as Record<string, unknown> | undefined)?.['net_score_difference'];
    return value === undefined || value === null ? row.score_difference : String(value);
  }

  showsPrize(): boolean {
    return this.stats().some((row) => row.prize !== undefined);
  }

  seriesBlurb(): string {
    const tiebreakers = this.competition().points_policy?.tiebreakers ?? [];
    if (tiebreakers[0] === 'wins') {
      return 'A championship table: ranked by wins, then seconds, then thirds. Entrants that do not finish never score.';
    }
    return 'A series table: each confirmed event awards placing points. Eliminations and withdrawals never score.';
  }

  loadStats(by: 'horse' | 'rider' | 'trainer' = this.statsBy()): void {
    this.statsBy.set(by);
    this.results.stats(this.competition().id, by).subscribe({
      next: (response) => this.stats.set(response.rows),
      error: () => this.stats.set([]),
    });
  }

  toggle(participantId: string): void {
    this.expanded.update((current) => (current === participantId ? null : participantId));
  }

  breakdownFor(participantId: string): CriterionBreakdown[] {
    return this.breakdown()[participantId] ?? [];
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
      placings: 'most wins, then seconds, then thirds',
      seconds: 'second places',
      thirds: 'third places',
      net_score_difference: 'goal difference without handicap goals',
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
