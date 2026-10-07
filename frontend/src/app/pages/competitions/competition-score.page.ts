import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import {
  IonBackButton,
  IonButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonInput,
  IonItem,
  IonList,
  IonNote,
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
import type { CompetitionDetail, ScoreAssistEntry } from '../../core/models';
import { isPointsTable } from '../../core/models';

@Component({
  selector: 'fm-competition-score',
  standalone: true,
  imports: [
    FormsModule,
    IonHeader,
    IonToolbar,
    IonTitle,
    IonButtons,
    IonBackButton,
    IonContent,
    IonList,
    IonItem,
    IonInput,
    IonTextarea,
    IonSelect,
    IonSelectOption,
    IonButton,
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
        <ion-title>{{ criteriaLeague() ? 'Add points' : 'Score' }}</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (competition(); as comp) {
        <h3 class="fm-section-title">Record a score</h3>
        <p class="hint">
          @if (criteriaLeague()) {
            Award a scoring criterion. The table adds what was achieved, and the
            note explains how those points were accumulated.
          } @else {
            Record a finished fixture as a win, draw, or loss. Scoring criteria
            still describe what a point means.
          }
        </p>

        @if (comp.scoring_categories.length === 0) {
          <ion-note class="footnote">Define scoring criteria in setup before recording scores.</ion-note>
        } @else if (criteriaLeague() && comp.participants.length === 0) {
          <ion-note class="footnote">Add entrants in setup, then award their points here.</ion-note>
        } @else if (criteriaLeague()) {
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
                label="How these points were accumulated"
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
              </ion-item>
            }
          </ion-list>
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
      .submit {
        margin: 16px;
      }
      .footnote {
        display: block;
        margin: 0 20px 12px;
      }
      .entry p {
        margin: 2px 0 0;
        color: var(--ion-color-medium);
        font-size: 0.82rem;
      }
      .quiet {
        font-style: italic;
      }
    `,
  ],
})
export class CompetitionScorePage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastController);

  private competitionId = '';

  readonly competition = signal<CompetitionDetail | null>(null);
  readonly entries = signal<ScoreAssistEntry[]>([]);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);

  participantId = '';
  categoryId = '';
  quantity = '1';
  homeId = '';
  awayId = '';
  outcome = 'home';
  note = '';

  readonly criteriaLeague = computed(() => {
    const competition = this.competition();
    return competition ? isPointsTable(competition) : false;
  });

  selectedCategory() {
    const competition = this.competition();
    return competition?.scoring_categories.find((category) => category.id === this.categoryId) ?? null;
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
        this.homeId = competition.participants[0]?.id ?? '';
        this.awayId = competition.participants[1]?.id ?? '';
        this.loading.set(false);
        this.loadEntries();
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

  canSubmit(): boolean {
    if (this.criteriaLeague()) {
      return Boolean(this.participantId && this.categoryId && this.note.trim() && Number(this.quantity));
    }
    return Boolean(this.homeId && this.awayId && this.homeId !== this.awayId && this.outcome);
  }

  submit(): void {
    if (!this.canSubmit() || this.busy()) return;
    this.busy.set(true);
    this.error.set(null);
    const body = this.criteriaLeague()
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
        const criteria = this.criteriaLeague();
        const toast = await this.toasts.create({
          message: criteria ? 'Points added to the table.' : 'Score recorded.',
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

  trim(value: string): string {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? String(parsed) : value;
  }
}
