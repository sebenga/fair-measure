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
  IonList,
  IonSelect,
  IonSelectOption,
  IonSpinner,
  IonTextarea,
  IonTitle,
  IonToolbar,
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
                    <span class="count">{{ group.presets.length }}</span>
                    <ion-icon name="chevron-forward-outline" aria-hidden="true" />
                  </button>
                }
                @if (focused() || groupOpen(group.key)) {
                  <div class="presets fm-stagger">
                    @for (preset of group.presets; track preset.key) {
                      <button
                        type="button"
                        class="preset"
                        [class.selected]="focused() && selectedPreset() === preset.key"
                        [attr.aria-pressed]="focused() && selectedPreset() === preset.key"
                        (click)="tapPreset(preset.key)"
                      >
                        <ion-icon [name]="presetIcon(preset)" aria-hidden="true" />
                        <span>{{ preset.label }}</span>
                        <small>{{ formatShort(preset.format) }}</small>
                      </button>
                    @if (focused() && selectedPreset() === preset.key) {
                      <div class="inline-scoring"><ng-container *ngTemplateOutlet="scoringPanel" /></div>
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
                        [disabled]="scoringDrafts().length === 1"
                        (click)="removeDraft(row.key)"
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

                <h3 class="fm-section-title">Format</h3>
                <div class="formats">
                  @for (option of versusFormats; track option.value) {
                    <button
                      type="button"
                      class="format"
                      [class.selected]="form.controls.format.value === option.value"
                      (click)="form.controls.format.setValue(option.value)"
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
              }
            } @else if (scoringLocked()) {
              <p class="hint">{{ lockedStructureHint() }}</p>
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
                @for (option of formatChoices(); track option.value) {
                  <button
                    type="button"
                    class="format"
                    [class.selected]="form.controls.format.value === option.value"
                    (click)="form.controls.format.setValue(option.value)"
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
                (click)="form.controls.is_private.setValue(false)"
              >
                <ion-icon name="globe-outline" aria-hidden="true" />
                <strong>Public</strong>
                <p>Anyone signed in can find it and ask to join.</p>
              </button>
              <button
                type="button"
                class="vis"
                [class.selected]="form.controls.is_private.value"
                (click)="form.controls.is_private.setValue(true)"
              >
                <ion-icon name="lock-closed-outline" aria-hidden="true" />
                <strong>Private</strong>
                <p>Only people you add can see it.</p>
              </button>
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
                }
                <div>
                  <dt>Visibility</dt>
                  <dd>{{ form.controls.is_private.value ? 'Private' : 'Public' }}</dd>
                </div>
                @if (scoutable()) {
                  <div>
                    <dt>Scouts</dt>
                    <dd>{{ form.controls.open_to_scouts.value ? 'Open: can name its own squad' : 'Closed' }}</dd>
                  </div>
                }
              </dl>
            </div>
          }
        }

        @if (error()) {
          <p class="fm-form-error" role="alert">{{ error() }}</p>
        }
      </form>
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
      blurb: 'Single elimination. Lose and you are out.',
      icon: 'git-network-outline',
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

  readonly versusFormats = this.formats.filter((option) => option.value !== 'freeform');

  readonly winPoints = signal('3');
  readonly drawPoints = signal('1');
  readonly lossPoints = signal('0');
  readonly versusEntrants = signal<'team' | 'individual'>('team');

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
        (preset.group_label ?? '').toLowerCase().includes(query)
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

  readonly form = this.fb.nonNullable.group(
    {
      name: ['', [Validators.required, Validators.maxLength(200)]],
      description: [''],
      sport: [''],
      format: ['league' as CompetitionFormat, [Validators.required]],
      starts_on: [''],
      ends_on: [''],
      timezone: [localTimezone()],
      is_private: [false],
      open_to_scouts: [false],
      match_weekdays: [[] as number[]],
    },
    { validators: endAfterStart },
  );

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

  formatHint(): string {
    if (this.isCustom()) {
      return this.pointsTable()
        ? 'Choose how the table is built. Points accumulation collects points without a match schedule.'
        : 'Choose how the table is built. A VS competition plays fixtures and ranks on match results.';
    }
    if (this.scoringLocked()) {
      return 'This follows the official structure for the preset. It cannot be changed.';
    }
    return 'This decides how fixtures are generated. You can still add one-off matches later.';
  }

  lockedStructureHint(): string {
    const preset = this.activePreset();
    if (!preset) return '';
    if (preset.table_mode === 'points') {
      const order = preset.accumulation_ranking === 'lowest_first' ? 'lowest total first' : 'highest first';
      return `Entrants do not play each other. The table ranks by points accumulated from the scoring rules above, ${order}.`;
    }
    if (preset.format === 'knockout') {
      return 'Knockout. The winner of each fixture advances until a champion is decided. There is no league table.';
    }
    return 'League. A win is worth 3 points, a draw 1, and a loss 0. The table ranks by points, then the sport’s tie-breakers.';
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
    return [{ key: chosen.group || 'other', label: chosen.group_label || 'Other', presets: [chosen] }];
  });

  tapPreset(key: string): void {
    if (this.focused() && key === this.selectedPreset()) {
      this.focused.set(false);
      return;
    }
    if (key !== this.selectedPreset()) this.selectPreset(key);
    this.focused.set(true);
    void this.content()?.scrollToTop(250);
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
    const choices = this.formats.filter((option) => mapped.has(option.value));
    return choices.length ? choices : this.formats;
  }

  private modelFormat(value: string): CompetitionFormat {
    if (value === 'groups_knockout') return 'group_knockout';
    if (value === 'round_robin') return 'league';
    if (
      value === 'league' ||
      value === 'knockout' ||
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
    this.scoringDrafts.update((rows) =>
      rows.map((row) => (row.key === key ? { ...row, ...patch } : row)),
    );
  }

  addDraft(): void {
    this.scoringDrafts.update((rows) => [...rows, this.blankDraft()]);
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
            }
          : {}),
        is_private: raw.is_private,
        open_to_scouts: this.scoutable() && raw.open_to_scouts,
        starts_on: raw.starts_on || null,
        ends_on: raw.ends_on || null,
        timezone: raw.timezone,
        match_weekdays: this.scoringBasis() === 'criteria' ? [] : raw.match_weekdays,
        preset,
      })
      .subscribe({
        next: (competition) => {
          this.saving.set(false);
          void this.navCtrl.navigateForward(`/tabs/competitions/${competition.id}/setup`, {
            replaceUrl: true,
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

  private replaceScoring(categories: Preset['scoring_categories']): void {
    if (!categories.length) {
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
