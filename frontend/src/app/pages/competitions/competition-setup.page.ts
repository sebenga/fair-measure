import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import {
  AlertController,
  IonBackButton,
  IonButton,
  IonButtons,
  IonCheckbox,
  IonContent,
  IonHeader,
  IonIcon,
  IonInput,
  IonItem,
  IonLabel,
  IonList,
  IonNote,
  IonSegment,
  IonSegmentButton,
  IonSelect,
  IonSelectOption,
  IonSpinner,
  IonTextarea,
  IonTitle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';
import type {
  CompetitionDetail,
  GenerateFixturesRequest,
  Participant,
  PointsPolicy,
  ScoringCategory,
} from '../../core/models';
import { isPointsTable } from '../../core/models';

type Section = 'entrants' | 'scoring' | 'schedule';

@Component({
  selector: 'fm-competition-setup',
  standalone: true,
  imports: [
    FormsModule,
    IonHeader,
    IonToolbar,
    IonTitle,
    IonButtons,
    IonBackButton,
    IonContent,
    IonSegment,
    IonSegmentButton,
    IonLabel,
    IonList,
    IonItem,
    IonInput,
    IonTextarea,
    IonSelect,
    IonSelectOption,
    IonCheckbox,
    IonButton,
    IonIcon,
    IonNote,
    IonSpinner,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start">
          <ion-back-button [defaultHref]="backHref()" />
        </ion-buttons>
        <ion-title>Setup</ion-title>
      </ion-toolbar>
      <ion-toolbar>
        <ion-segment [value]="section()" (ionChange)="setSection($any($event).detail.value)">
          <ion-segment-button value="entrants"><ion-label>Entrants</ion-label></ion-segment-button>
          <ion-segment-button value="scoring"><ion-label>Scoring</ion-label></ion-segment-button>
          <ion-segment-button value="schedule">
            <ion-label>{{ pointsTable() ? 'Entries' : 'Schedule' }}</ion-label>
          </ion-segment-button>
        </ion-segment>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (competition(); as comp) {
        @switch (section()) {
          @case ('entrants') {
            <h3 class="fm-section-title">Entrants ({{ participants().length }})</h3>

            <form class="add-row" (submit)="addParticipant($event)">
              <ion-input
                [(ngModel)]="newParticipantName"
                name="participant"
                placeholder="Team or player name"
                maxlength="200"
              />
              <ion-button
                type="submit"
                size="small"
                [disabled]="!newParticipantName.trim() || busy()"
              >
                Add
              </ion-button>
            </form>

            @if (participants().length === 0) {
              <div class="fm-empty">
                <ion-icon name="people-outline" aria-hidden="true" />
                <h3>No entrants yet</h3>
                <p>
                  @if (pointsTable()) {
                    Add the people or teams who will score into the table.
                  } @else {
                    Add at least two before generating a schedule.
                  }
                </p>
              </div>
            } @else {
              <ion-list inset="true">
                @for (participant of participants(); track participant.id) {
                  <ion-item>
                    <ion-label>
                      <h2>{{ participant.name }}</h2>
                      @if (participant.roster.length) {
                        <p>{{ participant.roster.length }} on the roster</p>
                      }
                    </ion-label>
                    <ion-button
                      slot="end"
                      fill="clear"
                      color="danger"
                      size="small"
                      (click)="removeParticipant(participant)"
                    >
                      <ion-icon slot="icon-only" name="trash-outline" aria-label="Remove" />
                    </ion-button>
                  </ion-item>
                }
              </ion-list>
            }
          }

          @case ('scoring') {
            <h3 class="fm-section-title">{{ pointsTable() ? 'KPIs' : 'Scoring types' }}</h3>
            <p class="hint">
              @if (pointsTable()) {
                Each KPI is something people can achieve. Logging a result adds
                what they achieved, multiplied by the per-unit value. Leave that
                at 1 to accumulate the number itself.
              } @else {
                Each type has a name, what it means, and how many points it is
                worth. A rugby try is 5, a missed chore might be −1. Turn off
                “counts toward the score” to record something without changing
                the total.
              }
            </p>

            <form class="add-category" (submit)="addCategory($event)">
              <ion-input
                [(ngModel)]="newCategoryName"
                name="categoryName"
                [label]="pointsTable() ? 'KPI' : 'Name'"
                labelPlacement="stacked"
                [placeholder]="pointsTable() ? 'e.g. Sales closed' : 'e.g. Try'"
                maxlength="120"
              />
              <ion-textarea
                [(ngModel)]="newCategoryDescription"
                name="categoryDescription"
                [label]="pointsTable() ? 'What you achieve' : 'What this means'"
                labelPlacement="stacked"
                [placeholder]="
                  pointsTable()
                    ? 'What does one unit of this KPI mean?'
                    : 'When is this score awarded?'
                "
                autoGrow="true"
                rows="2"
                maxlength="2000"
              />
              <div class="add-category-meta">
                <ion-input
                  class="points-input"
                  [(ngModel)]="newCategoryPoints"
                  name="categoryPoints"
                  [label]="pointsTable() ? 'Per unit' : 'Points'"
                  labelPlacement="stacked"
                  type="number"
                  inputmode="decimal"
                />
                <ion-checkbox
                  [(ngModel)]="newCategoryAffectsScore"
                  name="categoryAffectsScore"
                  labelPlacement="end"
                >
                  {{ pointsTable() ? 'Counts toward the table' : 'Counts toward the score' }}
                </ion-checkbox>
                <ion-button
                  type="submit"
                  size="small"
                  [disabled]="!newCategoryName.trim() || busy()"
                >
                  Add
                </ion-button>
              </div>
            </form>

            <ion-list inset="true">
              @for (category of categories(); track category.id) {
                <ion-item>
                  <ion-label>
                    <h2>{{ category.name }}</h2>
                    @if (category.description) {
                      <p>{{ category.description }}</p>
                    }
                    <p>
                      @if (pointsTable()) {
                        {{ trim(category.points) }} per unit achieved
                      } @else {
                        {{ trim(category.points) }} pts
                      }
                      @if (!category.affects_score) {
                        · recorded only
                      }
                    </p>
                  </ion-label>
                  <ion-button
                    slot="end"
                    fill="clear"
                    color="danger"
                    size="small"
                    (click)="removeCategory(category)"
                  >
                    <ion-icon slot="icon-only" name="trash-outline" aria-label="Remove" />
                  </ion-button>
                </ion-item>
              } @empty {
                <ion-item lines="none">
                  <ion-label color="medium">
                    {{ pointsTable() ? 'No KPIs yet. Add one above.' : 'No scoring types yet. Add one above.' }}
                  </ion-label>
                </ion-item>
              }
            </ion-list>

            @if (pointsTable()) {
              <ion-note class="footnote">
                The table ranks by accumulated achievement. Win, draw and loss
                points are not used.
              </ion-note>
            } @else {
            <h3 class="fm-section-title">League points</h3>
            @if (policy(); as pol) {
              <ion-list inset="true">
                <ion-item>
                  <ion-input
                    label="Points for a win"
                    labelPlacement="stacked"
                    type="number"
                    inputmode="decimal"
                    [value]="trim(pol.win_points)"
                    (ionBlur)="patchPolicy({ win_points: $any($event.target).value })"
                  />
                </ion-item>
                <ion-item>
                  <ion-input
                    label="Points for a draw"
                    labelPlacement="stacked"
                    type="number"
                    inputmode="decimal"
                    [value]="trim(pol.draw_points)"
                    [disabled]="!pol.allow_draws"
                    (ionBlur)="patchPolicy({ draw_points: $any($event.target).value })"
                  />
                </ion-item>
                <ion-item>
                  <ion-input
                    label="Points for a loss"
                    labelPlacement="stacked"
                    type="number"
                    inputmode="decimal"
                    [value]="trim(pol.loss_points)"
                    (ionBlur)="patchPolicy({ loss_points: $any($event.target).value })"
                  />
                </ion-item>
                <ion-item>
                  <ion-checkbox
                    labelPlacement="end"
                    justify="start"
                    [checked]="pol.allow_draws"
                    (ionChange)="patchPolicy({ allow_draws: $any($event).detail.checked })"
                  >
                    Draws are possible
                  </ion-checkbox>
                </ion-item>
              </ion-list>
              <ion-note class="footnote">
                Tie-breakers are applied in this order:
                {{ pol.tiebreakers.join(', ') }}.
              </ion-note>
            }
            }
          }

          @case ('schedule') {
            @if (pointsTable()) {
              <h3 class="fm-section-title">Scoring entries</h3>
              <p class="hint">
                This league is not head-to-head. Log what someone achieved on each
                KPI. The table adds that result, times the per-unit value.
              </p>

              <div class="fm-empty">
                <ion-icon name="podium-outline" aria-hidden="true" />
                <h3>No VS schedule to generate</h3>
                <p>
                  Add entrants, then open Fixtures and log what someone achieved
                  on a KPI. Completing the entry updates the table.
                </p>
                <ion-button fill="outline" (click)="goToFixtures()">
                  Go to fixtures
                </ion-button>
              </div>
            } @else {
              <h3 class="fm-section-title">Generate fixtures</h3>
              <p class="hint">
                This creates the whole schedule at once. Completed fixtures are never
                touched, so it is safe to re-run after adding an entrant.
              </p>

              <ion-list inset="true">
                <ion-item>
                  <ion-select
                    label="Method"
                    labelPlacement="stacked"
                    interface="popover"
                    [(ngModel)]="generate.method"
                    name="method"
                  >
                    <ion-select-option value="round_robin">
                      Round robin — everyone plays everyone
                    </ion-select-option>
                    <ion-select-option value="knockout">
                      Knockout — single elimination
                    </ion-select-option>
                  </ion-select>
                </ion-item>

                <ion-item>
                  <ion-input
                    label="First match day"
                    labelPlacement="stacked"
                    type="date"
                    [(ngModel)]="generate.starts_on"
                    name="startsOn"
                  />
                </ion-item>

                <ion-item>
                  <ion-input
                    label="Kick-off time"
                    labelPlacement="stacked"
                    type="time"
                    [(ngModel)]="generate.kickoff"
                    name="kickoff"
                  />
                </ion-item>

                <ion-item>
                  <ion-input
                    label="Venue"
                    labelPlacement="stacked"
                    [(ngModel)]="generate.location"
                    name="location"
                    placeholder="Optional"
                  />
                </ion-item>

                <ion-item>
                  <ion-input
                    label="Minutes between fixtures"
                    labelPlacement="stacked"
                    type="number"
                    inputmode="numeric"
                    [(ngModel)]="generate.minutes_between_fixtures"
                    name="gap"
                  />
                </ion-item>

                @if (generate.method === 'round_robin') {
                  <ion-item>
                    <ion-checkbox
                      labelPlacement="end"
                      justify="start"
                      [(ngModel)]="generate.double_round"
                      name="doubleRound"
                    >
                      Home and away (play each pairing twice)
                    </ion-checkbox>
                  </ion-item>
                }

                <ion-item>
                  <ion-checkbox
                    labelPlacement="end"
                    justify="start"
                    [(ngModel)]="generate.replace_existing"
                    name="replaceExisting"
                  >
                    Replace fixtures that have not been played
                  </ion-checkbox>
                </ion-item>
              </ion-list>

              <div class="weekdays">
                <p class="label">Match days</p>
                <div class="days">
                  @for (day of weekdays; track day.value) {
                    <button
                      type="button"
                      class="day"
                      [class.on]="selectedWeekdays().includes(day.value)"
                      (click)="toggleWeekday(day.value)"
                    >
                      {{ day.label }}
                    </button>
                  }
                </div>
              </div>

              @if (error()) {
                <p class="fm-form-error" role="alert">{{ error() }}</p>
              }

              <ion-button
                expand="block"
                class="submit"
                [disabled]="participants().length < 2 || busy()"
                (click)="generateFixtures()"
              >
                @if (busy()) {
                  <ion-spinner name="crescent" />
                } @else {
                  Generate schedule
                }
              </ion-button>

              @if (participants().length < 2) {
                <ion-note class="footnote">
                  Add at least two entrants first.
                </ion-note>
              }
            }
          }
        }
      }
    </ion-content>
  `,
  styleUrl: './competition-setup.page.scss',
})
export class CompetitionSetupPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly alerts = inject(AlertController);
  private readonly toasts = inject(ToastController);

  private competitionId = '';

  readonly competition = signal<CompetitionDetail | null>(null);
  readonly participants = signal<Participant[]>([]);
  readonly categories = signal<ScoringCategory[]>([]);
  readonly policy = signal<PointsPolicy | null>(null);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);
  readonly section = signal<Section>('entrants');
  readonly selectedWeekdays = signal<number[]>([5]);

  readonly pointsTable = computed(() => {
    const competition = this.competition();
    return competition ? isPointsTable(competition) : false;
  });

  readonly weekdays = [
    { value: 0, label: 'Mon' },
    { value: 1, label: 'Tue' },
    { value: 2, label: 'Wed' },
    { value: 3, label: 'Thu' },
    { value: 4, label: 'Fri' },
    { value: 5, label: 'Sat' },
    { value: 6, label: 'Sun' },
  ];

  newParticipantName = '';
  newCategoryName = '';
  newCategoryDescription = '';
  newCategoryPoints = '1';
  newCategoryAffectsScore = true;

  generate = {
    method: 'round_robin' as GenerateFixturesRequest['method'],
    starts_on: new Date().toISOString().slice(0, 10),
    kickoff: '15:00',
    location: '',
    minutes_between_fixtures: 0,
    double_round: false,
    replace_existing: false,
  };

  ngOnInit(): void {
    this.competitionId = this.route.snapshot.paramMap.get('id') ?? '';
    this.load();
  }

  load(): void {
    this.loading.set(true);

    this.api.getCompetition(this.competitionId).subscribe({
      next: (competition) => {
        this.competition.set(competition);
        this.participants.set(competition.participants);
        this.categories.set(competition.scoring_categories);
        this.policy.set(competition.points_policy);
        if (competition.match_weekdays.length) {
          this.selectedWeekdays.set(competition.match_weekdays);
        }
        if (competition.starts_on) {
          this.generate.starts_on = competition.starts_on;
        }
        this.loading.set(false);
      },
      error: async (err: unknown) => {
        this.loading.set(false);
        await this.toast(extractErrorMessage(err), 'danger');
      },
    });
  }

  setSection(value: string | undefined): void {
    if (value === 'entrants' || value === 'scoring' || value === 'schedule') {
      this.section.set(value);
    }
  }

  backHref(): string {
    return `/competitions/${this.competitionId}`;
  }

  goToFixtures(): void {
    void this.router.navigate(['/competitions', this.competitionId], {
      queryParams: { tab: 'fixtures' },
    });
  }

  // --- Entrants -------------------------------------------------------------

  addParticipant(event: Event): void {
    event.preventDefault();
    const name = this.newParticipantName.trim();
    if (!name || this.busy()) return;

    this.busy.set(true);
    this.api.createParticipant(this.competitionId, { name }).subscribe({
      next: (participant) => {
        this.participants.update((current) => [...current, participant]);
        this.newParticipantName = '';
        this.busy.set(false);
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not add that entrant.'), 'danger');
      },
    });
  }

  async removeParticipant(participant: Participant): Promise<void> {
    const alert = await this.alerts.create({
      header: `Remove ${participant.name}?`,
      message: 'Their fixtures and results are removed too.',
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        {
          text: 'Remove',
          role: 'destructive',
          handler: () => {
            this.api.deleteParticipant(this.competitionId, participant.id).subscribe({
              next: () =>
                this.participants.update((current) =>
                  current.filter((candidate) => candidate.id !== participant.id),
                ),
            });
          },
        },
      ],
    });
    await alert.present();
  }

  // --- Scoring --------------------------------------------------------------

  addCategory(event: Event): void {
    event.preventDefault();
    const name = this.newCategoryName.trim();
    if (!name || this.busy()) return;

    this.busy.set(true);
    this.api
      .createScoringCategory(this.competitionId, {
        name,
        description: this.newCategoryDescription.trim(),
        points: String(this.newCategoryPoints || '0'),
        affects_score: this.newCategoryAffectsScore,
      })
      .subscribe({
        next: (category) => {
          this.categories.update((current) => [...current, category]);
          this.newCategoryName = '';
          this.newCategoryDescription = '';
          this.newCategoryPoints = '1';
          this.newCategoryAffectsScore = true;
          this.busy.set(false);
        },
        error: async (err: unknown) => {
          this.busy.set(false);
          await this.toast(extractErrorMessage(err, 'Could not add that category.'), 'danger');
        },
      });
  }

  removeCategory(category: ScoringCategory): void {
    this.api.deleteScoringCategory(this.competitionId, category.id).subscribe({
      next: () =>
        this.categories.update((current) =>
          current.filter((candidate) => candidate.id !== category.id),
        ),
    });
  }

  patchPolicy(patch: Partial<PointsPolicy>): void {
    this.api.updatePointsPolicy(this.competitionId, patch).subscribe({
      next: (policy) => this.policy.set(policy),
      error: async (err: unknown) => {
        await this.toast(extractErrorMessage(err, 'Could not save that.'), 'danger');
      },
    });
  }

  // --- Schedule -------------------------------------------------------------

  toggleWeekday(day: number): void {
    this.selectedWeekdays.update((current) =>
      current.includes(day)
        ? current.filter((candidate) => candidate !== day)
        : [...current, day].sort((a, b) => a - b),
    );
  }

  generateFixtures(): void {
    if (this.busy()) return;

    this.busy.set(true);
    this.error.set(null);

    this.api
      .generateFixtures(this.competitionId, {
        method: this.generate.method,
        starts_on: this.generate.starts_on,
        kickoff: this.generate.kickoff,
        weekdays: this.selectedWeekdays(),
        location: this.generate.location,
        minutes_between_fixtures: Number(this.generate.minutes_between_fixtures) || 0,
        double_round: this.generate.double_round,
        replace_existing: this.generate.replace_existing,
      })
      .subscribe({
        next: async (fixtures) => {
          this.busy.set(false);
          await this.toast(`Created ${fixtures.length} fixtures.`, 'success');
          void this.router.navigate(['/competitions', this.competitionId], {
            queryParams: { tab: 'fixtures' },
          });
        },
        error: (err: unknown) => {
          this.busy.set(false);
          this.error.set(extractErrorMessage(err, 'Could not generate the schedule.'));
        },
      });
  }

  trim(value: string): string {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? String(parsed) : value;
  }

  private async toast(message: string, color: string): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2600 });
    await toast.present();
  }
}
