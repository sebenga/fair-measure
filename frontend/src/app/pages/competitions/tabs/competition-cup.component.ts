import { DatePipe } from '@angular/common';
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
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { IonButton, IonIcon, IonInput, IonItem, IonList, AlertController, ToastController } from '@ionic/angular/standalone';
import { switchMap } from 'rxjs/operators';

import { ApiService } from '../../../core/api.service';
import { extractErrorMessage } from '../../../core/error-message';
import type { CompetitionDetail, Fixture } from '../../../core/models';
import { RealtimeService } from '../../../core/realtime.service';
import { CompetitionFixturesComponent } from './competition-fixtures.component';
import { cupRoundName, isCupFixture } from './cup';

interface CupStep {
  key: number;
  label: string;
  status: 'done' | 'current' | 'next';
  played: number;
  total: number;
}

@Component({
  selector: 'fm-competition-cup',
  standalone: true,
  imports: [DatePipe, IonButton, IonIcon, IonInput, IonItem, IonList, CompetitionFixturesComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    @if (loading()) {
      <section class="progress fm-card" aria-busy="true" aria-label="Loading cup progress">
        <span class="fm-skeleton" style="width: 46%; height: 16px"></span>
        <span class="fm-skeleton" style="width: 72%; height: 12px; margin-top: 10px"></span>
        <span class="fm-skeleton" style="width: 100%; height: 36px; margin-top: 16px"></span>
      </section>
    } @else if (error()) {
      <div class="fm-empty">
        <ion-icon name="alert-circle-outline" aria-hidden="true" />
        <h3>Cup unavailable</h3>
        <p>{{ error() }}</p>
        <ion-button fill="clear" (click)="load()">Try again</ion-button>
      </div>
    } @else {
      <section class="progress fm-card" aria-label="Cup progress">
        <div class="head">
          <ion-icon name="trophy-outline" aria-hidden="true" />
          <div>
            <strong>{{ headline() }}</strong>
            <small>{{ summary() }}</small>
          </div>
        </div>

        @if (namedCups().length) {
          <ol class="cups">
            @for (cup of namedCups(); track cup.id) {
              <li [class.done]="cup.status === 'done'" [class.now]="cup.status === 'current'">
                <strong>{{ cup.name }}</strong>
                <small>{{ cup.caption }}</small>
              </li>
            }
          </ol>
        }

        @if (canManage()) {
          <div class="editor">
            <p class="hint">Add or rename cups. Names must be unique. Only one cup runs at a time.</p>
            <ion-list lines="none">
              @for (draft of drafts(); track draft.key) {
                <ion-item>
                  <ion-input
                    label="Cup name"
                    labelPlacement="stacked"
                    [value]="draft.name"
                    [disabled]="saving()"
                    (ionInput)="setDraft($index, $any($event).detail.value)"
                  />
                  @if (drafts().length > 1 && !draft.locked) {
                    <ion-button slot="end" fill="clear" [disabled]="saving()" (click)="removeDraft($index)">
                      Remove
                    </ion-button>
                  }
                </ion-item>
              }
            </ion-list>
            <div class="editor-actions">
              <ion-button size="small" fill="clear" [disabled]="saving()" (click)="addDraft()">
                Add a cup
              </ion-button>
              <ion-button size="small" [disabled]="saving() || !cupsDirty()" (click)="saveCups()">
                Save cups
              </ion-button>
            </div>
          </div>
        }

        @if (steps().length) {
          <ol class="steps">
            @for (step of steps(); track step.key) {
              <li [class.done]="step.status === 'done'" [class.now]="step.status === 'current'">
                <i aria-hidden="true"></i>
                <span>{{ step.label }}</span>
                @if (step.total) {
                  <em>{{ step.played }}/{{ step.total }}</em>
                }
              </li>
            }
          </ol>
        }

        <p class="meta">
          {{ played() }} of {{ total() }} {{ total() === 1 ? 'tie' : 'ties' }} played
          @if (stillIn(); as sides) {
            · {{ sides }} {{ sides === 1 ? 'side' : 'sides' }} still in
          }
          @if (nextWhen()) {
            · Next {{ nextWhen() | date: 'EEE d MMM' }}
          }
        </p>

        @if (canAdvance()) {
          <ion-button size="small" [disabled]="advancing()" (click)="advance()">
            Advance to the next round
          </ion-button>
        }
        @if (nextCup(); as upcoming) {
          <ion-button size="small" fill="outline" [disabled]="starting()" (click)="startNext(upcoming)">
            Start {{ upcoming.name }}
          </ion-button>
        }
      </section>

      <h3 class="fm-section-title">Cup fixtures</h3>
      <fm-competition-fixtures [competition]="competition()" track="cup" />
    }
  `,
  styles: [
    `
      .progress {
        margin: 12px 16px 0;
        padding: 14px 16px 16px;
      }

      .head {
        display: flex;
        align-items: flex-start;
        gap: 12px;
      }

      .head ion-icon {
        flex: 0 0 auto;
        margin-top: 2px;
        font-size: 1.4rem;
        color: var(--ion-color-warning-shade, #c08812);
      }

      .head div {
        display: grid;
        gap: 2px;
        min-width: 0;
      }

      .head strong {
        font-size: 1rem;
      }

      .head small {
        color: var(--ion-color-medium);
        font-size: 0.82rem;
        line-height: 1.4;
      }

      .steps {
        display: flex;
        list-style: none;
        margin: 16px 0 0;
        padding: 0;
        overflow-x: auto;
      }

      .steps li {
        position: relative;
        flex: 1 1 0;
        min-width: 76px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 5px;
        text-align: center;
      }

      .steps li i {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: var(--ion-color-step-200, #d7dde5);
      }

      .steps li:not(:last-child)::after {
        content: '';
        position: absolute;
        top: 4px;
        left: calc(50% + 8px);
        right: calc(-50% + 8px);
        height: 2px;
        background: var(--ion-color-step-150, #dbe2ea);
      }

      .steps li.done i,
      .steps li.now i {
        background: var(--ion-color-primary);
      }

      .steps li.done:not(:last-child)::after {
        background: var(--ion-color-primary);
      }

      .steps li.now i {
        box-shadow: 0 0 0 4px color-mix(in srgb, var(--ion-color-primary) 22%, transparent);
      }

      .steps li span {
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        color: var(--ion-color-medium);
      }

      .steps li.now span,
      .steps li.done span {
        color: var(--ion-text-color);
      }

      .steps li em {
        font-style: normal;
        font-size: 0.65rem;
        color: var(--ion-color-medium);
      }

      .meta {
        margin: 12px 0 0;
        color: var(--ion-color-medium);
        font-size: 0.8rem;
        line-height: 1.4;
      }

      .cups {
        display: grid;
        gap: 8px;
        list-style: none;
        margin: 14px 0 0;
        padding: 0;
      }

      .cups li {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        padding: 8px 10px;
        border-radius: 10px;
        background: var(--ion-color-step-50, #f4f5f8);
      }

      .cups li.now {
        background: color-mix(in srgb, var(--ion-color-primary) 12%, transparent);
      }

      .cups li.done strong {
        opacity: 0.75;
      }

      .cups small {
        color: var(--ion-color-medium);
        font-size: 0.75rem;
      }

      .editor {
        margin-top: 14px;
      }

      .editor .hint {
        margin: 0 0 8px;
        color: var(--ion-color-medium);
        font-size: 0.8rem;
        line-height: 1.4;
      }

      .editor ion-list {
        background: transparent;
        padding: 0;
      }

      .editor-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
      }

      ion-button {
        margin: 12px 0 0;
      }
    `,
  ],
})
export class CompetitionCupComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly realtime = inject(RealtimeService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly alerts = inject(AlertController);
  private readonly toasts = inject(ToastController);

  readonly competition = input.required<CompetitionDetail>();
  readonly changed = output<CompetitionDetail>();

  readonly fixtures = signal<Fixture[]>([]);
  readonly loading = signal(true);
  readonly advancing = signal(false);
  readonly starting = signal(false);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly drafts = signal<Array<{ key: string; id?: string; name: string; locked: boolean }>>([]);
  private draftSeq = 0;

  constructor() {
    effect(() => {
      this.competition();
      this.fixtures();
      if (untracked(() => this.saving() || this.cupsDirty())) return;
      this.resetDrafts();
    });
  }

  readonly cupFixtures = computed(() =>
    this.fixtures().filter((fixture) => isCupFixture(fixture, this.competition().stages)),
  );

  readonly namedCups = computed(() => {
    const stages = this.competition().stages.filter((stage) => stage.kind === 'knockout');
    const stored = this.competition().settings_json?.['cups'];
    const fallback = Array.isArray(stored) ? stored.map((item) => String(item)) : [];
    const rows = stages.length
      ? stages.map((stage) => ({
          id: stage.id,
          name: stage.name,
          fixtures: this.fixtures().filter((fixture) => fixture.stage === stage.id),
        }))
      : fallback.map((name, index) => ({ id: `name-${index}`, name, fixtures: [] as Fixture[] }));
    return rows.map((row) => {
      const open = row.fixtures.some((fixture) => ['scheduled', 'live', 'postponed'].includes(fixture.status));
      const finished = row.fixtures.length > 0 && row.fixtures.every(isFinished);
      const status: 'done' | 'current' | 'next' = open || (row.fixtures.length > 0 && !finished)
        ? 'current'
        : finished
          ? 'done'
          : 'next';
      const caption =
        status === 'done' ? 'Finished' : status === 'current' ? 'Running' : 'Waiting — one cup at a time';
      return { ...row, status, caption };
    });
  });

  readonly currentCup = computed(
    () =>
      this.namedCups().find((cup) => cup.status === 'current') ??
      this.namedCups().find((cup) => cup.status === 'next') ??
      this.namedCups().at(-1) ??
      null,
  );

  readonly nextCup = computed(() => {
    const role = this.competition().my_role;
    if (role !== 'owner' && role !== 'admin') return null;
    const cups = this.namedCups();
    const current = cups.find((cup) => cup.status === 'current');
    if (current) return null;
    return cups.find((cup) => cup.status === 'next') ?? null;
  });

  readonly activeCupFixtures = computed(() => this.currentCup()?.fixtures ?? this.cupFixtures());

  readonly steps = computed<CupStep[]>(() => {
    const cup = this.activeCupFixtures();
    const byRound = new Map<number, Fixture[]>();
    for (const fixture of cup) {
      const key = fixture.round_number ?? 1;
      const list = byRound.get(key) ?? [];
      list.push(fixture);
      byRound.set(key, list);
    }
    const generated = [...byRound.keys()].sort((left, right) => left - right);
    const latest = generated.at(-1) ?? 1;
    const firstRound = byRound.get(generated[0] ?? 1) ?? [];
    const starters = uniqueSides(firstRound);
    const expected = Math.max(latest, Math.ceil(Math.log2(Math.max(starters, 2))) || 1);

    const steps: CupStep[] = [];
    let currentAssigned = false;
    for (let round = 1; round <= expected; round += 1) {
      const ties = byRound.get(round) ?? [];
      const played = ties.filter(isFinished).length;
      const done = ties.length > 0 && played === ties.length;
      let status: CupStep['status'] = 'next';
      if (done) status = 'done';
      else if (ties.length && !currentAssigned) {
        status = 'current';
        currentAssigned = true;
      }
      steps.push({
        key: round,
        label: cupRoundName(ties.length, round, expected),
        status,
        played,
        total: ties.length,
      });
    }
    return steps;
  });

  readonly champion = computed(() => {
    const last = this.steps().at(-1);
    if (!last || last.status !== 'done' || last.total !== 1) return null;
    const cup = this.activeCupFixtures();
    if (!cup.length) return null;
    const latest = Math.max(...cup.map((fixture) => fixture.round_number ?? 1));
    const final = cup.find((fixture) => (fixture.round_number ?? 1) === latest);
    return final?.sides.find((side) => side.outcome === 'win')?.participant.name ?? null;
  });

  readonly played = computed(() => this.activeCupFixtures().filter(isFinished).length);

  readonly total = computed(() => this.activeCupFixtures().length);

  readonly stillIn = computed(() => {
    const cup = this.activeCupFixtures();
    if (!cup.length) return 0;
    const latest = Math.max(...cup.map((fixture) => fixture.round_number ?? 1));
    return uniqueSides(
      cup.filter((fixture) => (fixture.round_number ?? 1) === latest),
      (side) => side.outcome !== 'loss',
    );
  });

  readonly nextWhen = computed(() => {
    const upcoming = this.activeCupFixtures()
      .filter((fixture) => ['scheduled', 'live', 'postponed'].includes(fixture.status) && fixture.scheduled_at)
      .sort((left, right) => (left.scheduled_at ?? '').localeCompare(right.scheduled_at ?? ''));
    return upcoming[0]?.scheduled_at ?? null;
  });

  readonly canManage = computed(() => {
    const role = this.competition().my_role;
    return role === 'owner' || role === 'admin';
  });

  readonly canAdvance = computed(() => {
    const role = this.competition().my_role;
    if (role !== 'owner' && role !== 'admin') return false;
    const cup = this.activeCupFixtures();
    if (!cup.length || this.champion()) return false;
    const latest = Math.max(...cup.map((fixture) => fixture.round_number ?? 1));
    const current = cup.filter((fixture) => (fixture.round_number ?? 1) === latest);
    const winners = current.filter((fixture) => fixture.sides.some((side) => side.outcome === 'win'));
    return current.length > 0 && current.every(isFinished) && winners.length >= 2;
  });

  headline(): string {
    const winner = this.champion();
    const cupName = this.currentCup()?.name || 'Cup';
    if (winner) return `${winner} won ${cupName}`;
    const current = this.steps().find((step) => step.status === 'current');
    if (current) return `${cupName} · ${current.label}`;
    if (!this.activeCupFixtures().length) return `${cupName} not scheduled yet`;
    return `Waiting for the next ${cupName} round`;
  }

  summary(): string {
    if (this.champion()) return 'The knockout is complete.';
    const every = Number(this.competition().settings_json?.['cup_every_league_rounds'] ?? 0);
    if (!this.activeCupFixtures().length) {
      return every > 0
        ? `Cup ties land after every ${every} league match days. Generate the schedule from setup.`
        : 'Generate the schedule from setup to start the cup.';
    }
    const current = this.steps().find((step) => step.status === 'current');
    if (current?.total) {
      return `${current.played} of ${current.total} ties played in this round.`;
    }
    return every > 0
      ? `Cup days sit after every ${every} league match days.`
      : 'Winners move on when this round is finished.';
  }

  cupsDirty(): boolean {
    const current = this.namedCups().map((cup) => cup.name.trim().toLowerCase()).filter(Boolean);
    const drafts = this.drafts().map((row) => row.name.trim().toLowerCase()).filter(Boolean);
    if (current.join('|') !== drafts.join('|')) return true;
    const currentIds = this.namedCups()
      .map((cup) => cup.id)
      .filter((id) => !String(id).startsWith('name-'));
    const draftIds = this.drafts().map((row) => row.id).filter((id): id is string => !!id);
    return currentIds.length > 0 && draftIds.length > 0 && currentIds.join('|') !== draftIds.join('|');
  }

  setDraft(index: number, value: string | null | undefined): void {
    const name = value ?? '';
    this.drafts.update((rows) => rows.map((row, current) => (current === index ? { ...row, name } : row)));
  }

  addDraft(): void {
    this.draftSeq += 1;
    this.drafts.update((rows) => [
      ...rows,
      { key: `new-${this.draftSeq}`, name: '', locked: false },
    ]);
  }

  removeDraft(index: number): void {
    this.drafts.update((rows) => rows.filter((_, current) => current !== index));
  }

  saveCups(): void {
    if (!this.canManage() || this.saving() || !this.cupsDirty()) return;
    const payload = this.drafts()
      .map((row) => {
        const name = row.name.trim();
        return row.id ? { id: row.id, name } : { name };
      })
      .filter((row) => row.name);
    if (!payload.length) return;
    this.saving.set(true);
    this.api
      .updateCompetition(this.competition().id, { cups: payload })
      .pipe(switchMap(() => this.api.getCompetition(this.competition().id)))
      .subscribe({
        next: async (competition) => {
          this.saving.set(false);
          this.changed.emit(competition);
          this.resetDraftsFrom(competition);
          this.load(false);
          const toast = await this.toasts.create({
            message: 'Cups updated.',
            color: 'success',
            duration: 2200,
          });
          await toast.present();
        },
        error: async (err: unknown) => {
          this.saving.set(false);
          const toast = await this.toasts.create({
            message: extractErrorMessage(err, 'Could not save those cups.'),
            color: 'danger',
            duration: 2500,
          });
          await toast.present();
        },
      });
  }

  private resetDrafts(): void {
    this.resetDraftsFrom(this.competition());
  }

  private resetDraftsFrom(competition: CompetitionDetail): void {
    const stages = competition.stages.filter((stage) => stage.kind === 'knockout');
    const stored = competition.settings_json?.['cups'];
    const names: Array<{ id?: string; name: string }> = stages.length
      ? stages.map((stage) => ({ id: stage.id, name: stage.name }))
      : Array.isArray(stored)
        ? stored.map((item) => ({ name: String(item) }))
        : [{ name: 'Cup' }];
    const fixtures = this.fixtures();
    this.drafts.set(
      names.map((row, index) => ({
        key: row.id ?? `name-${index}`,
        id: row.id,
        name: row.name,
        locked: !!row.id && fixtures.some((fixture) => fixture.stage === row.id),
      })),
    );
  }

  ngOnInit(): void {
    this.load();
    this.realtime
      .onAny([
        'fixture.created',
        'fixture.updated',
        'fixture.deleted',
        'fixture.live',
        'fixture.completed',
        'fixtures.generated',
        'score.recorded',
        'score.corrected',
        'score.removed',
      ])
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.load(false));
  }

  load(showSpinner = true): void {
    if (showSpinner) this.loading.set(true);
    this.error.set(null);
    this.api.listFixtures(this.competition().id, { page_size: 200 }).subscribe({
      next: (page) => {
        this.fixtures.set(page.results);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err));
        this.loading.set(false);
      },
    });
  }

  async advance(): Promise<void> {
    if (!this.canAdvance() || this.advancing()) return;
    const alert = await this.alerts.create({
      header: 'Advance the cup?',
      message: 'Winners from this round are paired into the next ties.',
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        { text: 'Advance', role: 'confirm' },
      ],
    });
    await alert.present();
    const { role } = await alert.onDidDismiss();
    if (role !== 'confirm') return;

    this.advancing.set(true);
    this.api.advanceKnockout(this.competition().id).subscribe({
      next: async (result) => {
        this.advancing.set(false);
        this.load(false);
        const toast = await this.toasts.create({
          message: result.advanced
            ? `Cup round ${result.round_number} is scheduled.`
            : result.detail || 'The bracket is complete.',
          color: 'success',
          duration: 2400,
        });
        await toast.present();
      },
      error: async (err: unknown) => {
        this.advancing.set(false);
        const toast = await this.toasts.create({
          message: extractErrorMessage(err, 'Could not advance the cup.'),
          color: 'danger',
          duration: 2500,
        });
        await toast.present();
      },
    });
  }

  async startNext(cup: { id: string; name: string }): Promise<void> {
    if (this.starting()) return;
    const alert = await this.alerts.create({
      header: `Start ${cup.name}?`,
      message: 'Only one cup can run at a time. This opens the next named cup.',
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        { text: 'Start', role: 'confirm' },
      ],
    });
    await alert.present();
    const { role } = await alert.onDidDismiss();
    if (role !== 'confirm') return;
    this.starting.set(true);
    this.api.startCup(this.competition().id, { stage: cup.id, name: cup.name }).subscribe({
      next: async () => {
        this.starting.set(false);
        this.load(false);
        const toast = await this.toasts.create({
          message: `${cup.name} is on the board.`,
          color: 'success',
          duration: 2400,
        });
        await toast.present();
      },
      error: async (err: unknown) => {
        this.starting.set(false);
        const toast = await this.toasts.create({
          message: extractErrorMessage(err, 'Could not start that cup.'),
          color: 'danger',
          duration: 2500,
        });
        await toast.present();
      },
    });
  }
}

function isFinished(fixture: Fixture): boolean {
  return fixture.status === 'completed' || fixture.status === 'forfeit';
}

function uniqueSides(
  fixtures: Fixture[],
  keep: (side: Fixture['sides'][number]) => boolean = () => true,
): number {
  const ids = new Set<string>();
  for (const fixture of fixtures) {
    for (const side of fixture.sides) {
      if (keep(side)) ids.add(side.participant.id);
    }
  }
  return ids.size;
}
