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
  IonSearchbar,
  IonSegment,
  IonSegmentButton,
  IonSelect,
  IonSelectOption,
  IonSpinner,
  IonTextarea,
  IonTitle,
  IonToggle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';
import type { CompetitionOfficial, Horse } from '../../core/results.models';
import { ResultsService } from '../../core/results.service';
import type { LeagueScout } from '../../core/scouting.models';
import { ScoutingService } from '../../core/scouting.service';
import type {
  CompetitionDetail,
  DraftBoard,
  GenerateFixturesRequest,
  Membership,
  Participant,
  PointsPolicy,
  ProfileSummary,
  ScoringCategory,
} from '../../core/models';
import { isPointsTable, isScoringLocked, squadSizeOf, tableBonusOf } from '../../core/models';

type Section = 'entrants' | 'scoring' | 'schedule' | 'officials' | 'scouting';

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
    IonSearchbar,
    IonSpinner,
    IonToggle,
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
          @if (!pointsTable()) {
            <ion-segment-button value="schedule">
              <ion-label>Schedule</ion-label>
            </ion-segment-button>
          }
          <ion-segment-button value="officials"><ion-label>Officials</ion-label></ion-segment-button>
          @if (competition()?.scouting_eligible) {
            <ion-segment-button value="scouting"><ion-label>Scouting</ion-label></ion-segment-button>
          }
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

            @if (entrantKind() === 'team' && !isCombination()) {
              <p class="hint">
                Choose how teams are filled. A team needs {{ squadSize() }} players, and each player accepts before they count.
              </p>
              <div class="entry-modes">
                <button
                  type="button"
                  [class.selected]="teamEntry() === 'pick'"
                  (click)="setTeamEntry('pick')"
                  [disabled]="busy()"
                >
                  Pick teams
                </button>
                <button
                  type="button"
                  [class.selected]="teamEntry() === 'draft'"
                  (click)="setTeamEntry('draft')"
                  [disabled]="busy()"
                >
                  Draft
                </button>
              </div>
            }

            @if (isCombination()) {
              <form class="add-row combo-form" (submit)="addCombination($event)">
                <p class="hint">
                  Each entrant is a horse with its rider. Results belong to the pair; the table also keeps
                  separate records for each horse, rider and trainer.
                </p>
                <label class="combo-field">
                  Horse
                  <select [value]="comboHorse()" (change)="comboHorse.set($any($event.target).value)">
                    <option value="">Choose a horse</option>
                    @for (horse of horseChoices(); track horse.id) {
                      <option [value]="horse.id" [selected]="horse.id === comboHorse()">
                        {{ horse.name }}{{ horse.registration_number ? ' · ' + horse.registration_number : '' }}
                      </option>
                    }
                  </select>
                </label>
                <ion-searchbar
                  placeholder="Search the horse registry"
                  [debounce]="250"
                  (ionInput)="searchHorses($any($event.detail.value) ?? '')"
                />
                <label class="combo-field">
                  Rider (or jockey)
                  <input [(ngModel)]="comboRiderName" name="comboRider" placeholder="Name" maxlength="120" />
                </label>
                <label class="combo-field">
                  Link a Fair Measure profile (optional)
                  <select [value]="comboRiderId()" (change)="comboRiderId.set($any($event.target).value)">
                    <option value="">No profile</option>
                    @for (profile of riderChoices(); track profile.id) {
                      <option [value]="profile.id" [selected]="profile.id === comboRiderId()">{{ profile.display_name || profile.email }}</option>
                    }
                  </select>
                </label>
                <label class="combo-field">
                  Trainer (optional)
                  <input [(ngModel)]="comboTrainerName" name="comboTrainer" placeholder="Name" maxlength="120" />
                </label>
                <div class="combo-actions">
                  <ion-button type="submit" size="small" [disabled]="busy() || !comboHorse() || (!comboRiderName.trim() && !comboRiderId())">
                    Enter the combination
                  </ion-button>
                  <ion-button type="button" size="small" fill="clear" (click)="openHorses()">Register a horse</ion-button>
                </div>
              </form>
            } @else if (entrantKind() !== 'team' || teamEntry()) {
              <form class="add-row" (submit)="addParticipant($event)">
                <p class="hint">
                  @if (profileEntrants() && pointsTable()) {
                    Search for a profile and add them. Each profile enters once, and the table ranks them on their total.
                  } @else if (profileEntrants()) {
                    Search for a profile and add them. Each profile enters once, plays the others, and the table ranks them on match results.
                  } @else if (entrantKind() === 'individual' && pointsTable()) {
                    Add each person by name. The table ranks them on their total.
                  } @else if (entrantKind() === 'individual') {
                    Add each person by name. They play each other, and the table ranks them on match results.
                  } @else if (entrantKind() === 'pair') {
                    Name the pair first. Open it and pick two profiles. Each person accepts before they are in.
                  } @else if (teamEntry() === 'draft') {
                    Name each team. Players are drafted onto them, one pick at a time, until every team has {{ squadSize() }}.
                  } @else {
                    Name the team and select at least {{ squadSize() }} profiles. They accept before they join.
                  }
                </p>
                @if (teamEntry() === 'pick') {
                  <ion-searchbar
                    placeholder="Search profiles"
                    [debounce]="150"
                    (ionInput)="profileQuery.set($any($event.detail.value) ?? '')"
                  />
                  <p class="hint">{{ selectedProfileIds().length }} of {{ squadSize() }} selected</p>
                  <ion-list class="profiles" lines="none">
                    @for (profile of visibleProfiles(); track profile.id) {
                      <ion-item>
                        <ion-checkbox
                          slot="start"
                          [checked]="selectedProfileIds().includes(profile.id)"
                          [disabled]="profileBlocked(profile.id) || busy()"
                          (ionChange)="toggleProfile(profile.id, $event)"
                        />
                        <ion-label>
                          <h2>{{ profile.display_name || profile.email }}</h2>
                          <p>{{ profileNote(profile) }}</p>
                        </ion-label>
                      </ion-item>
                    }
                  </ion-list>
                }
                @if (profileEntrants()) {
                  <ion-searchbar
                    placeholder="Search profiles"
                    [debounce]="150"
                    (ionInput)="profileQuery.set($any($event.detail.value) ?? '')"
                  />
                  <ion-list class="profiles" lines="none">
                    @for (profile of visibleProfiles(); track profile.id) {
                      <ion-item>
                        <ion-label>
                          <h2>{{ profile.display_name || profile.email }}</h2>
                          <p>{{ profileNote(profile) }}</p>
                        </ion-label>
                        <ion-button
                          slot="end"
                          size="small"
                          [disabled]="profileBlocked(profile.id) || busy()"
                          (click)="addProfileEntrant(profile)"
                        >
                          Add
                        </ion-button>
                      </ion-item>
                    }
                  </ion-list>
                } @else {
                  <div class="add-name">
                    <ion-input
                      [(ngModel)]="newParticipantName"
                      name="participant"
                      [placeholder]="entrantKind() === 'individual' ? 'Player name' : 'Team name'"
                      maxlength="200"
                    />
                    <ion-button
                      type="submit"
                      size="small"
                      [disabled]="!canAddParticipant() || busy()"
                    >
                      Add
                    </ion-button>
                  </div>
                }
              </form>
            }

            @if (teamEntry() === 'draft' && draftBoard(); as board) {
              <h3 class="fm-section-title">Draft</h3>
              @if (board.on_the_clock) {
                <p class="hint">On the clock: {{ board.on_the_clock.name }}. Draft a profile onto that team.</p>
              } @else if (!board.teams.length) {
                <p class="hint">Name the teams first, then draft profiles onto them.</p>
              } @else {
                <p class="hint">Every team has {{ squadSize() }} players drafted.</p>
              }
              <ion-list inset="true">
                @for (team of board.teams; track team.id) {
                  <ion-item>
                    <ion-label>
                      <h2>{{ team.name }}</h2>
                      <p>
                        {{ team.accepted }} of {{ board.squad_size }} accepted
                        @if (team.pending) {
                          · {{ team.pending }} waiting
                        }
                      </p>
                    </ion-label>
                  </ion-item>
                }
              </ion-list>
              @if (board.on_the_clock) {
                <ion-searchbar
                  placeholder="Search profiles"
                  [debounce]="150"
                  (ionInput)="profileQuery.set($any($event.detail.value) ?? '')"
                />
                <ion-list class="profiles" lines="none">
                  @for (profile of visibleProfiles(); track profile.id) {
                    <ion-item>
                      <ion-label>
                        <h2>{{ profile.display_name || profile.email }}</h2>
                        <p>{{ profileNote(profile) }}</p>
                      </ion-label>
                      <ion-button
                        slot="end"
                        size="small"
                        [disabled]="profileBlocked(profile.id) || busy()"
                        (click)="draftProfile(profile)"
                      >
                        Draft
                      </ion-button>
                    </ion-item>
                  }
                </ion-list>
              }
            }

            @if (participants().length === 0) {
              <div class="fm-empty">
                <ion-icon name="people-outline" aria-hidden="true" />
                <h3>No entrants yet</h3>
                <p>
                  @if (pointsTable()) {
                    Add the {{ entrantKind() === 'individual' ? 'people' : 'teams' }} who will score into the table.
                  } @else {
                    Add at least two {{ entrantKind() === 'individual' ? 'players' : 'teams' }} before generating a schedule.
                  }
                </p>
              </div>
            } @else {
              <ion-list inset="true">
                @for (participant of participants(); track participant.id) {
                  <ion-item>
                    <ion-label>
                      <h2>{{ participant.name }}</h2>
                      <p>
                        @if (teamEntry() && participant.kind === 'team') {
                          {{ participant.roster.length }} of {{ squadSize() }} accepted
                          @if (participant.pending_count) {
                            · {{ participant.pending_count }} waiting
                          }
                        } @else if (profileEntrants()) {
                          {{ participant.roster[0]?.user ? 'Player profile' : 'No profile linked' }}
                        } @else {
                          {{ participant.roster.length }}
                          {{ participant.roster.length === 1 ? 'member' : 'members' }}
                        }
                      </p>
                    </ion-label>
                    <ion-button
                      slot="end"
                      fill="clear"
                      size="small"
                      (click)="openTeam(participant)"
                    >
                      Profile
                    </ion-button>
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
            <h3 class="fm-section-title">{{ pointsTable() ? 'How points are earned' : 'Scoring types' }}</h3>
            <p class="hint">
              @if (scoringLocked()) {
                This competition uses an official preset. Scoring categories and
                league points are fixed.
              } @else if (pointsTable()) {
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

            @if (!scoringLocked()) {
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
            }

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
                  @if (!scoringLocked()) {
                  <ion-button
                    slot="end"
                    fill="clear"
                    color="danger"
                    size="small"
                    (click)="removeCategory(category)"
                  >
                    <ion-icon slot="icon-only" name="trash-outline" aria-label="Remove" />
                  </ion-button>
                  }
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
                    [readonly]="scoringLocked()"
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
                    [readonly]="scoringLocked()"
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
                    [readonly]="scoringLocked()"
                    (ionBlur)="patchPolicy({ loss_points: $any($event.target).value })"
                  />
                </ion-item>
                <ion-item>
                  <ion-checkbox
                    labelPlacement="end"
                    justify="start"
                    [checked]="pol.allow_draws"
                    [disabled]="scoringLocked()"
                    (ionChange)="patchPolicy({ allow_draws: $any($event).detail.checked })"
                  >
                    Draws are possible
                  </ion-checkbox>
                </ion-item>
              </ion-list>
              <ion-note class="footnote">
                {{ leaguePointsNote() }}
                Tie-breakers are applied in this order:
                {{ pol.tiebreakers.join(', ') }}.
              </ion-note>
            }
            @if (!scoringLocked()) {
              <h3 class="fm-section-title">Bonus points</h3>
              <p class="hint">
                Extra table points from scoring, or from winning or losing by a set margin.
                Switch them off to keep the table as win, draw and loss only.
              </p>
              <ion-list inset="true">
                <ion-item>
                  <ion-toggle
                    labelPlacement="start"
                    justify="space-between"
                    [checked]="bonusEnabled()"
                    [disabled]="scoringLocked()"
                    (ionChange)="setBonusEnabled($any($event).detail.checked)"
                  >
                    Award bonus points
                  </ion-toggle>
                </ion-item>
                @if (bonusEnabled()) {
                  <ion-item>
                    <ion-select
                      label="Scoring bonus counts"
                      labelPlacement="stacked"
                      interface="action-sheet"
                      [value]="scoringBonusCode()"
                      [disabled]="scoringLocked()"
                      (ionChange)="scoringBonusCode.set($any($event).detail.value ?? ''); saveBonus()"
                    >
                      <ion-select-option value="">Match score</ion-select-option>
                      @for (category of categories(); track category.id) {
                        <ion-select-option [value]="category.code">{{ category.name }}</ion-select-option>
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
                      [readonly]="scoringLocked()"
                      (ionBlur)="scoringBonusThreshold.set($any($event.target).value); saveBonus()"
                    />
                  </ion-item>
                  <ion-item>
                    <ion-input
                      label="Scoring bonus points"
                      labelPlacement="stacked"
                      type="number"
                      inputmode="decimal"
                      [value]="scoringBonusPoints()"
                      [readonly]="scoringLocked()"
                      (ionBlur)="scoringBonusPoints.set($any($event.target).value); saveBonus()"
                    />
                  </ion-item>
                  <ion-item>
                    <ion-input
                      label="Winning-margin bonus at"
                      labelPlacement="stacked"
                      type="number"
                      inputmode="numeric"
                      [value]="winBonusMargin()"
                      [readonly]="scoringLocked()"
                      (ionBlur)="winBonusMargin.set($any($event.target).value); saveBonus()"
                    />
                  </ion-item>
                  <ion-item>
                    <ion-input
                      label="Winning-margin bonus points"
                      labelPlacement="stacked"
                      type="number"
                      inputmode="decimal"
                      [value]="winBonusPoints()"
                      [readonly]="scoringLocked()"
                      (ionBlur)="winBonusPoints.set($any($event.target).value); saveBonus()"
                    />
                  </ion-item>
                  <ion-item>
                    <ion-input
                      label="Losing bonus within"
                      labelPlacement="stacked"
                      type="number"
                      inputmode="numeric"
                      [value]="lossBonusMargin()"
                      [readonly]="scoringLocked()"
                      (ionBlur)="lossBonusMargin.set($any($event.target).value); saveBonus()"
                    />
                  </ion-item>
                  <ion-item>
                    <ion-input
                      label="Losing bonus points"
                      labelPlacement="stacked"
                      type="number"
                      inputmode="decimal"
                      [value]="lossBonusPoints()"
                      [readonly]="scoringLocked()"
                      (ionBlur)="lossBonusPoints.set($any($event.target).value); saveBonus()"
                    />
                  </ion-item>
                }
              </ion-list>
            }
            }
          }

          @case ('schedule') {
            @if (!pointsTable()) {
              <h3 class="fm-section-title">Generate fixtures</h3>
              <p class="hint">
                @if (competition()?.season_finished) {
                  This season is finished. Generate a new season or a knockout here,
                  or use the buttons on the competition page. Completed fixtures stay
                  in the record.
                } @else {
                  This creates the whole schedule at once. Completed fixtures are never
                  touched, so it is safe to re-run after adding an entrant.
                }
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
          @case ('officials') {
            <h3 class="fm-section-title">Game time</h3>
            <p class="hint">
              Every game needs a time limit and a referee before kickoff. Overtime is optional: set it to 0
              or remove it. Saving applies to every game that has not started; an admin can still change one
              game on its match page.
            </p>
            <form class="add-row" (submit)="saveTimeLimits($event)">
              <ion-input
                type="number"
                inputmode="numeric"
                min="1"
                required
                label="Time limit (required)"
                labelPlacement="stacked"
                [(ngModel)]="timeLimit"
                name="timeLimit"
                placeholder="Minutes"
              />
              <ion-input
                type="number"
                inputmode="numeric"
                min="0"
                label="Overtime"
                labelPlacement="stacked"
                [(ngModel)]="overtimeLimit"
                name="overtime"
                placeholder="0 for none"
              />
              <ion-button type="submit" size="small" [disabled]="busy() || !canManage() || !timeLimit">
                Save
              </ion-button>
              @if (canManage() && overtimeLimit && overtimeLimit !== '0') {
                <ion-button
                  type="button"
                  size="small"
                  fill="outline"
                  [disabled]="busy()"
                  (click)="removeOvertime()"
                >
                  Remove overtime
                </ion-button>
              }
            </form>

            <h3 class="fm-section-title">Stewards, judges and ground jury</h3>
            <p class="hint">
              @if (officialsRequired()) {
                This competition's results are official: only these people can confirm or amend a result,
                disqualify an entrant or record a vet elimination. Every change is logged with a reason.
              } @else {
                Officials can confirm and amend results, and record eliminations. Every change is logged.
              }
            </p>
            <ion-list inset="true">
              @for (official of officials(); track official.id) {
                <ion-item>
                  <ion-label>
                    <h2>{{ official.name }}</h2>
                    <p>{{ official.title_label }}</p>
                  </ion-label>
                  @if (canManage()) {
                    <ion-button slot="end" fill="clear" size="small" [disabled]="busy()" (click)="removeOfficial(official.id)">
                      Remove
                    </ion-button>
                  }
                </ion-item>
              } @empty {
                <ion-item><ion-label><p>No officials appointed yet.</p></ion-label></ion-item>
              }
            </ion-list>
            @if (canManage()) {
              <div class="add-row">
                <label class="combo-field">
                  Role
                  <select [value]="officialTitle()" (change)="officialTitle.set($any($event.target).value)">
                    @for (title of officialTitles(); track title.key) {
                      <option [value]="title.key" [selected]="title.key === officialTitle()">{{ title.label }}</option>
                    }
                  </select>
                </label>
              </div>
              <ion-searchbar
                placeholder="Search profiles to appoint"
                [debounce]="150"
                (ionInput)="stewardQuery.set($any($event.detail.value) ?? '')"
              />
              <ion-list class="profiles" lines="none">
                @for (profile of stewardChoices(); track profile.id) {
                  <ion-item>
                    <ion-label>
                      <h2>{{ profile.display_name || profile.email }}</h2>
                      <p>{{ profile.email }}</p>
                    </ion-label>
                    <ion-button slot="end" size="small" [disabled]="busy()" (click)="appointOfficial(profile)">
                      Appoint
                    </ion-button>
                  </ion-item>
                }
              </ion-list>
            }

            <h3 class="fm-section-title">Admins</h3>
            <p class="hint">
              The creator and admins choose who else can run this competition. Referees are chosen on each game and score only that game.
            </p>
            <ion-list inset="true">
              @for (membership of admins(); track membership.id) {
                <ion-item>
                  <ion-label>
                    <h2>{{ membership.user.display_name || membership.member_email }}</h2>
                    <p>{{ membership.role === 'owner' ? 'Creator' : 'Admin' }}</p>
                  </ion-label>
                  @if (canManage() && isOwner() && membership.role === 'admin') {
                    <ion-button slot="end" fill="clear" size="small" (click)="dismissAdmin(membership)">
                      Remove
                    </ion-button>
                  }
                </ion-item>
              }
            </ion-list>
            @if (canManage()) {
              <ion-searchbar
                placeholder="Search profiles"
                [debounce]="150"
                (ionInput)="officialQuery.set($any($event.detail.value) ?? '')"
              />
              <ion-list class="profiles" lines="none">
                @for (profile of officialChoices(); track profile.id) {
                  <ion-item>
                    <ion-label>
                      <h2>{{ profile.display_name || profile.email }}</h2>
                      <p>{{ profile.email }}</p>
                    </ion-label>
                    <ion-button slot="end" size="small" [disabled]="busy()" (click)="appointAdmin(profile)">
                      Make admin
                    </ion-button>
                  </ion-item>
                }
              </ion-list>
            }
          }
          @case ('scouting') {
            <h3 class="fm-section-title">Open to scouts</h3>
            <p class="hint">
              Opening the league lets scouts follow it. Its results feed scouting reports, and it can name its
              own squad of the best players, picked by position like a national team. Players still decide who
              sees their talent profile, and under-18s stay hidden until a guardian agrees. The feed and table
              stay as private or public as they are now.
            </p>
            <ion-list inset="true">
              <ion-item>
                <ion-toggle
                  [checked]="!!comp.open_to_scouts"
                  [disabled]="busy() || !canManage()"
                  (ionChange)="setOpenToScouts($any($event).detail.checked)"
                >
                  {{ comp.open_to_scouts ? 'Open to scouts' : 'Closed to scouts' }}
                </ion-toggle>
              </ion-item>
              <ion-item>
                <ion-select
                  label="Competition level"
                  labelPlacement="stacked"
                  interface="popover"
                  placeholder="Not set"
                  [value]="comp.settings_json['level'] ?? ''"
                  [disabled]="busy() || !canManage()"
                  (ionChange)="setLevel($any($event).detail.value)"
                >
                  @for (level of competitionLevels; track level.key) {
                    <ion-select-option [value]="level.key">{{ level.label }}</ion-select-option>
                  }
                </ion-select>
              </ion-item>
            </ion-list>
            <p class="hint">Scouts can search for players by the level they play at: the highest level of their teams' competitions.</p>

            @if (comp.open_to_scouts) {
              <div class="add-row">
                <ion-button size="small" (click)="openSquad()">
                  <ion-icon slot="start" name="shirt-outline" aria-hidden="true" />
                  League squad
                </ion-button>
              </div>

              <h3 class="fm-section-title">League scouts</h3>
              <p class="hint">
                League scouts follow this league and help pick its squad with you. They need a scout role in a
                scouting organisation; add them with the email they sign in with.
              </p>
              <ion-list inset="true">
                @for (scout of leagueScouts(); track scout.id) {
                  <ion-item>
                    <ion-label>
                      <h2>{{ scout.name }}</h2>
                      <p>{{ scout.organisation ?? 'Independent scout' }}</p>
                    </ion-label>
                    @if (canManage()) {
                      <ion-button slot="end" fill="clear" size="small" [disabled]="busy()" (click)="removeScout(scout.id)">
                        Remove
                      </ion-button>
                    }
                  </ion-item>
                } @empty {
                  <ion-item><ion-label><p>No scouts attached yet.</p></ion-label></ion-item>
                }
              </ion-list>
              @if (canManage()) {
                <form class="add-row" (submit)="addScout($event)">
                  <ion-input
                    type="email"
                    label="Scout's email"
                    labelPlacement="stacked"
                    [(ngModel)]="scoutEmail"
                    name="scoutEmail"
                    placeholder="scout@club.org"
                  />
                  <ion-button type="submit" size="small" [disabled]="busy() || !scoutEmail.trim()">Add scout</ion-button>
                </form>
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
  private readonly scouting = inject(ScoutingService);
  private readonly results = inject(ResultsService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly alerts = inject(AlertController);
  private readonly toasts = inject(ToastController);

  private competitionId = '';

  readonly competition = signal<CompetitionDetail | null>(null);
  readonly participants = signal<Participant[]>([]);
  readonly categories = signal<ScoringCategory[]>([]);
  readonly profiles = signal<ProfileSummary[]>([]);
  readonly profileQuery = signal('');
  readonly selectedProfileIds = signal<string[]>([]);
  readonly draftBoard = signal<DraftBoard | null>(null);
  readonly memberships = signal<Membership[]>([]);
  readonly officialQuery = signal('');
  readonly policy = signal<PointsPolicy | null>(null);
  readonly bonusEnabled = signal(false);
  readonly scoringBonusCode = signal('');
  readonly scoringBonusThreshold = signal('4');
  readonly scoringBonusPoints = signal('1');
  readonly winBonusMargin = signal('');
  readonly winBonusPoints = signal('1');
  readonly lossBonusMargin = signal('7');
  readonly lossBonusPoints = signal('1');
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);
  readonly section = signal<Section>('entrants');
  readonly leagueScouts = signal<LeagueScout[]>([]);
  scoutEmail = '';
  readonly selectedWeekdays = signal<number[]>([5]);

  readonly pointsTable = computed(() => {
    const competition = this.competition();
    return competition ? isPointsTable(competition) : false;
  });

  squadSize(): number {
    const competition = this.competition();
    return competition ? squadSizeOf(competition) : 14;
  }

  readonly scoringLocked = computed(() => {
    const competition = this.competition();
    return competition ? isScoringLocked(competition) : false;
  });

  leaguePointsNote(): string {
    const raw = this.competition()?.settings_json?.['league_points'];
    if (!raw || typeof raw !== 'object') return '';
    const points = raw as Record<string, number>;
    const parts: string[] = [];
    if (points['win'] != null) parts.push(`a win is ${points['win']}`);
    if (points['draw'] != null) parts.push(`a draw is ${points['draw']}`);
    if (points['loss'] != null) parts.push(`a loss is ${points['loss']}`);
    if (points['extra_time_win'] != null) parts.push(`a win in extra time is ${points['extra_time_win']}`);
    if (points['penalty_win'] != null) parts.push(`a win on penalties is ${points['penalty_win']}`);
    return parts.length ? `This variant awards ${parts.join(', ')}. ` : '';
  }

  readonly visibleProfiles = computed(() => {
    const query = this.profileQuery().trim().toLowerCase();
    const profiles = this.profiles();
    if (!query) return profiles;
    return profiles.filter((profile) => {
      const name = (profile.display_name || '').toLowerCase();
      const email = (profile.email || '').toLowerCase();
      return name.includes(query) || email.includes(query);
    });
  });

  readonly reservedIds = computed(() => {
    const ids = new Set<string>();
    for (const participant of this.participants()) {
      for (const member of participant.roster) {
        if (member.user) ids.add(member.user);
      }
      for (const userId of participant.pending_user_ids ?? []) ids.add(userId);
    }
    return ids;
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
  timeLimit = '';
  overtimeLimit = '';
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
        this.readBonus(competition);
        if (this.isCombination() && this.section() === 'entrants') this.loadHorses();
        if (isPointsTable(competition) && this.section() === 'schedule') {
          this.section.set('entrants');
        }
        if (competition.match_weekdays.length) {
          this.selectedWeekdays.set(competition.match_weekdays);
        }
        if (competition.starts_on) {
          this.generate.starts_on = competition.starts_on;
        }
        const limit = competition.settings_json?.['time_limit_minutes'];
        const overtime = competition.settings_json?.['overtime_minutes'];
        this.timeLimit = limit === undefined || limit === null ? '' : String(limit);
        this.overtimeLimit = overtime === undefined || overtime === null ? '' : String(overtime);
        this.loading.set(false);
        if (this.teamEntry() === 'draft' || this.teamEntry() === 'pick' || this.profileEntrants()) {
          this.ensureProfiles();
        }
        if (this.teamEntry() === 'draft') this.loadDraft();
        this.api.listMembers(this.competitionId).subscribe({
          next: (page) => this.memberships.set(page.results),
        });
      },
      error: async (err: unknown) => {
        this.loading.set(false);
        await this.toast(extractErrorMessage(err), 'danger');
      },
    });
  }

  setSection(value: string | undefined): void {
    if (value === 'schedule' && this.pointsTable()) return;
    if (
      value === 'entrants' ||
      value === 'scoring' ||
      value === 'schedule' ||
      value === 'officials' ||
      value === 'scouting'
    ) {
      this.section.set(value);
      if (value === 'officials') {
        this.ensureProfiles();
        this.loadOfficials();
      }
      if (value === 'entrants' && this.isCombination()) this.loadHorses();
      if (value === 'scouting') this.loadScouts();
    }
  }

  readonly competitionLevels = [
    { key: 'school', label: 'School' },
    { key: 'club', label: 'Club' },
    { key: 'provincial', label: 'Provincial' },
    { key: 'national', label: 'National' },
    { key: 'international', label: 'International' },
  ];

  setLevel(level: string): void {
    const competition = this.competition();
    if (!competition || (competition.settings_json?.['level'] ?? '') === level) return;
    this.busy.set(true);
    this.api
      .updateCompetition(this.competitionId, { settings_json: { ...(competition.settings_json ?? {}), level } })
      .subscribe({
        next: (updated) => {
          this.busy.set(false);
          this.competition.set(updated);
        },
        error: () => this.busy.set(false),
      });
  }

  setOpenToScouts(open: boolean): void {
    const competition = this.competition();
    if (!competition || !!competition.open_to_scouts === open || this.busy()) return;
    this.busy.set(true);
    this.api.updateCompetition(this.competitionId, { open_to_scouts: open }).subscribe({
      next: async (updated) => {
        this.competition.set({ ...competition, ...updated });
        this.busy.set(false);
        if (open) this.loadScouts();
        await this.toast(
          open ? 'Open to scouts. The league can now name its own squad.' : 'Closed to scouts.',
          'success',
        );
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        // Re-render so the toggle springs back to the saved value.
        this.competition.set({ ...competition });
        await this.toast(extractErrorMessage(err, 'Could not change the scouting setting.'), 'danger');
      },
    });
  }

  loadScouts(): void {
    if (!this.competition()?.open_to_scouts) {
      this.leagueScouts.set([]);
      return;
    }
    this.scouting.leagueScouts(this.competitionId).subscribe({
      next: (result) => this.leagueScouts.set(result.scouts),
      error: () => this.leagueScouts.set([]),
    });
  }

  addScout(event: Event): void {
    event.preventDefault();
    const email = this.scoutEmail.trim();
    if (!email || this.busy()) return;
    this.busy.set(true);
    this.scouting.addLeagueScout(this.competitionId, email).subscribe({
      next: async (result) => {
        this.leagueScouts.set(result.scouts);
        this.scoutEmail = '';
        this.busy.set(false);
        await this.toast('Scout added. They can now help pick the squad.', 'success');
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not add that scout.'), 'danger');
      },
    });
  }

  removeScout(scoutId: string): void {
    if (this.busy()) return;
    this.busy.set(true);
    this.scouting.removeLeagueScout(this.competitionId, scoutId).subscribe({
      next: (result) => {
        this.leagueScouts.set(result.scouts);
        this.busy.set(false);
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not remove that scout.'), 'danger');
      },
    });
  }

  openSquad(): void {
    void this.router.navigateByUrl(`/tabs/scouting/leagues/${this.competitionId}`);
  }

  backHref(): string {
    return `/tabs/competitions/${this.competitionId}`;
  }

  // --- Entrants -------------------------------------------------------------

  entrantKind(): 'team' | 'individual' | 'pair' {
    const value = this.competition()?.settings_json?.['participant_type'];
    if (value === 'individual' || value === 'pair') return value;
    return 'team';
  }

  /** Individuals here are profiles, picked from a search rather than typed in. */
  profileEntrants(): boolean {
    return this.entrantKind() === 'individual';
  }

  addProfileEntrant(profile: ProfileSummary): void {
    if (this.profileBlocked(profile.id) || this.busy()) return;
    this.busy.set(true);
    this.api
      .createParticipant(this.competitionId, { kind: 'individual', user: profile.id })
      .subscribe({
        next: (participant) => {
          this.participants.update((current) => [...current, participant]);
          this.busy.set(false);
        },
        error: async (err: unknown) => {
          this.busy.set(false);
          await this.toast(extractErrorMessage(err, 'Could not add that profile.'), 'danger');
        },
      });
  }

  teamEntry(): 'pick' | 'draft' | null {
    if (this.entrantKind() !== 'team') return null;
    const value = this.competition()?.settings_json?.['team_entry'];
    return value === 'pick' || value === 'draft' ? value : null;
  }

  canManage(): boolean {
    const role = this.competition()?.my_role;
    return role === 'owner' || role === 'admin';
  }

  isOwner(): boolean {
    return this.competition()?.my_role === 'owner';
  }

  readonly admins = computed(() =>
    this.memberships().filter((membership) => membership.role === 'owner' || membership.role === 'admin'),
  );

  readonly officials = signal<CompetitionOfficial[]>([]);
  readonly officialTitles = signal<Array<{ key: string; label: string }>>([]);
  readonly officialsRequired = signal(false);
  readonly officialTitle = signal('steward');
  readonly stewardQuery = signal('');
  readonly horses = signal<Horse[]>([]);
  readonly horseHits = signal<Horse[]>([]);
  readonly comboHorse = signal('');
  readonly comboRiderId = signal('');
  comboRiderName = '';
  comboTrainerName = '';

  readonly stewardChoices = computed(() => {
    const query = this.stewardQuery().trim().toLowerCase();
    if (!query) return [];
    return this.profiles()
      .filter((profile) => {
        const name = (profile.display_name || '').toLowerCase();
        return name.includes(query) || profile.email.toLowerCase().includes(query);
      })
      .slice(0, 12);
  });

  readonly horseChoices = computed(() => {
    const seen = new Set<string>();
    return [...this.horses(), ...this.horseHits()].filter((horse) => {
      if (seen.has(horse.id) || horse.status !== 'active') return false;
      seen.add(horse.id);
      return true;
    });
  });

  readonly riderChoices = computed(() => this.profiles().slice(0, 300));

  isCombination(): boolean {
    return this.competition()?.settings_json?.['participant_type'] === 'combination';
  }

  loadOfficials(): void {
    this.results.officials(this.competitionId).subscribe({
      next: (response) => {
        this.officials.set(response.officials);
        this.officialTitles.set(response.titles);
        this.officialsRequired.set(response.required);
      },
    });
  }

  appointOfficial(profile: ProfileSummary): void {
    if (this.busy()) return;
    this.busy.set(true);
    this.results.appointOfficial(this.competitionId, profile.id, this.officialTitle()).subscribe({
      next: async (response) => {
        this.officials.set(response.officials);
        this.busy.set(false);
        this.stewardQuery.set('');
        await this.toast(`${profile.display_name || profile.email} appointed.`, 'success');
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not appoint that official.'), 'danger');
      },
    });
  }

  removeOfficial(officialId: string): void {
    if (this.busy()) return;
    this.busy.set(true);
    this.results.removeOfficial(this.competitionId, officialId).subscribe({
      next: (response) => {
        this.officials.set(response.officials);
        this.busy.set(false);
      },
      error: () => this.busy.set(false),
    });
  }

  loadHorses(): void {
    this.results.horses().subscribe({ next: (rows) => this.horses.set(rows) });
    this.ensureProfiles();
  }

  searchHorses(query: string): void {
    if (!query.trim()) {
      this.horseHits.set([]);
      return;
    }
    this.results.horses(query).subscribe({ next: (rows) => this.horseHits.set(rows) });
  }

  openHorses(): void {
    void this.router.navigateByUrl('/tabs/horses');
  }

  addCombination(event: Event): void {
    event.preventDefault();
    if (this.busy() || !this.comboHorse()) return;
    this.busy.set(true);
    this.results
      .addCombination(this.competitionId, {
        horse: this.comboHorse(),
        ...(this.comboRiderId() ? { rider: this.comboRiderId() } : { rider_name: this.comboRiderName.trim() }),
        ...(this.comboTrainerName.trim() ? { trainer_name: this.comboTrainerName.trim() } : {}),
      })
      .subscribe({
        next: async (created) => {
          this.busy.set(false);
          this.comboHorse.set('');
          this.comboRiderId.set('');
          this.comboRiderName = '';
          this.comboTrainerName = '';
          await this.toast(`${created.name} entered.`, 'success');
          this.load();
        },
        error: async (err: unknown) => {
          this.busy.set(false);
          await this.toast(extractErrorMessage(err, 'Could not enter that combination.'), 'danger');
        },
      });
  }

  readonly officialChoices = computed(() => {
    const taken = new Set(this.admins().map((membership) => membership.user.id));
    const query = this.officialQuery().trim().toLowerCase();
    return this.profiles()
      .filter((profile) => !taken.has(profile.id))
      .filter((profile) => {
        if (!query) return true;
        const name = (profile.display_name || '').toLowerCase();
        return name.includes(query) || profile.email.toLowerCase().includes(query);
      })
      .slice(0, 20);
  });

  canAddParticipant(): boolean {
    if (!this.newParticipantName.trim()) return false;
    if (this.teamEntry() === 'pick') return this.selectedProfileIds().length >= 14;
    return true;
  }

  setTeamEntry(mode: 'pick' | 'draft'): void {
    const competition = this.competition();
    if (!competition || this.busy() || this.teamEntry() === mode) return;
    this.busy.set(true);
    const settings = {
      ...(competition.settings_json ?? {}),
      participant_type: 'team',
      team_entry: mode,
    };
    this.api.updateCompetition(this.competitionId, { settings_json: settings }).subscribe({
      next: (updated) => {
        const settingsJson =
          updated.settings_json && Object.keys(updated.settings_json).length
            ? updated.settings_json
            : settings;
        this.competition.update((current) =>
          current ? { ...current, settings_json: settingsJson } : current,
        );
        this.selectedProfileIds.set([]);
        this.busy.set(false);
        this.ensureProfiles();
        if (mode === 'draft') this.loadDraft();
        else this.draftBoard.set(null);
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not save that choice.'), 'danger');
      },
    });
  }

  profileBlocked(id: string): boolean {
    return this.reservedIds().has(id);
  }

  profileNote(profile: ProfileSummary): string {
    if (this.reservedIds().has(profile.id)) {
      return this.profileEntrants() ? 'Already entered' : 'Already picked in this league';
    }
    return profile.email;
  }

  toggleProfile(id: string, event: CustomEvent<{ checked: boolean }>): void {
    if (this.profileBlocked(id)) return;
    const checked = !!event.detail?.checked;
    this.selectedProfileIds.update((current) => {
      const selected = current.includes(id);
      if (checked === selected) return current;
      return checked ? [...current, id] : current.filter((item) => item !== id);
    });
  }

  draftProfile(profile: ProfileSummary): void {
    if (this.profileBlocked(profile.id) || this.busy()) return;
    this.busy.set(true);
    this.api.draftPlayer(this.competitionId, profile.id).subscribe({
      next: (board) => {
        this.draftBoard.set(board);
        this.busy.set(false);
        this.refreshEntrants();
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not draft that profile.'), 'danger');
      },
    });
  }

  private ensureProfiles(): void {
    if (this.profiles().length) return;
    this.api.listProfiles().subscribe({
      next: (page) => this.profiles.set(page.results),
    });
  }

  private loadDraft(): void {
    this.api.getDraft(this.competitionId).subscribe({
      next: (board) => this.draftBoard.set(board),
    });
  }

  private refreshEntrants(): void {
    this.api.getCompetition(this.competitionId).subscribe({
      next: (competition) => {
        this.competition.set(competition);
        this.participants.set(competition.participants);
      },
    });
  }

  removeOvertime(): void {
    this.overtimeLimit = '0';
    this.saveTimeLimits(new Event('submit'));
  }

  saveTimeLimits(event: Event): void {
    event.preventDefault();
    const competition = this.competition();
    if (!competition || !this.canManage() || this.busy()) return;
    const regulation = Number(this.timeLimit);
    const overtime = Number(this.overtimeLimit || 0);
    if (!Number.isFinite(regulation) || regulation < 1) {
      void this.toast('Enter a time limit of at least 1 minute.', 'danger');
      return;
    }
    if (!Number.isFinite(overtime) || overtime < 0) {
      void this.toast('Overtime cannot be negative. Use 0 for no overtime.', 'danger');
      return;
    }
    this.busy.set(true);
    const settings = {
      ...(competition.settings_json ?? {}),
      time_limit_minutes: regulation,
      overtime_minutes: overtime,
    };
    this.api.updateCompetition(this.competitionId, { settings_json: settings }).subscribe({
      next: (updated) => {
        const settingsJson =
          updated.settings_json && Object.keys(updated.settings_json).length
            ? updated.settings_json
            : settings;
        this.competition.update((current) =>
          current ? { ...current, settings_json: settingsJson } : current,
        );
        this.busy.set(false);
        this.overtimeLimit = String(overtime);
        void this.toast(
          overtime > 0 ? 'Game time saved for games not yet started.' : 'Overtime removed for games not yet started.',
          'success',
        );
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not save the time limit.'), 'danger');
      },
    });
  }

  appointAdmin(profile: ProfileSummary): void {
    if (!this.canManage() || this.busy()) return;
    this.busy.set(true);
    const existing = this.memberships().find((membership) => membership.user.id === profile.id);
    const request = existing
      ? this.api.updateMember(this.competitionId, existing.id, { role: 'admin' })
      : this.api.inviteMember(this.competitionId, { user_id: profile.id, role: 'admin' });
    request.subscribe({
      next: (membership) => {
        this.memberships.update((current) => {
          const without = current.filter((item) => item.id !== membership.id && item.user.id !== profile.id);
          return [...without, membership];
        });
        this.busy.set(false);
        void this.toast(`${profile.display_name || profile.email} is now an admin.`, 'success');
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not make that person an admin.'), 'danger');
      },
    });
  }

  dismissAdmin(membership: Membership): void {
    if (!this.isOwner() || this.busy()) return;
    this.busy.set(true);
    this.api.updateMember(this.competitionId, membership.id, { role: 'member' }).subscribe({
      next: (updated) => {
        this.memberships.update((current) =>
          current.map((item) => (item.id === updated.id ? updated : item)),
        );
        this.busy.set(false);
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not remove that admin.'), 'danger');
      },
    });
  }

  addParticipant(event: Event): void {
    event.preventDefault();
    const name = this.newParticipantName.trim();
    if (!this.canAddParticipant() || this.busy()) return;

    this.busy.set(true);
    this.api
      .createParticipant(this.competitionId, {
        name,
        kind: this.entrantKind() === 'individual' ? 'individual' : 'team',
        member_ids: this.teamEntry() === 'pick' ? this.selectedProfileIds() : [],
      })
      .subscribe({
      next: (participant) => {
        this.participants.update((current) => [...current, participant]);
        this.newParticipantName = '';
        this.selectedProfileIds.set([]);
        this.busy.set(false);
        if (this.teamEntry() === 'draft') {
          this.loadDraft();
          return;
        }
        if (participant.kind === 'team') {
          void this.router.navigate([
            '/tabs/competitions',
            this.competitionId,
            'teams',
            participant.id,
          ]);
        }
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not add that entrant.'), 'danger');
      },
    });
  }

  openTeam(participant: Participant): void {
    const profileId = this.profileEntrants() ? participant.roster[0]?.user : null;
    if (profileId) {
      void this.router.navigate(['/tabs/competitions', this.competitionId, 'players', profileId]);
      return;
    }
    void this.router.navigate(['/tabs/competitions', this.competitionId, 'teams', participant.id]);
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

  async removeCategory(category: ScoringCategory): Promise<void> {
    const points = this.pointsTable() ? `${this.trim(category.points)} per unit` : `${this.trim(category.points)} pts`;
    const alert = await this.alerts.create({
      header: `Delete ${category.name}?`,
      message: `${points}. It will no longer be available for scoring in this competition.`,
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        {
          text: 'Delete',
          role: 'destructive',
          handler: () => {
            this.api.deleteScoringCategory(this.competitionId, category.id).subscribe({
              next: () => {
                this.categories.update((current) =>
                  current.filter((candidate) => candidate.id !== category.id),
                );
                void this.toast(`${category.name} deleted.`, 'success');
              },
              error: async (err: unknown) => {
                await this.toast(extractErrorMessage(err, `Could not delete ${category.name}.`), 'danger');
              },
            });
          },
        },
      ],
    });
    await alert.present();
  }

  private readBonus(competition: CompetitionDetail): void {
    const bonus = tableBonusOf(competition);
    const policy = competition.points_policy;
    const enabled =
      bonus && 'enabled' in bonus
        ? !!bonus.enabled
        : policy.bonus_win_margin != null || policy.bonus_loss_margin != null;
    this.bonusEnabled.set(enabled);
    this.scoringBonusCode.set(bonus?.scoring_code ?? '');
    this.scoringBonusThreshold.set(bonus?.scoring_threshold != null ? String(bonus.scoring_threshold) : '4');
    this.scoringBonusPoints.set(bonus?.scoring_points != null ? String(bonus.scoring_points) : '1');
    const winMargin = bonus?.win_margin ?? policy.bonus_win_margin;
    const lossMargin = bonus?.loss_margin ?? policy.bonus_loss_margin;
    this.winBonusMargin.set(winMargin != null ? String(winMargin) : '');
    this.winBonusPoints.set(
      bonus?.win_points != null ? String(bonus.win_points) : this.trim(policy.bonus_win_points) || '1',
    );
    this.lossBonusMargin.set(lossMargin != null ? String(lossMargin) : enabled ? '7' : '');
    this.lossBonusPoints.set(
      bonus?.loss_points != null ? String(bonus.loss_points) : this.trim(policy.bonus_loss_points) || '1',
    );
  }

  setBonusEnabled(enabled: boolean): void {
    this.bonusEnabled.set(enabled);
    if (enabled && !this.scoringBonusCode()) {
      this.scoringBonusCode.set(this.categories()[0]?.code ?? '');
    }
    this.saveBonus();
  }

  saveBonus(): void {
    if (this.scoringLocked()) return;
    const competition = this.competition();
    if (!competition) return;
    const enabled = this.bonusEnabled();
    const winMargin = Number(this.winBonusMargin()) || null;
    const winPoints = Number(this.winBonusPoints() || 0);
    const lossMargin = Number(this.lossBonusMargin()) || null;
    const lossPoints = Number(this.lossBonusPoints() || 0);
    const tableBonus = enabled
      ? {
          enabled: true,
          scoring_threshold: Number(this.scoringBonusThreshold()) || null,
          scoring_points: Number(this.scoringBonusPoints() || 0),
          scoring_code: this.scoringBonusCode(),
          win_margin: winMargin,
          win_points: winPoints,
          loss_margin: lossMargin,
          loss_points: lossPoints,
        }
      : { enabled: false };
    const settings = { ...(competition.settings_json ?? {}), table_bonus: tableBonus };
    this.api.updateCompetition(this.competitionId, { settings_json: settings }).subscribe({
      next: (updated) => {
        const settingsJson =
          updated.settings_json && Object.keys(updated.settings_json).length
            ? updated.settings_json
            : settings;
        this.competition.update((current) =>
          current ? { ...current, settings_json: settingsJson } : current,
        );
        this.patchPolicy({
          bonus_win_margin: enabled ? winMargin : null,
          bonus_win_points: String(enabled ? winPoints : 0),
          bonus_loss_margin: enabled ? lossMargin : null,
          bonus_loss_points: String(enabled ? lossPoints : 0),
        });
      },
      error: async (err: unknown) => {
        await this.toast(extractErrorMessage(err, 'Could not save bonus points.'), 'danger');
      },
    });
  }

  patchPolicy(patch: Partial<PointsPolicy>): void {
    if (this.scoringLocked()) return;
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
          void this.router.navigate(['/tabs/competitions', this.competitionId], {
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
