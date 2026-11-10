import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import {
  IonBackButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonSpinner,
  IonTitle,
  AlertController,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';
import type { Observable } from 'rxjs';

import { extractErrorMessage } from '../../core/error-message';
import type { Athlete, GamesEventDetail, Noc, RecordScope } from '../../core/games.service';
import { GamesService } from '../../core/games.service';
import { GamesFollowComponent } from './games-follow.component';

const MEDAL_TYPE: Record<string, string> = {
  standard: 'Gold, silver and bronze from the final result',
  bronze_match: 'Bronze decided by a bronze-medal match',
  two_bronze: 'Two bronzes: both losing semi-finalists',
};

@Component({
  selector: 'fm-games-event',
  standalone: true,
  imports: [DatePipe, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonIcon, IonSpinner, GamesFollowComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './games.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button [defaultHref]="backHref()" /></ion-buttons>
        <ion-title>{{ event()?.name ?? 'Event' }}</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (event(); as e) {
        <section class="hero fm-enter">
          <p class="kicker">{{ e.sport }}{{ e.discipline && e.discipline !== e.sport ? ' · ' + e.discipline : '' }}</p>
          <h2>{{ e.name }}</h2>
          <p>{{ e.preset_label }} rules · {{ medalTypeLabel(e.medal_type) }}</p>
          @if (e.governing_body) {
            <p class="governance">
              @if (e.locked) {
                <span class="locked"><ion-icon name="lock-closed-outline" aria-hidden="true" /> Locked rules</span>
              }
              {{ e.governing_body }} · {{ e.rulebook }}
            </p>
          }
          <p>
            {{ e.venue || 'Venue to be confirmed' }}
            @if (e.scheduled_at) {
              · {{ e.scheduled_at | date: 'EEE d MMM, HH:mm' }}
            }
          </p>
        </section>

        <section class="fm-card section">
          <h3>Medals</h3>
          @for (medal of e.medals; track $index) {
            <p class="medal-line">
              <span [class]="'dot ' + medal.medal">{{ medal.medal.charAt(0).toUpperCase() }}</span>
              <span class="code">{{ medal.noc }}</span>
              {{ medal.entrant }}
            </p>
          } @empty {
            <p class="hint">
              Medals are awarded automatically when a technical delegate confirms the final result.
            </p>
          }
        </section>

        <div class="actions">
          <button type="button" class="btn" (click)="openCompetition(e)">
            <ion-icon name="create-outline" aria-hidden="true" />
            Results and fixtures
          </button>
          @if (e.can_manage && e.medal_type === 'bronze_match' && !e.bronze_fixture) {
            <button type="button" class="btn ghost" [disabled]="busy()" (click)="bronze(e)">Create bronze-medal match</button>
          }
          <fm-games-follow [gamesId]="gamesId()" target="sport" [ref]="e.sport_key" [label]="e.sport" />
          @if (e.can_manage && !e.medals.length) {
            <button type="button" class="btn ghost small" [disabled]="busy()" (click)="remove(e)">
              <ion-icon name="trash-outline" aria-hidden="true" />
              Remove event
            </button>
          }
          <button type="button" class="btn ghost small" (click)="goGames('reports/results-book?sport=' + e.sport_key)">
            <ion-icon name="document-text-outline" aria-hidden="true" />
            Results book
          </button>
        </div>

        @if (e.qualification_rule || e.qualification_mark || e.can_manage) {
          <section class="fm-card section">
            <h3>Qualification</h3>
            @if (e.can_manage) {
              <div class="row">
                <label class="field">How entrants go through<input [value]="qualRule()" (input)="qualRule.set($any($event.target).value)" placeholder="e.g. First 3 in each heat (Q) and the next 2 fastest (q)" /></label>
                <label class="field">Qualifying standard<input [value]="qualMark()" (input)="qualMark.set($any($event.target).value)" placeholder="e.g. 10.05" /></label>
              </div>
              <button type="button" class="btn small" [disabled]="busy()" (click)="saveQualification(e)">Save qualification</button>
            } @else {
              <p>{{ e.qualification_rule }}</p>
              @if (e.qualification_mark) {
                <p class="hint flush">Qualifying standard: <strong>{{ e.qualification_mark }}</strong></p>
              }
            }
          </section>
        }

        <section class="fm-card section">
          <h3>Entries ({{ e.entries.length }})</h3>
          <ul class="list">
            @for (entry of e.entries; track entry.id) {
              <li class="entry">
                <span class="code">{{ entry.noc }}</span>
                @if (entry.athlete_id) {
                  <a class="link" (click)="goGames('athletes/' + entry.athlete_id)">{{ entry.name }}</a>
                } @else {
                  {{ entry.name }}
                }
              </li>
            } @empty {
              <li class="hint">No entries yet.</li>
            }
          </ul>
          @if (e.can_manage) {
            <form class="add-entry" (submit)="addEntry($event, e)">
              <label class="field">
                NOC
                <select (change)="nocId.set($any($event.target).value)">
                  <option value="">Choose</option>
                  @for (noc of nocs(); track noc.id) {
                    <option [value]="noc.id" [selected]="nocId() === noc.id">{{ noc.code }} · {{ noc.name }}</option>
                  }
                </select>
              </label>
              @if (e.kind === 'individual') {
                <label class="field">
                  Athlete
                  <select (change)="athleteId.set($any($event.target).value)">
                    <option value="">Choose</option>
                    @for (athlete of athletesFor(nocId()); track athlete.id) {
                      <option [value]="athlete.id" [selected]="athleteId() === athlete.id">{{ athlete.name }}</option>
                    }
                  </select>
                </label>
              }
              <button type="submit" class="btn small" [disabled]="busy() || !nocId() || (e.kind === 'individual' && !athleteId())">
                Enter
              </button>
            </form>
          }
        </section>

        <section class="fm-card section">
          <h3>Rounds</h3>
          @if (e.rounds.length > 1 && !e.final_fixture) {
            <p class="hint flush">Medals come from the round named "Final" once officials confirm it. Heats and semi-finals never award medals.</p>
          }
          @for (round of e.rounds; track round.fixture_id) {
            <details class="round" [open]="$last">
              <summary>
                <strong>{{ round.label }}</strong>
                <small>{{ round.scheduled_at ? (round.scheduled_at | date: 'EEE d MMM, HH:mm') + ' · ' : '' }}{{ round.start_list.length }} entrant(s)</small>
                <span class="badge" [class.ok]="round.final || round.status === 'completed'">{{ round.final ? 'Final result' : round.status }}</span>
              </summary>
              @if (round.status === 'scheduled' && !hasResults(round.results)) {
                <p class="sub">Start list</p>
                <ol class="start-list">
                  @for (row of round.start_list; track row.position) {
                    <li><span class="code">{{ row.noc }}</span>{{ row.name }}</li>
                  }
                </ol>
              } @else {
                <table class="results">
                  <thead><tr><th>#</th><th class="left">Entrant</th><th>Mark</th><th></th></tr></thead>
                  <tbody>
                    @for (row of round.results; track row.participant_id) {
                      <tr>
                        <td>{{ row.status || (row.rank ?? '–') }}</td>
                        <td class="left">
                          <span class="code">{{ row.noc }}</span>
                          @if (row.athlete_id) {
                            <a (click)="goGames('athletes/' + row.athlete_id)">{{ row.name }}</a>
                          } @else {
                            {{ row.name }}
                          }
                        </td>
                        <td class="mark">{{ row.mark }}</td>
                        <td>@if (row.qualified) {<span class="badge ok">{{ row.qualified }}</span>}</td>
                      </tr>
                    }
                  </tbody>
                </table>
              }
              <div class="round-actions">
                <button type="button" class="btn ghost small" (click)="openFixture(e, round.fixture_id)">Open {{ e.result_type ? 'result sheet' : 'match' }}</button>
                @if (e.final_fixture === round.fixture_id) {
                  <span class="badge ok">Medal round</span>
                } @else if (e.can_manage && e.rounds.length > 1) {
                  <button type="button" class="btn ghost small" [disabled]="busy()" (click)="useForMedals(e, round.fixture_id)">Use for medals</button>
                }
              </div>
            </details>
          } @empty {
            <p class="hint">No rounds yet. Open "Results and fixtures" to schedule them.</p>
          }
        </section>

        <section class="fm-card section">
          <h3>Records</h3>
          <ul class="list">
            @for (record of e.records; track record.id) {
              <li class="record-line">
                <span class="badge warn">{{ record.scope_label }}</span>
                <span class="grow"><strong>{{ record.mark }}</strong> · {{ record.holder }}{{ record.noc ? ' (' + record.noc + ')' : '' }}{{ record.previous_mark ? ' · previous ' + record.previous_mark : '' }}</span>
                @if (e.can_add_records) {
                  <button type="button" class="btn ghost small" (click)="removeRecord(record.id)" aria-label="Remove this record">✕</button>
                }
              </li>
            } @empty {
              <li class="hint">No records set in this event.</li>
            }
          </ul>
          @if (e.can_add_records) {
            <form class="record-form" (submit)="addRecord($event, e)">
              <label class="field">
                Record
                <select (change)="recordScope.set($any($event.target).value)">
                  <option value="games" [selected]="recordScope() === 'games'">Games record</option>
                  <option value="national" [selected]="recordScope() === 'national'">National record</option>
                  <option value="world" [selected]="recordScope() === 'world'">World record</option>
                </select>
              </label>
              <label class="field">Mark<input [value]="recordMark()" (input)="recordMark.set($any($event.target).value)" placeholder="e.g. 9.79" /></label>
              <label class="field">Previous<input [value]="recordPrevious()" (input)="recordPrevious.set($any($event.target).value)" placeholder="optional" /></label>
              <label class="field">
                Set by
                <select (change)="recordAthlete.set($any($event.target).value)">
                  <option value="">Choose</option>
                  @for (entry of e.entries; track entry.id) {
                    @if (entry.athlete_id) {
                      <option [value]="entry.athlete_id" [selected]="recordAthlete() === entry.athlete_id">{{ entry.name }}</option>
                    }
                  }
                </select>
              </label>
              <button type="submit" class="btn small" [disabled]="busy() || !recordMark().trim() || !recordAthlete()">Add record</button>
            </form>
          }
        </section>

        @if (e.medal_log.length) {
          <section class="fm-card section">
            <h3>Medal decisions</h3>
            <ul class="list">
              @for (row of e.medal_log; track $index) {
                <li class="log">
                  <strong>{{ row.reason }}</strong>
                  <small>{{ row.created_at | date: 'd MMM y, HH:mm' }}</small>
                </li>
              }
            </ul>
          </section>
        }
      }
      <div style="height: 32px"></div>
    </ion-content>
  `,
  styles: [
    `
      .governance {
        margin-top: 6px !important;
        font-size: 0.8rem !important;
      }
      .locked {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        margin-right: 6px;
        padding: 1px 8px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.22);
        font-weight: 700;
      }
      .medal-line {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 0 0 8px;
      }

      .entry .link {
        color: var(--ion-color-primary);
        cursor: pointer;
      }

      .entry {
        padding: 6px 0;
        border-bottom: 1px solid var(--ion-color-step-50, #f1f2f4);
      }

      .add-entry {
        display: grid;
        grid-template-columns: 1fr 1fr auto;
        align-items: end;
        gap: 8px;
        margin-top: 12px;
      }

      .round {
        border-top: 1px solid var(--ion-color-step-50, #f1f2f4);
        padding: 8px 0;
      }
      .round summary {
        display: flex;
        align-items: center;
        gap: 8px;
        cursor: pointer;
      }
      .round summary small {
        flex: 1;
        color: var(--ion-color-medium);
      }
      .round-actions {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .results {
        width: 100%;
        margin: 8px 0;
        border-collapse: collapse;
        font-size: 0.88rem;
      }
      .results th,
      .results td {
        padding: 6px 4px;
        border-bottom: 1px solid var(--ion-color-step-50, #f1f2f4);
        text-align: center;
      }
      .results .left {
        text-align: left;
      }
      .results .mark {
        font-variant-numeric: tabular-nums;
        font-weight: 700;
      }
      .results a {
        color: var(--ion-color-primary);
        cursor: pointer;
      }
      .start-list {
        margin: 4px 0 8px;
        padding-left: 22px;
      }
      .start-list li {
        padding: 3px 0;
      }
      .sub {
        margin: 8px 0 4px;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--ion-color-medium);
      }
      .record-line {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.88rem;
      }
      .record-line .grow {
        flex: 1;
      }
      .record-form {
        display: grid;
        grid-template-columns: 1.2fr 1fr 1fr 1.4fr auto;
        gap: 8px;
        align-items: end;
        margin-top: 12px;
      }
      .hint.flush {
        margin: 4px 0 0;
      }
      .log small {
        display: block;
        color: var(--ion-color-medium);
      }
    `,
  ],
})
export class GamesEventPage {
  private readonly service = inject(GamesService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastController);
  private readonly alerts = inject(AlertController);

  readonly event = signal<GamesEventDetail | null>(null);
  readonly nocs = signal<Noc[]>([]);
  readonly athletes = signal<Athlete[]>([]);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly nocId = signal('');
  readonly athleteId = signal('');
  readonly qualRule = signal('');
  readonly qualMark = signal('');
  readonly recordScope = signal<RecordScope>('games');
  readonly recordMark = signal('');
  readonly recordPrevious = signal('');
  readonly recordAthlete = signal('');

  readonly gamesId = computed(() => this.route.snapshot.paramMap.get('id') ?? '');
  private readonly eventId = computed(() => this.route.snapshot.paramMap.get('eventId') ?? '');
  readonly backHref = computed(() => `/tabs/games/${this.gamesId()}`);

  ionViewWillEnter(): void {
    this.load();
    this.service.nocs(this.gamesId()).subscribe({ next: (rows) => this.nocs.set(rows) });
    this.service.athletes(this.gamesId()).subscribe({ next: (rows) => this.athletes.set(rows) });
  }

  private load(): void {
    this.service.event(this.gamesId(), this.eventId()).subscribe({
      next: (event) => {
        this.event.set(event);
        this.qualRule.set(event.qualification_rule);
        this.qualMark.set(event.qualification_mark);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  medalTypeLabel(type: string): string {
    return MEDAL_TYPE[type] ?? type;
  }

  athletesFor(nocId: string): Athlete[] {
    return this.athletes().filter((athlete) => athlete.noc_id === nocId);
  }

  sidesLine(sides: Array<{ name: string; score: string; outcome: string }>): string {
    if (sides.length > 2) return `${sides.length} entrants`;
    return sides
      .map((side) => {
        const score = Number(side.score);
        return `${side.name} ${Number.isFinite(score) ? score : side.score}`;
      })
      .join(' – ');
  }

  openCompetition(event: GamesEventDetail): void {
    void this.router.navigateByUrl(`/tabs/competitions/${event.competition_id}`);
  }

  openFixture(event: GamesEventDetail, fixtureId: string): void {
    const kind = event.result_type ? 'events' : 'fixtures';
    void this.router.navigateByUrl(`/tabs/competitions/${event.competition_id}/${kind}/${fixtureId}`);
  }

  addEntry(form: Event, event: GamesEventDetail): void {
    form.preventDefault();
    this.run(
      this.service.addEntry(this.gamesId(), event.id, {
        noc: this.nocId(),
        ...(event.kind === 'individual' ? { athlete: this.athleteId() } : {}),
      }),
      'Entered.',
    );
  }

  hasResults(rows: Array<{ rank: number | null; mark: string; status: string }>): boolean {
    return rows.some((row) => row.rank !== null || row.status || (row.mark && Number(row.mark) !== 0));
  }

  goGames(path: string): void {
    void this.router.navigateByUrl(`/tabs/games/${this.gamesId()}/${path}`);
  }

  async remove(event: GamesEventDetail): Promise<void> {
    const alert = await this.alerts.create({
      header: `Remove ${event.name}?`,
      message: 'The event, its entries and its results are deleted. You can add it again from Add sports.',
      buttons: [
        { text: 'Keep it', role: 'cancel' },
        {
          text: 'Remove',
          role: 'destructive',
          handler: () => {
            this.service.removeEvent(this.gamesId(), event.id).subscribe({
              next: async () => {
                await this.toast(`${event.name} removed.`, 'success');
                void this.router.navigateByUrl(`/tabs/games/${this.gamesId()}`);
              },
              error: async (err: unknown) => this.toast(extractErrorMessage(err, 'Could not remove the event.'), 'danger'),
            });
          },
        },
      ],
    });
    await alert.present();
  }

  useForMedals(event: GamesEventDetail, fixtureId: string): void {
    this.run(this.service.updateEvent(this.gamesId(), event.id, { final_fixture: fixtureId }), 'Medals now come from this round.');
  }

  saveQualification(event: GamesEventDetail): void {
    this.run(
      this.service.updateEvent(this.gamesId(), event.id, {
        qualification_rule: this.qualRule().trim(),
        qualification_mark: this.qualMark().trim(),
      }),
      'Qualification saved.',
    );
  }

  addRecord(form: Event, event: GamesEventDetail): void {
    form.preventDefault();
    this.run(
      this.service.addRecord(this.gamesId(), event.id, {
        scope: this.recordScope(),
        mark: this.recordMark().trim(),
        previous_mark: this.recordPrevious().trim(),
        athlete: this.recordAthlete(),
      }),
      'Record added.',
    );
    this.recordMark.set('');
    this.recordPrevious.set('');
  }

  removeRecord(recordId: string): void {
    this.run(this.service.removeRecord(this.gamesId(), recordId), 'Record removed.');
  }

  bronze(event: GamesEventDetail): void {
    this.run(this.service.bronzeMatch(this.gamesId(), event.id), 'Bronze-medal match created.');
  }

  private run(request: Observable<unknown>, success: string): void {
    this.busy.set(true);
    request.subscribe({
      next: async () => {
        this.busy.set(false);
        this.athleteId.set('');
        this.load();
        await this.toast(success, 'success');
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'That did not save.'), 'danger');
      },
    });
  }

  private async toast(message: string, color: 'success' | 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2400, position: 'top' });
    await toast.present();
  }
}
