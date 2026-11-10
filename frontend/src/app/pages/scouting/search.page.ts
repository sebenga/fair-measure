import { ChangeDetectionStrategy, Component, type WritableSignal, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import {
  AlertController,
  IonBackButton,
  IonButtons,
  IonContent,
  IonFooter,
  IonHeader,
  IonIcon,
  IonSpinner,
  IonTitle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';

import { extractErrorMessage } from '../../core/error-message';
import type {
  FilterOp,
  RatingAreaKey,
  Recommendation,
  SavedSearch,
  ScoutingCatalog,
  SearchFilters,
  SearchResult,
  SportCatalogue,
} from '../../core/scouting.models';
import { ScoutingService } from '../../core/scouting.service';

interface ValueRow {
  key: string;
  op: FilterOp;
  value: string;
}

const OPS: Array<{ key: FilterOp; label: string }> = [
  { key: 'lt', label: 'under' },
  { key: 'lte', label: 'at most' },
  { key: 'gte', label: 'at least' },
  { key: 'gt', label: 'over' },
  { key: 'eq', label: 'exactly' },
];

/** Talent search: filter by profile, tests, stats, percentiles and your organisation's ratings. */
@Component({
  selector: 'fm-talent-search',
  standalone: true,
  imports: [IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonFooter, IonIcon, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './scouting.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button defaultHref="/tabs/scouting" /></ion-buttons>
        <ion-title>Talent search</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (saved().length) {
        <div class="section saved">
          @for (row of saved(); track row.id) {
            <span class="saved-chip" [class.on]="activeSaved() === row.id">
              <button type="button" class="name" (click)="loadSavedSearch(row)">{{ row.name }}</button>
              <button type="button" class="icon" (click)="toggleAlerts(row)" [attr.aria-label]="row.alerts ? 'Turn alerts off' : 'Turn alerts on'">
                <ion-icon [name]="row.alerts ? 'notifications' : 'notifications-off-outline'" aria-hidden="true" />
              </button>
              <button type="button" class="icon" (click)="removeSaved(row)" aria-label="Delete saved search">✕</button>
            </span>
          }
        </div>
      }

      <details class="fm-card section filters" [open]="!results().length">
        <summary><strong>Filters</strong> <small>{{ activeCount() }} set</small></summary>
        <label class="field">Name<input [value]="q()" (input)="q.set($any($event.target).value)" placeholder="Any player" /></label>
        <div class="row">
          <label class="field">
            Sport
            <select (change)="chooseSport($any($event.target).value)">
              <option value="">Any sport</option>
              @for (item of catalog()?.sports ?? []; track item.key) {
                <option [value]="item.key" [selected]="sport() === item.key">{{ item.label }}</option>
              }
            </select>
          </label>
          <label class="field">
            Position
            <select (change)="position.set($any($event.target).value)" [disabled]="!sport()">
              <option value="">Any position</option>
              @for (item of sportInfo()?.positions ?? []; track item.key) {
                <option [value]="item.key" [selected]="position() === item.key">{{ item.label }}</option>
              }
            </select>
          </label>
        </div>
        <div class="row">
          <label class="field">
            Age group
            <select (change)="ageGroup.set($any($event.target).value)">
              <option value="">Any age</option>
              @for (item of catalog()?.age_groups ?? []; track item.key) {
                <option [value]="item.key" [selected]="ageGroup() === item.key">{{ item.label }}</option>
              }
            </select>
          </label>
          <label class="field">
            Gender category
            <select (change)="gender.set($any($event.target).value)">
              <option value="">Any</option>
              @for (item of catalog()?.gender_categories ?? []; track item.key) {
                <option [value]="item.key" [selected]="gender() === item.key">{{ item.label }}</option>
              }
            </select>
          </label>
        </div>
        <div class="row">
          <label class="field">
            Province / region
            <select (change)="region.set($any($event.target).value)">
              <option value="">Anywhere</option>
              @for (item of catalog()?.regions ?? []; track item.key) {
                <option [value]="item.key" [selected]="region() === item.key">{{ item.label }}</option>
              }
            </select>
          </label>
          <label class="field">
            Plays at least at
            <select (change)="level.set($any($event.target).value)">
              <option value="">Any level</option>
              @for (item of catalog()?.competition_levels ?? []; track item.key) {
                <option [value]="item.key" [selected]="level() === item.key">{{ item.label }}</option>
              }
            </select>
          </label>
        </div>
        <label class="check"><input type="checkbox" [checked]="hasVideo()" (change)="hasVideo.set($any($event.target).checked)" /> Has highlight video</label>

        @if (sportInfo(); as info) {
          <p class="sub">Physical tests (best result)</p>
          @for (row of tests(); track $index; let index = $index) {
            <div class="value-row">
              <select (change)="editRow(tests, index, 'key', $any($event.target).value)">
                @for (item of info.physical_tests; track item.key) {
                  <option [value]="item.key" [selected]="row.key === item.key">{{ item.label }} ({{ item.unit }})</option>
                }
              </select>
              <select (change)="editRow(tests, index, 'op', $any($event.target).value)">
                @for (op of ops; track op.key) {
                  <option [value]="op.key" [selected]="row.op === op.key">{{ op.label }}</option>
                }
              </select>
              <input inputmode="decimal" [value]="row.value" (input)="editRow(tests, index, 'value', $any($event.target).value)" placeholder="5.2" />
              <button type="button" class="icon" (click)="removeRow(tests, index)" aria-label="Remove">✕</button>
            </div>
          }
          <button type="button" class="btn ghost small" (click)="addRow(tests, info.physical_tests[0]?.key, 'lt')" [disabled]="!info.physical_tests.length">Add a test filter</button>

          <p class="sub">Match stats (latest season)</p>
          @for (row of statRows(); track $index; let index = $index) {
            <div class="value-row">
              <select (change)="editRow(statRows, index, 'key', $any($event.target).value)">
                @for (item of info.match_stats; track item.key) {
                  <option [value]="item.key" [selected]="row.key === item.key">{{ item.label }}</option>
                }
              </select>
              <select (change)="editRow(statRows, index, 'op', $any($event.target).value)">
                @for (op of ops; track op.key) {
                  <option [value]="op.key" [selected]="row.op === op.key">{{ op.label }}</option>
                }
              </select>
              <input inputmode="decimal" [value]="row.value" (input)="editRow(statRows, index, 'value', $any($event.target).value)" placeholder="1" />
              <button type="button" class="icon" (click)="removeRow(statRows, index)" aria-label="Remove">✕</button>
            </div>
          }
          <button type="button" class="btn ghost small" (click)="addRow(statRows, info.match_stats[0]?.key, 'gte')">Add a stat filter</button>

          <p class="sub">Percentile (within sport, position, age group and gender)</p>
          @for (row of percentileRows(); track $index; let index = $index) {
            <div class="value-row">
              <select (change)="editRow(percentileRows, index, 'key', $any($event.target).value)">
                @for (item of percentileOptions(); track item.key) {
                  <option [value]="item.key" [selected]="row.key === item.key">{{ item.label }}</option>
                }
              </select>
              <span class="at-least">at least</span>
              <input inputmode="numeric" [value]="row.value" (input)="editRow(percentileRows, index, 'value', $any($event.target).value)" placeholder="75" />
              <button type="button" class="icon" (click)="removeRow(percentileRows, index)" aria-label="Remove">✕</button>
            </div>
          }
          <button type="button" class="btn ghost small" (click)="addRow(percentileRows, percentileOptions()[0]?.key, 'gte')">Add a percentile filter</button>
        }

        <p class="sub">Your organisation's ratings</p>
        @for (row of areaRows(); track $index; let index = $index) {
          <div class="value-row">
            <select (change)="editRow(areaRows, index, 'key', $any($event.target).value)">
              @for (item of catalog()?.areas ?? []; track item.key) {
                <option [value]="item.key" [selected]="row.key === item.key">{{ item.label }}</option>
              }
            </select>
            <span class="at-least">at least</span>
            <input inputmode="decimal" [value]="row.value" (input)="editRow(areaRows, index, 'value', $any($event.target).value)" placeholder="7" />
            <button type="button" class="icon" (click)="removeRow(areaRows, index)" aria-label="Remove">✕</button>
          </div>
        }
        <button type="button" class="btn ghost small" (click)="addRow(areaRows, 'technical', 'gte')">Add an area score filter</button>
        <div class="row top">
          <label class="field">Potential at least<input inputmode="decimal" [value]="potentialMin()" (input)="potentialMin.set($any($event.target).value)" placeholder="1-10" /></label>
          <label class="field">
            Recommendation
            <select (change)="recommendation.set($any($event.target).value)">
              <option value="">Any</option>
              @for (item of catalog()?.rating_recommendations ?? []; track item.key) {
                <option [value]="item.key" [selected]="recommendation() === item.key">{{ item.label }}</option>
              }
            </select>
          </label>
        </div>

        <div class="actions-row">
          <button type="button" class="btn" [disabled]="busy()" (click)="run()">Search</button>
          <button type="button" class="btn ghost" [disabled]="busy()" (click)="saveSearch()">Save search</button>
          <button type="button" class="btn ghost small" (click)="clear()">Clear</button>
        </div>
      </details>

      @if (busy()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (searched()) {
        <p class="lede">{{ results().length }} player(s) match. Under-18s appear only with a guardian's consent.</p>
        <ul class="list section">
          @for (row of results(); track row.id) {
            <li class="fm-card result">
              <label class="pick" [class.disabled]="!picked().has(row.id) && picked().size >= 4">
                <input type="checkbox" [checked]="picked().has(row.id)" [disabled]="!picked().has(row.id) && picked().size >= 4" (change)="togglePick(row.id)" aria-label="Compare" />
              </label>
              <button type="button" class="grow open" (click)="open(row.id)">
                <strong>{{ row.name }}</strong>
                <small>{{ row.sport?.sport_label ?? '' }}{{ row.sport?.primary_position_label ? ' · ' + row.sport?.primary_position_label : '' }}{{ row.age_group ? ' · ' + row.age_group : '' }}</small>
                <span class="chips">
                  @for (fact of facts(row); track fact) {
                    <span class="badge">{{ fact }}</span>
                  }
                </span>
              </button>
              <button type="button" class="btn ghost small" (click)="shortlist(row)">Shortlist</button>
            </li>
          } @empty {
            <li class="hint">Nobody matches. Try fewer filters.</li>
          }
        </ul>
        <div style="height: 70px"></div>
      }
    </ion-content>

    @if (picked().size >= 2) {
      <ion-footer>
        <ion-toolbar>
          <div class="save-bar">
            <span>{{ picked().size }} selected</span>
            <button type="button" class="btn" (click)="compare()">Compare {{ picked().size }} players</button>
          </div>
        </ion-toolbar>
      </ion-footer>
    }
  `,
  styles: [
    `
      .saved {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .saved-chip {
        display: inline-flex;
        align-items: center;
        border: 1.5px solid var(--ion-color-step-150, #dfe2e6);
        border-radius: 999px;
        overflow: hidden;
      }
      .saved-chip.on {
        border-color: var(--ion-color-primary);
      }
      .saved-chip button {
        border: 0;
        background: none;
        color: inherit;
        font: inherit;
        padding: 6px 8px;
      }
      .saved-chip .name {
        padding-left: 12px;
        font-weight: 650;
      }
      .filters summary {
        cursor: pointer;
      }
      .filters summary small {
        color: var(--ion-color-medium);
      }
      .filters .field {
        margin-top: 8px;
      }
      .check {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 6px 0;
      }
      .sub {
        margin: 14px 0 6px;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--ion-color-medium);
      }
      .value-row {
        display: grid;
        grid-template-columns: 2fr 1fr 1fr auto;
        gap: 6px;
        align-items: center;
        margin-bottom: 6px;
      }
      .value-row select,
      .value-row input {
        min-height: 40px;
        padding: 6px 8px;
        border: 1px solid var(--ion-color-step-200, #d7d8da);
        border-radius: 10px;
        background: var(--ion-background-color, #fff);
        color: var(--ion-text-color);
        font: inherit;
        min-width: 0;
      }
      .at-least {
        font-size: 0.8rem;
        color: var(--ion-color-medium);
      }
      .icon {
        border: 0;
        background: none;
        color: var(--ion-color-medium);
        font: inherit;
      }
      .row.top {
        margin-top: 8px;
      }
      .actions-row {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 14px;
      }
      .result {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 10px 12px;
      }
      .pick input {
        width: 22px;
        height: 22px;
      }
      .open {
        display: grid;
        gap: 3px;
        border: 0;
        background: none;
        color: inherit;
        font: inherit;
        text-align: left;
      }
      .open small {
        color: var(--ion-color-medium);
      }
      .open .chips {
        gap: 4px;
      }
      .save-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 6px 16px;
      }
    `,
  ],
})
export class TalentSearchPage {
  private readonly scouting = inject(ScoutingService);
  private readonly router = inject(Router);
  private readonly alerts = inject(AlertController);
  private readonly toasts = inject(ToastController);

  readonly ops = OPS;
  readonly catalog = signal<ScoutingCatalog | null>(null);
  readonly sportInfo = signal<SportCatalogue | null>(null);
  readonly saved = signal<SavedSearch[]>([]);
  readonly activeSaved = signal('');
  readonly q = signal('');
  readonly sport = signal('');
  readonly position = signal('');
  readonly ageGroup = signal('');
  readonly gender = signal('');
  readonly region = signal('');
  readonly level = signal('');
  readonly hasVideo = signal(false);
  readonly tests = signal<ValueRow[]>([]);
  readonly statRows = signal<ValueRow[]>([]);
  readonly percentileRows = signal<ValueRow[]>([]);
  readonly areaRows = signal<ValueRow[]>([]);
  readonly potentialMin = signal('');
  readonly recommendation = signal('');
  readonly results = signal<SearchResult[]>([]);
  readonly searched = signal(false);
  readonly busy = signal(false);
  readonly picked = signal<Set<string>>(new Set());

  readonly percentileOptions = computed(() => {
    const info = this.sportInfo();
    if (!info) return [];
    return [
      ...info.match_stats.filter((row) => row.better).map((row) => ({ key: row.key, label: row.label })),
      ...info.physical_tests.map((row) => ({ key: row.key, label: row.label })),
    ];
  });

  readonly activeCount = computed(() => Object.keys(this.filters()).length);

  ionViewWillEnter(): void {
    this.scouting.catalog().subscribe({ next: (catalog) => this.catalog.set(catalog) });
    this.loadSaved();
  }

  private loadSaved(): void {
    this.scouting.savedSearches().subscribe({ next: (rows) => this.saved.set(rows) });
  }

  chooseSport(sport: string, done?: () => void): void {
    this.sport.set(sport);
    this.position.set('');
    this.tests.set([]);
    this.statRows.set([]);
    this.percentileRows.set([]);
    this.sportInfo.set(null);
    if (sport) {
      this.scouting.sportCatalogue(sport).subscribe({
        next: (row) => {
          this.sportInfo.set(row);
          done?.();
        },
      });
    } else {
      done?.();
    }
  }

  addRow(rows: WritableSignal<ValueRow[]>, key: string | undefined, op: FilterOp): void {
    if (!key) return;
    rows.update((current) => [...current, { key, op, value: '' }]);
  }

  editRow(rows: WritableSignal<ValueRow[]>, index: number, field: keyof ValueRow, value: string): void {
    rows.update((current) => current.map((row, at) => (at === index ? { ...row, [field]: value } : row)));
  }

  removeRow(rows: WritableSignal<ValueRow[]>, index: number): void {
    rows.update((current) => current.filter((_, at) => at !== index));
  }

  filters(): SearchFilters {
    const out: SearchFilters = {};
    const number = (value: string) => (value.trim() === '' ? null : Number(value.replace(',', '.')));
    if (this.q().trim()) out.q = this.q().trim();
    if (this.sport()) out.sport = this.sport();
    if (this.position()) out.position = this.position();
    if (this.ageGroup()) out.age_group = this.ageGroup();
    if (this.gender()) out.gender = this.gender();
    if (this.region()) out.region = this.region();
    if (this.level()) out.level = this.level();
    if (this.hasVideo()) out.has_video = true;
    const valued = (rows: ValueRow[]) =>
      rows.filter((row) => number(row.value) !== null).map((row) => ({ key: row.key, op: row.op, value: number(row.value) as number }));
    if (valued(this.tests()).length) out.tests = valued(this.tests());
    if (valued(this.statRows()).length) out.stats = valued(this.statRows());
    const minimums = (rows: ValueRow[]) =>
      rows.filter((row) => number(row.value) !== null).map((row) => ({ key: row.key, min: number(row.value) as number }));
    if (minimums(this.percentileRows()).length) out.percentiles = minimums(this.percentileRows());
    if (minimums(this.areaRows()).length) out.areas = minimums(this.areaRows()) as Array<{ key: RatingAreaKey; min: number }>;
    if (number(this.potentialMin()) !== null) out.potential_min = number(this.potentialMin()) as number;
    if (this.recommendation()) out.recommendation = this.recommendation() as Recommendation;
    return out;
  }

  run(): void {
    this.busy.set(true);
    this.scouting.search(this.filters()).subscribe({
      next: (page) => {
        this.results.set(page.results);
        this.searched.set(true);
        this.busy.set(false);
        this.picked.set(new Set([...this.picked()].filter((id) => page.results.some((row) => row.id === id))));
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Those filters did not work.'), 'danger');
      },
    });
  }

  clear(): void {
    this.q.set('');
    this.chooseSport('');
    this.ageGroup.set('');
    this.gender.set('');
    this.region.set('');
    this.level.set('');
    this.hasVideo.set(false);
    this.areaRows.set([]);
    this.potentialMin.set('');
    this.recommendation.set('');
    this.activeSaved.set('');
  }

  loadSavedSearch(row: SavedSearch): void {
    const filters = row.filters;
    const toRows = (items: Array<{ key: string; op?: FilterOp; value?: number; min?: number }> | undefined, op: FilterOp) =>
      (items ?? []).map((item) => ({ key: item.key, op: item.op ?? op, value: String(item.value ?? item.min ?? '') }));
    this.activeSaved.set(row.id);
    this.q.set(filters.q ?? '');
    this.ageGroup.set(filters.age_group ?? '');
    this.gender.set(filters.gender ?? '');
    this.region.set(filters.region ?? '');
    this.level.set(filters.level ?? '');
    this.hasVideo.set(!!filters.has_video);
    this.areaRows.set(toRows(filters.areas, 'gte'));
    this.potentialMin.set(filters.potential_min !== undefined ? String(filters.potential_min) : '');
    this.recommendation.set(filters.recommendation ?? '');
    this.chooseSport(filters.sport ?? '', () => {
      this.position.set(filters.position ?? '');
      this.tests.set(toRows(filters.tests, 'lt'));
      this.statRows.set(toRows(filters.stats, 'gte'));
      this.percentileRows.set(toRows(filters.percentiles, 'gte'));
      this.run();
    });
  }

  async saveSearch(): Promise<void> {
    const alert = await this.alerts.create({
      header: 'Save this search',
      message: 'We tell you (in the app and by push) when a new player matches. Tap the bell on a saved search to turn alerts off.',
      inputs: [{ name: 'name', type: 'text', placeholder: 'e.g. Fast U21 strikers' }],
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        { text: 'Save', handler: (data: { name?: string }) => this.persist(data?.name ?? '', true) },
      ],
    });
    await alert.present();
  }

  private persist(name: string, alerts: boolean): void {
    if (!name.trim()) {
      void this.toast('Name the search to save it.', 'danger');
      return;
    }
    this.scouting.saveSearch({ name: name.trim(), filters: this.filters(), alerts }).subscribe({
      next: async (row) => {
        this.loadSaved();
        this.activeSaved.set(row.id);
        await this.toast(`Saved "${row.name}": ${row.matches} match now. We will tell you about new ones.`, 'success');
      },
      error: async (err: unknown) => this.toast(extractErrorMessage(err, 'Could not save the search.'), 'danger'),
    });
  }

  toggleAlerts(row: SavedSearch): void {
    this.scouting.updateSavedSearch(row.id, { alerts: !row.alerts }).subscribe({ next: () => this.loadSaved() });
  }

  removeSaved(row: SavedSearch): void {
    this.scouting.deleteSavedSearch(row.id).subscribe({ next: () => this.loadSaved() });
  }

  togglePick(id: string): void {
    this.picked.update((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else if (next.size < 4) next.add(id);
      return next;
    });
  }

  compare(): void {
    void this.router.navigate(['/tabs/scouting/compare'], {
      queryParams: { profiles: [...this.picked()].join(','), sport: this.sport() || undefined },
    });
  }

  open(id: string): void {
    void this.router.navigate(['/tabs/scouting/players', id]);
  }

  facts(row: SearchResult): string[] {
    const info = this.sportInfo();
    const label = (key: string) =>
      info?.physical_tests.find((item) => item.key === key)?.label ?? info?.match_stats.find((item) => item.key === key)?.label ?? key;
    const out: string[] = [];
    if (row.facts.level) out.push(`${this.catalog()?.competition_levels?.find((item) => item.key === row.facts.level)?.label ?? row.facts.level} level`);
    if (row.facts.has_video) out.push('Video');
    for (const [key, value] of Object.entries(row.facts.tests ?? {})) out.push(`${label(key)} ${value}`);
    for (const [key, value] of Object.entries(row.facts.stats ?? {})) out.push(`${label(key)} ${value}`);
    for (const [key, value] of Object.entries(row.facts.percentiles ?? {})) out.push(`${label(key)} ${Math.round(value)}th pct`);
    if (row.facts.potential) out.push(`Potential ${row.facts.potential}`);
    if (row.facts.recommendation) out.push(this.catalog()?.rating_recommendations?.find((item) => item.key === row.facts.recommendation)?.label ?? '');
    return out.filter(Boolean);
  }

  async shortlist(row: SearchResult): Promise<void> {
    this.scouting.shortlists(row.id).subscribe({
      next: async (lists) => {
        const alert = await this.alerts.create({
          header: `Shortlist ${row.name}`,
          inputs: [
            ...lists.map((list) => ({
              type: 'radio' as const,
              label: `${list.name}${list.has_profile ? ' (already on it)' : ''}`,
              value: list.id,
              disabled: !!list.has_profile,
            })),
            { type: 'radio' as const, label: '+ New shortlist…', value: '__new__' },
          ],
          buttons: [
            { text: 'Cancel', role: 'cancel' },
            { text: 'Add', handler: (value: string) => this.addTo(value, row) },
          ],
        });
        await alert.present();
      },
      error: async (err: unknown) => this.toast(extractErrorMessage(err, 'Join a scouting organisation to use shortlists.'), 'danger'),
    });
  }

  private async addTo(value: string, row: SearchResult): Promise<void> {
    if (value === '__new__') {
      const prompt = await this.alerts.create({
        header: 'New shortlist',
        inputs: [{ name: 'name', type: 'text', placeholder: 'e.g. Winter trials' }],
        buttons: [
          { text: 'Cancel', role: 'cancel' },
          {
            text: 'Create',
            handler: (data: { name?: string }) => {
              this.scouting.createShortlist({ name: (data.name ?? '').trim() }).subscribe({
                next: (list) => this.addTo(list.id, row),
                error: async (err: unknown) => this.toast(extractErrorMessage(err, 'Could not create it.'), 'danger'),
              });
            },
          },
        ],
      });
      await prompt.present();
      return;
    }
    if (!value) return;
    this.scouting.addToShortlist(value, row.id).subscribe({
      next: async () => this.toast(`${row.name} added to the shortlist.`, 'success'),
      error: async (err: unknown) => this.toast(extractErrorMessage(err, 'Could not add them.'), 'danger'),
    });
  }

  private async toast(message: string, color: 'success' | 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2600, position: 'top' });
    await toast.present();
  }
}
