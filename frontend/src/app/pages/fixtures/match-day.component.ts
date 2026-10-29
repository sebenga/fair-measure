import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  computed,
  effect,
  inject,
  input,
  output,
  signal,
  untracked,
} from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AlertController, ToastController } from '@ionic/angular/standalone';

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
  imports: [NgTemplateOutlet],
  template: `
    @if (day()?.enabled === false) {
      <div class="fm-empty compact"><p>This competition does not use team sheets.</p></div>
    }

    <ng-template #sheetView let-side>
      @if (side.lineup; as lineup) {
        @if (pitchSlots(side).length) {
          <div class="pitch" [attr.aria-label]="side.name + ' line-up'">
            @for (row of rows(pitchSlots(side)); track $index) {
              <div class="pitch-row">
                @for (slot of row; track slot.index) {
                  @if (starterAt(side, slot.index); as starter) {
                    @let player = onPitch(side, starter);
                    @let replaced = player.player_id !== starter.player_id ? starter : null;
                    @if (canRecord() || rating()) {
                      <button
                        type="button"
                        class="shirt tappable"
                        [class.captain]="lineup.captain_id === player.player_id"
                        [class.off]="player.subbed_off || player.sent_off"
                        [class.rated]="marked().has(player.player_id)"
                        [style.--kit]="kit(side.participant_id)[0]"
                        [style.--kit-ink]="kit(side.participant_id)[1]"
                        [attr.aria-label]="pressLabel(player, replaced)"
                        (click)="pressPlayer(side, player)"
                      >
                        <ng-container
                          *ngTemplateOutlet="shirtBody; context: { $implicit: player, lineup: lineup, replaced: replaced }"
                        />
                      </button>
                    } @else {
                      <div
                        class="shirt"
                        [class.captain]="lineup.captain_id === player.player_id"
                        [class.off]="player.subbed_off || player.sent_off"
                        [style.--kit]="kit(side.participant_id)[0]"
                        [style.--kit-ink]="kit(side.participant_id)[1]"
                        [attr.aria-label]="replaced ? player.name + ' came on for ' + replaced.name : null"
                      >
                        <ng-container
                          *ngTemplateOutlet="shirtBody; context: { $implicit: player, lineup: lineup, replaced: replaced }"
                        />
                      </div>
                    }
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
            @for (starter of lineup.starters; track starter.player_id) {
              @let player = onPitch(side, starter);
              @let replaced = player.player_id !== starter.player_id ? starter : null;
              <li [class.off]="player.subbed_off || player.sent_off" [class.rated]="marked().has(player.player_id)">
                @if (canRecord() || rating()) {
                  <button
                    type="button"
                    class="list-player"
                    [attr.aria-label]="pressLabel(player, replaced)"
                    (click)="pressPlayer(side, player)"
                  >
                    <span class="num">{{ player.number ?? '' }}</span>
                    <span class="who">
                      <b>{{ player.name }}</b>
                      <small>
                        @if (replaced) {
                          ↑ for {{ shortName(replaced.name) }} ·
                        }
                        {{ shirtMeta(player) }}
                      </small>
                    </span>
                    @if (lineup.captain_id === player.player_id) {
                      <i class="badge inline" aria-label="Captain">C</i>
                    }
                  </button>
                } @else {
                  <span class="num">{{ player.number ?? '' }}</span>
                  <span class="who">
                    <b>{{ player.name }}</b>
                    <small>
                      @if (replaced) {
                        ↑ for {{ shortName(replaced.name) }} ·
                      }
                      {{ shirtMeta(player) }}
                    </small>
                  </span>
                  @if (lineup.captain_id === player.player_id) {
                    <i class="badge inline" aria-label="Captain">C</i>
                  }
                }
              </li>
            }
          </ul>
        }
        <section class="bench">
          <h3>
            Substitutes
            @if (side.substitutions_used || config()?.max_substitutions) {
              <small class="used">
                {{ side.substitutions_used }}{{ config()?.max_substitutions ? ' of ' + config()?.max_substitutions : '' }}
                used
              </small>
            }
          </h3>
          <div class="bench-row">
            @for (player of lineup.bench; track player.player_id) {
              @if (wentOffFor(side, player); as out) {
                <button
                  type="button"
                  class="shirt bench-shirt went-off"
                  [class.rated]="marked().has(out.player.player_id)"
                  [disabled]="rating() ? false : !day()?.can_substitute || busy()"
                  [style.--kit]="kit(side.participant_id)[0]"
                  [style.--kit-ink]="kit(side.participant_id)[1]"
                  [attr.aria-label]="
                    rating()
                      ? 'Stats and rating for ' + out.player.name
                      : out.player.name + ' went off for ' + player.name + (day()?.can_substitute ? '. Tap to undo.' : '')
                  "
                  (click)="rating() ? picked.emit({ sideId: side.side_id, playerId: out.player.player_id, name: out.player.name }) : confirmDelete(out.sub)"
                >
                  <i class="badge out" aria-hidden="true">↓</i>
                  <span class="kit slim">{{ out.player.number ?? '' }}</span>
                  <span class="who">
                    <b>{{ shortName(out.player.name) }}</b>
                    <small class="for">
                      Off{{ out.minute !== null ? ' ' + out.minute + "'" : '' }} · {{ shortName(player.name) }} on
                    </small>
                  </span>
                </button>
              } @else if (canBringOn(side, player)) {
                <button
                  type="button"
                  class="shirt bench-shirt tappable"
                  [style.--kit]="kit(side.participant_id)[0]"
                  [style.--kit-ink]="kit(side.participant_id)[1]"
                  [attr.aria-label]="'Bring ' + player.name + ' on'"
                  (click)="pressBench(side, player)"
                >
                  <span class="kit slim">{{ player.number ?? '' }}</span>
                  <span class="who">
                    <b>{{ shortName(player.name) }}</b>
                    <small>{{ shirtMeta(player) }}</small>
                  </span>
                </button>
              } @else {
                <div
                  class="shirt bench-shirt"
                  [class.used]="player.on_field || player.subbed_off"
                  [style.--kit]="kit(side.participant_id)[0]"
                  [style.--kit-ink]="kit(side.participant_id)[1]"
                >
                  <span class="kit slim">{{ player.number ?? '' }}</span>
                  <span class="who">
                    <b>{{ shortName(player.name) }}</b>
                    <small>{{ shirtMeta(player) }}</small>
                  </span>
                </div>
              }
            } @empty {
              <p class="muted">No substitutes named.</p>
            }
          </div>
        </section>
      } @else {
        <p class="muted">{{ side.name }} have not picked their team yet.</p>
      }
      @if (rating()) {
      } @else if (side.can_edit) {
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

    <ng-template #shirtBody let-player let-lineup="lineup" let-replaced="replaced">
      @if (lineup.captain_id === player.player_id) {
        <i class="badge" aria-label="Captain">C</i>
      }
      @if (replaced) {
        <i class="badge came-on" [attr.aria-label]="'Came on for ' + replaced.name">↑</i>
      }
      <span class="kit">{{ player.number ?? '' }}</span>
      <span class="who">
        <b>{{ shortName(player.name) }}</b>
        @if (replaced) {
          <small class="for">for {{ shortName(replaced.name) }}</small>
        }
        <small>{{ shirtMeta(player) }}</small>
      </span>
    </ng-template>

    @if (day()?.enabled && sides().length) {
      @if (rating()) {
        <h3 class="fm-section-title">Player ratings</h3>
        <p class="hint">Tap a player to record their stats and rate them. A green ring means you have rated them.</p>
      } @else {
        <h3 class="fm-section-title">Team sheets</h3>
        <p class="hint">
          Both teams must submit a team sheet of at least {{ sheetMinimum() }} before kickoff, and every
          named player needs a shirt number. Officials must be picked on Setup.
        </p>
      }
      @if (canRecord() && !rating()) {
        <p class="hint">
          Tap a player to record a yellow card, red card, goal or own goal{{
            day()?.can_substitute ? ', or to take them off. Tap a substitute to bring them on' : ''
          }}.
        </p>
      }
      <div class="lineup-stack" [class.editing]="!!draft()">
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
          <div class="numbers">
            <p class="hint">Shirt numbers (required)</p>
            @for (player of draftNamed(); track player.player_id) {
              <label [class.missing]="!numberFor(player.player_id)">
                <span>{{ player.name }}</span>
                <input
                  type="number"
                  min="0"
                  required
                  inputmode="numeric"
                  [value]="numberFor(player.player_id)"
                  (input)="setNumber(player.player_id, value($event))"
                />
              </label>
            }
          </div>
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
  `,
  styles: [
    `
      .sheet {
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
      .lineup-stack {
        display: grid;
        gap: 16px;
        margin: 0 16px 16px;
      }
      @media (max-width: 419px) {
        .pitch {
          gap: 12px;
          padding: 14px 8px 16px;
          min-height: 0;
        }
        .kit {
          width: 44px;
          height: 48px;
        }
        .kit.slim {
          width: 38px;
          height: 42px;
        }
      }
      .pitch {
        position: relative;
        display: grid;
        gap: 14px;
        min-height: 420px;
        padding: 18px 10px 22px;
        border-radius: 20px;
        background:
          radial-gradient(circle at 50% 50%, rgb(255 255 255 / 10%) 0 18%, transparent 19%),
          linear-gradient(#2f8f46, #1f6b34 48%, #2f8f46);
        box-shadow: inset 0 0 0 3px rgb(255 255 255 / 18%);
        color: #fff;
      }
      .pitch-row {
        display: flex;
        justify-content: center;
        flex-wrap: wrap;
        align-items: flex-start;
        gap: 10px;
      }
      .shirt {
        display: grid;
        justify-items: center;
        gap: 4px;
        position: relative;
        width: 76px;
        padding: 0;
      }
      button.shirt {
        border: 0;
        background: none;
        color: #fff;
        font: inherit;
      }
      button.shirt.tappable {
        cursor: pointer;
      }
      .list-player {
        display: flex;
        align-items: center;
        gap: 8px;
        width: 100%;
        padding: 0;
        border: 0;
        background: none;
        color: var(--fm-ink);
        font: inherit;
        text-align: left;
        cursor: pointer;
      }
      .kit {
        display: grid;
        place-items: center;
        width: 52px;
        height: 56px;
        border-radius: 10px 10px 14px 14px;
        background: var(--kit, #1d4ed8);
        color: var(--kit-ink, #fff);
        font-size: 0.95rem;
        font-weight: 800;
        line-height: 1;
        box-shadow: 0 6px 14px rgb(0 0 0 / 25%);
      }
      .kit.slim {
        width: 44px;
        height: 48px;
        font-size: 0.85rem;
      }
      .kit.hollow {
        background: transparent;
        color: #fff;
        border: 2px dashed rgb(255 255 255 / 70%);
        box-shadow: none;
      }
      .who {
        display: grid;
        width: 100%;
        min-width: 0;
        padding: 4px 4px 5px;
        border-radius: 8px;
        background: rgb(15 23 42 / 82%);
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
        line-height: 1.2;
      }
      .who small {
        font-size: 0.58rem;
        opacity: 0.85;
        white-space: normal;
        overflow: visible;
        text-overflow: unset;
        line-height: 1.2;
      }
      .badge {
        position: absolute;
        top: -4px;
        right: 8px;
        width: 18px;
        height: 18px;
        border-radius: 999px;
        background: #f5c400;
        color: #111;
        font-size: 0.62rem;
        font-weight: 800;
        font-style: normal;
        display: grid;
        place-items: center;
      }
      .badge.inline {
        position: static;
      }
      .shirt.rated .kit {
        box-shadow:
          0 0 0 2px var(--ion-color-success, #16a34a),
          0 4px 10px rgb(0 0 0 / 25%);
      }
      .list li.rated .num {
        color: var(--ion-color-success, #16a34a);
      }
      .badge.out {
        right: auto;
        left: 8px;
        background: var(--ion-color-danger, #dc2626);
        color: #fff;
      }
      button.bench-shirt:disabled {
        cursor: default;
        opacity: 1;
      }
      .bench h3 .used {
        margin-left: 6px;
        font-size: 0.72rem;
        font-weight: 600;
        color: var(--ion-color-medium);
      }
      .bench-shirt.went-off .kit {
        opacity: 0.6;
      }
      .bench-shirt.went-off .for {
        color: var(--ion-color-danger, #dc2626);
      }
      .badge.came-on {
        right: auto;
        left: 8px;
        background: var(--ion-color-success, #16a34a);
        color: #fff;
      }
      .who small.for {
        font-weight: 700;
        opacity: 1;
      }
      button.bench-shirt {
        color: inherit;
        cursor: pointer;
      }
      .shirt.off {
        opacity: 0.55;
      }
      .empty {
        display: grid;
        justify-items: center;
        gap: 6px;
        width: 76px;
        color: rgb(255 255 255 / 85%);
        text-align: center;
      }
      .empty small {
        font-size: 0.62rem;
      }
      .bench h3 {
        margin: 0 0 8px;
        font-size: 0.92rem;
      }
      .bench-shirt {
        width: 92px;
      }
      .bench-row {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        padding: 4px 0 8px;
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
      .editor {
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
      .numbers label {
        display: grid;
        grid-template-columns: 1fr 80px;
        align-items: center;
        gap: 8px;
        margin-top: 6px;
      }
      .numbers label.missing input {
        border-color: var(--ion-color-danger);
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
        color: var(--fm-accent);
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
  /** Referee, owner or admin during a live match can record a goal or a card from the shirt. */
  readonly canRecord = input(false);
  readonly contribution = output<{
    sideId: string;
    playerId: string;
    name: string;
    canSubstitute: boolean;
  }>();
  /** 'rate': the pitch only picks a player for stats and a rating; no team-sheet editing. */
  readonly mode = input<'lineup' | 'rate'>('lineup');
  /** Players the viewer has already rated, ringed on the pitch. */
  readonly marked = input<ReadonlySet<string>>(new Set());
  readonly picked = output<{ sideId: string; playerId: string; name: string }>();
  /** Whether every side has a team sheet to draw, so the pitch can stand in for a list. */
  readonly pitchReady = output<boolean>();
  readonly rating = computed(() => this.mode() === 'rate');

  readonly day = signal<MatchDay | null>(null);
  readonly draft = signal<Draft | null>(null);
  readonly busy = signal(false);
  readonly subMinute = computed(() => {
    const minute = this.minute();
    return minute === null ? '' : String(minute);
  });

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

  constructor() {
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
    if (parts.length < 2) return name;
    const initial = parts[0].charAt(0).toUpperCase();
    return `${initial}. ${parts[parts.length - 1]}`;
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
    const raw = player.rating;
    if (raw == null || raw === '') return '';
    const value = Number(raw);
    return Number.isFinite(value) ? value.toFixed(1) : String(raw);
  }

  shirtMeta(player: LineupPlayer): string {
    return [this.ratingLabel(player), this.statLabel(player), this.minutesLabel(player)]
      .filter(Boolean)
      .join(' · ') || '—';
  }

  statLabel(player: LineupPlayer): string {
    return (player.stats ?? [])
      .filter((row) => Number(row.count) > 0)
      .slice(0, 4)
      .map((row) => `${Number(row.count)}${this.statAbbrev(row)}`)
      .join(' ');
  }

  private statAbbrev(row: { code: string; label: string }): string {
    const code = (row.code || '').toLowerCase();
    const short: Record<string, string> = {
      goal: 'G',
      'own-goal': 'OG',
      assist: 'A',
      shot: 'Sh',
      'shot-on-target': 'SoT',
      tackle: 'T',
      interception: 'Int',
      save: 'Sv',
      'yellow-card': 'YC',
      'red-card': 'RC',
    };
    return short[code] || row.label.slice(0, 2);
  }

  pitchSlots(side: TeamSheetSide): FormationSlot[] {
    const lineup = side.lineup;
    if (!lineup) return [];
    if (lineup.slots.length) return lineup.slots;
    return this.slotsFromStarters(lineup.starters.length, lineup.formation);
  }

  private slotsFromStarters(count: number, formation: string): FormationSlot[] {
    const rows = this.parseShape(formation) || this.guessShape(count);
    if (!rows.length) return [];
    const slots: FormationSlot[] = [{ index: 0, row: 0, column: 0, columns: 1, label: 'GK' }];
    rows.forEach((width, rowIndex) => {
      for (let column = 0; column < width; column += 1) {
        slots.push({
          index: slots.length,
          row: rowIndex + 1,
          column,
          columns: width,
          label: '',
        });
      }
    });
    return slots;
  }

  private parseShape(formation: string): number[] | null {
    const rows = formation
      .split('-')
      .map((part) => Number(part.trim()))
      .filter((count) => Number.isFinite(count) && count > 0);
    return rows.length ? rows : null;
  }

  private guessShape(count: number): number[] {
    if (count >= 11) return [4, 3, 3];
    if (count === 10) return [4, 3, 2];
    if (count === 8) return [3, 3, 1];
    if (count === 7) return [2, 3, 1];
    if (count === 6) return [2, 2, 1];
    if (count === 5) return [2, 2];
    return count > 1 ? [count - 1] : [];
  }

  rows(slots: FormationSlot[]): FormationSlot[][] {
    const byRow = new Map<number, FormationSlot[]>();
    for (const slot of slots) byRow.set(slot.row, [...(byRow.get(slot.row) ?? []), slot]);
    return [...byRow.entries()].sort((a, b) => b[0] - a[0]).map(([, row]) => row);
  }

  pressPlayer(side: TeamSheetSide, player: LineupPlayer): void {
    if (this.rating()) {
      this.picked.emit({ sideId: side.side_id, playerId: player.player_id, name: player.name });
      return;
    }
    if (!this.canRecord()) return;
    if (player.sent_off) {
      void this.toast(`${player.name} is already sent off.`);
      return;
    }
    if (player.subbed_off) {
      void this.toast(`${player.name} is off the field.`);
      return;
    }
    this.contribution.emit({
      sideId: side.side_id,
      playerId: player.player_id,
      name: player.name,
      canSubstitute: this.canTakeOff(side, player.player_id),
    });
  }

  pressLabel(player: LineupPlayer, replaced: LineupPlayer | null): string {
    if (this.rating()) return `Stats and rating for ${player.name}`;
    const action = this.day()?.can_substitute ? 'Goal, card or substitution' : 'Record a goal or card';
    return `${action} for ${player.name}${replaced ? `, on for ${replaced.name}` : ''}`;
  }

  /** Who is in a starter's position now: the last player to come on for them, or the starter. */
  onPitch(side: TeamSheetSide, starter: LineupPlayer): LineupPlayer {
    const lineup = side.lineup;
    if (!lineup) return starter;
    const named = [...lineup.starters, ...lineup.bench];
    const seen = new Set([starter.player_id]);
    let current = starter;
    while (current.subbed_off) {
      const sub = this.subsFor(side.side_id)
        .filter((row) => row.player_off.player_id === current.player_id)
        .at(-1);
      const next = sub ? named.find((player) => player.player_id === sub.player_on.player_id) : undefined;
      if (!next || seen.has(next.player_id)) break;
      seen.add(next.player_id);
      current = next;
    }
    return current;
  }

  /** The player who went off when this substitute came on, shown in the substitute's bench spot. */
  wentOffFor(
    side: TeamSheetSide,
    substitute: LineupPlayer,
  ): { player: LineupPlayer; minute: number | null; sub: SubstitutionRecord } | null {
    const lineup = side.lineup;
    if (!lineup) return null;
    const sub = this.subsFor(side.side_id)
      .filter((row) => row.player_on.player_id === substitute.player_id)
      .at(-1);
    if (!sub) return null;
    const player = [...lineup.starters, ...lineup.bench].find(
      (item) => item.player_id === sub.player_off.player_id,
    );
    return player ? { player, minute: sub.minute, sub } : null;
  }

  private canTakeOff(side: TeamSheetSide, playerId: string): boolean {
    return (
      !!this.day()?.can_substitute &&
      side.substitutions_left !== 0 &&
      side.on_field.includes(playerId) &&
      side.available_subs.length > 0
    );
  }

  canBringOn(side: TeamSheetSide, player: LineupPlayer): boolean {
    return (
      this.canRecord() &&
      !!this.day()?.can_substitute &&
      side.substitutions_left !== 0 &&
      side.available_subs.includes(player.player_id)
    );
  }

  /** Take `playerId` off: pick who comes on, at the clock's minute. */
  async offerSubstitution(sideId: string, playerId: string): Promise<void> {
    const side = this.sides().find((item) => item.side_id === sideId);
    if (!side || this.busy()) return;
    if (!this.canTakeOff(side, playerId)) {
      await this.toast('No substitution is possible for that player right now.');
      return;
    }
    const off = this.player(side, playerId);
    const choices = this.available(side);
    const on = await this.pickPlayer(
      `${off?.name ?? 'Player'} off`,
      'Who comes on?',
      choices,
    );
    if (on) this.submitSubstitution(side, playerId, on);
  }

  async pressBench(side: TeamSheetSide, player: LineupPlayer): Promise<void> {
    if (!this.canBringOn(side, player) || this.busy()) return;
    const off = await this.pickPlayer(`${player.name} on`, 'Who comes off?', this.onField(side));
    if (off) this.submitSubstitution(side, off, player.player_id);
  }

  private async pickPlayer(header: string, subHeader: string, players: MatchPlayer[]): Promise<string | null> {
    if (!players.length) {
      await this.toast('There is nobody to swap with.');
      return null;
    }
    const minute = this.subMinute();
    const alert = await this.alerts.create({
      header,
      subHeader: minute ? `${subHeader} (${minute}')` : subHeader,
      inputs: players.map((player, index) => ({
        type: 'radio' as const,
        label: this.label(player),
        value: player.player_id,
        checked: index === 0,
      })),
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        { text: 'Substitute', role: 'confirm' },
      ],
    });
    await alert.present();
    const { role, data } = await alert.onDidDismiss<{ values: string }>();
    return role === 'confirm' && data?.values ? data.values : null;
  }

  starterAt(side: TeamSheetSide, slot: number) {
    const starters = side.lineup?.starters ?? [];
    const bySlot = starters.find((player) => player.slot === slot);
    if (bySlot) return bySlot;
    const unslotted = starters.every((player) => player.slot === null);
    return unslotted ? (starters[slot] ?? null) : null;
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
      numbers: playerId ? this.withNumber(draft.numbers, playerId) : draft.numbers,
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
    this.patch({
      starters: [...draft.starters, playerId],
      bench: draft.bench.filter((id) => id !== playerId),
      numbers: this.withNumber(draft.numbers, playerId),
    });
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
    this.patch({ bench: [...draft.bench, playerId], numbers: this.withNumber(draft.numbers, playerId) });
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

  private withNumber(numbers: Record<string, string>, playerId: string): Record<string, string> {
    if ((numbers[playerId] ?? '').trim()) return numbers;
    const player = this.squad().find((item) => item.player_id === playerId);
    if (player?.number !== null && player?.number !== undefined) {
      const taken = this.takenNumbers(numbers);
      if (!taken.has(player.number)) {
        return { ...numbers, [playerId]: String(player.number) };
      }
    }
    return { ...numbers, [playerId]: String(this.nextFreeNumber(numbers)) };
  }

  private takenNumbers(numbers: Record<string, string>): Set<number> {
    return new Set(
      Object.values(numbers)
        .map((value) => Number(value))
        .filter((value) => Number.isInteger(value) && value >= 0),
    );
  }

  private nextFreeNumber(numbers: Record<string, string>): number {
    const taken = this.takenNumbers(numbers);
    let next = 1;
    while (taken.has(next)) next += 1;
    return next;
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
    let numbers = { ...draft.numbers };
    for (const id of [...Object.values(slots), ...starters, ...bench]) {
      if (id) numbers = this.withNumber(numbers, id);
    }
    this.patch({ slots, starters, bench, numbers });
  }

  save(): void {
    const draft = this.draft();
    if (!draft || this.busy()) return;
    const number = (id: string) => draft.numbers[id]?.trim() ?? '';
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
    const named = [...starters, ...draft.bench.map((id) => ({ player: id, number: number(id) }))];
    if (named.some((row) => row.number === '')) {
      void this.toast('Give every player on the team sheet a shirt number.');
      return;
    }
    const parsed = named.map((row) => Number(row.number));
    if (parsed.some((value) => !Number.isInteger(value) || value < 0)) {
      void this.toast('Shirt numbers are whole numbers.');
      return;
    }
    if (new Set(parsed).size !== parsed.length) {
      void this.toast('Two players have the same shirt number.');
      return;
    }
    const body = {
      formation: draft.formation,
      captain: draft.captain || null,
      starters: starters.map((row) => ({ ...row, number: Number(row.number) })),
      bench: draft.bench.map((id) => ({ player: id, number: Number(number(id)) })),
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

  subsFor(sideId: string): SubstitutionRecord[] {
    return this.subs().filter((sub) => sub.side_id === sideId);
  }

  private submitSubstitution(side: TeamSheetSide, off: string, on: string, reason = 'tactical'): void {
    if (this.busy()) return;
    this.busy.set(true);
    this.api
      .recordSubstitution(this.competitionId(), this.fixtureId(), {
        side: side.side_id,
        player_off: off,
        player_on: on,
        minute: this.subMinute() || null,
        reason,
      })
      .subscribe({
        next: (day) => {
          this.busy.set(false);
          this.day.set(day);
          const offName = this.player(side, off)?.name ?? 'Player';
          const onName = this.player(side, on)?.name ?? 'substitute';
          void this.toast(`${onName} on for ${offName}.`, 'success');
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

  reload(): void {
    this.load();
  }

  private load(): void {
    this.api.teamSheets(this.competitionId(), this.fixtureId()).subscribe({
      next: (day) => {
        this.day.set(day);
        const sides = day.sides ?? [];
        this.pitchReady.emit(!!day.enabled && sides.length > 0 && sides.every((side) => !!side.lineup));
      },
      error: () => {
        this.day.set({ enabled: false });
        this.pitchReady.emit(false);
      },
    });
  }

  private async toast(message: string, color: 'danger' | 'success' = 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, duration: 2500, color });
    await toast.present();
  }
}
