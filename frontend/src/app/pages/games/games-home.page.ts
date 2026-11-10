import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import {
  IonBackButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonRefresher,
  IonRefresherContent,
  IonSpinner,
  IonTitle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';

import { extractErrorMessage } from '../../core/error-message';
import type {
  Athlete,
  Games,
  GamesEventRow,
  GamesOverview,
  MedalTableRow,
  MedalsResponse,
  Noc,
  PointsRow,
} from '../../core/games.service';
import { GamesService } from '../../core/games.service';
import { RealtimeService, gamesRoom } from '../../core/realtime.service';

type Tab = 'today' | 'medals' | 'points' | 'events' | 'nocs' | 'schedule' | 'reports';

@Component({
  selector: 'fm-games-home',
  standalone: true,
  imports: [
    DatePipe,
    NgTemplateOutlet,
    IonHeader,
    IonToolbar,
    IonTitle,
    IonButtons,
    IonBackButton,
    IonContent,
    IonIcon,
    IonSpinner,
    IonRefresher,
    IonRefresherContent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './games.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button defaultHref="/tabs/games" /></ion-buttons>
        <ion-title>{{ games()?.name ?? 'Games' }}</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      <ion-refresher slot="fixed" (ionRefresh)="refresh($event)"><ion-refresher-content /></ion-refresher>

      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (games(); as g) {
        <section class="hero fm-enter">
          <span class="rings" aria-hidden="true">◯◯◯</span>
          <p class="kicker">{{ g.kind === 'custom' ? 'Local games' : g.kind + ' Games' }}{{ g.edition ? ' · ' + g.edition : '' }}</p>
          <h2>{{ g.name }}</h2>
          <p>
            {{ g.host }}
            @if (g.starts_on) {
              · {{ g.starts_on | date: 'd MMM' }}–{{ g.ends_on | date: 'd MMM y' }}
            }
          </p>
          <p>{{ g.event_count }} events · {{ g.noc_count }} {{ teamWord() }}s · medal table: {{ g.medal_table_ranking === 'gold_first' ? 'golds first' : 'total medals first' }}</p>
        </section>

        @if (g.can_manage) {
          <div class="actions">
            <button type="button" class="btn" (click)="go('sports')">
              <ion-icon name="add-outline" aria-hidden="true" />
              Add sports
            </button>
          </div>
        }

        <div class="segmented" role="tablist">
          @for (option of tabs(); track option.key) {
            <button type="button" role="tab" [class.on]="tab() === option.key" (click)="tab.set(option.key)">{{ option.label }}</button>
          }
        </div>

        @switch (tab()) {
          @case ('today') {
            @if (overview(); as o) {
              <section class="fm-card section countdown" [class.live]="o.countdown.state === 'live'">
                @switch (o.countdown.state) {
                  @case ('upcoming') {
                    <p class="big">{{ o.countdown.days_to_go }}</p>
                    <p>{{ o.countdown.days_to_go === 1 ? 'day' : 'days' }} to go · starts {{ g.starts_on | date: 'EEEE d MMMM' }}</p>
                  }
                  @case ('live') {
                    <p class="big">Day {{ o.countdown.day }}</p>
                    <p>The Games are on{{ g.ends_on ? ' until ' + (g.ends_on | date: 'd MMMM') : '' }}</p>
                  }
                  @case ('finished') {
                    <p class="big">Finished</p>
                    <p>Final medal table below; download it from Reports.</p>
                  }
                  @default {
                    <p class="big">Dates to be set</p>
                    <p>The organiser has not set the Games dates yet.</p>
                  }
                }
              </section>

              <section class="fm-card section">
                <h3><ion-icon name="radio-outline" aria-hidden="true" /> Live now</h3>
                <ul class="list">
                  @for (row of o.live; track row.fixture_id) {
                    <li>
                      <button type="button" class="row-btn" (click)="go('events/' + row.id)">
                        <span class="live-dot" aria-hidden="true"></span>
                        <span class="grow"><strong>{{ row.sport }}: {{ row.name }}</strong><small>{{ row.session || 'Under way' }}{{ row.venue ? ' · ' + row.venue : '' }}</small></span>
                      </button>
                    </li>
                  } @empty {
                    <li class="hint">Nothing is live right now.</li>
                  }
                </ul>
              </section>

              <section class="fm-card section">
                <h3><ion-icon name="time-outline" aria-hidden="true" /> Today</h3>
                <ul class="list">
                  @for (row of o.today; track $index) {
                    <li>
                      <button type="button" class="row-btn" (click)="go('events/' + row.id)">
                        <strong class="when">{{ row.at | date: 'HH:mm' }}</strong>
                        <span class="grow"><strong>{{ row.sport }}: {{ row.name }}</strong><small>{{ row.session ? row.session + ' · ' : '' }}{{ row.venue || 'Venue to be confirmed' }}</small></span>
                        @if (row.fixture_status === 'completed') {
                          <span class="badge ok">Done</span>
                        }
                      </button>
                    </li>
                  } @empty {
                    <li class="hint">Nothing scheduled today.</li>
                  }
                </ul>
              </section>

              <section class="fm-card section">
                <h3>Medal table</h3>
                <ng-container *ngTemplateOutlet="medalTable; context: { rows: table().slice(0, 10) }" />
                @if (table().length > 10) {
                  <button type="button" class="btn ghost small" (click)="tab.set('medals')">Full table</button>
                }
              </section>

              @if (points().length) {
                <section class="fm-card section">
                  <h3>Points table</h3>
                  <ng-container *ngTemplateOutlet="pointsTable; context: { rows: points().slice(0, 10) }" />
                </section>
              }

              <section class="fm-card section">
                <h3>Latest medals</h3>
                <ng-container *ngTemplateOutlet="feed; context: { rows: o.latest_medals }" />
              </section>
            }
          }
          @case ('points') {
            <section class="fm-card section">
              <h3>Points table</h3>
              <p class="hint">Points per place: {{ g.placing_points.join(', ') }}. Equal places earn the same points.</p>
              <ng-container *ngTemplateOutlet="pointsTable; context: { rows: points() }" />
            </section>
          }
          @case ('reports') {
            <section class="fm-card section">
              <h3>Reports</h3>
              <p class="hint">Open a report to print it or save it as a PDF, or download it as CSV.</p>
              <ul class="list">
                <li>
                  <button type="button" class="row-btn" (click)="go('reports/medal-table')">
                    <ion-icon name="podium-outline" aria-hidden="true" />
                    <span class="grow"><strong>Final medal table</strong><small>{{ points().length ? 'With the points table' : 'Every NOC, ranked' }}</small></span>
                  </button>
                </li>
                <li>
                  <button type="button" class="row-btn" (click)="go('reports/daily?date=' + reportDay())">
                    <ion-icon name="calendar-outline" aria-hidden="true" />
                    <span class="grow"><strong>Daily results</strong><small>Medals, results and records for one day</small></span>
                  </button>
                  <label class="field inline">Day<input type="date" [value]="reportDay()" (input)="reportDay.set($any($event.target).value)" /></label>
                </li>
                <li>
                  <button type="button" class="row-btn" (click)="go('reports/results-book' + (reportSport() ? '?sport=' + reportSport() : ''))">
                    <ion-icon name="document-text-outline" aria-hidden="true" />
                    <span class="grow"><strong>Results book</strong><small>Every round, {{ reportSport() ? 'one sport' : 'every sport' }}</small></span>
                  </button>
                  <label class="field inline">
                    Sport
                    <select (change)="reportSport.set($any($event.target).value)">
                      <option value="">Every sport</option>
                      @for (group of eventGroups(); track group.sport) {
                        <option [value]="group.events[0].sport_key">{{ group.sport }}</option>
                      }
                    </select>
                  </label>
                </li>
              </ul>
              <p class="hint">For an NOC summary, open the {{ teamWord() }} and choose "Summary report".</p>
            </section>
          }
          @case ('medals') {
            <section class="fm-card section">
              <h3>Medal table</h3>
              <ng-container *ngTemplateOutlet="medalTable; context: { rows: table() }" />
            </section>

            <section class="fm-card section">
              <h3>Medals by sport</h3>
              @for (sport of medals()?.by_sport ?? []; track sport.sport) {
                <p class="sport-line">
                  <strong>{{ sport.sport }}</strong>
                  @for (row of sport.nocs; track row.code) {
                    <span class="code">{{ row.code }}</span>{{ row.gold }}·{{ row.silver }}·{{ row.bronze }}
                  }
                </p>
              } @empty {
                <p class="hint">No medals yet.</p>
              }
            </section>

            <section class="fm-card section">
              <h3>Latest medals</h3>
              <ng-container *ngTemplateOutlet="feed; context: { rows: medals()?.feed ?? [] }" />
            </section>
          }
          @case ('events') {
            @for (group of eventGroups(); track group.sport) {
              <p class="sport-title">{{ group.sport }} · {{ group.events.length }}</p>
              <ul class="list section">
                @for (event of group.events; track event.id) {
                  <li>
                    <button type="button" class="row-btn fm-card" (click)="go('events/' + event.id)">
                      <span class="grow">
                        <strong>{{ event.name }}</strong>
                        <small>{{ event.discipline !== event.sport ? event.discipline + ' · ' : '' }}{{ event.venue || 'Venue to be confirmed' }}{{ event.scheduled_at ? ' · ' + (event.scheduled_at | date: 'EEE d MMM, HH:mm') : '' }}</small>
                      </span>
                      <span class="badge" [class.ok]="event.status === 'medals_awarded'">{{ statusLabel(event.status) }}</span>
                    </button>
                  </li>
                }
              </ul>
            } @empty {
              <p class="hint">No events yet.{{ g.can_manage ? ' Use Add sports to choose them.' : '' }}</p>
            }
          }
          @case ('nocs') {
            <ul class="list section">
              @for (noc of nocs(); track noc.id) {
                <li>
                  <button type="button" class="row-btn fm-card" (click)="go('nocs/' + noc.id)">
                    <span class="code" [style.background]="noc.colour || null">{{ noc.code }}</span>
                    <span class="grow">
                      <strong>{{ noc.name }}</strong>
                      <small>{{ athleteCount(noc.id) }} athlete(s)</small>
                    </span>
                    <ion-icon name="chevron-forward-outline" aria-hidden="true" />
                  </button>
                </li>
              } @empty {
                <li class="hint">No {{ teamWord().toLowerCase() }}s yet.</li>
              }
            </ul>
            @if (g.can_manage) {
              <form class="fm-card section" (submit)="addNoc($event)">
                <h3>Add a {{ teamWord().toLowerCase() === "noc" ? "NOC" : teamWord().toLowerCase() }}</h3>
                <p class="hint">A country, or a house, school or province for local games.</p>
                <div class="row">
                  <label class="field">Name<input [value]="nocName()" (input)="nocName.set($any($event.target).value)" /></label>
                  <label class="field">Code (3 letters)<input maxlength="3" [value]="nocCode()" (input)="nocCode.set($any($event.target).value)" /></label>
                </div>
                <label class="field">Colour<input type="color" [value]="nocColour()" (input)="nocColour.set($any($event.target).value)" /></label>
                <button type="submit" class="btn" [disabled]="busy() || !nocName().trim() || nocCode().trim().length !== 3">Add NOC</button>
              </form>
              <form class="fm-card section" (submit)="addAthlete($event)">
                <h3>Add an athlete</h3>
                <div class="row">
                  <label class="field">Name<input [value]="athleteName()" (input)="athleteName.set($any($event.target).value)" /></label>
                  <label class="field">
                    NOC
                    <select (change)="athleteNoc.set($any($event.target).value)">
                      <option value="">Choose</option>
                      @for (noc of nocs(); track noc.id) {
                        <option [value]="noc.id" [selected]="athleteNoc() === noc.id">{{ noc.code }} · {{ noc.name }}</option>
                      }
                    </select>
                  </label>
                </div>
                <button type="submit" class="btn" [disabled]="busy() || !athleteName().trim() || !athleteNoc()">Add athlete</button>
              </form>
            }
          }
          @case ('schedule') {
            @for (day of schedule(); track day.day) {
              <p class="sport-title">{{ day.day === 'unscheduled' ? 'Not scheduled yet' : (day.day | date: 'EEEE d MMMM') }}</p>
              <ul class="list section">
                @for (event of day.events; track event.id) {
                  <li>
                    <button type="button" class="row-btn fm-card" (click)="go('events/' + event.id)">
                      <span class="grow">
                        <strong>{{ event.scheduled_at ? (event.scheduled_at | date: 'HH:mm') + ' · ' : '' }}{{ event.sport }}: {{ event.name }}</strong>
                        <small>{{ event.venue || 'Venue to be confirmed' }}</small>
                      </span>
                      <span class="badge" [class.ok]="event.status === 'medals_awarded'">{{ statusLabel(event.status) }}</span>
                    </button>
                  </li>
                }
              </ul>
            } @empty {
              <p class="hint">Nothing scheduled yet.</p>
            }
          }
        }
      }
      <div style="height: 32px"></div>

      <ng-template #medalTable let-rows="rows">
        <table class="medal-table">
          <thead>
            <tr>
              <th>#</th>
              <th class="noc">{{ teamWord() }}</th>
              <th><span class="dot gold" title="Gold">G</span></th>
              <th><span class="dot silver" title="Silver">S</span></th>
              <th><span class="dot bronze" title="Bronze">B</span></th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            @for (row of asMedalRows(rows); track row.noc_id) {
              <tr (click)="go('nocs/' + row.noc_id)" [class.bump]="bumped().has(row.noc_id)">
                <td>{{ row.rank }}</td>
                <td class="noc"><span class="code" [style.background]="row.colour || null">{{ row.code }}</span>{{ row.name }}</td>
                <td>{{ row.gold }}</td>
                <td>{{ row.silver }}</td>
                <td>{{ row.bronze }}</td>
                <td class="total">{{ row.total }}</td>
              </tr>
            } @empty {
              <tr><td colspan="6" class="hint">Add {{ teamWord().toLowerCase() }}s to start the table.</td></tr>
            }
          </tbody>
        </table>
      </ng-template>

      <ng-template #pointsTable let-rows="rows">
        <table class="medal-table">
          <thead>
            <tr>
              <th>#</th>
              <th class="noc">{{ teamWord() }}</th>
              <th>Points</th>
              <th><span class="dot gold" title="Gold">G</span></th>
              <th><span class="dot silver" title="Silver">S</span></th>
              <th><span class="dot bronze" title="Bronze">B</span></th>
            </tr>
          </thead>
          <tbody>
            @for (row of asPointsRows(rows); track row.noc_id) {
              <tr (click)="go('nocs/' + row.noc_id)" [class.bump]="bumped().has(row.noc_id)">
                <td>{{ row.rank }}</td>
                <td class="noc"><span class="code" [style.background]="row.colour || null">{{ row.code }}</span>{{ row.name }}</td>
                <td class="total">{{ row.points }}</td>
                <td>{{ row.gold }}</td>
                <td>{{ row.silver }}</td>
                <td>{{ row.bronze }}</td>
              </tr>
            }
          </tbody>
        </table>
      </ng-template>

      <ng-template #feed let-rows="rows">
        <ul class="list">
          @for (item of asFeed(rows); track $index) {
            <li>
              <button type="button" class="row-btn" (click)="go('events/' + item.event_id)">
                <span [class]="'dot ' + item.medal">{{ item.medal.charAt(0).toUpperCase() }}</span>
                <span class="grow">
                  <strong>{{ item.entrant }}</strong>
                  <small>{{ item.event }}</small>
                </span>
              </button>
            </li>
          } @empty {
            <li class="hint">Medals appear here as officials confirm finals.</li>
          }
        </ul>
      </ng-template>
    </ion-content>
  `,
  styles: [
    `
      .countdown {
        text-align: center;
        background: linear-gradient(135deg, color-mix(in srgb, var(--ion-color-primary) 10%, transparent), transparent);
      }
      .countdown .big {
        margin: 0;
        font-size: 2.4rem;
        font-weight: 850;
        color: var(--ion-color-primary);
      }
      .countdown p {
        margin: 2px 0;
        color: var(--ion-color-medium);
      }
      .section h3 ion-icon {
        vertical-align: -2px;
        margin-right: 4px;
      }
      .live-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: var(--ion-color-danger);
        animation: fm-pulse 1.4s ease-in-out infinite;
        flex: 0 0 auto;
      }
      .when {
        min-width: 46px;
        font-variant-numeric: tabular-nums;
      }
      .sport-line {
        margin: 0 0 8px;
        font-size: 0.86rem;
      }
      .sport-line strong {
        display: block;
        margin-bottom: 2px;
      }
      .sport-line .code {
        margin-left: 6px;
      }
      .field.inline {
        margin: 4px 12px 8px;
      }
      tr.bump td {
        animation: fm-row-bump 1.2s ease;
      }
      @keyframes fm-pulse {
        50% {
          opacity: 0.35;
        }
      }
      @keyframes fm-row-bump {
        from {
          background: color-mix(in srgb, var(--ion-color-warning) 35%, transparent);
        }
      }
      @media (prefers-reduced-motion: reduce) {
        .live-dot,
        tr.bump td {
          animation: none;
        }
      }
    `,
  ],
})
export class GamesHomePage {
  private readonly service = inject(GamesService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastController);

  private readonly realtime = inject(RealtimeService);
  private readonly destroyRef = inject(DestroyRef);

  readonly tab = signal<Tab>('today');
  readonly overview = signal<GamesOverview | null>(null);
  readonly liveTable = signal<MedalTableRow[] | null>(null);
  readonly livePoints = signal<PointsRow[] | null>(null);
  readonly bumped = signal<Set<string>>(new Set());
  readonly reportDay = signal(new Date().toISOString().slice(0, 10));
  readonly reportSport = signal('');
  readonly teamWord = computed(() => this.games()?.team_label || 'NOC');
  readonly tabs = computed<Array<{ key: Tab; label: string }>>(() => [
    { key: 'today', label: 'Today' },
    { key: 'medals', label: 'Medals' },
    ...(this.points().length ? [{ key: 'points' as Tab, label: 'Points' }] : []),
    { key: 'events', label: 'Events' },
    { key: 'nocs', label: `${this.teamWord()}s` },
    { key: 'schedule', label: 'Schedule' },
    { key: 'reports', label: 'Reports' },
  ]);
  readonly table = computed(() => this.liveTable() ?? this.medals()?.table ?? this.overview()?.medal_table ?? []);
  readonly points = computed(() => this.livePoints() ?? this.medals()?.points_table ?? this.overview()?.points_table ?? []);
  readonly games = signal<Games | null>(null);
  readonly medals = signal<MedalsResponse | null>(null);
  readonly events = signal<GamesEventRow[]>([]);
  readonly nocs = signal<Noc[]>([]);
  readonly athletes = signal<Athlete[]>([]);
  readonly schedule = signal<Array<{ day: string; events: GamesEventRow[] }>>([]);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly nocName = signal('');
  readonly nocCode = signal('');
  readonly nocColour = signal('#0b3d91');
  readonly athleteName = signal('');
  readonly athleteNoc = signal('');

  private readonly gamesId = computed(() => this.route.snapshot.paramMap.get('id') ?? '');

  readonly eventGroups = computed(() => {
    const groups = new Map<string, GamesEventRow[]>();
    for (const event of this.events()) {
      groups.set(event.sport, [...(groups.get(event.sport) ?? []), event]);
    }
    return [...groups.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([sport, events]) => ({ sport, events }));
  });

  constructor() {
    this.realtime
      .on<{ games_id: string; table: MedalTableRow[]; points_table: PointsRow[] }>('games.medals')
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((payload) => {
        if (payload.games_id !== this.gamesId()) return;
        const before = new Map(this.table().map((row) => [row.noc_id, row.total]));
        this.liveTable.set(payload.table);
        if (payload.points_table?.length) this.livePoints.set(payload.points_table);
        this.bumped.set(new Set(payload.table.filter((row) => before.get(row.noc_id) !== row.total).map((row) => row.noc_id)));
        this.service.overview(this.gamesId()).subscribe({ next: (data) => this.overview.set(data) });
        this.service.medals(this.gamesId()).subscribe({ next: (data) => this.medals.set(data) });
      });
  }

  ionViewWillEnter(): void {
    this.load();
    this.realtime.subscribe(gamesRoom(this.gamesId()));
  }

  ionViewWillLeave(): void {
    this.realtime.unsubscribe(gamesRoom(this.gamesId()));
  }

  asMedalRows(rows: unknown): MedalTableRow[] {
    return rows as MedalTableRow[];
  }

  asPointsRows(rows: unknown): PointsRow[] {
    return rows as PointsRow[];
  }

  asFeed(rows: unknown): MedalsResponse['feed'] {
    return rows as MedalsResponse['feed'];
  }

  private load(done?: () => void): void {
    const id = this.gamesId();
    this.service.get(id).subscribe({
      next: (games) => {
        this.games.set(games);
        this.loading.set(false);
        done?.();
      },
      error: () => {
        this.loading.set(false);
        done?.();
      },
    });
    this.service.overview(id).subscribe({ next: (data) => this.overview.set(data) });
    this.service.medals(id).subscribe({
      next: (medals) => {
        this.medals.set(medals);
        this.liveTable.set(null);
        this.livePoints.set(null);
      },
    });
    this.service.events(id).subscribe({ next: (rows) => this.events.set(rows) });
    this.service.nocs(id).subscribe({ next: (rows) => this.nocs.set(rows) });
    this.service.athletes(id).subscribe({ next: (rows) => this.athletes.set(rows) });
    this.service.schedule(id).subscribe({ next: (rows) => this.schedule.set(rows) });
  }

  refresh(event: CustomEvent): void {
    this.load(() => void (event.target as HTMLIonRefresherElement).complete());
  }

  go(path: string): void {
    void this.router.navigateByUrl(`/tabs/games/${this.gamesId()}/${path}`);
  }


  statusLabel(status: string): string {
    return { scheduled: 'Scheduled', in_progress: 'Under way', medals_awarded: 'Medals' }[status] ?? status;
  }

  athleteCount(nocId: string): number {
    return this.athletes().filter((athlete) => athlete.noc_id === nocId).length;
  }

  addNoc(event: Event): void {
    event.preventDefault();
    this.busy.set(true);
    this.service
      .addNoc(this.gamesId(), { name: this.nocName().trim(), code: this.nocCode().trim(), colour: this.nocColour() })
      .subscribe({
        next: async (noc) => {
          this.busy.set(false);
          this.nocName.set('');
          this.nocCode.set('');
          this.load();
          await this.toast(`${noc.code} added.`, 'success');
        },
        error: async (err: unknown) => {
          this.busy.set(false);
          await this.toast(extractErrorMessage(err, 'Could not add that NOC.'), 'danger');
        },
      });
  }

  addAthlete(event: Event): void {
    event.preventDefault();
    this.busy.set(true);
    this.service.addAthlete(this.gamesId(), { name: this.athleteName().trim(), noc: this.athleteNoc() }).subscribe({
      next: async (athlete) => {
        this.busy.set(false);
        this.athleteName.set('');
        this.load();
        await this.toast(`${athlete.name} added for ${athlete.noc}.`, 'success');
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not add that athlete.'), 'danger');
      },
    });
  }

  private async toast(message: string, color: 'success' | 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2400, position: 'top' });
    await toast.present();
  }
}
