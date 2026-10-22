import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  effect,
  inject,
  input,
  signal,
  untracked,
} from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AlertController, IonIcon, ToastController } from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import {
  arrowDownOutline,
  arrowUpOutline,
  ribbonOutline,
  swapHorizontalOutline,
  trashOutline,
} from 'ionicons/icons';

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';
import type {
  FormationSlot,
  LineupPlayer,
  MatchDay,
  MatchPlayer,
  SubstitutionRecord,
  TeamSheetSide,
} from '../../core/models';

const KITS: Array<[string, string]> = [
  ['#c81e1e', '#fff'],
  ['#1d4ed8', '#fff'],
  ['#111827', '#fff'],
  ['#f8fafc', '#111827'],
  ['#15803d', '#fff'],
  ['#eab308', '#111827'],
  ['#7c3aed', '#fff'],
  ['#ea580c', '#fff'],
  ['#0f766e', '#fff'],
  ['#be185d', '#fff'],
];
import { RealtimeService } from '../../core/realtime.service';

interface Draft {
  sideId: string;
  formation: string;
  /** Formation slot index to player id. */
  slots: Record<number, string>;
  /** Starters when the competition has no formations. */
  starters: string[];
  bench: string[];
  captain: string;
  numbers: Record<string, string>;
}

/** Team sheets (formation, starters, bench) and the substitutions made during the match. */
@Component({
  selector: 'fm-match-day',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [IonIcon, NgTemplateOutlet],
  template: `
    @if (day()?.enabled === false && part() !== 'subs') {
      <div class="fm-empty compact"><p>This competition does not use team sheets.</p></div>
    }

    <ng-template #sheetView let-side>
      @if (side.lineup; as lineup) {
        @if (lineup.slots.length) {
          <div class="pitch" [attr.aria-label]="side.name + ' line-up'">
            @for (row of rows(lineup.slots); track $index) {
              <div class="pitch-row">
                @for (slot of row; track slot.index) {
                  @if (starterAt(side, slot.index); as player) {
                    <div
                      class="shirt"
                      [class.captain]="lineup.captain_id === player.player_id"
                      [class.off]="player.subbed_off || player.sent_off"
                      [style.--kit]="kit(side.participant_id)[0]"
                      [style.--kit-ink]="kit(side.participant_id)[1]"
                    >
                      <span class="kit">{{ player.number ?? '' }}</span>
                      <span class="who">
                        <b>{{ shortName(player.name) }}</b>
                        @if (lineup.captain_id === player.player_id) {
                          <ion-icon name="ribbon-outline" class="mark" aria-label="Captain" />
                        }
                        @if (sheetMeta(player); as meta) {
                          <small>{{ meta }}</small>
                        }
                      </span>
                    </div>
                  } @else {
                    <div class="empty">
                      <span class="kit hollow">–</span>
                      <small>{{ slot.label }}</small>
                    </div>
                  }
                }
              </div>
            }
          </div>
        } @else {
          <ul class="list">
            @for (player of lineup.starters; track player.player_id) {
              <li [class.off]="player.subbed_off">
                <span class="num">{{ player.number ?? '' }}</span>
                <span class="who">
                  <b>{{ player.name }}</b>
                  @if (sheetMeta(player); as meta) {
                    <small>{{ meta }}</small>
                  }
                </span>
                @if (lineup.captain_id === player.player_id) {
                  <ion-icon name="ribbon-outline" class="mark" aria-label="Captain" />
                }
              </li>
            }
          </ul>
        }
        <p class="hint">Bench</p>
        <div class="bench-row">
          @for (player of lineup.bench; track player.player_id) {
            <div
              class="shirt bench-shirt"
              [class.used]="player.on_field || player.subbed_off"
              [style.--kit]="kit(side.participant_id)[0]"
              [style.--kit-ink]="kit(side.participant_id)[1]"
            >
              <span class="kit slim">{{ player.number ?? '' }}</span>
              <span class="who">
                <b>{{ shortName(player.name) }}</b>
                @if (sheetMeta(player); as meta) {
                  <small>{{ meta }}</small>
                }
              </span>
            </div>
          } @empty {
            <p class="muted">No substitutes named.</p>
          }
        </div>
      } @else {
        <p class="muted">{{ side.name }} have not picked their team yet.</p>
      }
      @if (side.can_edit) {
        <div class="actions">
          <button type="button" class="primary" (click)="edit(side)">
            {{ side.lineup ? 'Edit team sheet' : 'Pick team' }}
          </button>
        </div>
      } @else if (!side.lineup) {
        <p class="hint">The team's manager, the referee or an admin picks the team.</p>
      } @else if (status() !== 'scheduled' && status() !== 'postponed') {
        <p class="hint">The team sheet is locked after kickoff.</p>
      }
    </ng-template>

    @if (day()?.enabled && sides().length && part() !== 'subs') {
      <h3 class="fm-section-title">Team sheets</h3>
      <p class="hint">
        Both teams must submit a team sheet of at least {{ sheetMinimum() }} before kickoff. Officials
        must be picked on Setup.
      </p>
      <div class="fm-team-columns" [class.many]="sides().length > 2" [class.editing]="!!draft()">
        @for (side of sides(); track side.side_id) {
          <div class="fm-card sheet" [class.edit]="draft()?.sideId === side.side_id">
            <span class="fm-team-head">
              {{ side.name }}
              @if (side.lineup?.formation) {
                <small>{{ side.lineup?.formation }}</small>
              }
            </span>
            @if (draft(); as d) {
              @if (d.sideId === side.side_id) {
      <div class="editor">
        @if (formationKeys().length) {
          <label class="field">
            Formation
            <select [value]="d.formation" (change)="setFormation(value($event))">
              @for (key of formationKeys(); track key) {
                <option [value]="key" [selected]="key === d.formation">{{ key }}</option>
              }
            </select>
          </label>
        } @else {
          <label class="field">
            Formation (optional)
            <input [value]="d.formation" placeholder="e.g. 3-2-1" (change)="setFreeFormation(value($event))" />
          </label>
        }

        @if (draftSlots().length) {
          <div class="pitch editing" aria-label="Starting positions">
            @for (row of rows(draftSlots()); track $index) {
              <div class="pitch-row">
                @for (slot of row; track slot.index) {
                  <label class="slot" [class.empty]="!d.slots[slot.index]">
                    <span class="pos">{{ slot.label || 'Pos ' + (slot.index + 1) }}</span>
                    <select
                      [attr.aria-label]="(slot.label || 'Position') + ' ' + (slot.index + 1)"
                      (change)="assignSlot(slot.index, value($event))"
                    >
                      <option value="" [selected]="!d.slots[slot.index]">Pick</option>
                      @for (player of slotChoices(slot.index); track player.player_id) {
                        <option [value]="player.player_id" [selected]="d.slots[slot.index] === player.player_id">
                          {{ label(player) }}
                        </option>
                      }
                    </select>
                  </label>
                }
              </div>
            }
          </div>
        } @else {
          <p class="hint">
            Starters
            @if (sheetMinimum(); as needed) {
              ({{ d.starters.length }} of {{ needed }})
            }
          </p>
          <div class="chips">
            @for (player of side.squad; track player.player_id) {
              <button
                type="button"
                class="pick"
                [class.on]="d.starters.includes(player.player_id)"
                (click)="toggleStarter(player.player_id)"
              >
                {{ label(player) }}
              </button>
            }
          </div>
        }

        <p class="hint">
          Bench
          @if (config()?.bench_max !== null && config()?.bench_max !== undefined) {
            ({{ d.bench.length }} of {{ config()?.bench_max }})
          }
        </p>
        <div class="chips">
          @for (player of benchChoices(); track player.player_id) {
            <button
              type="button"
              class="pick"
              [class.on]="d.bench.includes(player.player_id)"
              (click)="toggleBench(player.player_id)"
            >
              {{ label(player) }}
            </button>
          } @empty {
            <span class="muted">Everyone in the squad is starting.</span>
          }
        </div>

        <label class="field">
          Captain
          <select (change)="setCaptain(value($event))">
            <option value="" [selected]="!d.captain">No captain</option>
            @for (player of draftStarters(); track player.player_id) {
              <option [value]="player.player_id" [selected]="d.captain === player.player_id">
                {{ player.name }}
              </option>
            }
          </select>
        </label>

        @if (draftNamed().length) {
          <details class="numbers">
            <summary>Shirt numbers</summary>
            @for (player of draftNamed(); track player.player_id) {
              <label>
                <span>{{ player.name }}</span>
                <input
                  type="number"
                  min="0"
                  inputmode="numeric"
                  [value]="numberFor(player.player_id)"
                  (change)="setNumber(player.player_id, value($event))"
                />
              </label>
            }
          </details>
        }

        <div class="actions">
          <button type="button" class="ghost" [disabled]="busy()" (click)="autoFill()">Auto-fill</button>
          <button type="button" class="ghost" [disabled]="busy()" (click)="cancel()">Cancel</button>
          <button type="button" class="primary" [disabled]="busy()" (click)="save()">Save team sheet</button>
        </div>
      </div>
              } @else {
                <ng-container *ngTemplateOutlet="sheetView; context: { $implicit: side }" />
              }
            } @else {
              <ng-container *ngTemplateOutlet="sheetView; context: { $implicit: side }" />
            }
          </div>
        }
      </div>
    }

    @if (day()?.enabled && sides().length && part() !== 'sheets' && showSubstitutions()) {
      <h3 class="fm-section-title">
        Substitutions
        @if (subs().length) {
          <span class="count">{{ subs().length }}</span>
        }
      </h3>
      <div class="fm-team-columns" [class.many]="sides().length > 2">
        @for (side of sides(); track side.side_id) {
          <div class="fm-card subs">
            <span class="fm-team-head">{{ side.name }}</span>
            <p class="used">
              {{ side.substitutions_used }}
              @if (config()?.max_substitutions; as limit) {
                of {{ limit }}
              }
              used
            </p>

            @if (day()?.can_substitute) {
              @if (side.lineup) {
                @if (side.substitutions_left !== 0) {
                  <div class="sub-form">
                    <label class="field">
                      Off
                      <select (change)="setSub(side.side_id, 'off', value($event))">
                        <option value="" [selected]="!subFor(side.side_id).off">Coming off</option>
                        @for (player of onField(side); track player.player_id) {
                          <option [value]="player.player_id" [selected]="subFor(side.side_id).off === player.player_id">{{ label(player) }}</option>
                        }
                      </select>
                    </label>
                    <label class="field">
                      On
                      <select (change)="setSub(side.side_id, 'on', value($event))">
                        <option value="" [selected]="!subFor(side.side_id).on">Coming on</option>
                        @for (player of available(side); track player.player_id) {
                          <option [value]="player.player_id" [selected]="subFor(side.side_id).on === player.player_id">{{ label(player) }}</option>
                        }
                      </select>
                    </label>
                    <div class="row">
                      <label class="field">
                        Minute
                        <input
                          type="number"
                          min="0"
                          inputmode="numeric"
                          [value]="subMinute()"
                          (input)="setMinute(value($event))"
                        />
                      </label>
                      <label class="field">
                        Reason
                        <select (change)="setSub(side.side_id, 'reason', value($event))">
                          @for (reason of day()?.reasons ?? []; track reason.key) {
                            <option [value]="reason.key" [selected]="subFor(side.side_id).reason === reason.key">{{ reason.label }}</option>
                          }
                        </select>
                      </label>
                    </div>
                    <button
                      type="button"
                      class="record"
                      [disabled]="busy() || !subFor(side.side_id).off || !subFor(side.side_id).on"
                      (click)="substitute(side)"
                    >
                      <ion-icon name="swap-horizontal-outline" aria-hidden="true" />
                      Record
                    </button>
                  </div>
                } @else {
                  <p class="hint">All substitutions used.</p>
                }
              } @else {
                <p class="hint">Pick the team sheet first.</p>
              }
            }

            @if (part() !== 'subs') {
              @for (sub of subsFor(side.side_id); track sub.id) {
                <div class="sub">
                  <span class="minute">{{ sub.minute !== null ? sub.minute + "'" : '–' }}</span>
                  <span class="detail">
                    <span class="on"><ion-icon name="arrow-up-outline" aria-label="On" /> {{ sub.player_on.name }}</span>
                    <span class="off"><ion-icon name="arrow-down-outline" aria-label="Off" /> {{ sub.player_off.name }}</span>
                    <em>{{ reasonLabel(sub.reason) }}</em>
                  </span>
                  @if (day()?.can_substitute) {
                    <button
                      type="button"
                      class="undo"
                      [disabled]="busy()"
                      [attr.aria-label]="'Delete substitution of ' + sub.player_off.name"
                      (click)="confirmDelete(sub)"
                    >
                      <ion-icon name="trash-outline" />
                    </button>
                  }
                </div>
              } @empty {
                <p class="muted">No substitutions yet.</p>
              }
            }
          </div>
        }
      </div>
    }
  `,
  styles: [
    `
      .sheet,
      .subs {
        padding: 12px;
        display: grid;
        align-content: start;
        gap: 10px;
      }
      .fm-team-head small {
        margin-left: 6px;
        font-weight: 600;
        letter-spacing: 0;
        color: var(--ion-color-medium);
      }
      @media (max-width: 419px) {
        .pitch {
          gap: 12px;
          padding: 12px 8px 14px;
        }
        .kit {
          width: 36px;
          height: 40px;
          font-size: 0.85rem;
        }
        .kit.slim {
          width: 32px;
          height: 36px;
        }
      }
      .record {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        width: 100%;
        padding: 9px 12px;
        border: 0;
        border-radius: 999px;
        background: var(--ion-color-primary);
        color: var(--ion-color-primary-contrast);
        font: inherit;
        font-weight: 700;
        cursor: pointer;
      }
      .record:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .pitch {
        display: flex;
        flex-direction: column;
        gap: 14px;
        padding: 16px 10px 18px;
        border-radius: 16px;
        background:
          radial-gradient(circle at 50% 8%, rgb(255 255 255 / 0.14), transparent 28%),
          repeating-linear-gradient(0deg, rgb(255 255 255 / 0.06) 0 28px, transparent 28px 56px),
          linear-gradient(180deg, #15803d, #166534);
        color: #fff;
      }
      .pitch-row {
        display: flex;
        justify-content: center;
        align-items: flex-start;
        gap: 8px;
      }
      .shirt {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        position: relative;
        min-width: 0;
        flex: 1 1 0;
        max-width: 76px;
        overflow: hidden;
      }
      .kit {
        position: relative;
        display: grid;
        place-items: center;
        flex: 0 0 auto;
        width: 42px;
        height: 46px;
        border-radius: 10px 10px 14px 14px;
        background: var(--kit, #1d4ed8);
        color: var(--kit-ink, #fff);
        font-size: 0.95rem;
        font-weight: 800;
        line-height: 1;
        box-shadow: 0 6px 14px rgb(0 0 0 / 25%);
      }
      .kit.slim {
        width: 36px;
        height: 40px;
        font-size: 0.85rem;
      }
      .kit.hollow {
        background: transparent;
        color: #fff;
        border: 2px dashed rgb(255 255 255 / 70%);
        box-shadow: none;
      }
      .who {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        width: 100%;
        min-width: 0;
        padding: 5px 4px 6px;
        border-radius: 7px;
        background: rgb(15 23 42 / 88%);
        color: #fff;
        text-align: center;
      }
      .who b,
      .who small {
        display: block;
        min-width: 0;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .who b {
        font-size: 0.68rem;
        line-height: 1.15;
      }
      .who small {
        font-size: 0.58rem;
        font-weight: 650;
        letter-spacing: 0.01em;
        opacity: 0.9;
      }
      .mark {
        flex: 0 0 auto;
        width: 14px;
        height: 14px;
        font-size: 14px;
        color: #facc15;
      }
      .shirt.off {
        opacity: 0.55;
      }
      .empty {
        display: grid;
        justify-items: center;
        gap: 6px;
        flex: 1 1 0;
        min-width: 0;
        max-width: 76px;
        color: rgb(255 255 255 / 85%);
        text-align: center;
      }
      .empty small {
        font-size: 0.62rem;
      }
      .bench-row {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        padding: 4px 0 8px;
      }
      .bench-shirt {
        flex: 0 0 72px;
        max-width: 72px;
        overflow: hidden;
      }
      .list .mark {
        color: var(--ion-color-warning, #facc15);
      }
      .pitch.editing .slot {
        display: grid;
        gap: 3px;
        flex: 1 1 0;
        min-width: 0;
        max-width: 110px;
      }
      .pitch.editing .pos {
        font-size: 0.66rem;
        font-weight: 800;
        letter-spacing: 0.04em;
        text-align: center;
      }
      .pitch.editing select {
        width: 100%;
        padding: 5px 4px;
        border: 0;
        border-radius: 8px;
        background: #fff;
        color: #0f172a;
        font: inherit;
        font-size: 0.72rem;
      }
      .pitch.editing .slot.empty select {
        background: rgb(255 255 255 / 0.75);
      }
      .field {
        display: grid;
        gap: 4px;
        font-size: 0.75rem;
        font-weight: 650;
        color: var(--ion-color-medium);
      }
      .field select,
      .field input,
      .numbers input {
        width: 100%;
        min-height: 40px;
        padding: 6px 10px;
        border: 1px solid var(--ion-color-step-200, #d7d8da);
        border-radius: 10px;
        background: var(--ion-background-color, #fff);
        color: var(--ion-text-color);
        font: inherit;
        font-size: 0.9rem;
      }
      .row {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
        gap: 8px;
      }
      .editor,
      .sub-form {
        display: grid;
        gap: 10px;
      }
      .chips {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .pick {
        padding: 6px 10px;
        border: 1.5px solid var(--ion-color-step-150, #dfe2e6);
        border-radius: 999px;
        background: none;
        color: inherit;
        font: inherit;
        font-size: 0.8rem;
        cursor: pointer;
      }
      .pick.on {
        border-color: var(--ion-color-primary);
        background: var(--ion-color-primary);
        color: var(--ion-color-primary-contrast);
      }
      .numbers {
        display: grid;
        gap: 6px;
        font-size: 0.85rem;
      }
      .numbers summary {
        cursor: pointer;
        font-weight: 650;
      }
      .numbers label {
        display: grid;
        grid-template-columns: 1fr 80px;
        align-items: center;
        gap: 8px;
        margin-top: 6px;
      }
      .numbers input {
        min-height: 34px;
      }
      .actions {
        display: flex;
        flex-wrap: wrap;
        justify-content: flex-end;
        gap: 8px;
      }
      .actions button {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 9px 14px;
        border: 0;
        border-radius: 999px;
        font: inherit;
        font-weight: 700;
        cursor: pointer;
      }
      .actions button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
      .actions .primary {
        background: var(--ion-color-primary);
        color: var(--ion-color-primary-contrast);
      }
      .actions .ghost {
        background: var(--ion-color-light);
        color: var(--ion-color-light-contrast);
      }
      .list {
        display: grid;
        gap: 4px;
        margin: 0;
        padding: 0;
        list-style: none;
        font-size: 0.88rem;
      }
      .list li {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .list .who {
        flex: 1 1 auto;
        padding: 0;
        background: none;
        color: inherit;
        text-align: left;
      }
      .list .who b {
        font-size: 0.88rem;
      }
      .list .who small {
        font-size: 0.72rem;
        color: var(--ion-color-medium);
      }
      .list li.off,
      .list li.used {
        color: var(--ion-color-medium);
      }
      .list .num {
        min-width: 22px;
        font-weight: 800;
        color: var(--ion-color-primary);
      }
      .sub-on {
        color: var(--ion-color-success);
      }
      .hint {
        margin: 0;
        font-size: 0.78rem;
        color: var(--ion-color-medium);
      }
      .muted {
        margin: 0;
        font-size: 0.85rem;
        color: var(--ion-color-medium);
      }
      .used {
        margin: -4px 0 0;
        font-size: 0.78rem;
        color: var(--ion-color-medium);
      }
      .sub {
        display: grid;
        grid-template-columns: 32px 1fr auto;
        align-items: center;
        gap: 10px;
        padding-top: 8px;
        border-top: 1px solid var(--ion-color-step-100, #eef0f3);
      }
      .sub .minute {
        font-weight: 800;
        color: var(--ion-color-primary);
      }
      .sub .detail {
        display: grid;
        gap: 2px;
        font-size: 0.86rem;
      }
      .sub .on ion-icon {
        color: var(--ion-color-success);
      }
      .sub .off ion-icon {
        color: var(--ion-color-danger);
      }
      .sub em {
        font-style: normal;
        font-size: 0.74rem;
        color: var(--ion-color-medium);
      }
      .undo {
        display: grid;
        place-items: center;
        width: 34px;
        height: 34px;
        border: 0;
        border-radius: 50%;
        background: none;
        color: var(--ion-color-danger);
        cursor: pointer;
      }
    `,
  ],
})
export class MatchDayComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly realtime = inject(RealtimeService);
  private readonly alerts = inject(AlertController);
  private readonly toasts = inject(ToastController);
  private readonly destroyRef = inject(DestroyRef);

  readonly competitionId = input.required<string>();
  readonly fixtureId = input.required<string>();
  readonly status = input<string>('scheduled');
  /** The match clock's current minute, used as the default for a substitution. */
  readonly minute = input<number | null>(null);
  /** Which panels to show: everything, only the team sheets, or only substitutions. */
  readonly part = input<'all' | 'sheets' | 'subs'>('all');

  readonly day = signal<MatchDay | null>(null);
  readonly draft = signal<Draft | null>(null);
  readonly busy = signal(false);
  readonly subMinute = signal('');
  readonly subDrafts = signal<Record<string, { off: string; on: string; reason: string }>>({});
  private minuteTouched = false;

  readonly sides = computed(() => this.day()?.sides ?? []);
  readonly config = computed(() => this.day()?.config);
  readonly sheetMinimum = computed(
    () => this.config()?.min_personnel ?? this.config()?.starters ?? 11,
  );
  readonly subs = computed(() => this.day()?.substitutions ?? []);
  readonly formationKeys = computed(() => this.config()?.formations ?? []);
  readonly draftSlots = computed<FormationSlot[]>(() => {
    const draft = this.draft();
    if (!draft) return [];
    return this.day()?.formations?.find((item) => item.key === draft.formation)?.slots ?? [];
  });
  readonly showSubstitutions = computed(
    () =>
      this.status() === 'live' ||
      this.status() === 'completed' ||
      this.status() === 'forfeit' ||
      this.subs().length > 0,
  );

  constructor() {
    addIcons({
      arrowDownOutline,
      arrowUpOutline,
      ribbonOutline,
      swapHorizontalOutline,
      trashOutline,
    });
    effect(() => {
      const minute = this.minute();
      if (!this.minuteTouched) this.subMinute.set(minute === null ? '' : String(minute));
    });
    effect(() => {
      this.status();
      if (untracked(() => this.day())) this.load();
    });
  }

  ngOnInit(): void {
    this.load();
    this.realtime
      .onAny<{ fixture_id: string }>(['fixture.updated'])
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((message) => {
        if (message.payload.fixture_id === this.fixtureId() && !this.draft()) this.load();
      });
  }

  value(event: Event): string {
    return (event.target as HTMLInputElement | HTMLSelectElement).value.trim();
  }

  label(player: MatchPlayer): string {
    return player.number !== null && player.number !== undefined ? `${player.number} · ${player.name}` : player.name;
  }

  shortName(name: string): string {
    const parts = name.trim().split(/\s+/);
    return parts.length > 1 ? parts.slice(1).join(' ') : name;
  }

  kit(teamId: string): [string, string] {
    let hash = 0;
    for (let i = 0; i < teamId.length; i += 1) hash = (hash * 31 + teamId.charCodeAt(i)) >>> 0;
    return KITS[hash % KITS.length];
  }

  minutesLabel(player: LineupPlayer): string {
    return player.minutes == null ? '' : `${player.minutes}'`;
  }

  ratingLabel(player: LineupPlayer): string {
    return player.rating ? player.rating : '';
  }

  sheetMeta(player: LineupPlayer): string {
    return [this.minutesLabel(player), this.ratingLabel(player)].filter(Boolean).join(' · ');
  }

  rows(slots: FormationSlot[]): FormationSlot[][] {
    const byRow = new Map<number, FormationSlot[]>();
    for (const slot of slots) byRow.set(slot.row, [...(byRow.get(slot.row) ?? []), slot]);
    return [...byRow.entries()].sort((a, b) => b[0] - a[0]).map(([, row]) => row);
  }

  starterAt(side: TeamSheetSide, slot: number) {
    return side.lineup?.starters.find((player) => player.slot === slot) ?? null;
  }

  reasonLabel(key: string): string {
    return this.day()?.reasons?.find((reason) => reason.key === key)?.label ?? key;
  }

  // --- Team sheet editing ---

  edit(side: TeamSheetSide): void {
    const lineup = side.lineup;
    const formation = lineup?.formation || this.formationKeys()[0] || '';
    const slots: Record<number, string> = {};
    const starters: string[] = [];
    for (const player of lineup?.starters ?? []) {
      if (player.slot !== null && this.formationKeys().length) slots[player.slot] = player.player_id;
      else starters.push(player.player_id);
    }
    const numbers: Record<string, string> = {};
    for (const player of side.squad) {
      if (player.number !== null) numbers[player.player_id] = String(player.number);
    }
    for (const player of [...(lineup?.starters ?? []), ...(lineup?.bench ?? [])]) {
      numbers[player.player_id] = player.number !== null ? String(player.number) : '';
    }
    this.draft.set({
      sideId: side.side_id,
      formation,
      slots,
      starters,
      bench: (lineup?.bench ?? []).map((player) => player.player_id),
      captain: lineup?.captain_id ?? '',
      numbers,
    });
  }

  cancel(): void {
    this.draft.set(null);
  }

  private squad(): Array<MatchPlayer & { position: string }> {
    const sideId = this.draft()?.sideId;
    return this.sides().find((side) => side.side_id === sideId)?.squad ?? [];
  }

  private startingIds(draft: Draft): string[] {
    return this.draftSlots().length ? Object.values(draft.slots).filter(Boolean) : draft.starters;
  }

  draftStarters(): MatchPlayer[] {
    const draft = this.draft();
    if (!draft) return [];
    const ids = new Set(this.startingIds(draft));
    return this.squad().filter((player) => ids.has(player.player_id));
  }

  draftNamed(): MatchPlayer[] {
    const draft = this.draft();
    if (!draft) return [];
    const ids = new Set([...this.startingIds(draft), ...draft.bench]);
    return this.squad().filter((player) => ids.has(player.player_id));
  }

  slotChoices(slot: number): MatchPlayer[] {
    const draft = this.draft();
    if (!draft) return [];
    const taken = new Set(
      Object.entries(draft.slots)
        .filter(([index, id]) => Number(index) !== slot && id)
        .map(([, id]) => id),
    );
    return this.squad().filter((player) => !taken.has(player.player_id));
  }

  benchChoices(): MatchPlayer[] {
    const draft = this.draft();
    if (!draft) return [];
    const starting = new Set(this.startingIds(draft));
    return this.squad().filter((player) => !starting.has(player.player_id));
  }

  private patch(change: Partial<Draft>): void {
    const draft = this.draft();
    if (draft) this.draft.set({ ...draft, ...change });
  }

  setFormation(formation: string): void {
    const draft = this.draft();
    if (!draft) return;
    const ordered = Object.entries(draft.slots)
      .sort((a, b) => Number(a[0]) - Number(b[0]))
      .map(([, id]) => id)
      .filter(Boolean);
    const next = this.day()?.formations?.find((item) => item.key === formation)?.slots ?? [];
    const slots: Record<number, string> = {};
    next.forEach((slot, index) => {
      if (ordered[index]) slots[slot.index] = ordered[index];
    });
    this.patch({ formation, slots });
  }

  setFreeFormation(formation: string): void {
    this.patch({ formation });
  }

  assignSlot(slot: number, playerId: string): void {
    const draft = this.draft();
    if (!draft) return;
    const slots = { ...draft.slots };
    if (playerId) slots[slot] = playerId;
    else delete slots[slot];
    this.patch({
      slots,
      bench: draft.bench.filter((id) => id !== playerId),
      captain: Object.values(slots).includes(draft.captain) ? draft.captain : '',
    });
  }

  toggleStarter(playerId: string): void {
    const draft = this.draft();
    if (!draft) return;
    if (draft.starters.includes(playerId)) {
      this.patch({
        starters: draft.starters.filter((id) => id !== playerId),
        captain: draft.captain === playerId ? '' : draft.captain,
      });
      return;
    }
    const limit = this.config()?.starters;
    if (limit && draft.starters.length >= limit) {
      void this.toast(`Name at most ${limit} starters.`);
      return;
    }
    this.patch({ starters: [...draft.starters, playerId], bench: draft.bench.filter((id) => id !== playerId) });
  }

  toggleBench(playerId: string): void {
    const draft = this.draft();
    if (!draft) return;
    if (draft.bench.includes(playerId)) {
      this.patch({ bench: draft.bench.filter((id) => id !== playerId) });
      return;
    }
    const limit = this.config()?.bench_max;
    if (limit !== null && limit !== undefined && draft.bench.length >= limit) {
      void this.toast(`Name at most ${limit} substitutes.`);
      return;
    }
    this.patch({ bench: [...draft.bench, playerId] });
  }

  setCaptain(playerId: string): void {
    this.patch({ captain: playerId });
  }

  numberFor(playerId: string): string {
    return this.draft()?.numbers[playerId] ?? '';
  }

  setNumber(playerId: string, number: string): void {
    const draft = this.draft();
    if (draft) this.patch({ numbers: { ...draft.numbers, [playerId]: number } });
  }

  autoFill(): void {
    const draft = this.draft();
    if (!draft) return;
    const slots = { ...draft.slots };
    const starters = [...draft.starters];
    const used = new Set([...Object.values(slots), ...starters]);
    const free = this.squad().filter((player) => !used.has(player.player_id)).map((player) => player.player_id);
    if (this.draftSlots().length) {
      for (const slot of this.draftSlots()) {
        if (!slots[slot.index] && free.length) slots[slot.index] = free.shift() as string;
      }
    } else {
      const limit = this.config()?.starters ?? free.length;
      while (starters.length < limit && free.length) starters.push(free.shift() as string);
    }
    const benchMax = this.config()?.bench_max ?? free.length;
    const bench = [...draft.bench.filter((id) => free.includes(id))];
    for (const id of free) {
      if (bench.length >= benchMax) break;
      if (!bench.includes(id)) bench.push(id);
    }
    this.patch({ slots, starters, bench });
  }

  save(): void {
    const draft = this.draft();
    if (!draft || this.busy()) return;
    const number = (id: string) => draft.numbers[id] ?? '';
    const starters = this.draftSlots().length
      ? Object.entries(draft.slots)
          .filter(([, id]) => id)
          .map(([slot, id]) => ({ player: id, slot: Number(slot), number: number(id) }))
      : draft.starters.map((id) => ({ player: id, number: number(id) }));
    const needed = this.sheetMinimum();
    if (starters.length < needed) {
      void this.toast(`Name at least ${needed} players on the team sheet.`);
      return;
    }
    const body = {
      formation: draft.formation,
      captain: draft.captain || null,
      starters,
      bench: draft.bench.map((id) => ({ player: id, number: number(id) })),
    };
    this.busy.set(true);
    this.api.saveTeamSheet(this.competitionId(), this.fixtureId(), draft.sideId, body).subscribe({
      next: (day) => {
        this.busy.set(false);
        this.draft.set(null);
        this.day.set(day);
        void this.toast('Team sheet saved.', 'success');
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not save the team sheet.'));
      },
    });
  }

  // --- Substitutions ---

  private player(side: TeamSheetSide, id: string): MatchPlayer | undefined {
    return side.squad.find((player) => player.player_id === id);
  }

  onField(side: TeamSheetSide): MatchPlayer[] {
    return side.on_field.map((id) => this.player(side, id)).filter((player): player is MatchPlayer => !!player);
  }

  available(side: TeamSheetSide): MatchPlayer[] {
    return side.available_subs
      .map((id) => this.player(side, id))
      .filter((player): player is MatchPlayer => !!player);
  }

  subFor(sideId: string): { off: string; on: string; reason: string } {
    return this.subDrafts()[sideId] ?? { off: '', on: '', reason: 'tactical' };
  }

  setSub(sideId: string, field: 'off' | 'on' | 'reason', value: string): void {
    this.subDrafts.update((drafts) => ({ ...drafts, [sideId]: { ...this.subFor(sideId), [field]: value } }));
  }

  subsFor(sideId: string): SubstitutionRecord[] {
    return this.subs().filter((sub) => sub.side_id === sideId);
  }

  setMinute(minute: string): void {
    this.minuteTouched = true;
    this.subMinute.set(minute);
  }

  substitute(side: TeamSheetSide): void {
    if (this.busy()) return;
    this.busy.set(true);
    this.api
      .recordSubstitution(this.competitionId(), this.fixtureId(), {
        side: side.side_id,
        player_off: this.subFor(side.side_id).off,
        player_on: this.subFor(side.side_id).on,
        minute: this.subMinute() || null,
        reason: this.subFor(side.side_id).reason,
      })
      .subscribe({
        next: (day) => {
          this.busy.set(false);
          this.day.set(day);
          this.subDrafts.update((drafts) => ({ ...drafts, [side.side_id]: { off: '', on: '', reason: 'tactical' } }));
          this.minuteTouched = false;
        },
        error: async (err: unknown) => {
          this.busy.set(false);
          await this.toast(extractErrorMessage(err, 'Could not record that substitution.'));
        },
      });
  }

  async confirmDelete(sub: SubstitutionRecord): Promise<void> {
    const alert = await this.alerts.create({
      header: 'Delete substitution?',
      message: `${sub.player_on.name} for ${sub.player_off.name}${sub.minute !== null ? ` (${sub.minute}')` : ''}. ${sub.player_off.name} goes back on the field.`,
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        { text: 'Delete', role: 'destructive', handler: () => this.remove(sub) },
      ],
    });
    await alert.present();
  }

  private remove(sub: SubstitutionRecord): void {
    this.busy.set(true);
    this.api.deleteSubstitution(this.competitionId(), this.fixtureId(), sub.id).subscribe({
      next: (day) => {
        this.busy.set(false);
        this.day.set(day);
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not delete that substitution.'));
      },
    });
  }

  private load(): void {
    this.api.teamSheets(this.competitionId(), this.fixtureId()).subscribe({
      next: (day) => {
        this.day.set(day);
      },
      error: () => this.day.set({ enabled: false }),
    });
  }

  private async toast(message: string, color: 'danger' | 'success' = 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, duration: 2500, color });
    await toast.present();
  }
}
