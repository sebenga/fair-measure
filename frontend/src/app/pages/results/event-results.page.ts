import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import {
  AlertController,
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
import type { Observable } from 'rxjs';

import { extractErrorMessage } from '../../core/error-message';
import type { EntryData, ResultEntry, ResultSheet } from '../../core/results.models';
import { ResultsService } from '../../core/results.service';

const TYPE_LABEL: Record<string, string> = {
  finishing_order: 'Finishing order',
  faults_then_time: 'Faults, then time',
  penalty_total_lowest: 'Lowest penalty total',
  judged_percentage: 'Judged percentage',
  timed_with_vet_gates: 'Fastest time through every vet gate',
  points_per_run: 'Points per run',
};

const WELFARE = '__welfare__';

/** "1:02:30", "4:05" or "245.3" → seconds. */
function toSeconds(text: string): number | null {
  const value = text.trim();
  if (!value) return null;
  if (!value.includes(':')) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  const parts = value.split(':').map(Number);
  if (parts.some((part) => !Number.isFinite(part))) return null;
  return parts.reduce((total, part) => total * 60 + part, 0);
}

function clock(seconds: number | string | null | undefined): string {
  const total = Number(seconds);
  if (!Number.isFinite(total)) return '';
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = Math.round(total % 60);
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}` : `${m}:${String(s).padStart(2, '0')}`;
}

@Component({
  selector: 'fm-event-results',
  standalone: true,
  imports: [
    DatePipe,
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
  styleUrl: './event-results.page.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button [defaultHref]="backHref()" /></ion-buttons>
        <ion-title>{{ sheet()?.fixture?.label || 'Event' }}</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      <ion-refresher slot="fixed" (ionRefresh)="reload($event)"><ion-refresher-content /></ion-refresher>

      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (error()) {
        <div class="fm-empty">
          <ion-icon name="alert-circle-outline" aria-hidden="true" />
          <h3>Results unavailable</h3>
          <p>{{ error() }}</p>
        </div>
      } @else if (sheet(); as s) {
        <section class="hero fm-enter">
          <p class="kicker">{{ typeLabel(s.result_type) }}</p>
          <h2>{{ s.fixture.label }}</h2>
          <div class="hero-row">
            <span class="badge" [class.ok]="s.final" [class.warn]="!s.final">
              {{ s.final ? 'Final' : 'Provisional' }}
            </span>
            @if (s.final && s.finalised_at) {
              <span class="stamp">Confirmed {{ s.finalised_at | date: 'd MMM y, HH:mm' }}{{ s.finalised_by ? ' by ' + s.finalised_by : '' }}</span>
            }
          </div>
          @if (s.permissions.officials_required) {
            <p class="note">
              Officials' decisions are final. Only stewards, judges or the ground jury can confirm or amend this
              result, and every change is logged with its reason.
            </p>
          }
        </section>

        <h3 class="fm-section-title">Ranking</h3>
        <ol class="ranking fm-stagger">
          @for (entry of s.entries; track entry.side_id) {
            <li class="fm-card" [class.out]="entry.effective_status">
              <span class="place" [attr.data-place]="entry.rank ?? ''">
                {{ entry.rank ?? (entry.effective_status || '–') }}
              </span>
              <span class="who">
                <strong>{{ entry.combination?.horse ?? entry.name }}</strong>
                @if (entry.combination; as c) {
                  <small>{{ c.rider }}{{ c.trainer ? ' · trainer ' + c.trainer : '' }}</small>
                }
                @if (entry.effective_status) {
                  <small class="reason">
                    @if (entry.welfare_locked) {
                      <ion-icon name="lock-closed-outline" aria-label="Welfare elimination" />
                    }
                    {{ statusLabel(entry.effective_status) }}{{ entry.breakdown['status_reason'] ? ': ' + entry.breakdown['status_reason'] : '' }}
                  </small>
                }
              </span>
              <span class="value">{{ headline(entry) }}</span>
              @if (s.permissions.can_decide && !entry.welfare_locked) {
                <button type="button" class="icon-btn" (click)="statusFor(entry)" [attr.aria-label]="'Decision for ' + entry.name">
                  <ion-icon name="flag-outline" />
                </button>
              }
            </li>
          }
        </ol>

        @if (canEdit()) {
          <h3 class="fm-section-title">{{ s.final ? 'Amend the result' : 'Record results' }}</h3>
          @if (s.final) {
            <p class="hint">This result is final. Changes need a reason and are added to the log below.</p>
          }

          @if (eventSettings().length) {
            <section class="fm-card editor">
              <h4>Event settings</h4>
              <div class="grid">
                @for (item of eventSettings(); track item.path) {
                  <label class="field">
                    {{ item.label }}
                    <input [value]="item.value" (change)="setConfig(item.group, item.key, $event)" inputmode="decimal" />
                  </label>
                }
              </div>
            </section>
          }

          @for (entry of s.entries; track entry.side_id) {
            <details class="fm-card editor" [open]="openSide() === entry.side_id" (toggle)="onToggle(entry.side_id, $event)">
              <summary>
                <strong>{{ entry.combination?.horse ?? entry.name }}</strong>
                <small>{{ entry.combination?.rider ?? '' }}</small>
                @if (dirty()[entry.side_id]) {
                  <span class="badge warn">Unsaved</span>
                }
              </summary>

              @if (entry.welfare_locked) {
                <p class="hint">Eliminated on welfare grounds. That decision stands and cannot be changed.</p>
              } @else {
                @switch (s.result_type) {
                  @case ('finishing_order') {
                    <div class="grid">
                      <label class="field">Position<input type="number" min="1" [value]="val(entry, ['position'])" (change)="setNum(entry, ['position'], $event)" /></label>
                      <label class="field">
                        Did not finish
                        <select (change)="setText(entry, ['status'], $event)">
                          <option value="" [selected]="!val(entry, ['status'])">Finished</option>
                          @for (status of s.statuses; track status.code) {
                            <option [value]="status.code" [selected]="val(entry, ['status']) === status.code">{{ status.code }} · {{ status.label }}</option>
                          }
                        </select>
                      </label>
                      @for (field of s.config.record_fields ?? []; track field) {
                        <label class="field">{{ field }}<input [value]="val(entry, [field])" (change)="setText(entry, [field], $event)" /></label>
                      }
                    </div>
                  }
                  @case ('faults_then_time') {
                    @for (round of s.config.rounds ?? [{ key: 'round', label: 'Round' }]; track round.key) {
                      <p class="sub">{{ round.label ?? round.key }}{{ round.decides ? ' (decides first place)' : '' }}</p>
                      <div class="grid">
                        @for (item of s.config.penalties ?? []; track item.key) {
                          <label class="field">{{ item.label }}<input type="number" min="0" [value]="val(entry, ['rounds', round.key, item.key])" (change)="setNum(entry, ['rounds', round.key, item.key], $event)" /></label>
                        }
                        <label class="field">Time (s or m:ss)<input [value]="val(entry, ['rounds', round.key, 'time'])" (change)="setTime(entry, ['rounds', round.key, 'time'], $event)" /></label>
                      </div>
                    }
                  }
                  @case ('penalty_total_lowest') {
                    @if ((s.config.inspections ?? []).length) {
                      <p class="sub">Horse inspections</p>
                      <div class="grid">
                        @for (inspection of s.config.inspections ?? []; track inspection.key) {
                          <label class="field">
                            {{ inspection.label }}
                            <select (change)="setText(entry, ['inspections', inspection.key], $event)">
                              <option value="" [selected]="!val(entry, ['inspections', inspection.key])">Not yet</option>
                              <option value="pass" [selected]="val(entry, ['inspections', inspection.key]) === 'pass'">Accepted</option>
                              <option value="fail" [selected]="val(entry, ['inspections', inspection.key]) === 'fail'">Not accepted</option>
                            </select>
                          </label>
                        }
                      </div>
                    }
                    @for (phase of s.config.phases ?? []; track phase.key) {
                      <p class="sub">{{ phase.label }}</p>
                      <div class="grid">
                        @if (phase.input === 'percentage') {
                          <label class="field">Percentage<input inputmode="decimal" [value]="val(entry, ['phases', phase.key, 'percentage'])" (change)="setNum(entry, ['phases', phase.key, 'percentage'], $event)" /></label>
                        } @else {
                          @for (item of phase.penalties ?? []; track item.key) {
                            @if (item.per_obstacle) {
                              <label class="field">{{ item.label }} by obstacle (e.g. 5:1, 9:2)<input [value]="obstacles(entry, ['phases', phase.key, item.key])" (change)="setObstacles(entry, ['phases', phase.key, item.key], $event)" /></label>
                            } @else {
                              <label class="field">{{ item.label }}<input type="number" min="0" [value]="val(entry, ['phases', phase.key, item.key])" (change)="setNum(entry, ['phases', phase.key, item.key], $event)" /></label>
                            }
                          }
                          <label class="field">Time (s or m:ss)<input [value]="val(entry, ['phases', phase.key, 'time'])" (change)="setTime(entry, ['phases', phase.key, 'time'], $event)" /></label>
                        }
                      </div>
                    }
                  }
                  @case ('judged_percentage') {
                    <div class="marks-wrap">
                      <table class="marks">
                        <thead>
                          <tr>
                            <th>Movement</th>
                            <th>×</th>
                            @for (judge of judges(); track judge) {
                              <th>{{ judge }}</th>
                            }
                          </tr>
                        </thead>
                        <tbody>
                          @for (item of s.config.sheet ?? []; track item.key) {
                            <tr [class.collective]="item.collective">
                              <td>{{ item.label }}</td>
                              <td>{{ item.coefficient ?? 1 }}</td>
                              @for (judge of judges(); track judge) {
                                <td>
                                  <input
                                    inputmode="decimal"
                                    [attr.aria-label]="judge + ' ' + item.label"
                                    [value]="val(entry, ['marks', judge, item.key])"
                                    (change)="setNum(entry, ['marks', judge, item.key], $event)"
                                  />
                                </td>
                              }
                            </tr>
                          }
                        </tbody>
                      </table>
                    </div>
                    <div class="grid">
                      <label class="field">Errors of course<input type="number" min="0" [value]="val(entry, ['errors'])" (change)="setNum(entry, ['errors'], $event)" /></label>
                    </div>
                  }
                  @case ('timed_with_vet_gates') {
                    @for (loop of s.config.loops ?? []; track loop.key; let index = $index) {
                      <p class="sub">{{ loop.label }}{{ loop.distance_km ? ' · ' + loop.distance_km + ' km' : '' }}</p>
                      <div class="grid">
                        <label class="field">Riding time (h:mm:ss)<input [value]="clockOf(entry, ['loops', index, 'ride_seconds'])" (change)="setTime(entry, ['loops', index, 'ride_seconds'], $event)" /></label>
                        <label class="field">Hold (not counted)<input [value]="clockOf(entry, ['loops', index, 'hold_seconds'])" (change)="setTime(entry, ['loops', index, 'hold_seconds'], $event)" /></label>
                        <label class="field">Heart rate (bpm)<input type="number" [value]="val(entry, ['loops', index, 'heart_rate'])" (change)="setNum(entry, ['loops', index, 'heart_rate'], $event)" /></label>
                        <label class="field">
                          Soundness
                          <select (change)="setBool(entry, ['loops', index, 'sound'], $event)">
                            <option value="" [selected]="val(entry, ['loops', index, 'sound']) === ''">Not checked</option>
                            <option value="true" [selected]="val(entry, ['loops', index, 'sound']) === true">Sound</option>
                            <option value="false" [selected]="val(entry, ['loops', index, 'sound']) === false">Lame</option>
                          </select>
                        </label>
                      </div>
                    }
                    <div class="grid">
                      <label class="field">
                        Final inspection
                        <select (change)="setText(entry, ['final_inspection', 'result'], $event)">
                          <option value="" [selected]="!val(entry, ['final_inspection', 'result'])">Not yet</option>
                          <option value="pass" [selected]="val(entry, ['final_inspection', 'result']) === 'pass'">Passed</option>
                          <option value="ftq" [selected]="val(entry, ['final_inspection', 'result']) === 'ftq'">Failed to qualify</option>
                        </select>
                      </label>
                    </div>
                  }
                  @case ('points_per_run') {
                    @for (run of runsOf(entry); track $index; let index = $index) {
                      <div class="grid run">
                        <label class="field">
                          Run {{ index + 1 }}
                          <select (change)="setText(entry, ['runs', index, 'outcome'], $event)">
                            <option value="" [selected]="!run.outcome">Choose</option>
                            @for (outcome of s.config.outcomes ?? []; track outcome.key) {
                              <option [value]="outcome.key" [selected]="run.outcome === outcome.key">{{ outcome.label }} ({{ outcome.points }})</option>
                            }
                          </select>
                        </label>
                        <label class="field">Time (s)<input inputmode="decimal" [value]="run.time ?? ''" (change)="setNum(entry, ['runs', index, 'time'], $event)" /></label>
                      </div>
                    }
                    <button type="button" class="btn ghost small" (click)="addRun(entry)">Add a run</button>
                  }
                }
              }
            </details>
          }

          <div class="actions">
            <button type="button" class="btn" [disabled]="busy() || !anyDirty()" (click)="save()">
              {{ s.final ? 'Save amendment' : 'Save results' }}
            </button>
            @if (s.permissions.can_decide && !s.final) {
              <button type="button" class="btn ghost" [disabled]="busy() || anyDirty()" (click)="finalise()">
                <ion-icon name="checkmark-outline" aria-hidden="true" />
                Confirm as final
              </button>
            }
          </div>
          @if (!s.permissions.can_decide && s.permissions.officials_required) {
            <p class="hint">You can record provisional results. A steward, judge or the ground jury confirms them.</p>
          }
        }

        <h3 class="fm-section-title">Decisions and amendments</h3>
        <ul class="log">
          @for (row of s.amendments; track row.id) {
            <li>
              <strong>{{ row.action_label }}</strong>
              @if (row.entrant) {
                <span> · {{ row.entrant }}</span>
              }
              <small>{{ row.created_at | date: 'd MMM y, HH:mm' }}{{ row.actor ? ' · ' + row.actor : '' }}</small>
              @if (row.reason) {
                <p>{{ row.reason }}</p>
              }
            </li>
          } @empty {
            <li class="muted">Nothing logged yet. Confirming the result and every later change is recorded here.</li>
          }
        </ul>
      }
      <div style="height: 32px"></div>
    </ion-content>
  `,
})
export class EventResultsPage {
  private readonly results = inject(ResultsService);
  private readonly route = inject(ActivatedRoute);
  private readonly alerts = inject(AlertController);
  private readonly toasts = inject(ToastController);

  readonly sheet = signal<ResultSheet | null>(null);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly drafts = signal<Record<string, EntryData>>({});
  readonly dirty = signal<Record<string, boolean>>({});
  readonly configDraft = signal<Record<string, Record<string, unknown>> | null>(null);
  readonly openSide = signal<string | null>(null);

  private readonly fixtureId = computed(() => this.route.snapshot.paramMap.get('fixtureId') ?? '');
  readonly backHref = computed(
    () => `/tabs/competitions/${this.route.snapshot.paramMap.get('competitionId') ?? ''}`,
  );

  readonly canEdit = computed(() => {
    const sheet = this.sheet();
    if (!sheet) return false;
    return sheet.final ? sheet.permissions.can_decide : sheet.permissions.can_record;
  });

  readonly anyDirty = computed(
    () => Object.values(this.dirty()).some(Boolean) || this.configDraft() !== null,
  );

  readonly judges = computed(() => {
    const sheet = this.sheet();
    if (!sheet) return [];
    if (sheet.config.judges?.length) return sheet.config.judges;
    const found = new Set<string>();
    for (const entry of sheet.entries) Object.keys(entry.data?.['marks'] ?? {}).forEach((judge) => found.add(judge));
    return found.size ? [...found] : ['C'];
  });

  /** Per-event settings an official can set: time allowed per round or phase. */
  readonly eventSettings = computed(() => {
    const sheet = this.sheet();
    if (!sheet) return [];
    const rows: Array<{ path: string; group: string; key: string; label: string; value: string }> = [];
    const allowed = { ...(sheet.config.time_allowed ?? {}), ...(this.configDraft()?.['time_allowed'] ?? {}) } as Record<string, unknown>;
    const parts =
      sheet.result_type === 'faults_then_time'
        ? (sheet.config.rounds ?? []).map((round) => ({ key: round.key, label: round.label ?? round.key }))
        : sheet.result_type === 'penalty_total_lowest'
          ? (sheet.config.phases ?? []).filter((phase) => phase.input !== 'percentage')
          : [];
    for (const part of parts) {
      rows.push({
        path: `time_allowed.${part.key}`,
        group: 'time_allowed',
        key: part.key,
        label: `Time allowed: ${part.label} (s)`,
        value: allowed[part.key] === undefined ? '' : String(allowed[part.key]),
      });
    }
    return rows;
  });

  ionViewWillEnter(): void {
    this.load();
  }

  private load(done?: () => void): void {
    this.results.sheet(this.fixtureId()).subscribe({
      next: (sheet) => {
        this.apply(sheet);
        this.loading.set(false);
        done?.();
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err, 'This event could not be loaded.'));
        this.loading.set(false);
        done?.();
      },
    });
  }

  reload(event: CustomEvent): void {
    this.load(() => void (event.target as HTMLIonRefresherElement).complete());
  }

  private apply(sheet: ResultSheet): void {
    this.sheet.set(sheet);
    this.drafts.set(Object.fromEntries(sheet.entries.map((entry) => [entry.side_id, structuredClone(entry.data ?? {})])));
    this.dirty.set({});
    this.configDraft.set(null);
  }

  typeLabel(type: string): string {
    return TYPE_LABEL[type] ?? type;
  }

  statusLabel(code: string): string {
    return this.sheet()?.statuses.find((status) => status.code === code)?.label ?? code;
  }

  headline(entry: ResultEntry): string {
    const b = entry.breakdown ?? {};
    if (entry.effective_status) return entry.effective_status;
    if (entry.primary === null) return 'Waiting';
    switch (this.sheet()?.result_type) {
      case 'finishing_order':
        return [entry.data?.['margin'], entry.data?.['time'] ? `${entry.data['time']} s` : ''].filter(Boolean).join(' · ') || ordinal(entry.rank);
      case 'faults_then_time': {
        const decider = typeof b['decider'] === 'object' ? b['decider'] : null;
        const base = `${trim(b['faults'])} faults · ${trim(b['time'])} s`;
        return decider ? `${base} · jump-off ${trim(decider.faults)} / ${trim(decider.time)} s` : base;
      }
      case 'penalty_total_lowest':
        return `${trim(entry.primary)} penalties`;
      case 'judged_percentage':
        return `${entry.primary}%`;
      case 'timed_with_vet_gates':
        return `${clock(b['ride_seconds'])} · ${b['average_speed_kmh']} km/h`;
      case 'points_per_run':
        return `${trim(entry.primary)} pts`;
      default:
        return entry.primary;
    }
  }

  // --- Draft editing -----------------------------------------------------------

  val(entry: ResultEntry, path: Array<string | number>): any {
    let node: any = this.drafts()[entry.side_id];
    for (const key of path) {
      if (node === undefined || node === null) return '';
      node = node[key as any];
    }
    return node ?? '';
  }

  private put(entry: ResultEntry, path: Array<string | number>, value: unknown): void {
    this.drafts.update((all) => {
      const copy = structuredClone(all[entry.side_id] ?? {});
      let node: any = copy;
      path.forEach((key, index) => {
        const last = index === path.length - 1;
        if (last) {
          if (value === '' || value === null || value === undefined) delete node[key as any];
          else node[key as any] = value;
          return;
        }
        if (node[key as any] === undefined || node[key as any] === null) {
          node[key as any] = typeof path[index + 1] === 'number' ? [] : {};
        }
        node = node[key as any];
      });
      return { ...all, [entry.side_id]: copy };
    });
    this.dirty.update((all) => ({ ...all, [entry.side_id]: true }));
  }

  setText(entry: ResultEntry, path: Array<string | number>, event: Event): void {
    this.put(entry, path, (event.target as HTMLInputElement).value.trim());
  }

  setNum(entry: ResultEntry, path: Array<string | number>, event: Event): void {
    const raw = (event.target as HTMLInputElement).value.trim();
    const parsed = Number(raw);
    this.put(entry, path, raw === '' ? '' : Number.isFinite(parsed) ? parsed : raw);
  }

  setTime(entry: ResultEntry, path: Array<string | number>, event: Event): void {
    const raw = (event.target as HTMLInputElement).value;
    this.put(entry, path, toSeconds(raw) ?? '');
  }

  setBool(entry: ResultEntry, path: Array<string | number>, event: Event): void {
    const raw = (event.target as HTMLSelectElement).value;
    this.put(entry, path, raw === '' ? '' : raw === 'true');
  }

  clockOf(entry: ResultEntry, path: Array<string | number>): string {
    const value = this.val(entry, path);
    return value === '' ? '' : clock(value);
  }

  obstacles(entry: ResultEntry, path: Array<string | number>): string {
    const value = this.val(entry, path);
    if (!value || typeof value !== 'object') return '';
    return Object.entries(value)
      .map(([obstacle, count]) => `${obstacle}:${count}`)
      .join(', ');
  }

  setObstacles(entry: ResultEntry, path: Array<string | number>, event: Event): void {
    const text = (event.target as HTMLInputElement).value;
    const parsed: Record<string, number> = {};
    for (const part of text.split(',')) {
      const [obstacle, count] = part.split(':').map((item) => item.trim());
      if (obstacle && Number(count) > 0) parsed[obstacle] = Number(count);
    }
    this.put(entry, path, Object.keys(parsed).length ? parsed : '');
  }

  runsOf(entry: ResultEntry): Array<{ outcome?: string; time?: number }> {
    const runs = this.val(entry, ['runs']);
    const planned = Number(this.sheet()?.config.runs ?? 0);
    const list = Array.isArray(runs) ? [...runs] : [];
    while (list.length < planned) list.push({});
    return list;
  }

  addRun(entry: ResultEntry): void {
    const runs = this.runsOf(entry);
    this.put(entry, ['runs', runs.length, 'outcome'], (this.sheet()?.config.outcomes ?? [])[0]?.key ?? '');
  }

  setConfig(group: string, key: string, event: Event): void {
    const raw = (event.target as HTMLInputElement).value.trim();
    const value = raw === '' ? undefined : Number(raw);
    this.configDraft.update((current) => {
      const next = { ...(current ?? {}) };
      const bucket = { ...((this.sheet()?.config[group] as Record<string, unknown>) ?? {}), ...(next[group] ?? {}) };
      if (value === undefined || !Number.isFinite(value)) delete bucket[key];
      else bucket[key] = value;
      next[group] = bucket;
      return next;
    });
  }

  onToggle(sideId: string, event: Event): void {
    if ((event.target as HTMLDetailsElement).open) this.openSide.set(sideId);
  }

  // --- Saving and official decisions ------------------------------------------------

  async save(): Promise<void> {
    const sheet = this.sheet();
    if (!sheet) return;
    const entries = Object.entries(this.dirty())
      .filter(([, changed]) => changed)
      .map(([side]) => ({ side, data: this.drafts()[side] ?? {} }));
    const config = this.configDraft() ?? undefined;
    if (sheet.final) {
      const reason = await this.ask('Amend a final result', 'Why is the result being changed? This is logged.');
      if (!reason) return;
      this.run(this.results.save(sheet.fixture.id, entries, { reason, config }), 'Amendment saved and logged.');
      return;
    }
    this.run(this.results.save(sheet.fixture.id, entries, { config }), 'Provisional results saved.');
  }

  async finalise(): Promise<void> {
    const sheet = this.sheet();
    if (!sheet) return;
    const alert = await this.alerts.create({
      header: 'Confirm the result as final?',
      message: 'The table updates straight away. After this, only officials can change it, with a reason.',
      buttons: [
        { text: 'Not yet', role: 'cancel' },
        {
          text: 'Confirm',
          handler: () => this.run(this.results.finalise(sheet.fixture.id), 'Result confirmed.'),
        },
      ],
    });
    await alert.present();
  }

  async statusFor(entry: ResultEntry): Promise<void> {
    const sheet = this.sheet();
    if (!sheet) return;
    const alert = await this.alerts.create({
      header: entry.combination?.horse ?? entry.name,
      subHeader: 'Official decision',
      inputs: [
        ...sheet.statuses.map((status) => ({
          type: 'radio' as const,
          label: `${status.code} · ${status.label}`,
          value: status.code,
          checked: entry.status === status.code,
        })),
        {
          type: 'radio' as const,
          label: `${this.welfareCode()} · Welfare (vet) elimination, final`,
          value: WELFARE,
        },
        { type: 'radio' as const, label: 'Clear the decision', value: '', checked: !entry.status },
      ],
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        {
          text: 'Next',
          handler: (choice: string) => {
            const welfare = choice === WELFARE;
            void this.confirmStatus(entry, welfare ? this.welfareCode() : (choice ?? ''), welfare);
          },
        },
      ],
    });
    await alert.present();
  }

  /** The status a welfare elimination is recorded under: EL if the preset has it. */
  private welfareCode(): string {
    const codes = (this.sheet()?.statuses ?? []).map((status) => status.code);
    return codes.includes('EL') ? 'EL' : (codes[0] ?? 'EL');
  }

  private async confirmStatus(entry: ResultEntry, status: string, welfare: boolean): Promise<void> {
    const sheet = this.sheet();
    if (!sheet) return;
    const alert = await this.alerts.create({
      header: status ? `${status}: ${this.statusLabel(status)}` : 'Clear the decision',
      subHeader: welfare ? 'Welfare elimination. Nobody can override this in the app.' : undefined,
      message: 'Give the reason. Every decision is logged.',
      inputs: [{ name: 'reason', type: 'textarea', placeholder: 'Reason' }],
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        {
          text: 'Save decision',
          handler: (values: { reason?: string }) => {
            const reason = (values?.reason ?? '').trim();
            if (!reason) {
              void this.toast('A reason is required.', 'danger');
              return false;
            }
            this.run(
              this.results.setStatus(sheet.fixture.id, { side: entry.side_id, status, reason, welfare }),
              welfare ? 'Welfare elimination recorded.' : status ? 'Decision recorded.' : 'Decision cleared.',
            );
            return true;
          },
        },
      ],
    });
    await alert.present();
  }

  private async ask(header: string, message: string): Promise<string | null> {
    const alert = await this.alerts.create({
      header,
      message,
      inputs: [{ name: 'reason', type: 'textarea', placeholder: 'Reason' }],
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        { text: 'Save', role: 'confirm' },
      ],
    });
    await alert.present();
    const { data, role } = await alert.onDidDismiss<{ values: { reason?: string } }>();
    if (role !== 'confirm') return null;
    const reason = (data?.values?.reason ?? '').trim();
    if (!reason) {
      await this.toast('A reason is required to amend a final result.', 'danger');
      return null;
    }
    return reason;
  }

  private run(request: Observable<ResultSheet>, success: string): void {
    if (this.busy()) return;
    this.busy.set(true);
    request.subscribe({
      next: async (sheet) => {
        this.apply(sheet);
        this.busy.set(false);
        await this.toast(success, 'success');
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'That did not save.'), 'danger');
      },
    });
  }

  private async toast(message: string, color: 'success' | 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2600, position: 'top' });
    await toast.present();
  }
}

function trim(value: unknown): string {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? String(parsed) : String(value ?? '');
}

function ordinal(rank: number | null): string {
  if (rank === null) return '';
  const suffix = rank % 100 >= 11 && rank % 100 <= 13 ? 'th' : ['th', 'st', 'nd', 'rd'][rank % 10] ?? 'th';
  return `${rank}${suffix}`;
}
