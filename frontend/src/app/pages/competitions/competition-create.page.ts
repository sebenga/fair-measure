import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal, viewChild } from '@angular/core';
import { NgTemplateOutlet } from '@angular/common';
import { AbstractControl, FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import {
  IonBackButton,
  IonButton,
  IonButtons,
  IonCheckbox,
  IonContent,
  IonFooter,
  IonHeader,
  IonIcon,
  IonInput,
  IonItem,
  IonLabel,
  IonList,
  IonSelect,
  IonSelectOption,
  IonSpinner,
  IonTextarea,
  IonTitle,
  IonToolbar,
  AlertController,
  NavController,
} from '@ionic/angular/standalone';

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';
import type { ScoutingCatalog } from '../../core/scouting.models';
import { ScoutingService, scoutingSportFor } from '../../core/scouting.service';
import type { CompetitionFormat, Preset, PresetKind } from '../../core/models';
import { isPointsPreset } from '../../core/models';

type Step = 1 | 2 | 3;

interface FormatOption {
  value: CompetitionFormat;
  label: string;
  blurb: string;
  icon: string;
}

interface ScoringDraft {
  key: number;
  name: string;
  description: string;
  points: string;
  affects_score: boolean;
  code: string;
}

interface FamilyCard {
  key: string;
  label: string;
  icon?: string;
  caption: string;
  presets: Preset[];
}

const WEEKDAYS = [
  { value: 0, label: 'Mon' },
  { value: 1, label: 'Tue' },
  { value: 2, label: 'Wed' },
  { value: 3, label: 'Thu' },
  { value: 4, label: 'Fri' },
  { value: 5, label: 'Sat' },
  { value: 6, label: 'Sun' },
];

const TIMEZONES = [
  'Africa/Cairo',
  'Africa/Johannesburg',
  'Africa/Lagos',
  'Africa/Nairobi',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/New_York',
  'America/Sao_Paulo',
  'Asia/Dubai',
  'Asia/Kolkata',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Australia/Sydney',
  'Europe/Amsterdam',
  'Europe/Berlin',
  'Europe/London',
  'Europe/Paris',
  'Pacific/Auckland',
  'UTC',
];

function endAfterStart(group: AbstractControl): { dateOrder: true } | null {
  const starts = group.get('starts_on')?.value as string;
  const ends = group.get('ends_on')?.value as string;
  if (starts && ends && ends < starts) {
    return { dateOrder: true };
  }
  return null;
}

function localTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

function presetKind(preset: Preset): PresetKind {
  if (preset.kind) return preset.kind;
  if (preset.key === 'custom') return 'custom';
  return 'sport';
}

@Component({
  selector: 'fm-competition-create',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    NgTemplateOutlet,
    IonHeader,
    IonToolbar,
    IonTitle,
    IonButtons,
    IonBackButton,
    IonContent,
    IonFooter,
    IonList,
    IonItem,
    IonLabel,
    IonInput,
    IonTextarea,
    IonSelect,
    IonSelectOption,
    IonCheckbox,
    IonButton,
    IonIcon,
    IonSpinner,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './competition-create.page.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start">
          <ion-back-button defaultHref="/tabs/competitions" />
        </ion-buttons>
        <ion-title>New competition</ion-title>
      </ion-toolbar>
      <ion-toolbar>
        <nav class="steps" aria-label="Create competition steps">
          @for (item of steps; track item.n) {
            <button
              type="button"
              class="step"
              [class.active]="step() === item.n"
              [class.done]="step() > item.n"
              (click)="goTo(item.n)"
            >
              <span class="num">{{ item.n }}</span>
              <span class="label">{{ item.label }}</span>
            </button>
            @if (item.n < 3) {
              <span class="rail" aria-hidden="true"></span>
            }
          }
        </nav>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      <form [formGroup]="form" (ngSubmit)="onFormSubmit()" novalidate>
        @switch (step()) {
          @case (1) {
            <h3 class="fm-section-title">What are you running?</h3>
            <p class="hint">
              Pick an official sport, or Custom if you want to define the scoring yourself. Tap a card to see its scoring.
            </p>

            @if (focused()) {
              <p class="hint">Tap {{ activePreset()?.label ?? 'it' }} again to hide its scoring and see every option.</p>
            }

            @if (shownEveryday().length) {
              <div class="presets fm-stagger">
                @for (preset of shownEveryday(); track preset.key) {
                  <button
                    type="button"
                    class="preset"
                    [class.selected]="focused() && selectedPreset() === preset.key"
                    [attr.aria-pressed]="focused() && selectedPreset() === preset.key"
                    (click)="tapPreset(preset.key)"
                  >
                    <ion-icon [name]="presetIcon(preset)" aria-hidden="true" />
                    <span>{{ preset.label }}</span>
                    <small>{{ kindCaption(preset) }}</small>
                  </button>
                @if (focused() && selectedPreset() === preset.key) {
                  <div class="inline-scoring"><ng-container *ngTemplateOutlet="scoringPanel" /></div>
                }
                }
              </div>
            }

            @if (sportPresets().length) {
              @if (!focused()) {
                <ion-list inset="true" class="find-sport">
                  <ion-item>
                    <ion-input
                      label="Find a sport"
                      labelPlacement="stacked"
                      placeholder="Soccer, swimming, chess"
                      [value]="sportQuery()"
                      (ionInput)="sportQuery.set(stringValue($event))"
                    />
                  </ion-item>
                </ion-list>
              }

              @for (group of shownGroups(); track group.key) {
                @if (!focused()) {
                  <button
                    type="button"
                    class="group-toggle"
                    [class.open]="groupOpen(group.key)"
                    [attr.aria-expanded]="groupOpen(group.key)"
                    (click)="toggleGroup(group.key)"
                  >
                    <span>{{ group.label }}</span>
                    <span class="count">{{ familyCards(group.presets).length }}</span>
                    <ion-icon name="chevron-forward-outline" aria-hidden="true" />
                  </button>
                }
                @if (focused() || groupOpen(group.key)) {
                  <div class="presets fm-stagger">
                    @for (card of familyCards(group.presets); track card.key) {
                      <button
                        type="button"
                        class="preset"
                        [class.selected]="familySelected(card)"
                        [attr.aria-pressed]="familySelected(card)"
                        (click)="tapFamily(card)"
                      >
                        <ion-icon [name]="presetIcon(card.presets[0])" aria-hidden="true" />
                        <span>{{ card.label }}</span>
                        <small>{{ card.caption }}</small>
                      </button>
                    @if (familySelected(card)) {
                      <div class="inline-scoring">
                        @if (card.presets.length > 1) {
                          <div class="variant-chips">
                            @for (preset of card.presets; track preset.key) {
                              <button
                                type="button"
                                class="chip"
                                [class.selected]="selectedPreset() === preset.key"
                                (click)="selectVariant(preset.key, $event)"
                              >
                                {{ preset.variant_label || preset.label }}
                              </button>
                            }
                          </div>
                          @if (activePreset()?.description; as summary) {
                            <p class="variant-summary">{{ firstSentence(summary) }}</p>
                          }
                        }
                        <ng-container *ngTemplateOutlet="scoringPanel" />
                      </div>
                    }
                    }
                  </div>
                }
              }

              @if (!focused() && sportQuery() && !sportGroups().length) {
                <p class="hint">No sport matches that.</p>
              }
            }

            <ng-template #scoringPanel>
              @if (showTypeLabel()) {
                <ion-list inset="true">
                  <ion-item>
                    <ion-input
                      label="What is it?"
                      labelPlacement="stacked"
                      formControlName="sport"
                      [placeholder]="typePlaceholder()"
                      maxlength="80"
                    />
                  </ion-item>
                </ion-list>
              }

              <h3 class="fm-section-title">{{ pointsTable() ? 'Scoring criteria' : 'Scoring' }}</h3>
              <p class="hint">
                @if (scoringLocked()) {
                  Official scoring is fixed. These categories and point values
                  cannot be changed after the competition is created.
                } @else if (isCustom()) {
                  Define the scoring criteria first. Each one needs a name, what the
                  points mean, and how many points one unit is worth. You choose
                  next whether the table uses match results or the sum of these criteria.
                } @else if (pointsTable()) {
                  Each row is a scoring criterion. The table accumulates what people
                  achieve on it. Leave “per unit” at 1 to add the number they enter.
                } @else {
                  Each row is a scoring type: a name, what it means, and how many
                  points it is worth. Turn off “counts toward the score” to record
                  something without changing the total.
                }
              </p>

              @if (scoringLocked()) {
                @if (activePreset()?.result_type) {
                  <p class="hint">
                    Results are recorded on an event sheet after the competition is created.
                    Officials confirm each result. These rules cannot be edited.
                  </p>
                }
                <div class="scoring-list">
                  @for (row of scoringDrafts(); track row.key) {
                  <div class="score-row locked fm-card">
                    <div class="score-line">
                      <strong>{{ row.name }}</strong>
                      <span class="pts" [class.muted]="!row.affects_score">
                        {{ row.points }} {{ pointsTable() ? 'per unit' : 'pts' }}{{ row.affects_score ? '' : ' · recorded only' }}
                      </span>
                    </div>
                    @if (row.description) {
                      <p>{{ row.description }}</p>
                    }
                  </div>
                  }
                </div>
              } @else {
              <div class="scoring-list">
                @for (row of scoringDrafts(); track row.key) {
                  <div class="score-row fm-card">
                    <div class="score-head">
                      <ion-input
                        [label]="pointsTable() || isCustom() ? 'Criterion' : 'Name'"
                        labelPlacement="stacked"
                        [value]="row.name"
                        [placeholder]="pointsTable() || isCustom() ? 'e.g. Sales closed' : 'e.g. Try'"
                        maxlength="120"
                        (ionInput)="patchDraft(row.key, { name: stringValue($event) })"
                      />
                      <ion-input
                        class="points"
                        [label]="pointsTable() ? 'Per unit' : 'Points'"
                        labelPlacement="stacked"
                        type="number"
                        inputmode="decimal"
                        [value]="row.points"
                        (ionInput)="patchDraft(row.key, { points: stringValue($event) })"
                      />
                      <ion-button
                        fill="clear"
                        color="danger"
                        size="small"
                        type="button"
                        [disabled]="scoringDrafts().length === 1 && !row.name.trim() && !row.description.trim()"
                        (click)="confirmRemoveDraft(row.key)"
                      >
                        <ion-icon
                          slot="icon-only"
                          name="trash-outline"
                          [attr.aria-label]="pointsTable() ? 'Remove KPI' : 'Remove scoring type'"
                        />
                      </ion-button>
                    </div>
                    <ion-textarea
                      [label]="pointsTable() || isCustom() ? 'Description of these points' : 'What this means'"
                      labelPlacement="stacked"
                      [value]="row.description"
                      [placeholder]="
                        pointsTable() || isCustom()
                          ? 'Shown when someone expands this criterion on the table.'
                          : 'Describe when this score is awarded.'
                      "
                      autoGrow="true"
                      rows="2"
                      maxlength="2000"
                      (ionInput)="patchDraft(row.key, { description: stringValue($event) })"
                    />
                    <ion-checkbox
                      labelPlacement="end"
                      [checked]="row.affects_score"
                      (ionChange)="patchDraft(row.key, { affects_score: checkboxValue($event) })"
                    >
                      {{ pointsTable() ? 'Counts toward the table' : 'Counts toward the score' }}
                    </ion-checkbox>
                  </div>
                }
              </div>

              <div class="add-score">
                <ion-button fill="outline" type="button" (click)="addDraft()">
                  <ion-icon slot="start" name="add-outline" />
                  {{ pointsTable() || isCustom() ? 'Add scoring criterion' : 'Add scoring type' }}
                </ion-button>
              </div>
              }
            </ng-template>
          }

          @case (2) {
            <h3 class="fm-section-title">The basics</h3>
            <p class="hint">
              @if (isCustom()) {
                Give it a name people will recognise on the table.
              } @else {
                Give it a name people will recognise on the fixture list.
              }
            </p>

            <ion-list inset="true">
              <ion-item>
                <ion-input
                  label="Name"
                  labelPlacement="stacked"
                  formControlName="name"
                  placeholder="Thursday Night Sevens"
                  maxlength="200"
                  errorText="A name is required."
                />
              </ion-item>
              @if (form.controls.name.touched && form.controls.name.invalid) {
                <p class="fm-form-error" role="alert">Give the competition a name.</p>
              }
              <ion-item>
                <ion-textarea
                  label="Description"
                  labelPlacement="stacked"
                  formControlName="description"
                  placeholder="Who is it for, and what are the stakes?"
                  autoGrow="true"
                  rows="3"
                  maxlength="2000"
                />
              </ion-item>
            </ion-list>

            <h3 class="fm-section-title">{{ isCustom() ? 'How points are added' : scoringLocked() ? 'Competition structure' : 'Format' }}</h3>
            <p class="hint">{{ formatHint() }}</p>

            @if (isCustom()) {
              <div class="formats">
                <button
                  type="button"
                  class="format"
                  [class.selected]="pointsTable()"
                  (click)="setCustomMode('points')"
                >
                  <ion-icon name="stats-chart-outline" aria-hidden="true" />
                  <div>
                    <strong>Points accumulation</strong>
                    <p>
                      An admin adds points against the criteria you defined. Entrants do not
                      play each other, and there is no fixture schedule.
                    </p>
                  </div>
                  @if (pointsTable()) {
                    <ion-icon name="checkmark-outline" class="tick" aria-hidden="true" />
                  }
                </button>
                <button
                  type="button"
                  class="format"
                  [class.selected]="!pointsTable()"
                  (click)="setCustomMode('versus')"
                >
                  <ion-icon name="people-outline" aria-hidden="true" />
                  <div>
                    <strong>VS competition</strong>
                    <p>
                      Entrants play each other in fixtures. Your criteria score each match, the
                      higher total wins, and the table awards the points you set for a win, draw and loss.
                    </p>
                  </div>
                  @if (!pointsTable()) {
                    <ion-icon name="checkmark-outline" class="tick" aria-hidden="true" />
                  }
                </button>
              </div>

              @if (!pointsTable()) {
                <h3 class="fm-section-title">Who plays</h3>
                <div class="formats">
                  <button
                    type="button"
                    class="format"
                    [class.selected]="versusEntrants() === 'team'"
                    (click)="versusEntrants.set('team')"
                  >
                    <ion-icon name="people-outline" aria-hidden="true" />
                    <div>
                      <strong>Teams</strong>
                      <p>Teams play each other. Players join a team, and each event names the player.</p>
                    </div>
                    @if (versusEntrants() === 'team') {
                      <ion-icon name="checkmark-outline" class="tick" aria-hidden="true" />
                    }
                  </button>
                  <button
                    type="button"
                    class="format"
                    [class.selected]="versusEntrants() === 'individual'"
                    (click)="versusEntrants.set('individual')"
                  >
                    <ion-icon name="person-circle-outline" aria-hidden="true" />
                    <div>
                      <strong>Individuals</strong>
                      <p>One person plays another. Each entrant is a single player.</p>
                    </div>
                    @if (versusEntrants() === 'individual') {
                      <ion-icon name="checkmark-outline" class="tick" aria-hidden="true" />
                    }
                  </button>
                </div>

                <h3 class="fm-section-title">Table points</h3>
                <p class="hint">Points each entrant earns on the table for a result.</p>
                <ion-list inset="true">
                  <ion-item>
                    <ion-input
                      label="Win"
                      labelPlacement="stacked"
                      type="number"
                      inputmode="decimal"
                      [value]="winPoints()"
                      (ionInput)="winPoints.set(stringValue($event))"
                    />
                  </ion-item>
                  <ion-item>
                    <ion-input
                      label="Draw"
                      labelPlacement="stacked"
                      type="number"
                      inputmode="decimal"
                      [value]="drawPoints()"
                      (ionInput)="drawPoints.set(stringValue($event))"
                    />
                  </ion-item>
                  <ion-item>
                    <ion-input
                      label="Loss"
                      labelPlacement="stacked"
                      type="number"
                      inputmode="decimal"
                      [value]="lossPoints()"
                      (ionInput)="lossPoints.set(stringValue($event))"
                    />
                  </ion-item>
                </ion-list>

                <h3 class="fm-section-title">Bonus points</h3>
                <p class="hint">
                  Extra table points from how the match was scored, or from the winning or losing
                  margin. Switch them off to keep the table as win, draw and loss only.
                </p>
                <div class="formats">
                  <button
                    type="button"
                    class="format"
                    [class.selected]="bonusEnabled()"
                    (click)="setBonusEnabled(true)"
                  >
                    <ion-icon name="sparkles-outline" aria-hidden="true" />
                    <div>
                      <strong>Include bonus points</strong>
                      <p>The table also adds bonus points from scoring and from close or wide results.</p>
                    </div>
                    @if (bonusEnabled()) {
                      <ion-icon name="checkmark-outline" class="tick" aria-hidden="true" />
                    }
                  </button>
                  <button
                    type="button"
                    class="format"
                    [class.selected]="!bonusEnabled()"
                    (click)="setBonusEnabled(false)"
                  >
                    <ion-icon name="remove-circle-outline" aria-hidden="true" />
                    <div>
                      <strong>No bonus points</strong>
                      <p>The table only uses the win, draw and loss points above.</p>
                    </div>
                    @if (!bonusEnabled()) {
                      <ion-icon name="checkmark-outline" class="tick" aria-hidden="true" />
                    }
                  </button>
                </div>

                @if (bonusEnabled()) {
                  <ion-list inset="true">
                    <ion-item>
                      <ion-select
                        label="Scoring bonus counts"
                        labelPlacement="stacked"
                        interface="action-sheet"
                        [value]="scoringBonusCode()"
                        (ionChange)="scoringBonusCode.set(stringValue($event))"
                      >
                        <ion-select-option value="">Match score</ion-select-option>
                        @for (row of namedDrafts(); track row.key) {
                          <ion-select-option [value]="row.code || row.name.trim()">
                            {{ row.name.trim() }}
                          </ion-select-option>
                        }
                      </ion-select>
                    </ion-item>
                    <ion-item>
                      <ion-input
                        label="Award when they reach"
                        labelPlacement="stacked"
                        type="number"
                        inputmode="numeric"
                        [value]="scoringBonusThreshold()"
                        (ionInput)="scoringBonusThreshold.set(stringValue($event))"
                      />
                    </ion-item>
                    <ion-item>
                      <ion-input
                        label="Scoring bonus points"
                        labelPlacement="stacked"
                        type="number"
                        inputmode="decimal"
                        [value]="scoringBonusPoints()"
                        (ionInput)="scoringBonusPoints.set(stringValue($event))"
                      />
                    </ion-item>
                    <ion-item>
                      <ion-input
                        label="Winning-margin bonus at"
                        labelPlacement="stacked"
                        type="number"
                        inputmode="numeric"
                        [value]="winBonusMargin()"
                        (ionInput)="winBonusMargin.set(stringValue($event))"
                      />
                    </ion-item>
                    <ion-item>
                      <ion-input
                        label="Winning-margin bonus points"
                        labelPlacement="stacked"
                        type="number"
                        inputmode="decimal"
                        [value]="winBonusPoints()"
                        (ionInput)="winBonusPoints.set(stringValue($event))"
                      />
                    </ion-item>
                    <ion-item>
                      <ion-input
                        label="Losing bonus within"
                        labelPlacement="stacked"
                        type="number"
                        inputmode="numeric"
                        [value]="lossBonusMargin()"
                        (ionInput)="lossBonusMargin.set(stringValue($event))"
                      />
                    </ion-item>
                    <ion-item>
                      <ion-input
                        label="Losing bonus points"
                        labelPlacement="stacked"
                        type="number"
                        inputmode="decimal"
                        [value]="lossBonusPoints()"
                        (ionInput)="lossBonusPoints.set(stringValue($event))"
                      />
                    </ion-item>
                  </ion-list>
                  <p class="hint">
                    Leave a threshold blank to skip that bonus. Scoring bonus uses the count of the
                    chosen criterion, or the match total when “Match score” is selected.
                  </p>
                }

                <h3 class="fm-section-title">Format</h3>
                <p class="hint">Choose league, knockout, or both. You must pick one.</p>
                <div class="formats">
                  @for (option of structureFormats; track option.value) {
                    <button
                      type="button"
                      class="format"
                      [class.selected]="form.controls.format.value === option.value"
                      (click)="chooseFormat(option.value)"
                    >
                      <ion-icon [name]="option.icon" aria-hidden="true" />
                      <div>
                        <strong>{{ option.label }}</strong>
                        <p>{{ option.blurb }}</p>
                      </div>
                      @if (form.controls.format.value === option.value) {
                        <ion-icon name="checkmark-outline" class="tick" aria-hidden="true" />
                      }
                    </button>
                  }
                </div>
                @if (form.controls.format.value === 'league_knockout') {
                  <ng-container [ngTemplateOutlet]="leagueCupFields" />
                }
                <p class="hint">
                  Each match keeps a timeline: who scored, who was booked, and at which minute.
                  Yellow and red cards sit next to your scoring criteria. Rate players during the match.
                </p>
              }
            } @else if (scoringLocked()) {
              <p class="hint">{{ lockedStructureHint() }}</p>
              @if (!pointsTable()) {
                <div class="formats">
                  @for (option of structureChoices(); track option.value) {
                    <button
                      type="button"
                      class="format"
                      [class.selected]="form.controls.format.value === option.value"
                      (click)="chooseFormat(option.value)"
                    >
                      <ion-icon [name]="option.icon" aria-hidden="true" />
                      <div>
                        <strong>{{ option.label }}</strong>
                        <p>{{ option.blurb }}</p>
                      </div>
                      @if (form.controls.format.value === option.value) {
                        <ion-icon name="checkmark-outline" class="tick" aria-hidden="true" />
                      }
                    </button>
                  }
                </div>
                @if (form.controls.format.value === 'league_knockout') {
                  <ng-container [ngTemplateOutlet]="leagueCupFields" />
                }
              }
              @if (unitCountOptions(); as choice) {
                <h3 class="fm-section-title">{{ unitName(choice.unit) }}s per match</h3>
                <p class="hint">Chosen now and locked once the competition is created.</p>
                <div class="presets">
                  @for (count of choice.options; track count) {
                    <button
                      type="button"
                      class="preset"
                      [class.selected]="unitCount() === count"
                      (click)="unitCount.set(count)"
                    >
                      <span>{{ count }}</span>
                      <small>{{ unitName(choice.unit) }}s</small>
                    </button>
                  }
                </div>
              }
            } @else {
              <div class="formats">
                @for (option of structureChoices(); track option.value) {
                  <button
                    type="button"
                    class="format"
                    [class.selected]="form.controls.format.value === option.value"
                    (click)="chooseFormat(option.value)"
                  >
                    <ion-icon [name]="option.icon" aria-hidden="true" />
                    <div>
                      <strong>{{ option.label }}</strong>
                      <p>{{ option.blurb }}</p>
                    </div>
                    @if (form.controls.format.value === option.value) {
                      <ion-icon name="checkmark-outline" class="tick" aria-hidden="true" />
                    }
                  </button>
                }
              </div>
              @if (form.controls.format.value === 'league_knockout') {
                <ng-container [ngTemplateOutlet]="leagueCupFields" />
              }
            }

            @if (canOfferSample()) {
              <ng-container [ngTemplateOutlet]="sampleFields" />
            }
          }

          @case (3) {
            <h3 class="fm-section-title">When it runs</h3>
            <p class="hint">
              @if (pointsTable()) {
                Dates are optional. There is no fixture list and no match schedule.
              } @else {
                Dates and match days are optional. Leave them blank if you are still deciding.
              }
            </p>

            <ion-list inset="true">
              <ion-item>
                <ion-input
                  label="Starts on"
                  labelPlacement="stacked"
                  type="date"
                  formControlName="starts_on"
                />
              </ion-item>
              <ion-item>
                <ion-input
                  label="Ends on"
                  labelPlacement="stacked"
                  type="date"
                  formControlName="ends_on"
                />
              </ion-item>
              <ion-item>
                <ion-select
                  label="Timezone"
                  labelPlacement="stacked"
                  interface="action-sheet"
                  formControlName="timezone"
                >
                  @for (zone of timezones; track zone) {
                    <ion-select-option [value]="zone">{{ zone }}</ion-select-option>
                  }
                </ion-select>
              </ion-item>
            </ion-list>

            @if (form.hasError('dateOrder')) {
              <p class="fm-form-error" role="alert">The end date is before the start date.</p>
            }

            @if (!pointsTable() && form.controls.format.value === 'league_knockout') {
              <ng-container [ngTemplateOutlet]="leagueCupFields" />
              <p class="hint">
                After this many league match days there is a competition game. Change this later when you generate the schedule.
              </p>
            }

            @if (!pointsTable()) {
            <div class="weekdays">
              <p class="label">Usual match days</p>
              <div class="days">
                @for (day of weekdays; track day.value) {
                  <button
                    type="button"
                    class="day"
                    [class.on]="isWeekdayOn(day.value)"
                    (click)="toggleWeekday(day.value)"
                  >
                    {{ day.label }}
                  </button>
                }
              </div>
            </div>
            }

            <h3 class="fm-section-title">Who can see it</h3>
            <div class="visibility">
              <button
                type="button"
                class="vis"
                [class.selected]="!form.controls.is_private.value"
                (click)="setPrivate(false)"
              >
                <ion-icon name="globe-outline" aria-hidden="true" />
                <strong>Public</strong>
                <p>Anyone signed in can find it and ask to join.</p>
              </button>
              <button
                type="button"
                class="vis"
                [class.selected]="form.controls.is_private.value"
                (click)="setPrivate(true)"
              >
                <ion-icon name="lock-closed-outline" aria-hidden="true" />
                <strong>Private</strong>
                <p>Only people you add can see it.</p>
              </button>
              @if (!form.controls.is_private.value) {
                <button
                  type="button"
                  class="vis landing"
                  [class.selected]="form.controls.show_on_landing.value"
                  (click)="form.controls.show_on_landing.setValue(!form.controls.show_on_landing.value)"
                >
                  <ion-icon name="megaphone-outline" aria-hidden="true" />
                  <strong>Show on the landing page</strong>
                  <p>
                    Visitors can see this competition before they sign in. Use this to make it more
                    public.
                  </p>
                </button>
              }
            </div>

            @if (scoutable()) {
              <h3 class="fm-section-title">Scouting</h3>
              <div class="visibility">
                <button
                  type="button"
                  class="vis"
                  [class.selected]="!form.controls.open_to_scouts.value"
                  (click)="form.controls.open_to_scouts.setValue(false)"
                >
                  <ion-icon name="eye-off-outline" aria-hidden="true" />
                  <strong>Closed to scouts</strong>
                  <p>The league stays between its players, officials and fans.</p>
                </button>
                <button
                  type="button"
                  class="vis"
                  [class.selected]="form.controls.open_to_scouts.value"
                  (click)="form.controls.open_to_scouts.setValue(true)"
                >
                  <ion-icon name="ribbon-outline" aria-hidden="true" />
                  <strong>Open to scouts</strong>
                  <p>
                    Scouts can follow it, its results feed scouting reports, and it can name its own squad
                    of the best players. Players still decide who sees their profile.
                  </p>
                </button>
              </div>
            }

            <div class="summary fm-card">
              <h4>You are creating</h4>
              <dl>
                <div>
                  <dt>Name</dt>
                  <dd>{{ form.controls.name.value || 'Untitled' }}</dd>
                </div>
                <div>
                  <dt>Type</dt>
                  <dd>{{ typeLabel() }}</dd>
                </div>
                @if (activePreset()?.description) {
                  <div>
                    <dt>How points are earned</dt>
                    <dd>{{ activePreset()?.description }}</dd>
                  </div>
                }
                <div>
                  <dt>Scoring</dt>
                  <dd>
                    {{ namedDrafts().length }} criteria,
                    {{ scoringBasis() === 'criteria' ? 'summed' : 'win / draw / loss' }}
                  </dd>
                </div>
                <div>
                  <dt>Format</dt>
                  <dd>
                    @if (pointsTable()) {
                      Points accumulation
                    } @else if (isCustom()) {
                      VS competition · {{ formatShort(form.controls.format.value) }}
                    } @else {
                      {{ formatShort(form.controls.format.value) }}
                    }
                  </dd>
                </div>
                @if (isCustom() && !pointsTable()) {
                  <div>
                    <dt>Who plays</dt>
                    <dd>{{ versusEntrants() === 'team' ? 'Teams' : 'Individuals' }}</dd>
                  </div>
                  <div>
                    <dt>Table points</dt>
                    <dd>
                      Win {{ winPoints() || 0 }} · Draw {{ drawPoints() || 0 }} · Loss {{ lossPoints() || 0 }}
                    </dd>
                  </div>
                  <div>
                    <dt>Bonus points</dt>
                    <dd>{{ bonusSummary() }}</dd>
                  </div>
                }
                <div>
                  <dt>Visibility</dt>
                  <dd>{{ visibilityLabel() }}</dd>
                </div>
                @if (scoutable()) {
                  <div>
                    <dt>Scouts</dt>
                    <dd>{{ form.controls.open_to_scouts.value ? 'Open: can name its own squad' : 'Closed' }}</dd>
                  </div>
                }
              </dl>
            </div>

            @if (canOfferSample()) {
              <ng-container [ngTemplateOutlet]="sampleFields" />
            }
          }
        }

        @if (error()) {
          <p class="fm-form-error" role="alert">{{ error() }}</p>
        }

        <ng-template #leagueCupFields>
          <ion-list inset="true">
            <ion-item>
              <ion-input
                label="Cup game after every"
                labelPlacement="stacked"
                type="number"
                inputmode="numeric"
                min="1"
                formControlName="cup_every_league_rounds"
              />
            </ion-item>
            @for (name of cupNames(); track $index) {
              <ion-item>
                <ion-input
                  label="Cup name"
                  labelPlacement="stacked"
                  [value]="name"
                  (ionInput)="setCupName($index, $any($event).detail.value)"
                />
                @if (cupNames().length > 1) {
                  <ion-button slot="end" fill="clear" (click)="removeCup($index)">Remove</ion-button>
                }
              </ion-item>
            }
            <ion-item button="true" (click)="addCup()">
              <ion-label>Add another cup</ion-label>
            </ion-item>
          </ion-list>
          <p class="hint">
            Each cup needs a unique name. Only one cup runs at a time; the next starts after the current
            cup is finished.
          </p>
        </ng-template>
      </form>

      <ng-template #sampleFields>
        <h3 class="fm-section-title">Try it first</h3>
        <ion-list inset="true">
          <ion-item>
            <ion-checkbox
              labelPlacement="end"
              justify="start"
              [checked]="fillSample()"
              (ionChange)="fillSample.set($any($event).detail.checked === true)"
            >
              Generate a one-hour demo {{ sampleNoun() }} after create
            </ion-checkbox>
          </ion-item>
        </ion-list>
        <p class="hint">
          Fills {{ samplePeople() }}, officials
          @if (!pointsTable() && versusEntrants() === 'team') {
            , picks, fixtures, player ratings, player stats, the league squad and a fantasy league
          } @else if (!pointsTable()) {
            , picks and fixtures
          }
          so you can see the product without the full setup. This is a demo
          {{ sampleNoun() }} and it deletes itself after one hour.
        </p>
      </ng-template>
    </ion-content>

    <ion-footer>
      <ion-toolbar>
        <div class="footer-actions">
          @if (step() > 1) {
            <ion-button fill="clear" type="button" (click)="back()">Back</ion-button>
          } @else {
            <span></span>
          }

          @if (step() < 3) {
            <ion-button type="button" (click)="next()">Continue</ion-button>
          } @else {
            <ion-button type="button" (click)="submit()" [disabled]="form.invalid || saving()">
              @if (saving()) {
                <ion-spinner name="crescent" />
              } @else {
                Create competition
              }
            </ion-button>
          }
        </div>
      </ion-toolbar>
    </ion-footer>
  `,
})
export class CompetitionCreatePage implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(ApiService);
  private readonly navCtrl = inject(NavController);
  private readonly alerts = inject(AlertController);
  private readonly scouting = inject(ScoutingService);

  readonly scoutingCatalog = signal<ScoutingCatalog | null>(null);
  private nextDraftKey = 1;

  readonly weekdays = WEEKDAYS;
  readonly steps = [
    { n: 1 as const, label: 'Type' },
    { n: 2 as const, label: 'Details' },
    { n: 3 as const, label: 'Schedule' },
  ];

  readonly formats: FormatOption[] = [
    {
      value: 'league',
      label: 'League',
      blurb: 'Everyone plays everyone. Ranked on a table from match results.',
      icon: 'podium-outline',
    },
    {
      value: 'knockout',
      label: 'Knockout',
      blurb: 'Single elimination. Lose and you are out. There is no league table.',
      icon: 'git-network-outline',
    },
    {
      value: 'league_knockout',
      label: 'League and knockout',
      blurb: 'A league table plus named cups. Cups run one at a time after every few league match days.',
      icon: 'git-merge-outline',
    },
    {
      value: 'group_knockout',
      label: 'Groups then knockout',
      blurb: 'Group stage first, then a knockout from the top finishers.',
      icon: 'grid-outline',
    },
    {
      value: 'ladder',
      label: 'Ladder',
      blurb: 'Challenge the person above you. Rankings move after each result.',
      icon: 'swap-vertical-outline',
    },
    {
      value: 'freeform',
      label: 'Freeform',
      blurb: 'No generated schedule. Add fixtures whenever you want.',
      icon: 'sparkles-outline',
    },
  ];

  readonly structureFormats = this.formats.filter((option) =>
    option.value === 'league' || option.value === 'knockout' || option.value === 'league_knockout',
  );

  readonly versusFormats = this.formats.filter((option) => option.value !== 'freeform');

  readonly winPoints = signal('3');
  readonly drawPoints = signal('1');
  readonly lossPoints = signal('0');
  readonly versusEntrants = signal<'team' | 'individual'>('team');
  readonly bonusEnabled = signal(false);
  readonly scoringBonusCode = signal('');
  readonly scoringBonusThreshold = signal('4');
  readonly scoringBonusPoints = signal('1');
  readonly winBonusMargin = signal('');
  readonly winBonusPoints = signal('1');
  readonly lossBonusMargin = signal('7');
  readonly lossBonusPoints = signal('1');

  readonly presets = signal<Preset[]>([]);
  readonly selectedPreset = signal<string>('custom');
  readonly scoringDrafts = signal<ScoringDraft[]>([this.blankDraft()]);
  readonly step = signal<Step>(1);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);

  readonly everydayPresets = computed(() =>
    this.presets().filter((preset) => presetKind(preset) !== 'sport'),
  );

  readonly sportPresets = computed(() =>
    this.presets().filter((preset) => presetKind(preset) === 'sport'),
  );

  readonly sportQuery = signal('');

  /** Long catalogues stay closed until the reader opens them. */
  readonly closedGroups = signal(new Set(['olympic', 'winter']));

  readonly sportGroups = computed(() => {
    const query = this.sportQuery().trim().toLowerCase();
    const sports = this.sportPresets().filter((preset) => {
      if (!query) return true;
      return (
        preset.label.toLowerCase().includes(query) ||
        preset.sport.toLowerCase().includes(query) ||
        (preset.group_label ?? '').toLowerCase().includes(query) ||
        (preset.family_label ?? '').toLowerCase().includes(query) ||
        (preset.variant_label ?? '').toLowerCase().includes(query)
      );
    });
    const order = ['ball', 'racket', 'golf', 'target', 'board', 'equestrian', 'olympic', 'winter'];
    const buckets = new Map<string, Preset[]>();
    const labels = new Map<string, string>();
    for (const preset of sports) {
      const key = preset.group || 'other';
      const list = buckets.get(key) ?? [];
      list.push(preset);
      buckets.set(key, list);
      if (!labels.has(key)) labels.set(key, preset.group_label || 'Other');
    }
    const keys = [
      ...order.filter((key) => buckets.has(key)),
      ...[...buckets.keys()].filter((key) => !order.includes(key)),
    ];
    return keys.map((key) => ({
      key,
      label: labels.get(key) ?? 'Other',
      presets: buckets.get(key) ?? [],
    }));
  });

  readonly activePreset = computed(() => {
    const key = this.selectedPreset();
    return this.presets().find((preset) => preset.key === key) ?? null;
  });

  readonly scoringBasis = signal<'results' | 'criteria'>('criteria');

  readonly pointsTable = computed(() => this.scoringBasis() === 'criteria');
  readonly fillSample = signal(false);

  canOfferSample(): boolean {
    if (this.pointsTable()) return true;
    return !!this.form.controls.format.value;
  }

  sampleNoun(): string {
    if (this.pointsTable()) return 'competition';
    if (this.form.controls.format.value === 'knockout') return 'cup';
    return 'league';
  }

  samplePeople(): string {
    if (this.pointsTable() || this.versusEntrants() === 'individual') return 'players';
    return 'teams';
  }

  readonly namedDrafts = computed(() =>
    this.scoringDrafts().filter((row) => row.name.trim()),
  );

  readonly isCustom = computed(() => {
    const preset = this.activePreset();
    return this.selectedPreset() === 'custom' || (preset ? presetKind(preset) === 'custom' : true);
  });

  readonly scoringLocked = computed(() => {
    const preset = this.activePreset();
    return !!preset && preset.key !== 'custom' && preset.scoring_locked !== false;
  });

  readonly timezones = this.buildTimezones();

  readonly cupNames = signal<string[]>(['Cup']);

  readonly form = this.fb.nonNullable.group(
    {
      name: ['', [Validators.required, Validators.maxLength(200)]],
      description: [''],
      sport: [''],
      format: ['league' as CompetitionFormat, [Validators.required]],
      cup_every_league_rounds: [3, [Validators.min(1)]],
      starts_on: [''],
      ends_on: [''],
      timezone: [localTimezone()],
      is_private: [false],
      show_on_landing: [false],
      open_to_scouts: [false],
      match_weekdays: [[] as number[]],
    },
    { validators: endAfterStart },
  );

  addCup(): void {
    this.cupNames.update((names) => [...names, '']);
  }

  removeCup(index: number): void {
    this.cupNames.update((names) => names.filter((_, current) => current !== index));
  }

  setCupName(index: number, value: string | null | undefined): void {
    const next = value ?? '';
    const names = this.cupNames();
    if (names[index] === next) return;
    this.cupNames.set(names.map((name, current) => (current === index ? next : name)));
  }

  normalizedCups(): string[] {
    const seen = new Set<string>();
    const names: string[] = [];
    for (const raw of this.cupNames()) {
      const name = raw.trim();
      const key = name.toLowerCase();
      if (!name || seen.has(key)) continue;
      seen.add(key);
      names.push(name);
    }
    return names.length ? names : ['Cup'];
  }

  ngOnInit(): void {
    this.scouting.catalog().subscribe({
      next: (catalog) => this.scoutingCatalog.set(catalog),
      error: () => this.scoutingCatalog.set(null),
    });
    this.api.listPresets().subscribe({
      next: (presets) => {
        this.presets.set(presets);
        this.selectPreset(this.selectedPreset());
      },
      error: () => this.presets.set([]),
    });
  }

  readonly unitCount = signal<number | null>(null);

  unitCountOptions(): { unit: string; options: number[]; default?: number } | null {
    const options = this.activePreset()?.unit_count_options;
    return options?.options?.length ? options : null;
  }

  unitName(unit: string): string {
    const text = unit.replace(/_/g, ' ');
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  selectPreset(key: string): void {
    this.selectedPreset.set(key);
    const preset = this.presets().find((candidate) => candidate.key === key);
    this.unitCount.set(preset?.unit_count_options?.default ?? null);
    if (preset?.format) {
      this.form.patchValue({ format: preset.format, sport: preset.sport });
    }
    if (preset) {
      this.replaceScoring(preset.scoring_categories);
    } else if (key === 'custom') {
      this.form.patchValue({ sport: '' });
      this.replaceScoring([]);
    }
    this.scoringBasis.set(isPointsPreset(preset ?? { key }) ? 'criteria' : 'results');
    if (this.isCustom()) {
      this.scoringBasis.set('criteria');
      this.form.controls.format.setValue('freeform');
      this.form.controls.match_weekdays.setValue([]);
    } else {
      this.ensureCompatibleFormat();
    }
  }

  setCustomMode(mode: 'points' | 'versus'): void {
    if (mode === 'versus') {
      this.scoringBasis.set('results');
      if (this.form.controls.format.value === 'freeform') {
        this.form.controls.format.setValue('league');
      }
      return;
    }
    this.scoringBasis.set('criteria');
    this.form.controls.format.setValue('freeform');
    this.form.controls.match_weekdays.setValue([]);
  }

  setBonusEnabled(enabled: boolean): void {
    this.bonusEnabled.set(enabled);
    if (!enabled) return;
    if (!this.scoringBonusCode()) {
      const first = this.namedDrafts()[0];
      this.scoringBonusCode.set(first ? first.code || first.name.trim() : '');
    }
  }

  bonusSummary(): string {
    if (!this.bonusEnabled()) return 'Off';
    const parts: string[] = [];
    if (this.scoringBonusThreshold()) {
      const of = this.scoringBonusLabel();
      parts.push(`+${this.scoringBonusPoints() || 0} for ${this.scoringBonusThreshold()}+ ${of}`);
    }
    if (this.winBonusMargin()) {
      parts.push(`+${this.winBonusPoints() || 0} winning by ${this.winBonusMargin()}`);
    }
    if (this.lossBonusMargin()) {
      parts.push(`+${this.lossBonusPoints() || 0} losing by ${this.lossBonusMargin()}`);
    }
    return parts.length ? parts.join(' · ') : 'On, no thresholds set';
  }

  private scoringBonusLabel(): string {
    const code = this.scoringBonusCode();
    if (!code) return 'match score';
    return this.namedDrafts().find((row) => (row.code || row.name.trim()) === code)?.name.trim() || code;
  }

  private tableBonusPayload(): Record<string, unknown> {
    if (!this.bonusEnabled()) return { enabled: false };
    return {
      enabled: true,
      scoring_threshold: Number(this.scoringBonusThreshold()) || null,
      scoring_points: Number(this.scoringBonusPoints() || 0),
      scoring_code: this.scoringBonusCode(),
      win_margin: Number(this.winBonusMargin()) || null,
      win_points: Number(this.winBonusPoints() || 0),
      loss_margin: Number(this.lossBonusMargin()) || null,
      loss_points: Number(this.lossBonusPoints() || 0),
    };
  }

  formatHint(): string {
    if (this.isCustom()) {
      return this.pointsTable()
        ? 'Choose how the table is built. Points accumulation collects points without a match schedule.'
        : 'Choose league, knockout, or both. A VS competition plays fixtures and ranks on match results.';
    }
    if (this.scoringLocked()) {
      return 'Scoring follows the official rules. Choose whether this is a league, a knockout, or both.';
    }
    return 'Choose league, knockout, or both. You can still add one-off matches later.';
  }

  lockedStructureHint(): string {
    const preset = this.activePreset();
    if (!preset) return '';
    if (preset.table_mode === 'points') {
      const order = preset.accumulation_ranking === 'lowest_first' ? 'lowest total first' : 'highest first';
      return `Entrants do not play each other. The table ranks by points accumulated from the scoring rules above, ${order}.`;
    }
    return 'Choose league, knockout, or league and knockout. Scoring stays as the official rules.';
  }

  showTypeLabel(): boolean {
    const preset = this.activePreset();
    if (!preset) return true;
    return presetKind(preset) !== 'sport';
  }

  typePlaceholder(): string {
    const preset = this.activePreset();
    const kind = preset ? presetKind(preset) : 'custom';
    if (kind === 'work') return 'e.g. sales KPIs, support SLAs';
    if (kind === 'home') return 'e.g. flat cleaning, garden jobs';
    return 'e.g. chess, office olympics, chores';
  }

  kindCaption(preset: Preset): string {
    switch (presetKind(preset)) {
      case 'work':
        return 'Official scoring';
      case 'home':
        return 'Official scoring';
      case 'custom':
        return 'Define scoring yourself';
      default:
        return this.formatShort(preset.format);
    }
  }

  presetIcon(preset: Preset): string {
    return preset.icon || 'trophy-outline';
  }

  /** Tapping a card shows only that card and its scoring; tapping it again shows every card. */
  readonly focused = signal(false);
  private readonly content = viewChild(IonContent);

  readonly shownEveryday = computed(() =>
    this.focused()
      ? this.everydayPresets().filter((preset) => preset.key === this.selectedPreset())
      : this.everydayPresets(),
  );

  readonly shownGroups = computed(() => {
    if (!this.focused()) return this.sportGroups();
    const chosen = this.sportPresets().find((preset) => preset.key === this.selectedPreset());
    if (!chosen) return [];
    const members = chosen.family
      ? this.sportPresets().filter((preset) => preset.family === chosen.family)
      : [chosen];
    return [{ key: chosen.group || 'other', label: chosen.group_label || 'Other', presets: members }];
  });

  familyCards(presets: Preset[]): FamilyCard[] {
    const families = new Map<string, Preset[]>();
    const singles: Preset[] = [];
    for (const preset of presets) {
      if (preset.family) {
        const members = families.get(preset.family) ?? [];
        members.push(preset);
        families.set(preset.family, members);
      } else {
        singles.push(preset);
      }
    }
    const cards: FamilyCard[] = [];
    for (const [family, members] of families) {
      const head = this.familyHead(members);
      cards.push({
        key: family,
        label: head.family_label || head.label,
        icon: head.icon,
        caption: members.length === 1 ? this.presetSide(head) : `${members.length} codes`,
        presets: members,
      });
    }
    for (const preset of singles) {
      cards.push({
        key: preset.key,
        label: preset.label,
        icon: preset.icon,
        caption: this.presetSide(preset),
        presets: [preset],
      });
    }
    return cards;
  }

  familySelected(card: FamilyCard): boolean {
    return this.focused() && card.presets.some((preset) => preset.key === this.selectedPreset());
  }

  tapFamily(card: FamilyCard): void {
    if (this.familySelected(card)) {
      this.focused.set(false);
      return;
    }
    const current = card.presets.find((preset) => preset.key === this.selectedPreset());
    this.selectPreset((current ?? this.familyHead(card.presets)).key);
    this.focused.set(true);
    this.scrollToStart();
  }

  selectVariant(key: string, event: Event): void {
    event.stopPropagation();
    this.selectPreset(key);
    this.focused.set(true);
  }

  firstSentence(text: string): string {
    const match = text.match(/^[^.!?]+[.!?]?/);
    return (match?.[0] ?? text).trim();
  }

  private familyHead(members: Preset[]): Preset {
    return (
      members.find((preset) =>
        ['association', 'fifteens', 'thirteens'].includes(preset.variant ?? ''),
      ) ?? members[0]
    );
  }

  tapPreset(key: string): void {
    if (this.focused() && key === this.selectedPreset()) {
      this.focused.set(false);
      return;
    }
    if (key !== this.selectedPreset()) this.selectPreset(key);
    this.focused.set(true);
    this.scrollToStart();
  }

  groupOpen(key: string): boolean {
    if (this.sportQuery().trim()) return true;
    return !this.closedGroups().has(key);
  }

  toggleGroup(key: string): void {
    if (this.sportQuery().trim()) return;
    this.closedGroups.update((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  formatChoices(): FormatOption[] {
    const allowed = this.activePreset()?.formats_allowed;
    if (!allowed?.length) return this.formats;
    const mapped = new Set(allowed.map((value) => this.modelFormat(value)));
    if (mapped.has('league') && mapped.has('knockout')) mapped.add('league_knockout');
    const choices = this.formats.filter((option) => mapped.has(option.value));
    return choices.length ? choices : this.formats;
  }

  structureChoices(): FormatOption[] {
    const allowed = new Set(this.formatChoices().map((option) => option.value));
    const choices = this.structureFormats.filter((option) => allowed.has(option.value));
    return choices.length ? choices : this.structureFormats;
  }

  private modelFormat(value: string): CompetitionFormat {
    if (value === 'groups_knockout') return 'group_knockout';
    if (value === 'round_robin') return 'league';
    if (
      value === 'league' ||
      value === 'knockout' ||
      value === 'league_knockout' ||
      value === 'group_knockout' ||
      value === 'ladder' ||
      value === 'freeform'
    ) {
      return value;
    }
    return 'league';
  }

  formatShort(format: string): string {
    return this.formats.find((option) => option.value === format)?.label ?? format;
  }

  presetSide(preset: Preset): string {
    const starters = preset.team_sheet?.starters;
    if (starters === 1) return '1 player';
    if (starters && starters > 0) return `${starters}-a-side`;
    return this.formatShort(preset.format);
  }

  chooseFormat(value: CompetitionFormat): void {
    this.form.controls.format.setValue(value);
    if (value !== 'freeform') {
      this.ensureMatchEventDrafts();
    }
  }

  /** VS matches record who scored or was booked, so those event types stay on the sheet. */
  private ensureMatchEventDrafts(): void {
    const have = new Set(
      this.scoringDrafts().map((row) => (row.code || row.name).trim().toLowerCase()),
    );
    const extras: Array<Partial<ScoringDraft>> = [
      {
        name: 'Yellow card',
        code: 'yellow-card',
        points: '0',
        affects_score: false,
        description: 'A booking. Shown on the match timeline with the minute and the player.',
      },
      {
        name: 'Red card',
        code: 'red-card',
        points: '0',
        affects_score: false,
        description: 'A sending-off. Shown on the match timeline with the minute and the player.',
      },
    ];
    const add = extras.filter((row) => !have.has((row.code || row.name || '').toLowerCase()));
    if (!add.length) return;
    this.scoringDrafts.update((rows) => [...rows, ...add.map((row) => this.blankDraft(row))]);
  }

  private ensureCompatibleFormat(): void {
    const allowed = new Set(this.formats.map((option) => option.value));
    if (!allowed.has(this.form.controls.format.value)) {
      this.form.controls.format.setValue('league');
    }
  }

  typeLabel(): string {
    const typed = this.form.controls.sport.value.trim();
    if (typed) return typed;
    return this.activePreset()?.label ?? this.selectedPreset();
  }

  stringValue(event: Event): string {
    return String((event as CustomEvent<{ value: string | null | undefined }>).detail?.value ?? '');
  }

  checkboxValue(event: Event): boolean {
    return Boolean((event as CustomEvent<{ checked: boolean }>).detail?.checked);
  }

  patchDraft(key: number, patch: Partial<ScoringDraft>): void {
    this.scoringDrafts.update((rows) => {
      const current = rows.find((row) => row.key === key);
      if (!current) return rows;
      const next = { ...current, ...patch };
      const unchanged = (Object.keys(patch) as Array<keyof ScoringDraft>).every(
        (field) => current[field] === next[field],
      );
      if (unchanged) return rows;
      return rows.map((row) => (row.key === key ? next : row));
    });
  }

  /** A failed scroll must not surface as "Something went wrong on this screen." */
  private scrollToStart(): void {
    void this.content()
      ?.scrollToTop(250)
      ?.catch(() => undefined);
  }

  addDraft(): void {
    this.scoringDrafts.update((rows) => [...rows, this.blankDraft()]);
  }

  /** Ask before deleting a filled-in scoring item; an empty row just goes. */
  async confirmRemoveDraft(key: number): Promise<void> {
    const row = this.scoringDrafts().find((item) => item.key === key);
    if (!row) return;
    if (!row.name.trim() && !row.description.trim()) {
      this.removeDraft(key);
      return;
    }
    const unit = this.pointsTable() ? 'per unit' : 'pts';
    const alert = await this.alerts.create({
      header: `Delete ${row.name.trim() || 'this scoring item'}?`,
      message: `${row.points || '0'} ${unit}. This removes it from the scoring.`,
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        { text: 'Delete', role: 'destructive', handler: () => this.removeDraft(key) },
      ],
    });
    await alert.present();
  }

  removeDraft(key: number): void {
    this.scoringDrafts.update((rows) => {
      const next = rows.filter((row) => row.key !== key);
      return next.length ? next : [this.blankDraft()];
    });
  }

  isWeekdayOn(day: number): boolean {
    return this.form.controls.match_weekdays.value.includes(day);
  }

  toggleWeekday(day: number): void {
    const current = this.form.controls.match_weekdays.value;
    const next = current.includes(day)
      ? current.filter((candidate) => candidate !== day)
      : [...current, day].sort((a, b) => a - b);
    this.form.controls.match_weekdays.setValue(next);
  }

  next(): void {
    if (this.step() === 1 && this.isCustom() && this.namedDrafts().length === 0) {
      this.error.set('Define at least one scoring criterion before continuing.');
      return;
    }
    if (this.step() === 2 && this.form.controls.name.invalid) {
      this.form.controls.name.markAsTouched();
      this.error.set('Give the competition a name.');
      this.scrollToStart();
      return;
    }
    this.error.set(null);
    if (this.step() < 3) {
      this.step.set((this.step() + 1) as Step);
    }
  }

  onFormSubmit(): void {
    if (this.step() < 3) {
      this.next();
      return;
    }
    this.submit();
  }

  back(): void {
    if (this.step() > 1) {
      this.step.set((this.step() - 1) as Step);
    }
  }

  goTo(target: Step): void {
    if (target < this.step()) {
      this.step.set(target);
      return;
    }
    if (target === 2 || (target === 3 && this.form.controls.name.valid)) {
      this.step.set(target);
      return;
    }
    this.form.controls.name.markAsTouched();
    this.error.set('Give the competition a name.');
    this.scrollToStart();
  }

  setPrivate(isPrivate: boolean): void {
    this.form.controls.is_private.setValue(isPrivate);
    if (isPrivate) {
      this.form.controls.show_on_landing.setValue(false);
    }
  }

  visibilityLabel(): string {
    if (this.form.controls.is_private.value) return 'Private';
    if (this.form.controls.show_on_landing.value) return 'Public · on the landing page';
    return 'Public';
  }

  /** Only sports that scouting covers can be opened to scouts. */
  scoutable(): boolean {
    return scoutingSportFor(this.form.controls.sport.value, this.scoutingCatalog()) !== null;
  }

  submit(): void {
    if (this.form.invalid || this.saving()) {
      this.form.markAllAsTouched();
      this.step.set(this.form.controls.name.invalid ? 2 : 3);
      return;
    }

    this.saving.set(true);
    this.error.set(null);

    const raw = this.form.getRawValue();
    const preset = this.selectedPreset();
    const locked = this.scoringLocked();
    if (!this.pointsTable() && raw.format !== 'freeform') {
      this.ensureMatchEventDrafts();
    }
    const scoring_categories = this.namedDrafts().map((row) => ({
      name: row.name.trim(),
      description: row.description.trim(),
      points: row.points || (this.pointsTable() ? '1' : '0'),
      affects_score: row.affects_score,
      ...(row.code ? { code: row.code } : {}),
    }));

    this.api
      .createCompetition({
        name: raw.name.trim(),
        description: raw.description.trim(),
        sport: raw.sport.trim(),
        format: raw.format,
        ...(raw.format === 'league_knockout'
          ? {
              cup_every_league_rounds: Number(raw.cup_every_league_rounds) || 3,
              cups: this.normalizedCups(),
            }
          : {}),
        ...(locked ? {} : { scoring_basis: this.scoringBasis(), scoring_categories }),
        ...(this.unitCountOptions() && this.unitCount() ? { unit_count: this.unitCount() } : {}),
        ...(this.isCustom() && !this.pointsTable()
          ? {
              participant_type: this.versusEntrants(),
              league_points: {
                win: Number(this.winPoints() || 0),
                draw: Number(this.drawPoints() || 0),
                loss: Number(this.lossPoints() || 0),
              },
              table_bonus: this.tableBonusPayload(),
            }
          : {}),
        is_private: raw.is_private,
        show_on_landing: !raw.is_private && raw.show_on_landing,
        open_to_scouts: this.scoutable() && raw.open_to_scouts,
        starts_on: raw.starts_on || null,
        ends_on: raw.ends_on || null,
        timezone: raw.timezone,
        match_weekdays: this.scoringBasis() === 'criteria' ? [] : raw.match_weekdays,
        preset,
      })
      .subscribe({
        next: (competition) => {
          const goSetup = () => {
            this.saving.set(false);
            void this.navCtrl.navigateForward(`/tabs/competitions/${competition.id}/setup`, {
              replaceUrl: true,
            });
          };
          if (!this.fillSample()) {
            goSetup();
            return;
          }
          this.api.generateDemoLeague(competition.id).subscribe({
            next: () => goSetup(),
            error: () => goSetup(),
          });
        },
        error: (err: unknown) => {
          this.saving.set(false);
          this.error.set(extractErrorMessage(err, 'Could not create that competition.'));
        },
      });
  }

  private blankDraft(partial?: Partial<ScoringDraft>): ScoringDraft {
    const key = this.nextDraftKey++;
    return {
      key,
      name: partial?.name ?? '',
      description: partial?.description ?? '',
      points: partial?.points ?? '1',
      affects_score: partial?.affects_score ?? true,
      code: partial?.code ?? '',
    };
  }

  private replaceScoring(categories: Preset['scoring_categories'] | null | undefined): void {
    if (!categories?.length) {
      this.scoringDrafts.set([this.blankDraft()]);
      return;
    }
    this.scoringDrafts.set(
      categories.map((category) =>
        this.blankDraft({
          name: category.name,
          description: category.description ?? '',
          points: category.points,
          affects_score: category.affects_score,
          code: category.code,
        }),
      ),
    );
  }

  private buildTimezones(): string[] {
    const local = localTimezone();
    const zones = new Set(TIMEZONES);
    zones.add(local);
    return [...zones].sort((a, b) => a.localeCompare(b));
  }
}
