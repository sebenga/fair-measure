import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { AlertController, IonButton, IonButtons, IonContent, IonHeader, IonIcon, IonInput, IonItem, IonList, IonNote, IonSelect, IonSelectOption, IonSpinner, IonTextarea, IonTitle, IonToolbar, ToastController, IonLabel, IonBackButton } from '@ionic/angular/standalone';

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';
import type { CompetitionDetail, ScoreAssistEntry, VotingRound } from '../../core/models';
import { BackHrefPipe } from '../../shared/back-href.pipe';
import {
  accumulatesAsVoteCount,
  isPointsTable,
  pointsByVoting,
  scoresAllOnCriterion,
  votesPerMember,
  votingVisibility,
} from '../../core/models';

@Component({
  selector: 'fm-competition-score',
  standalone: true,
  imports: [BackHrefPipe, IonBackButton, 
    FormsModule,
    IonHeader,
    IonToolbar,
    IonTitle,
    IonButtons, IonContent,
    IonList,
    IonItem,
    IonInput,
    IonTextarea,
    IonSelect,
    IonSelectOption,
    IonLabel,
    IonButton,
    IonIcon,
    IonNote,
    IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start">
          <ion-back-button [defaultHref]="(backHref()) | backHref" />
        </ion-buttons>
        <ion-title>
          {{
            voteCountTable()
              ? 'Vote'
              : votingOn()
                ? 'Vote & points'
                : criteriaLeague()
                  ? 'Add points'
                  : 'Score'
          }}
        </ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (competition(); as comp) {
        @if (votingOn()) {
          <h3 class="fm-section-title">{{ voteCountTable() ? 'Vote only' : 'Member voting' }}</h3>
          <p class="hint">
            @if (voteCountTable()) {
              @if (memberVoteBudget() <= 1) {
                One vote for the whole competition — pick one entrant. Your ballot locks after you cast it; you cannot vote again.
              } @else {
                You have {{ memberVoteBudget() }} votes for this competition. Allocate all of them once across entrants, then your ballot locks and you cannot vote again.
              }
              Closing a round adds those votes to the table (1 vote = 1 on the standings).
            } @else if (memberVoteBudget() <= 1) {
              One vote each per round — pick one entrant. Your ballot locks after you cast it.
            } @else {
              Each voter has {{ memberVoteBudget() }} votes per round to split across entrants. Saving locks the ballot.
            }
            Default for new rounds is
            {{ ballotVisibility() === 'visible' ? 'live tallies' : 'hidden until an admin closes the round' }}.
            @if (!voteCountTable()) {
              Closing awards one criterion unit per vote to the table.
            }
          </p>

          @if (canManageVotes()) {
            <ion-list inset="true">
              <ion-item>
                <ion-select label="Criterion" labelPlacement="stacked" [(ngModel)]="voteCategoryId" name="vote-criterion">
                  @for (category of comp.scoring_categories; track category.id) {
                    <ion-select-option [value]="category.id">
                      @if (voteCountTable()) {
                        {{ category.name }} · 1 per vote
                      } @else {
                        {{ category.name }} · {{ trim(category.points) }} per vote
                      }
                    </ion-select-option>
                  }
                </ion-select>
              </ion-item>
              <ion-item>
                <ion-input
                  label="Round title (optional)"
                  labelPlacement="stacked"
                  [(ngModel)]="voteTitle"
                  name="vote-title"
                  maxlength="200"
                  placeholder="e.g. Week 3 popular pick"
                />
              </ion-item>
              <ion-item>
                <ion-select
                  label="This round"
                  labelPlacement="stacked"
                  [(ngModel)]="voteRoundVisibility"
                  name="vote-visibility"
                >
                  <ion-select-option value="secret">Private — hide tallies until close</ion-select-option>
                  <ion-select-option value="visible">Public — show live tallies</ion-select-option>
                </ion-select>
              </ion-item>
            </ion-list>
            <ion-button expand="block" class="submit" [disabled]="voteBusy() || !voteCategoryId" (click)="openRound()">
              @if (voteBusy()) {
                <ion-spinner name="crescent" />
              } @else {
                Open voting round
              }
            </ion-button>
          }

          @if (voteError()) {
            <p class="fm-form-error" role="alert">{{ voteError() }}</p>
          }

          @if (!rounds().length) {
            <ion-note class="footnote">No voting rounds yet.</ion-note>
          } @else {
            @for (round of rounds(); track round.id) {
              <section class="vote-round">
                <div class="vote-head">
                  <div>
                    <strong>{{ round.title }}</strong>
                    <small>
                      {{ round.category_name }} · {{ round.status }}
                      · {{ round.visibility === 'visible' ? 'public' : 'private' }}
                      · {{ round.vote_count }} vote{{ round.vote_count === 1 ? '' : 's' }}
                    </small>
                  </div>
                  @if (canManageVotes() && round.status === 'open') {
                    <ion-button size="small" fill="outline" [disabled]="voteBusy()" (click)="closeRound(round)">
                      Close &amp; award
                    </ion-button>
                  }
                </div>

                @if (round.status === 'open' && canVote()) {
                  @if (hasCastBallot(round)) {
                    <ion-note class="footnote" role="status">
                      Ballot locked.
                      @if (round.my_vote) {
                        You voted for {{ round.my_vote.participant_name }}.
                      } @else if (round.my_votes?.length) {
                        Saved:
                        @for (row of round.my_votes; track row.participant_id; let last = $last) {
                          {{ row.votes }} for {{ row.participant_name }}{{ last ? '.' : ', ' }}
                        }
                      }
                      @if (voteCountTable() || round.vote_only) {
                        You cannot vote again in this competition.
                      } @else {
                        You cannot vote again in this round.
                      }
                    </ion-note>
                  } @else if ((round.votes_per_member ?? memberVoteBudget()) <= 1) {
                    <ion-list inset="true">
                      <ion-item>
                        <ion-select
                          label="Your vote"
                          labelPlacement="stacked"
                          [ngModel]="round.my_vote?.participant_id || ''"
                          (ngModelChange)="castFor(round, $event)"
                          [name]="'vote-' + round.id"
                          [disabled]="voteBusy()"
                        >
                          @for (participant of comp.participants; track participant.id) {
                            <ion-select-option [value]="participant.id">{{ participant.name }}</ion-select-option>
                          }
                        </ion-select>
                      </ion-item>
                    </ion-list>
                  } @else {
                    <ion-note class="footnote">
                      {{ draftUsed(round) }} of {{ round.votes_per_member ?? memberVoteBudget() }} used ·
                      {{ draftRemaining(round) }} left
                      @if (voteCountTable() || round.vote_only) {
                        · allocate all votes, then cast once
                      } @else {
                        · save once to lock your ballot
                      }
                    </ion-note>
                    <ion-list inset="true">
                      @for (participant of comp.participants; track participant.id) {
                        <ion-item>
                          <ion-label>{{ participant.name }}</ion-label>
                          <div class="vote-stepper" slot="end">
                            <ion-button
                              size="small"
                              fill="clear"
                              [disabled]="voteBusy() || draftFor(round, participant.id) <= 0"
                              (click)="nudgeAllocation(round, participant.id, -1)"
                            >
                              −
                            </ion-button>
                            <strong>{{ draftFor(round, participant.id) }}</strong>
                            <ion-button
                              size="small"
                              fill="clear"
                              [disabled]="voteBusy() || draftRemaining(round) <= 0"
                              (click)="nudgeAllocation(round, participant.id, 1)"
                            >
                              +
                            </ion-button>
                          </div>
                        </ion-item>
                      }
                    </ion-list>
                    <ion-button
                      expand="block"
                      class="submit"
                      [disabled]="voteBusy() || !canSubmitBallot(round)"
                      (click)="submitAllocations(round)"
                    >
                      @if (voteBusy()) {
                        <ion-spinner name="crescent" />
                      } @else {
                        Cast my ballot
                      }
                    </ion-button>
                  }
                }

                @if (round.tallies_hidden) {
                  <ion-note class="footnote">Tallies are private until this round closes.</ion-note>
                } @else if (round.tallies?.length) {
                  <ul class="tallies">
                    @for (row of round.tallies; track row.participant_id) {
                      <li>
                        <span>{{ row.participant_name }}</span>
                        <strong>{{ row.votes }}</strong>
                      </li>
                    }
                  </ul>
                } @else if (round.status === 'closed') {
                  <ion-note class="footnote">No votes were cast.</ion-note>
                }
              </section>
            }
          }
        }

        @if (canScoreAdmin()) {
        <h3 class="fm-section-title">{{ votingOn() ? 'Admin award' : 'Record a score' }}</h3>
        <p class="hint">
          {{
            criteriaLeague()
              ? allOnCriterion()
                ? 'Pick one criterion and enter what every entrant achieved in this round. Leave a blank for anyone with nothing to add.'
                : 'Award a scoring criterion. The table adds what was achieved, and the note explains how those points were accumulated.'
              : 'Record a finished fixture as a win, draw, or loss. Scoring criteria still describe what a point means.'
          }}
        </p>

        @if (comp.scoring_categories.length === 0) {
          <ion-note class="footnote">Define scoring criteria in setup before recording scores.</ion-note>
        } @else if (criteriaLeague() && comp.participants.length === 0) {
          <ion-note class="footnote">Add entrants in setup, then award their points here.</ion-note>
        } @else if (criteriaLeague()) {
          @if (allOnCriterion()) {
            <ion-list inset="true">
              <ion-item>
                <ion-select label="Criterion" labelPlacement="stacked" [(ngModel)]="categoryId" name="criterion">
                  @for (category of comp.scoring_categories; track category.id) {
                    <ion-select-option [value]="category.id">
                      {{ category.name }} · {{ trim(category.points) }} per unit
                    </ion-select-option>
                  }
                </ion-select>
              </ion-item>
              <ion-item>
                <ion-textarea
                  label="How these points were accumulated (required)"
                  labelPlacement="stacked"
                  [(ngModel)]="note"
                  name="note"
                  autoGrow="true"
                  rows="3"
                  maxlength="280"
                  placeholder="e.g. Week 4 sales board."
                />
              </ion-item>
              @for (participant of comp.participants; track participant.id) {
                <ion-item>
                  <ion-input
                    [label]="participant.name"
                    labelPlacement="stacked"
                    type="number"
                    inputmode="decimal"
                    [ngModel]="roundQuantities[participant.id] ?? ''"
                    (ngModelChange)="setRoundQuantity(participant.id, $event)"
                    [name]="'qty-' + participant.id"
                    placeholder="0"
                  />
                </ion-item>
              }
            </ion-list>
          } @else {
            <ion-list inset="true">
              <ion-item>
                <ion-select label="Who" labelPlacement="stacked" [(ngModel)]="participantId" name="who">
                  @for (participant of comp.participants; track participant.id) {
                    <ion-select-option [value]="participant.id">{{ participant.name }}</ion-select-option>
                  }
                </ion-select>
              </ion-item>
              <ion-item>
                <ion-select label="Criterion" labelPlacement="stacked" [(ngModel)]="categoryId" name="criterion">
                  @for (category of comp.scoring_categories; track category.id) {
                    <ion-select-option [value]="category.id">
                      {{ category.name }} · {{ trim(category.points) }} per unit
                    </ion-select-option>
                  }
                </ion-select>
              </ion-item>
              <ion-item>
                <ion-input
                  label="What they achieved"
                  labelPlacement="stacked"
                  type="number"
                  inputmode="decimal"
                  [(ngModel)]="quantity"
                  name="quantity"
                />
              </ion-item>
              <ion-item>
                <ion-textarea
                  label="How these points were accumulated (required)"
                  labelPlacement="stacked"
                  [(ngModel)]="note"
                  name="note"
                  autoGrow="true"
                  rows="3"
                  maxlength="280"
                  placeholder="e.g. Three enterprise deals closed this week."
                />
              </ion-item>
            </ion-list>
          }
          @if (selectedCategory(); as category) {
            <ion-note class="footnote">{{ category.description || 'This criterion has no description yet.' }}</ion-note>
          }
        } @else {
          <ion-list inset="true">
            <ion-item>
              <ion-select label="Home" labelPlacement="stacked" [(ngModel)]="homeId" name="home">
                @for (participant of comp.participants; track participant.id) {
                  <ion-select-option [value]="participant.id">{{ participant.name }}</ion-select-option>
                }
              </ion-select>
            </ion-item>
            <ion-item>
              <ion-select label="Away" labelPlacement="stacked" [(ngModel)]="awayId" name="away">
                @for (participant of comp.participants; track participant.id) {
                  <ion-select-option [value]="participant.id">{{ participant.name }}</ion-select-option>
                }
              </ion-select>
            </ion-item>
            <ion-item>
              <ion-select label="Result" labelPlacement="stacked" [(ngModel)]="outcome" name="outcome">
                <ion-select-option value="home">Home win</ion-select-option>
                <ion-select-option value="draw">Draw</ion-select-option>
                <ion-select-option value="away">Away win</ion-select-option>
              </ion-select>
            </ion-item>
            <ion-item>
              <ion-textarea
                label="Note"
                labelPlacement="stacked"
                [(ngModel)]="note"
                name="note"
                autoGrow="true"
                rows="2"
                maxlength="280"
                placeholder="Optional. What decided the result?"
              />
            </ion-item>
          </ion-list>
        }

        @if (error()) {
          <p class="fm-form-error" role="alert">{{ error() }}</p>
        }

        <ion-button expand="block" class="submit" [disabled]="busy() || !canSubmit()" (click)="submit()">
          @if (busy()) {
            <ion-spinner name="crescent" />
          } @else {
            {{ criteriaLeague() ? 'Add to the table' : 'Record result' }}
          }
        </ion-button>

        <h3 class="fm-section-title">Recent entries</h3>
        @if (entries().length === 0) {
          <ion-note class="footnote">Nothing logged yet.</ion-note>
        } @else {
          <ion-list inset="true">
            @for (entry of entries(); track entry.id) {
              <ion-item>
                <div class="entry">
                  <strong>{{ entry.participant_name }} · {{ entry.criterion }}</strong>
                  <p>{{ trim(entry.awarded) }} pts from {{ trim(entry.quantity) }}</p>
                  @if (entry.note) {
                    <p>{{ entry.note }}</p>
                  }
                  @if (entry.description) {
                    <p class="quiet">{{ entry.description }}</p>
                  }
                </div>
                <ion-button
                  slot="end"
                  fill="clear"
                  color="danger"
                  size="small"
                  [disabled]="busy()"
                  (click)="confirmDelete(entry)"
                  [attr.aria-label]="'Delete ' + entry.criterion + ' for ' + entry.participant_name"
                >
                  <ion-icon slot="icon-only" name="trash-outline" aria-hidden="true" />
                </ion-button>
              </ion-item>
            }
          </ion-list>
        }
        }
      }
    </ion-content>
  `,
  styles: [
    `
      .centered {
        display: grid;
        place-items: center;
        padding: 64px 0;
      }
      .fm-section-title {
        margin-left: 32px;
        margin-right: 32px;
      }
      .hint {
        margin: 0 32px 12px;
        font-size: 0.9rem;
        line-height: 1.5;
        text-align: left;
        color: var(--ion-color-medium);
      }
      .submit {
        margin: 16px;
      }
      .footnote {
        display: block;
        margin: 0 32px 12px;
        text-align: left;
      }
      .entry p {
        margin: 2px 0 0;
        color: var(--ion-color-medium);
        font-size: 0.82rem;
      }
      .quiet {
        font-style: italic;
      }
      .vote-round {
        margin: 0 16px 18px;
        padding: 12px 14px;
        border-radius: 12px;
        border: 1px solid var(--ion-color-step-150, #e6e8eb);
      }
      .vote-head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 10px;
        margin-bottom: 8px;
      }
      .vote-head strong {
        display: block;
      }
      .vote-stepper {
        display: inline-flex;
        align-items: center;
        gap: 4px;
      }
      .vote-stepper strong {
        min-width: 1.5rem;
        text-align: center;
      }
      .vote-head small {
        color: var(--ion-color-medium);
        font-size: 0.78rem;
      }
      .tallies {
        list-style: none;
        margin: 8px 0 0;
        padding: 0;
        display: grid;
        gap: 6px;
      }
      .tallies li {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        font-size: 0.9rem;
      }
    `],
})
export class CompetitionScorePage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastController);
  private readonly alerts = inject(AlertController);

  private competitionId = '';

  readonly competition = signal<CompetitionDetail | null>(null);
  readonly entries = signal<ScoreAssistEntry[]>([]);
  readonly rounds = signal<VotingRound[]>([]);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly voteBusy = signal(false);
  readonly error = signal<string | null>(null);
  readonly voteError = signal<string | null>(null);

  participantId = '';
  categoryId = '';
  voteCategoryId = '';
  voteTitle = '';
  /** Per-round override; defaults to the competition setting when the board loads. */
  voteRoundVisibility: 'secret' | 'visible' = 'secret';
  quantity = '1';
  homeId = '';
  awayId = '';
  outcome = 'home';
  note = '';
  roundQuantities: Record<string, string> = {};

  readonly criteriaLeague = computed(() => {
    const competition = this.competition();
    return competition ? isPointsTable(competition) : false;
  });

  readonly allOnCriterion = computed(() => {
    const competition = this.competition();
    return competition ? scoresAllOnCriterion(competition) : false;
  });

  readonly votingOn = computed(() => {
    const competition = this.competition();
    return competition ? pointsByVoting(competition) : false;
  });

  readonly ballotVisibility = computed(() => {
    const competition = this.competition();
    return competition ? votingVisibility(competition) : 'secret';
  });

  readonly memberVoteBudget = computed(() => {
    const competition = this.competition();
    return competition ? votesPerMember(competition) : 1;
  });

  readonly voteCountTable = computed(() => {
    const competition = this.competition();
    return competition ? accumulatesAsVoteCount(competition) : false;
  });

  /** Local draft allocations per open round (participant id → votes). */
  readonly allocationDrafts = signal<Record<string, Record<string, number>>>({});

  readonly roundMode = computed(() => this.criteriaLeague() && this.allOnCriterion());

  canVote(): boolean {
    return Boolean(this.competition()?.my_role);
  }

  canManageVotes(): boolean {
    const role = this.competition()?.my_role;
    return role === 'owner' || role === 'admin';
  }

  canScoreAdmin(): boolean {
    // Vote-only boards are scored solely by ballots — no manual admin awards.
    if (this.voteCountTable()) return false;
    const role = this.competition()?.my_role;
    return role === 'owner' || role === 'admin' || role === 'scorer';
  }

  selectedCategory() {
    const competition = this.competition();
    return competition?.scoring_categories.find((category) => category.id === this.categoryId) ?? null;
  }

  setRoundQuantity(participantId: string, value: string | number | null | undefined): void {
    this.roundQuantities = { ...this.roundQuantities, [participantId]: String(value ?? '') };
  }

  ngOnInit(): void {
    this.competitionId = this.route.snapshot.paramMap.get('id') ?? '';
    this.load();
  }

  backHref(): string {
    return `/tabs/competitions/${this.competitionId}`;
  }

  load(): void {
    this.loading.set(true);
    this.api.getCompetition(this.competitionId).subscribe({
      next: (competition) => {
        this.competition.set(competition);
        this.participantId = competition.participants[0]?.id ?? '';
        this.categoryId = competition.scoring_categories[0]?.id ?? '';
        this.voteCategoryId = competition.scoring_categories[0]?.id ?? '';
        this.voteRoundVisibility = votingVisibility(competition);
        this.homeId = competition.participants[0]?.id ?? '';
        this.awayId = competition.participants[1]?.id ?? '';
        this.roundQuantities = Object.fromEntries(
          competition.participants.map((participant) => [participant.id, '']),
        );
        this.loading.set(false);
        if (this.canScoreAdmin()) this.loadEntries();
        if (pointsByVoting(competition)) this.loadRounds();
      },
      error: (err: unknown) => {
        this.loading.set(false);
        this.error.set(extractErrorMessage(err));
      },
    });
  }

  loadEntries(): void {
    this.api.listScoreAssist(this.competitionId).subscribe({
      next: (entries) => this.entries.set(entries),
      error: () => this.entries.set([]),
    });
  }

  loadRounds(): void {
    this.api.listVotingRounds(this.competitionId).subscribe({
      next: (rounds) => {
        this.rounds.set(rounds);
        for (const round of rounds) {
          this.seedDraft(round);
        }
      },
      error: () => this.rounds.set([]),
    });
  }

  private draftFromRound(round: VotingRound): Record<string, number> {
    return Object.fromEntries((round.my_votes ?? []).map((row) => [row.participant_id, row.votes]));
  }

  private seedDraft(round: VotingRound, force = false): void {
    if (!force && this.allocationDrafts()[round.id]) return;
    this.allocationDrafts.update((all) => ({ ...all, [round.id]: this.draftFromRound(round) }));
  }

  private draftMap(round: VotingRound): Record<string, number> {
    return this.allocationDrafts()[round.id] ?? this.draftFromRound(round);
  }

  draftFor(round: VotingRound, participantId: string): number {
    return this.draftMap(round)[participantId] ?? 0;
  }

  draftUsed(round: VotingRound): number {
    return Object.values(this.draftMap(round)).reduce((sum, n) => sum + n, 0);
  }

  draftRemaining(round: VotingRound): number {
    return Math.max(0, (round.votes_per_member ?? this.memberVoteBudget()) - this.draftUsed(round));
  }

  allocationDirty(round: VotingRound): boolean {
    const saved = new Map((round.my_votes ?? []).map((row) => [row.participant_id, row.votes]));
    const draft = this.draftMap(round);
    const ids = new Set([...saved.keys(), ...Object.keys(draft)]);
    for (const id of ids) {
      if ((saved.get(id) ?? 0) !== (draft[id] ?? 0)) return true;
    }
    return false;
  }

  nudgeAllocation(round: VotingRound, participantId: string, delta: number): void {
    if (round.status !== 'open' || this.voteBusy()) return;
    const draft = { ...this.draftMap(round) };
    const current = draft[participantId] ?? 0;
    const next = current + delta;
    if (next < 0) return;
    if (delta > 0 && this.draftRemaining(round) < delta) return;
    if (next === 0) delete draft[participantId];
    else draft[participantId] = next;
    this.allocationDrafts.update((all) => ({ ...all, [round.id]: draft }));
  }

  submitAllocations(round: VotingRound): void {
    if (this.voteBusy() || round.status !== 'open') return;
    if (this.hasCastBallot(round)) {
      this.voteError.set(
        this.voteCountTable()
          ? 'You already cast your ballot in this competition.'
          : 'You already cast your ballot in this round.',
      );
      return;
    }
    if (!this.canSubmitBallot(round)) {
      const budget = round.votes_per_member ?? this.memberVoteBudget();
      this.voteError.set(`Allocate all ${budget} votes before casting your ballot.`);
      return;
    }
    const allocations = Object.entries(this.draftMap(round))
      .filter(([, votes]) => votes > 0)
      .map(([participant, votes]) => ({ participant, votes }));
    if (!allocations.length) return;
    this.voteBusy.set(true);
    this.voteError.set(null);
    this.api.castVote(this.competitionId, round.id, { allocations }).subscribe({
      next: (res) => {
        this.seedDraft(res.round, true);
        this.rounds.update((rows) => rows.map((row) => (row.id === round.id ? res.round : row)));
        this.voteBusy.set(false);
        void this.notify('Ballot cast and locked.', 'success');
      },
      error: (err: unknown) => {
        this.voteBusy.set(false);
        this.voteError.set(extractErrorMessage(err, 'Could not save those votes.'));
      },
    });
  }

  openRound(): void {
    if (this.voteBusy() || !this.voteCategoryId) return;
    this.voteBusy.set(true);
    this.voteError.set(null);
    this.api
      .openVotingRound(this.competitionId, {
        scoring_category: this.voteCategoryId,
        title: this.voteTitle.trim(),
        visibility: this.voteRoundVisibility,
      })
      .subscribe({
        next: (round) => {
          this.seedDraft(round, true);
          this.rounds.update((rows) => [round, ...rows]);
          this.voteTitle = '';
          this.voteBusy.set(false);
          void this.notify('Voting round opened.', 'success');
        },
        error: (err: unknown) => {
          this.voteBusy.set(false);
          this.voteError.set(extractErrorMessage(err, 'Could not open a voting round.'));
        },
      });
  }

  hasCastBallot(round: VotingRound): boolean {
    if (round.ballot_locked || round.competition_ballot_cast) return true;
    if (this.voteCountTable() || round.vote_only) {
      return this.rounds().some(
        (row) =>
          row.competition_ballot_cast ||
          (row.votes_used ?? 0) > 0 ||
          !!row.my_vote ||
          (row.my_votes?.length ?? 0) > 0,
      );
    }
    return (round.votes_used ?? 0) > 0 || !!round.my_vote || (round.my_votes?.length ?? 0) > 0;
  }

  canSubmitBallot(round: VotingRound): boolean {
    const budget = round.votes_per_member ?? this.memberVoteBudget();
    const used = this.draftUsed(round);
    if (used < 1) return false;
    if (this.voteCountTable() || round.vote_only) return used === budget;
    return true;
  }

  castFor(round: VotingRound, participantId: string): void {
    if (!participantId || this.voteBusy() || round.status !== 'open') return;
    if (this.hasCastBallot(round)) {
      this.voteError.set(
        this.voteCountTable()
          ? 'You already cast your ballot in this competition.'
          : 'You already cast your ballot in this round.',
      );
      return;
    }
    this.voteBusy.set(true);
    this.voteError.set(null);
    this.api.castVote(this.competitionId, round.id, { participant: participantId }).subscribe({
      next: (res) => {
        this.seedDraft(res.round, true);
        this.rounds.update((rows) => rows.map((row) => (row.id === round.id ? res.round : row)));
        this.voteBusy.set(false);
        const name = res.vote?.participant_name ?? 'entrant';
        void this.notify(`Voted for ${name}. Ballot locked.`, 'success');
      },
      error: (err: unknown) => {
        this.voteBusy.set(false);
        this.voteError.set(extractErrorMessage(err, 'Could not cast that vote.'));
      },
    });
  }

  closeRound(round: VotingRound): void {
    if (this.voteBusy() || round.status !== 'open') return;
    this.voteBusy.set(true);
    this.voteError.set(null);
    this.api.closeVotingRound(this.competitionId, round.id).subscribe({
      next: (updated) => {
        this.rounds.update((rows) => rows.map((row) => (row.id === round.id ? updated : row)));
        this.voteBusy.set(false);
        if (this.canScoreAdmin()) this.loadEntries();
        void this.notify('Round closed. Points added to the table.', 'success');
      },
      error: (err: unknown) => {
        this.voteBusy.set(false);
        this.voteError.set(extractErrorMessage(err, 'Could not close that round.'));
      },
    });
  }

  canSubmit(): boolean {
    if (this.roundMode()) {
      const scored = Object.values(this.roundQuantities).some((value) => Number(value));
      return Boolean(this.categoryId && this.note.trim() && scored);
    }
    if (this.criteriaLeague()) {
      return Boolean(this.participantId && this.categoryId && this.note.trim() && Number(this.quantity));
    }
    return Boolean(this.homeId && this.awayId && this.homeId !== this.awayId && this.outcome);
  }

  submit(): void {
    if (!this.canSubmit() || this.busy()) return;
    this.busy.set(true);
    this.error.set(null);
    const body = this.roundMode()
      ? {
          kind: 'criterion_round',
          scoring_category: this.categoryId,
          note: this.note.trim(),
          entries: Object.entries(this.roundQuantities)
            .filter(([ value]) => Number(value))
            .map(([participant, quantity]) => ({ participant, quantity })),
        }
      : this.criteriaLeague()
        ? {
            kind: 'criterion',
            participant: this.participantId,
            scoring_category: this.categoryId,
            quantity: this.quantity,
            note: this.note.trim(),
          }
        : {
            kind: 'result',
            home: this.homeId,
            away: this.awayId,
            outcome: this.outcome,
            note: this.note.trim(),
          };

    this.api.recordScoreAssist(this.competitionId, body).subscribe({
      next: async () => {
        this.busy.set(false);
        this.note = '';
        if (this.roundMode()) {
          this.roundQuantities = Object.fromEntries(
            Object.keys(this.roundQuantities).map((id) => [id, '']),
          );
        }
        const criteria = this.criteriaLeague();
        const toast = await this.toasts.create({
          message: criteria
            ? this.roundMode()
              ? 'Round added to the table.'
              : 'Points added to the table.'
            : 'Score recorded.',
          duration: 1800,
          position: 'bottom',
        });
        await toast.present();
        if (criteria) {
          void this.router.navigate(['/tabs/competitions', this.competitionId], {
            queryParams: { tab: 'standings' },
          });
          return;
        }
        this.loadEntries();
      },
      error: (err: unknown) => {
        this.busy.set(false);
        this.error.set(extractErrorMessage(err, 'Could not record that score.'));
      },
    });
  }

  /** Delete a logged score after a confirmation; the table is worked out again. */
  async confirmDelete(entry: ScoreAssistEntry): Promise<void> {
    const official = this.competition()?.settings_json?.['official_results'] === true;
    const alert = await this.alerts.create({
      header: 'Delete this score?',
      message: `${entry.participant_name} · ${entry.criterion}: ${this.trim(entry.awarded)} pts. The table is worked out again.`,
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
            this.deleteEntry(entry, reason || undefined);
            return true;
          },
        }],
    });
    await alert.present();
  }

  private deleteEntry(entry: ScoreAssistEntry, reason?: string): void {
    this.busy.set(true);
    this.api.deleteEvent(entry.fixture_id, entry.id, reason).subscribe({
      next: () => {
        this.busy.set(false);
        this.entries.update((rows) => rows.filter((row) => row.id !== entry.id));
        void this.notify('Score deleted. The table is updated.', 'success');
      },
      error: (err: unknown) => {
        this.busy.set(false);
        void this.notify(extractErrorMessage(err, 'Could not delete that score.'), 'danger');
      },
    });
  }

  private async notify(message: string, color: string): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2200, position: 'bottom' });
    await toast.present();
  }

  trim(value: string): string {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? String(parsed) : value;
  }
}
