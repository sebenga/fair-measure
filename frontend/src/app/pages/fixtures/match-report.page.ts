import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import {
  IonBackButton,
  IonButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonTitle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import { createOutline, printOutline } from 'ionicons/icons';

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';
import type { LineupPlayer, MatchReportData } from '../../core/models';

interface ReportDraft {
  summary: string;
  attendance: string;
  conditions: string;
  incidents: string;
  injuries: string;
}

/** The post-match report: the recorded facts of the match plus the officials' account. */
@Component({
  selector: 'fm-match-report',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [
    DatePipe,
    IonHeader,
    IonToolbar,
    IonTitle,
    IonButtons,
    IonBackButton,
    IonButton,
    IonIcon,
    IonContent,
  ],
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start">
          <ion-back-button [defaultHref]="backHref()" />
        </ion-buttons>
        <ion-title>Match report</ion-title>
        <ion-buttons slot="end">
          @if (data()?.can_edit && !draft()) {
            <ion-button (click)="edit()" aria-label="Edit report">
              <ion-icon slot="icon-only" name="create-outline" />
            </ion-button>
          }
          <ion-button (click)="print()" aria-label="Print or save as PDF">
            <ion-icon slot="icon-only" name="print-outline" />
          </ion-button>
        </ion-buttons>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="fm-card sheet"><span class="fm-skeleton" style="height: 80px"></span></div>
      } @else if (error()) {
        <div class="fm-empty">
          <h3>Could not load the report</h3>
          <p>{{ error() }}</p>
        </div>
      } @else if (data(); as r) {
        <article class="fm-card sheet">
          <header class="title">
            <p class="eyebrow">{{ r.fixture.competition }}{{ r.fixture.label ? ' · ' + r.fixture.label : '' }}</p>
            <div class="result">
              @for (side of r.sides; track side.side_id; let last = $last) {
                <div class="team" [class.won]="side.outcome === 'win'">
                  <span class="name">{{ side.name }}</span>
                  <span class="score">{{ side.score }}</span>
                  @if (side.forfeited) {
                    <span class="ff">forfeit</span>
                  }
                </div>
                @if (!last) {
                  <span class="dash">–</span>
                }
              }
            </div>
            <p class="meta">
              @if (r.fixture.scheduled_at) {
                {{ r.fixture.scheduled_at | date: 'EEE d MMM y, HH:mm' }}
              }
              @if (r.fixture.location) {
                · {{ r.fixture.location }}
              }
              @if (r.fixture.duration_minutes) {
                · {{ r.fixture.duration_minutes }} min
              }
            </p>
            @if (!r.finished) {
              <p class="notice no-print">The report is written once the result is in. These are the facts so far.</p>
            }
          </header>

          <section>
            <h4>Officials' report</h4>
            @if (draft(); as d) {
              <form class="form no-print" (submit)="save($event)">
                <label>
                  Summary
                  <textarea
                    rows="5"
                    required
                    placeholder="How the match went, key moments, the result."
                    [value]="d.summary"
                    (input)="set('summary', $event)"
                  ></textarea>
                </label>
                <div class="pair">
                  <label>
                    Attendance
                    <input type="number" min="0" inputmode="numeric" [value]="d.attendance" (input)="set('attendance', $event)" />
                  </label>
                  <label>
                    Conditions
                    <input placeholder="Weather and pitch" [value]="d.conditions" (input)="set('conditions', $event)" />
                  </label>
                </div>
                <label>
                  Disciplinary and incidents
                  <textarea rows="3" placeholder="Misconduct, crowd, stoppages" [value]="d.incidents" (input)="set('incidents', $event)"></textarea>
                </label>
                <label>
                  Injuries
                  <textarea rows="3" placeholder="Who, when, treatment" [value]="d.injuries" (input)="set('injuries', $event)"></textarea>
                </label>
                <div class="actions">
                  <button type="button" class="ghost" [disabled]="saving()" (click)="draft.set(null)">Cancel</button>
                  <button type="submit" class="primary" [disabled]="saving()">Submit report</button>
                </div>
              </form>
            } @else if (r.report; as report) {
              <p class="summary">{{ report.summary }}</p>
              <dl class="facts">
                @if (report.attendance !== null) {
                  <dt>Attendance</dt>
                  <dd>{{ report.attendance }}</dd>
                }
                @if (report.conditions) {
                  <dt>Conditions</dt>
                  <dd>{{ report.conditions }}</dd>
                }
                @if (report.incidents) {
                  <dt>Incidents</dt>
                  <dd class="pre">{{ report.incidents }}</dd>
                }
                @if (report.injuries) {
                  <dt>Injuries</dt>
                  <dd class="pre">{{ report.injuries }}</dd>
                }
              </dl>
              <p class="signed">
                Submitted by {{ report.written_by || 'an official' }}
                @if (report.submitted_at) {
                  · {{ report.submitted_at | date: 'd MMM y, HH:mm' }}
                }
              </p>
            } @else {
              <p class="muted">No report has been written yet.</p>
              @if (r.can_edit) {
                <div class="actions no-print">
                  <button type="button" class="primary" (click)="edit()">Write the report</button>
                </div>
              }
            }
          </section>

          @if (r.goals.length) {
            <section>
              <h4>Scoring</h4>
              <ul class="events">
                @for (goal of r.goals; track $index) {
                  <li>
                    <span class="min">{{ goal.minute !== null ? goal.minute + "'" : '' }}</span>
                    <span><strong>{{ goal.player || goal.team }}</strong> {{ goal.label }}</span>
                    <em>{{ goal.team }}</em>
                  </li>
                }
              </ul>
            </section>
          }

          @if (r.cards.length) {
            <section>
              <h4>Discipline</h4>
              <ul class="events">
                @for (card of r.cards; track $index) {
                  <li>
                    <span class="min">{{ card.minute !== null ? card.minute + "'" : '' }}</span>
                    <span><i class="card" [attr.data-kind]="card.kind" aria-hidden="true"></i> <strong>{{ card.player || '—' }}</strong> {{ card.label }}</span>
                    <em>{{ card.team }}</em>
                  </li>
                }
              </ul>
            </section>
          }

          @if (r.substitutions.length) {
            <section>
              <h4>Substitutions</h4>
              <ul class="events">
                @for (sub of r.substitutions; track sub.id) {
                  <li>
                    <span class="min">{{ sub.minute !== null ? sub.minute + "'" : '' }}</span>
                    <span><strong>{{ sub.player_on.name }}</strong> on for {{ sub.player_off.name }}</span>
                    <em>{{ sub.team }}</em>
                  </li>
                }
              </ul>
            </section>
          }

          @if (hasLineups(r)) {
            <section>
              <h4>Line-ups</h4>
              <div class="lineups">
                @for (side of r.sides; track side.side_id) {
                  <div>
                    <h5>
                      {{ side.name }}
                      @if (side.lineup?.formation) {
                        <small>{{ side.lineup?.formation }}</small>
                      }
                    </h5>
                    @if (side.lineup; as lineup) {
                      <ol>
                        @for (player of lineup.starters; track player.player_id) {
                          <li>{{ line(player) }}{{ lineup.captain_id === player.player_id ? ' (C)' : '' }}</li>
                        }
                      </ol>
                      @if (lineup.bench.length) {
                        <p class="bench-title">Substitutes</p>
                        <ul>
                          @for (player of lineup.bench; track player.player_id) {
                            <li [class.used]="player.on_field || player.subbed_off">{{ line(player) }}</li>
                          }
                        </ul>
                      }
                    } @else {
                      <p class="muted">No team sheet.</p>
                    }
                  </div>
                }
              </div>
            </section>
          }

          @if (r.awards.length || r.referees.length) {
            <section class="pair-sections">
              @if (r.awards.length) {
                <div>
                  <h4>Awards</h4>
                  <ul class="plain">
                    @for (award of r.awards; track award.label) {
                      <li><strong>{{ award.label }}:</strong> {{ award.winner.name }}{{ award.winner.team ? ' (' + award.winner.team + ')' : '' }}</li>
                    }
                  </ul>
                </div>
              }
              @if (r.referees.length) {
                <div>
                  <h4>Officials</h4>
                  <ul class="plain">
                    @for (name of r.referees; track name) {
                      <li>{{ name }}</li>
                    }
                  </ul>
                </div>
              }
            </section>
          }
        </article>
      }
    </ion-content>
  `,
  styles: [
    `
      .sheet {
        display: grid;
        gap: 18px;
        margin: 12px 16px 24px;
        padding: 18px 16px;
      }
      .title {
        text-align: center;
      }
      .eyebrow {
        margin: 0 0 8px;
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: var(--ion-color-medium);
      }
      .result {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 14px;
      }
      .team {
        display: grid;
        gap: 2px;
        min-width: 0;
      }
      .team .name {
        font-weight: 700;
      }
      .team .score {
        font-size: 2rem;
        font-weight: 800;
      }
      .team.won .score {
        color: var(--ion-color-primary);
      }
      .ff {
        font-size: 0.7rem;
        color: var(--ion-color-danger);
      }
      .dash {
        font-size: 1.6rem;
        color: var(--ion-color-medium);
      }
      .meta {
        margin: 8px 0 0;
        font-size: 0.82rem;
        color: var(--ion-color-medium);
      }
      .notice {
        margin: 10px 0 0;
        padding: 8px 10px;
        border-radius: 10px;
        background: color-mix(in srgb, var(--ion-color-warning) 18%, transparent);
        font-size: 0.82rem;
      }
      section {
        display: grid;
        gap: 8px;
        padding-top: 14px;
        border-top: 1px solid var(--ion-color-step-100, #eef0f3);
      }
      h4 {
        margin: 0;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: var(--ion-color-primary);
      }
      h5 {
        margin: 0 0 6px;
        font-size: 0.95rem;
      }
      h5 small {
        margin-left: 6px;
        font-weight: 600;
        color: var(--ion-color-medium);
      }
      .summary,
      .pre {
        white-space: pre-wrap;
      }
      .summary {
        margin: 0;
        line-height: 1.5;
      }
      .facts {
        display: grid;
        grid-template-columns: max-content 1fr;
        gap: 6px 12px;
        margin: 0;
        font-size: 0.88rem;
      }
      .facts dt {
        font-weight: 700;
        color: var(--ion-color-medium);
      }
      .facts dd {
        margin: 0;
      }
      .signed,
      .muted {
        margin: 0;
        font-size: 0.8rem;
        color: var(--ion-color-medium);
      }
      .events {
        display: grid;
        gap: 6px;
        margin: 0;
        padding: 0;
        list-style: none;
        font-size: 0.88rem;
      }
      .events li {
        display: grid;
        grid-template-columns: 36px 1fr auto;
        gap: 8px;
        align-items: baseline;
      }
      .events .min {
        font-weight: 800;
        color: var(--ion-color-primary);
      }
      .events em {
        font-style: normal;
        font-size: 0.76rem;
        color: var(--ion-color-medium);
      }
      .card {
        display: inline-block;
        width: 9px;
        height: 12px;
        border-radius: 2px;
        vertical-align: -1px;
        background: var(--ion-color-medium);
      }
      .card[data-kind='yellow'] {
        background: #facc15;
      }
      .card[data-kind='red'] {
        background: #dc2626;
      }
      .lineups,
      .pair-sections {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 16px;
      }
      .lineups ol,
      .lineups ul,
      .plain {
        margin: 0;
        padding-left: 18px;
        font-size: 0.86rem;
        line-height: 1.55;
      }
      .plain {
        padding-left: 0;
        list-style: none;
      }
      .bench-title {
        margin: 8px 0 2px;
        font-size: 0.76rem;
        font-weight: 700;
        color: var(--ion-color-medium);
      }
      .used {
        font-weight: 700;
      }
      .form {
        display: grid;
        gap: 10px;
      }
      .form label {
        display: grid;
        gap: 4px;
        font-size: 0.76rem;
        font-weight: 650;
        color: var(--ion-color-medium);
      }
      .form input,
      .form textarea {
        width: 100%;
        padding: 8px 10px;
        border: 1px solid var(--ion-color-step-200, #d7d8da);
        border-radius: 10px;
        background: var(--ion-background-color, #fff);
        color: var(--ion-text-color);
        font: inherit;
        font-size: 0.92rem;
      }
      .pair {
        display: grid;
        grid-template-columns: 1fr 2fr;
        gap: 10px;
      }
      .actions {
        display: flex;
        justify-content: flex-end;
        gap: 8px;
      }
      .actions button {
        padding: 9px 16px;
        border: 0;
        border-radius: 999px;
        font: inherit;
        font-weight: 700;
        cursor: pointer;
      }
      .actions button:disabled {
        opacity: 0.5;
      }
      .actions .primary {
        background: var(--ion-color-primary);
        color: var(--ion-color-primary-contrast);
      }
      .actions .ghost {
        background: var(--ion-color-light);
        color: var(--ion-color-light-contrast);
      }
      @media print {
        .sheet {
          margin: 0;
          padding: 0;
          color: #000;
        }
        .no-print {
          display: none !important;
        }
      }
    `,
  ],
})
export class MatchReportPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly toasts = inject(ToastController);

  private competitionId = '';
  private fixtureId = '';

  readonly data = signal<MatchReportData | null>(null);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly draft = signal<ReportDraft | null>(null);

  constructor() {
    addIcons({ createOutline, printOutline });
  }

  ngOnInit(): void {
    this.competitionId = this.route.snapshot.paramMap.get('competitionId') ?? '';
    this.fixtureId = this.route.snapshot.paramMap.get('fixtureId') ?? '';
    this.api.matchReport(this.competitionId, this.fixtureId).subscribe({
      next: (data) => {
        this.data.set(data);
        this.loading.set(false);
        if (data.can_edit && !data.report) this.edit();
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err));
        this.loading.set(false);
      },
    });
  }

  backHref(): string {
    return `/tabs/competitions/${this.competitionId}/fixtures/${this.fixtureId}`;
  }

  hasLineups(report: MatchReportData): boolean {
    return report.sides.some((side) => !!side.lineup);
  }

  line(player: LineupPlayer): string {
    const number = player.number !== null ? `${player.number}. ` : '';
    const position = player.position ? ` (${player.position})` : '';
    return `${number}${player.name}${position}`;
  }

  edit(): void {
    const report = this.data()?.report;
    this.draft.set({
      summary: report?.summary ?? '',
      attendance: report?.attendance !== null && report?.attendance !== undefined ? String(report.attendance) : '',
      conditions: report?.conditions ?? '',
      incidents: report?.incidents ?? '',
      injuries: report?.injuries ?? '',
    });
  }

  set(field: keyof ReportDraft, event: Event): void {
    const draft = this.draft();
    if (!draft) return;
    this.draft.set({ ...draft, [field]: (event.target as HTMLInputElement | HTMLTextAreaElement).value });
  }

  save(event: Event): void {
    event.preventDefault();
    const draft = this.draft();
    if (!draft || this.saving()) return;
    this.saving.set(true);
    this.api
      .saveMatchReport(this.competitionId, this.fixtureId, {
        ...draft,
        attendance: draft.attendance === '' ? null : draft.attendance,
      })
      .subscribe({
        next: async (data) => {
          this.saving.set(false);
          this.data.set(data);
          this.draft.set(null);
          const toast = await this.toasts.create({ message: 'Report submitted.', duration: 2000, color: 'success' });
          await toast.present();
        },
        error: async (err: unknown) => {
          this.saving.set(false);
          const toast = await this.toasts.create({
            message: extractErrorMessage(err, 'Could not submit the report.'),
            duration: 3000,
            color: 'danger',
          });
          await toast.present();
        },
      });
  }

  print(): void {
    window.print();
  }
}
