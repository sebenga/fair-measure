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
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { AlertController, IonIcon, ToastController } from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import { arrowDownOutline, arrowUpOutline, swapHorizontalOutline, trashOutline } from 'ionicons/icons';

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';
import type {
  FormationSlot,
  MatchDay,
  MatchPlayer,
  SubstitutionRecord,
  TeamSheetSide,
} from '../../core/models';
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
  imports: [IonIcon, RouterLink],
  template: `
    @if (status() === 'completed' || status() === 'forfeit') {
      <h3 class="fm-section-title">Match report</h3>
      <a class="fm-card report-link" [routerLink]="['/tabs/competitions', competitionId(), 'fixtures', fixtureId(), 'report']">
        <ion-icon name="document-text-outline" aria-hidden="true" />
        <span>
          <strong>Post-match report</strong>
          <em>Result, line-ups, goals, cards, substitutions and the officials' notes. Printable.</em>
        </span>
        <ion-icon name="chevron-forward-outline" aria-hidden="true" />
      </a>
    }

    @if (day()?.enabled && sides().length) {
      <h3 class="fm-section-title">Team sheets</h3>
      <div class="fm-card sheet">
        <div class="team-tabs" role="tablist" aria-label="Team">
          @for (side of sides(); track side.side_id) {
            <button
              type="button"
              role="tab"
              [attr.aria-selected]="side.side_id === selectedId()"
              [class.on]="side.side_id === selectedId()"
              (click)="select(side.side_id)"
            >
              {{ side.name }}
              @if (side.lineup) {
                <small>{{ side.lineup.formation || side.lineup.starters.length + ' named' }}</small>
              } @else {
                <small>not picked</small>
              }
            </button>
          }
        </div>

        @if (selected(); as side) {
          @if (draft(); as d) {
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
                  @if (config()?.starters; as limit) {
                    ({{ d.starters.length }} of {{ limit }})
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
            @if (side.lineup; as lineup) {
              @if (lineup.slots.length) {
                <div class="pitch" [attr.aria-label]="side.name + ' line-up'">
                  @for (row of rows(lineup.slots); track $index) {
                    <div class="pitch-row">
                      @for (slot of row; track slot.index) {
                        @if (starterAt(side, slot.index); as player) {
                          <div class="spot" [class.off]="player.subbed_off">
                            <span class="shirt">{{ player.number ?? '' }}</span>
                            <span class="who">
                              {{ shortName(player.name) }}
                              @if (lineup.captain_id === player.player_id) {
                                <b class="captain" aria-label="Captain">C</b>
                              }
                            </span>
                            @if (player.subbed_off) {
                              <ion-icon name="arrow-down-outline" class="sub-off" aria-label="Substituted" />
                            }
                          </div>
                        } @else {
                          <div class="spot vacant"><span class="shirt">–</span><span class="who">{{ slot.label }}</span></div>
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
                      {{ player.name }}
                      @if (lineup.captain_id === player.player_id) {
                        <b class="captain">C</b>
                      }
                    </li>
                  }
                </ul>
              }
              <p class="hint">Bench</p>
              <ul class="list bench">
                @for (player of lineup.bench; track player.player_id) {
                  <li [class.used]="player.on_field || player.subbed_off">
                    <span class="num">{{ player.number ?? '' }}</span>
                    {{ player.name }}
                    @if (player.on_field) {
                      <ion-icon name="arrow-up-outline" class="sub-on" aria-label="Came on" />
                    }
                  </li>
                } @empty {
                  <li class="muted">No substitutes named.</li>
                }
              </ul>
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
          }
        }
      </div>

      @if (showSubstitutions()) {
        <h3 class="fm-section-title">
          Substitutions
          @if (subs().length) {
            <span class="count">{{ subs().length }}</span>
          }
        </h3>
        <div class="fm-card subs">
          <div class="used">
            @for (side of sides(); track side.side_id) {
              <span>
                <strong>{{ side.name }}</strong>
                {{ side.substitutions_used }}
                @if (config()?.max_substitutions; as limit) {
                  of {{ limit }}
                }
                used
              </span>
            }
          </div>

          @if (day()?.can_substitute) {
            @if (selected(); as side) {
              @if (side.lineup) {
                <div class="sub-form">
                  <p class="hint">Recording for <strong>{{ side.name }}</strong>. Switch team with the tabs above.</p>
                  <label class="field">
                    Off
                    <select (change)="subOff.set(value($event))">
                      <option value="" [selected]="!subOff()">Player coming off</option>
                      @for (player of onField(side); track player.player_id) {
                        <option [value]="player.player_id" [selected]="subOff() === player.player_id">{{ label(player) }}</option>
                      }
                    </select>
                  </label>
                  <label class="field">
                    On
                    <select (change)="subOn.set(value($event))">
                      <option value="" [selected]="!subOn()">Substitute coming on</option>
                      @for (player of available(side); track player.player_id) {
                        <option [value]="player.player_id" [selected]="subOn() === player.player_id">{{ label(player) }}</option>
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
                      <select (change)="subReason.set(value($event))">
                        @for (reason of day()?.reasons ?? []; track reason.key) {
                          <option [value]="reason.key" [selected]="subReason() === reason.key">{{ reason.label }}</option>
                        }
                      </select>
                    </label>
                  </div>
                  <div class="actions">
                    <button
                      type="button"
                      class="primary"
                      [disabled]="busy() || !subOff() || !subOn() || side.substitutions_left === 0"
                      (click)="substitute(side)"
                    >
                      <ion-icon name="swap-horizontal-outline" aria-hidden="true" />
                      Record substitution
                    </button>
                  </div>
                  @if (side.substitutions_left === 0) {
                    <p class="hint">{{ side.name }} have used all their substitutions.</p>
                  }
                </div>
              } @else {
                <p class="hint">Pick {{ side.name }}'s team sheet before recording substitutions.</p>
              }
            }
          }

          @for (sub of subs(); track sub.id) {
            <div class="sub">
              <span class="minute">{{ sub.minute !== null ? sub.minute + "'" : '–' }}</span>
              <span class="detail">
                <span class="on"><ion-icon name="arrow-up-outline" aria-label="On" /> {{ sub.player_on.name }}</span>
                <span class="off"><ion-icon name="arrow-down-outline" aria-label="Off" /> {{ sub.player_off.name }}</span>
                <em>{{ sub.team }} · {{ reasonLabel(sub.reason) }}</em>
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
        </div>
      }
    }
  `,
  styles: [
    `
      .report-link {
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 0 16px 16px;
        padding: 14px 16px;
        color: inherit;
        text-decoration: none;
      }
      .report-link > ion-icon:first-child {
        font-size: 1.6rem;
        color: var(--ion-color-primary);
      }
      .report-link span {
        flex: 1 1 auto;
        display: grid;
        gap: 2px;
      }
      .report-link em {
        font-style: normal;
        font-size: 0.78rem;
        color: var(--ion-color-medium);
      }
      .sheet,
      .subs {
        margin: 0 16px 16px;
        padding: 12px 14px;
        display: grid;
        gap: 10px;
      }
      .team-tabs {
        display: grid;
        grid-auto-flow: column;
        grid-auto-columns: 1fr;
        gap: 6px;
        padding: 4px;
        border-radius: 12px;
        background: var(--ion-color-light);
        color: var(--ion-color-light-contrast);
      }
      .team-tabs button {
        display: grid;
        gap: 2px;
        padding: 8px 6px;
        border: 0;
        border-radius: 9px;
        background: transparent;
        color: inherit;
        font: inherit;
        font-weight: 700;
        cursor: pointer;
      }
      .team-tabs button small {
        font-weight: 500;
        font-size: 0.72rem;
        opacity: 0.75;
      }
      .team-tabs button.on {
        background: var(--ion-color-primary);
        color: var(--ion-color-primary-contrast);
      }
      .pitch {
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding: 14px 8px;
        border-radius: 14px;
        background:
          repeating-linear-gradient(0deg, rgb(255 255 255 / 0.05) 0 28px, transparent 28px 56px),
          linear-gradient(180deg, #15803d, #166534);
        color: #fff;
      }
      .pitch-row {
        display: flex;
        justify-content: space-evenly;
        gap: 6px;
      }
      .spot {
        display: grid;
        justify-items: center;
        gap: 3px;
        min-width: 0;
        flex: 1 1 0;
        max-width: 84px;
        position: relative;
        text-align: center;
      }
      .spot .shirt {
        display: grid;
        place-items: center;
        width: 30px;
        height: 30px;
        border-radius: 50%;
        background: #fff;
        color: #14532d;
        font-weight: 800;
        font-size: 0.8rem;
      }
      .spot .who {
        font-size: 0.7rem;
        font-weight: 600;
        line-height: 1.15;
        overflow-wrap: anywhere;
      }
      .spot.off {
        opacity: 0.55;
      }
      .spot.vacant .shirt {
        background: rgb(255 255 255 / 0.3);
        color: #fff;
      }
      .sub-off {
        position: absolute;
        top: -2px;
        right: 8px;
        color: #fca5a5;
      }
      .captain {
        display: inline-grid;
        place-items: center;
        width: 15px;
        height: 15px;
        margin-left: 3px;
        border-radius: 50%;
        background: #facc15;
        color: #422006;
        font-size: 0.6rem;
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
        grid-template-columns: 1fr 1fr;
        gap: 10px;
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
        display: flex;
        flex-wrap: wrap;
        gap: 6px 16px;
        font-size: 0.8rem;
        color: var(--ion-color-medium);
      }
      .used strong {
        color: var(--ion-text-color);
      }
      .sub {
        display: grid;
        grid-template-columns: 40px 1fr auto;
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

  readonly day = signal<MatchDay | null>(null);
  readonly selectedId = signal('');
  readonly draft = signal<Draft | null>(null);
  readonly busy = signal(false);
  readonly subOff = signal('');
  readonly subOn = signal('');
  readonly subMinute = signal('');
  readonly subReason = signal('tactical');
  private minuteTouched = false;

  readonly sides = computed(() => this.day()?.sides ?? []);
  readonly config = computed(() => this.day()?.config);
  readonly subs = computed(() => this.day()?.substitutions ?? []);
  readonly selected = computed(
    () => this.sides().find((side) => side.side_id === this.selectedId()) ?? this.sides()[0] ?? null,
  );
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
    addIcons({ arrowDownOutline, arrowUpOutline, swapHorizontalOutline, trashOutline });
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

  select(sideId: string): void {
    if (this.draft() && this.draft()?.sideId !== sideId) this.draft.set(null);
    this.selectedId.set(sideId);
    this.subOff.set('');
    this.subOn.set('');
  }

  label(player: MatchPlayer): string {
    return player.number !== null && player.number !== undefined ? `${player.number} · ${player.name}` : player.name;
  }

  shortName(name: string): string {
    const parts = name.trim().split(/\s+/);
    return parts.length > 1 ? parts.slice(1).join(' ') : name;
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
    this.selectedId.set(side.side_id);
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
    return this.selected()?.squad ?? [];
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
        player_off: this.subOff(),
        player_on: this.subOn(),
        minute: this.subMinute() || null,
        reason: this.subReason(),
      })
      .subscribe({
        next: (day) => {
          this.busy.set(false);
          this.day.set(day);
          this.subOff.set('');
          this.subOn.set('');
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
        if (!this.selectedId() && day.sides?.length) this.selectedId.set(day.sides[0].side_id);
      },
      error: () => this.day.set({ enabled: false }),
    });
  }

  private async toast(message: string, color: 'danger' | 'success' = 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, duration: 2500, color });
    await toast.present();
  }
}
