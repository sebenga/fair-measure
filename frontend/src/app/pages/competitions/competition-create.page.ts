import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
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
              Pick an official sport, or Custom if you want to define the scoring yourself.
            </p>

            @if (everydayPresets().length) {
              <div class="presets">
                @for (preset of everydayPresets(); track preset.key) {
                  <button
                    type="button"
                    class="preset"
                    [class.selected]="selectedPreset() === preset.key"
                    (click)="selectPreset(preset.key)"
                  >
                    <ion-icon [name]="presetIcon(preset)" aria-hidden="true" />
                    <span>{{ preset.label }}</span>
                    <small>{{ kindCaption(preset) }}</small>
                  </button>
                }
              </div>
            }

            @if (sportPresets().length) {
              <p class="group-label">Sports</p>
              <div class="presets">
                @for (preset of sportPresets(); track preset.key) {
                  <button
                    type="button"
                    class="preset"
                    [class.selected]="selectedPreset() === preset.key"
                    (click)="selectPreset(preset.key)"
                  >
                    <ion-icon [name]="presetIcon(preset)" aria-hidden="true" />
                    <span>{{ preset.label }}</span>
                    <small>{{ formatShort(preset.format) }}</small>
                  </button>
                }
              </div>
            }

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
              <div class="scoring-list">
                @for (row of scoringDrafts(); track row.key) {
                  <div class="score-row fm-card">
                    <strong>{{ row.name }}</strong>
                    <p>
                      {{ row.points }} {{ pointsTable() ? 'per unit' : 'pts' }}
                      @if (!row.affects_score) {
                        · recorded only
                      }
                    </p>
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
          }

          @case (2) {
            <h3 class="fm-section-title">The basics</h3>
            <p class="hint">Give it a name people will recognise on the fixture list.</p>

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

            <h3 class="fm-section-title">{{ scoringLocked() ? 'Competition structure' : showLeagueStructure() ? 'League structure' : 'Format' }}</h3>
            <p class="hint">{{ formatHint() }}</p>

            @if (scoringLocked()) {
              <p class="hint">{{ lockedStructureHint() }}</p>
            } @else if (showLeagueStructure()) {
              <div class="formats">
                <button
                  type="button"
                  class="format"
                  [class.selected]="scoringBasis() === 'results'"
                  (click)="setScoringBasis('results')"
                >
                  <ion-icon name="git-compare-outline" aria-hidden="true" />
                  <div>
                    <strong>Versus league</strong>
                    <p>
                      Head-to-head fixtures. Points come from win, draw, or loss.
                    </p>
                  </div>
                  @if (scoringBasis() === 'results') {
                    <ion-icon name="checkmark-outline" class="tick" aria-hidden="true" />
                  }
                </button>
                <button
                  type="button"
                  class="format"
                  [class.selected]="scoringBasis() === 'criteria'"
                  (click)="setScoringBasis('criteria')"
                >
                  <ion-icon name="podium-outline" aria-hidden="true" />
                  <div>
                    <strong>Points accumulation</strong>
                    <p>
                      Ranked by the sum of scoring criteria. Expand a row to see
                      how each total was earned and what those points mean.
                    </p>
                  </div>
                  @if (scoringBasis() === 'criteria') {
                    <ion-icon name="checkmark-outline" class="tick" aria-hidden="true" />
                  }
                </button>
              </div>
            } @else {
              <div class="formats">
                @for (option of formats; track option.value) {
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
                Dates are optional. Scoring days are a reminder for when people usually log
                points — there is no head-to-head schedule to generate.
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

            <div class="weekdays">
              <p class="label">{{ pointsTable() ? 'Usual scoring days' : 'Usual match days' }}</p>
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
                    @if (showLeagueStructure()) {
                      {{ scoringBasis() === 'criteria' ? 'Points accumulation' : 'Versus league' }}
                    } @else {
                      {{ formatShort(form.controls.format.value) }}
                    }
                  </dd>
                </div>
                <div>
                  <dt>Visibility</dt>
                  <dd>{{ form.controls.is_private.value ? 'Private' : 'Public' }}</dd>
                </div>
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

  readonly presets = signal<Preset[]>([]);
  readonly selectedPreset = signal<string>('custom');
  readonly scoringDrafts = signal<ScoringDraft[]>([this.blankDraft()]);
  readonly step = signal<Step>(1);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);

  readonly everydayPresets = computed(() =>
    this.presets().filter(
      (preset) =>
        presetKind(preset) !== 'sport' && preset.key !== 'kpi' && preset.key !== 'cleaning',
    ),
  );

  readonly sportPresets = computed(() =>
    this.presets().filter((preset) => presetKind(preset) === 'sport'),
  );

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

  /** Custom competitions choose Versus or points accumulation. Official presets do not. */
  readonly showLeagueStructure = computed(() => this.isCustom());

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
      match_weekdays: [[] as number[]],
    },
    { validators: endAfterStart },
  );

  ngOnInit(): void {
    this.api.listPresets().subscribe({
      next: (presets) => {
        this.presets.set(presets);
        this.selectPreset(this.selectedPreset());
      },
      error: () => this.presets.set([]),
    });
  }

  selectPreset(key: string): void {
    this.selectedPreset.set(key);
    const preset = this.presets().find((candidate) => candidate.key === key);
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
    if (this.showLeagueStructure()) {
      this.form.controls.format.setValue(this.scoringBasis() === 'criteria' ? 'freeform' : 'league');
    } else {
      this.ensureCompatibleFormat();
    }
  }

  setScoringBasis(basis: 'results' | 'criteria'): void {
    this.scoringBasis.set(basis);
    // Versus needs a scheduleable league; accumulation is logged as entries.
    this.form.controls.format.setValue(basis === 'criteria' ? 'freeform' : 'league');
  }

  formatHint(): string {
    if (this.scoringLocked()) {
      return 'This follows the official structure for the preset. It cannot be changed.';
    }
    if (this.showLeagueStructure()) {
      return 'Choose how the table is built. Sports brackets are not used here.';
    }
    return 'This decides how fixtures are generated. You can still add one-off matches later.';
  }

  lockedStructureHint(): string {
    const preset = this.activePreset();
    if (!preset) return '';
    if (preset.table_mode === 'points') {
      return 'Entrants do not play each other. The table ranks by points accumulated from the scoring rules above, highest first.';
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
    const byKey: Record<string, string> = {
      custom: 'construct-outline',
      soccer: 'football-outline',
      rugby: 'american-football-outline',
      basketball: 'basketball-outline',
      tennis: 'tennisball-outline',
      squash: 'tennisball-outline',
      golf: 'golf-outline',
      scrabble: 'text-outline',
      darts: 'locate-outline',
    };
    if (byKey[preset.key]) return byKey[preset.key];
    switch (presetKind(preset)) {
      case 'work':
        return 'stats-chart-outline';
      case 'home':
        return 'water-outline';
      case 'custom':
        return 'construct-outline';
      default:
        return 'trophy-outline';
    }
  }

  formatShort(format: string): string {
    return this.formats.find((option) => option.value === format)?.label ?? format;
  }

  private ensureCompatibleFormat(): void {
    if (this.showLeagueStructure()) {
      this.form.controls.format.setValue(
        this.scoringBasis() === 'criteria' ? 'freeform' : 'league',
      );
      return;
    }
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
        is_private: raw.is_private,
        starts_on: raw.starts_on || null,
        ends_on: raw.ends_on || null,
        timezone: raw.timezone,
        match_weekdays: raw.match_weekdays,
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
