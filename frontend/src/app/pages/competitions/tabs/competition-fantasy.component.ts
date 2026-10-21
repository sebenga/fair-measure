import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  input,
  signal,
} from '@angular/core';
import {
  AlertController,
  IonButton,
  IonIcon,
  IonInput,
  IonSegment,
  IonSegmentButton,
  IonLabel,
  IonSpinner,
  ToastController,
} from '@ionic/angular/standalone';

import { ApiService } from '../../../core/api.service';
import { AuthService } from '../../../core/auth.service';
import { extractErrorMessage } from '../../../core/error-message';
import type {
  CompetitionDetail,
  FantasyOverview,
  FantasyPlayer,
  FantasySlot,
  FantasyStandingRow,
  FantasyTeam,
} from '../../../core/models';

type View = 'team' | 'players' | 'league';

interface DraftPick {
  player: FantasyPlayer;
  slot: FantasySlot;
  is_starter: boolean;
  is_captain: boolean;
  is_vice: boolean;
  bench_order: number;
}

const SQUAD: Record<FantasySlot, number> = { GKP: 2, DEF: 5, MID: 5, FWD: 3 };
const XI: Record<FantasySlot, number> = { GKP: 1, DEF: 4, MID: 4, FWD: 2 };
const SLOTS: FantasySlot[] = ['GKP', 'DEF', 'MID', 'FWD'];
const KITS: Array<[string, string]> = [
  ['#c81e1e', '#fff'],
  ['#1d4ed8', '#fff'],
  ['#111827', '#fff'],
  ['#f8fafc', '#111827'],
  ['#15803d', '#fff'],
  ['#eab308', '#111827'],
  ['#7c3aed', '#fff'],
  ['#ea580c', '#fff'],
  ['#0f766e', '#fff'],
  ['#be185d', '#fff'],
];

@Component({
  selector: 'fm-competition-fantasy',
  standalone: true,
  imports: [IonButton, IonIcon, IonInput, IonSegment, IonSegmentButton, IonLabel, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="subnav">
      <ion-segment [value]="view()" (ionChange)="setView($any($event).detail.value)">
        <ion-segment-button value="team"><ion-label>My Team</ion-label></ion-segment-button>
        <ion-segment-button value="players"><ion-label>Players</ion-label></ion-segment-button>
        <ion-segment-button value="league"><ion-label>League</ion-label></ion-segment-button>
      </ion-segment>
    </div>

    @if (loading()) {
      <div class="centered"><ion-spinner name="crescent" /></div>
    } @else if (error()) {
      <div class="fm-empty">
        <ion-icon name="alert-circle-outline" aria-hidden="true" />
        <h3>Fantasy unavailable</h3>
        <p>{{ error() }}</p>
        <ion-button fill="clear" (click)="load()">Try again</ion-button>
      </div>
    } @else if (playerCount() < 15) {
      <div class="fm-empty">
        <ion-icon name="shirt-outline" aria-hidden="true" />
        <h3>Not enough players yet</h3>
        <p>
          Fantasy needs at least 15 rostered players across the clubs. Add squads in Setup, then
          pick your XI here.
        </p>
      </div>
    } @else {
      @switch (view()) {
        @case ('team') {
          <section class="status">
            <button type="button" class="team-name" (click)="rename()">
              <strong>{{ teamName() }}</strong>
              <small>Tap to rename</small>
            </button>
            <div class="meters">
              <span>
                <em>{{ pickedCount() }}/15</em>
                selected
              </span>
              <span>
                <em>£{{ remaining() }}m</em>
                remaining
              </span>
              <span>
                <em>{{ saved()?.points ?? '0' }}</em>
                pts
              </span>
              @if (saved()?.rank) {
                <span>
                  <em>{{ saved()?.rank }}</em>
                  of {{ saved()?.managers }}
                </span>
              }
            </div>
          </section>

          <div class="pitch" aria-label="Fantasy pitch">
            @for (row of pitchRows(); track row.slot) {
              <div class="line" [attr.data-slot]="row.slot">
                @for (cell of row.cells; track cell.key) {
                  @if (cell.pick; as pick) {
                    <button
                      type="button"
                      class="shirt"
                      [class.captain]="pick.is_captain"
                      [style.--kit]="kit(pick.player.team_id)[0]"
                      [style.--kit-ink]="kit(pick.player.team_id)[1]"
                      (click)="actOn(pick)"
                    >
                      <i class="badge" aria-hidden="true">
                        @if (pick.is_captain) {
                          C
                        } @else if (pick.is_vice) {
                          V
                        }
                      </i>
                      <span class="kit">{{ numberOf(pick.player) }}</span>
                      <span class="who">
                        <b>{{ shortName(pick.player.name) }}</b>
                        <small>£{{ pick.player.price }}m · {{ pick.player.points }} pts</small>
                      </span>
                    </button>
                  } @else {
                    <button type="button" class="empty" (click)="openPicker(row.slot, false)">
                      <ion-icon name="add-outline" aria-hidden="true" />
                      <small>{{ row.label }}</small>
                    </button>
                  }
                }
              </div>
            }
          </div>

          <section class="bench">
            <h3>Substitutes</h3>
            <div class="bench-row">
              @for (cell of benchCells(); track cell.key) {
                @if (cell.pick; as pick) {
                  <button type="button" class="shirt bench-shirt" (click)="actOn(pick)">
                    <span class="kit slim">{{ numberOf(pick.player) }}</span>
                    <span class="who">
                      <b>{{ shortName(pick.player.name) }}</b>
                      <small>{{ pick.slot }} · £{{ pick.player.price }}m</small>
                    </span>
                  </button>
                } @else if (cell.slot) {
                  <button type="button" class="empty slim" (click)="openPicker(cell.slot, true)">
                    <ion-icon name="add-outline" aria-hidden="true" />
                    <small>{{ cell.slot }}</small>
                  </button>
                }
              }
            </div>
          </section>

          <div class="actions">
            <ion-button fill="outline" (click)="autoPick()" [disabled]="busy()">Auto Pick</ion-button>
            <ion-button fill="outline" color="medium" (click)="reset()" [disabled]="busy() || !picks().length">
              Reset
            </ion-button>
            <ion-button (click)="save()" [disabled]="busy() || !dirty()">
              {{ busy() ? 'Saving…' : 'Save team' }}
            </ion-button>
          </div>
          <p class="hint">
            15 players, £100m, max {{ overview()?.rules?.max_per_club ?? 3 }} from one club.
            Captain scores double. Points come from this competition’s recorded match stats.
          </p>
        }
        @case ('players') {
          <div class="market-bar">
            <ion-input
              [value]="query()"
              placeholder="Search players or clubs"
              (ionInput)="query.set($any($event).detail.value ?? '')"
            />
            <div class="slot-filters">
              <button type="button" [class.on]="marketSlot() === ''" (click)="marketSlot.set('')">All</button>
              @for (slot of slots; track slot) {
                <button type="button" [class.on]="marketSlot() === slot" (click)="marketSlot.set(slot)">
                  {{ slot }}
                </button>
              }
            </div>
          </div>
          <ul class="market">
            @for (player of visibleMarket(); track player.id) {
              <li>
                <span class="pos">{{ player.slot }}</span>
                <span class="info">
                  <strong>{{ player.name }}</strong>
                  <small>{{ player.team_name }} · {{ player.points }} pts</small>
                </span>
                <em>£{{ player.price }}m</em>
                @if (pickedIds().has(player.id)) {
                  <ion-button size="small" fill="clear" color="medium" (click)="removePlayer(player.id)">
                    Remove
                  </ion-button>
                } @else {
                  <ion-button size="small" (click)="addPlayer(player)" [disabled]="!canAdd(player)">
                    Add
                  </ion-button>
                }
              </li>
            } @empty {
              <li class="none">No players match that search.</li>
            }
          </ul>
        }
        @case ('league') {
          @if (standings().length === 0) {
            <div class="fm-empty">
              <ion-icon name="trophy-outline" aria-hidden="true" />
              <h3>No managers yet</h3>
              <p>Save a squad on My Team to join this competition’s fantasy league.</p>
            </div>
          } @else {
            <div class="table-wrap fm-card">
              <table>
                <thead>
                  <tr>
                    <th class="pos">#</th>
                    <th>Team</th>
                    <th>GW</th>
                    <th class="pts">Pts</th>
                  </tr>
                </thead>
                <tbody>
                  @for (row of standings(); track row.team_id) {
                    <tr [class.mine]="row.manager.id === me()">
                      <td class="pos">{{ row.rank }}</td>
                      <td>
                        <strong>{{ row.name }}</strong>
                        <small>{{ row.manager.display_name }}</small>
                      </td>
                      <td>{{ row.event_points }}</td>
                      <td class="pts">{{ row.points }}</td>
                    </tr>
                  }
                </tbody>
              </table>
            </div>
            @if (overview()?.rules; as rules) {
              <section class="scoring-guide fm-card">
                <h3>How fantasy points are earned</h3>
                <ul>
                  @for (item of rules.scoring; track item.label) {
                    <li><strong>{{ item.label }}</strong> {{ item.points }}</li>
                  }
                </ul>
              </section>
            }
          }
        }
      }
    }

    @if (picker(); as pickState) {
      <div class="sheet" role="dialog" aria-label="Pick a player">
        <div class="sheet-card">
          <header>
            <h3>Pick a {{ pickState.slot }}</h3>
            <ion-button fill="clear" (click)="closePicker()">Close</ion-button>
          </header>
          <ion-input
            [value]="query()"
            placeholder="Search"
            (ionInput)="query.set($any($event).detail.value ?? '')"
          />
          <ul class="market">
            @for (player of pickerMarket(); track player.id) {
              <li>
                <span class="pos">{{ player.slot }}</span>
                <span class="info">
                  <strong>{{ player.name }}</strong>
                  <small>{{ player.team_name }} · £{{ player.price }}m · {{ player.points }} pts</small>
                </span>
                <ion-button size="small" (click)="choose(player)" [disabled]="!canAdd(player, pickState.replaceId)">
                  Select
                </ion-button>
              </li>
            } @empty {
              <li class="none">No free {{ pickState.slot }} players left.</li>
            }
          </ul>
        </div>
      </div>
    }
  `,
  styles: [
    `
      .subnav,
      .status,
      .actions,
      .hint,
      .market-bar,
      .bench {
        margin: 12px 16px 0;
      }

      .centered {
        display: grid;
        place-items: center;
        padding: 64px 0;
      }

      .status {
        display: grid;
        gap: 10px;
      }

      .team-name {
        display: grid;
        gap: 2px;
        padding: 0;
        border: 0;
        background: none;
        color: inherit;
        font: inherit;
        text-align: left;
        cursor: pointer;
      }

      .team-name small {
        color: var(--ion-color-medium);
      }

      .meters {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }

      .meters span {
        display: grid;
        padding: 8px 10px;
        border-radius: 12px;
        background: var(--ion-color-step-50, #f4f5f8);
        font-size: 0.72rem;
        color: var(--ion-color-medium);
      }

      .meters em {
        font-style: normal;
        font-size: 1rem;
        font-weight: 750;
        color: var(--ion-text-color);
      }

      .pitch {
        position: relative;
        margin: 12px 16px 0;
        padding: 18px 10px 22px;
        border-radius: 20px;
        background:
          radial-gradient(circle at 50% 50%, rgb(255 255 255 / 10%) 0 18%, transparent 19%),
          linear-gradient(#2f8f46, #1f6b34 48%, #2f8f46);
        box-shadow: inset 0 0 0 3px rgb(255 255 255 / 18%);
        display: grid;
        gap: 14px;
        min-height: 420px;
      }

      .line {
        display: flex;
        justify-content: center;
        flex-wrap: wrap;
        gap: 10px;
      }

      .shirt,
      .empty {
        width: 76px;
        padding: 0;
        border: 0;
        background: none;
        color: inherit;
        font: inherit;
        cursor: pointer;
      }

      .shirt {
        display: grid;
        justify-items: center;
        gap: 4px;
        position: relative;
      }

      .kit {
        display: grid;
        place-items: center;
        width: 52px;
        height: 56px;
        border-radius: 10px 10px 14px 14px;
        background: var(--kit, #1d4ed8);
        color: var(--kit-ink, #fff);
        font-weight: 800;
        box-shadow: 0 6px 14px rgb(0 0 0 / 25%);
      }

      .kit.slim,
      .empty.slim {
        width: 44px;
        height: 48px;
      }

      .who {
        display: grid;
        width: 100%;
        padding: 4px 4px 5px;
        border-radius: 8px;
        background: rgb(15 23 42 / 82%);
        color: #fff;
        text-align: center;
      }

      .who b {
        font-size: 0.68rem;
        line-height: 1.2;
      }

      .who small {
        font-size: 0.58rem;
        opacity: 0.85;
      }

      .badge {
        position: absolute;
        top: -4px;
        right: 8px;
        width: 18px;
        height: 18px;
        border-radius: 999px;
        background: #f5c400;
        color: #111;
        font-size: 0.62rem;
        font-weight: 800;
        font-style: normal;
        display: grid;
        place-items: center;
      }

      .empty {
        display: grid;
        justify-items: center;
        gap: 6px;
        color: rgb(255 255 255 / 85%);
      }

      .empty ion-icon {
        width: 48px;
        height: 48px;
        border-radius: 999px;
        border: 2px dashed rgb(255 255 255 / 70%);
        padding: 10px;
      }

      .empty.slim ion-icon {
        width: 40px;
        height: 40px;
      }

      .bench h3 {
        margin: 0 0 8px;
        font-size: 0.92rem;
      }

      .bench-row {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        padding-bottom: 4px;
      }

      .bench-shirt {
        width: 92px;
      }

      .actions {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }

      .hint {
        color: var(--ion-color-medium);
        font-size: 0.86rem;
        line-height: 1.45;
        margin-bottom: 24px;
      }

      .slot-filters {
        display: flex;
        gap: 6px;
        margin-top: 8px;
      }

      .slot-filters button {
        padding: 6px 10px;
        border: 0;
        border-radius: 999px;
        background: var(--ion-color-step-100, #e9ecf1);
        color: inherit;
        font: inherit;
        font-size: 0.78rem;
        font-weight: 650;
      }

      .slot-filters button.on {
        background: var(--ion-color-primary);
        color: var(--ion-color-primary-contrast);
      }

      .market {
        list-style: none;
        margin: 8px 16px 24px;
        padding: 0;
      }

      .market li {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px 4px;
        border-bottom: 1px solid var(--ion-color-step-100, #e9ecf1);
      }

      .market .pos {
        width: 38px;
        font-size: 0.72rem;
        font-weight: 800;
        color: var(--ion-color-primary);
      }

      .market .info {
        flex: 1 1 auto;
        display: grid;
        min-width: 0;
      }

      .market small {
        color: var(--ion-color-medium);
      }

      .market em {
        font-style: normal;
        font-weight: 700;
      }

      .market .none {
        color: var(--ion-color-medium);
        border: 0;
      }

      .table-wrap {
        overflow-x: auto;
      }

      table {
        width: 100%;
        border-collapse: collapse;
      }

      th,
      td {
        padding: 8px 6px;
        text-align: left;
      }

      th.pos,
      td.pos,
      th.pts,
      td.pts {
        text-align: right;
      }

      td small {
        display: block;
        color: var(--ion-color-medium);
      }

      tr.mine {
        background: color-mix(in srgb, var(--ion-color-primary) 12%, transparent);
      }

      .scoring-guide ul {
        margin: 0;
        padding-left: 18px;
      }

      .scoring-guide li + li {
        margin-top: 4px;
      }

      .sheet {
        position: fixed;
        inset: 0;
        z-index: 40;
        display: grid;
        align-items: end;
        background: rgb(15 23 42 / 45%);
      }

      .sheet-card {
        max-height: 78vh;
        overflow: auto;
        padding: 12px 16px 24px;
        border-radius: 20px 20px 0 0;
        background: var(--ion-background-color, #fff);
      }

      .sheet-card header {
        display: flex;
        align-items: center;
        justify-content: space-between;
      }

      .sheet-card h3 {
        margin: 0;
      }

      .sheet-card .market {
        margin: 8px 0 0;
      }
    `,
  ],
})
export class CompetitionFantasyComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly alerts = inject(AlertController);
  private readonly toasts = inject(ToastController);

  readonly competition = input.required<CompetitionDetail>();
  readonly slots = SLOTS;

  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);
  readonly view = signal<View>('team');
  readonly overview = signal<FantasyOverview | null>(null);
  readonly market = signal<FantasyPlayer[]>([]);
  readonly standings = signal<FantasyStandingRow[]>([]);
  readonly picks = signal<DraftPick[]>([]);
  readonly teamName = signal('My Team');
  readonly query = signal('');
  readonly marketSlot = signal<FantasySlot | ''>('');
  readonly picker = signal<{ slot: FantasySlot; bench: boolean; replaceId?: string } | null>(null);
  readonly savedSnapshot = signal('');

  readonly playerCount = computed(() => this.overview()?.player_count ?? 0);
  readonly saved = computed(() => this.overview()?.team ?? null);
  readonly pickedCount = computed(() => this.picks().length);
  readonly pickedIds = computed(() => new Set(this.picks().map((pick) => pick.player.id)));
  readonly remaining = computed(() => {
    const used = this.picks().reduce((sum, pick) => sum + Number(pick.player.price), 0);
    return (100 - used).toFixed(1);
  });
  readonly dirty = computed(() => this.snapshotOf(this.picks(), this.teamName()) !== this.savedSnapshot());
  readonly me = computed(() => this.auth.user()?.id ?? '');

  readonly pitchRows = computed(() =>
    SLOTS.map((slot) => {
      const starters = this.picks().filter((pick) => pick.slot === slot && pick.is_starter);
      const empties = Math.max(0, XI[slot] - starters.length);
      const cells: Array<{ key: string; pick: DraftPick | null }> = starters.map((pick) => ({
        key: pick.player.id,
        pick,
      }));
      for (let i = 0; i < empties; i += 1) {
        cells.push({ key: `${slot}-empty-${i}`, pick: null });
      }
      return { slot, label: slot, cells };
    }),
  );

  readonly benchCells = computed(() => {
    const cells: Array<{ key: string; pick: DraftPick | null; slot: FantasySlot }> = [];
    for (const slot of SLOTS) {
      const sitting = this.picks().filter((pick) => pick.slot === slot && !pick.is_starter);
      sitting.forEach((pick) => cells.push({ key: pick.player.id, pick, slot }));
      const empties = Math.max(0, SQUAD[slot] - XI[slot] - sitting.length);
      for (let i = 0; i < empties; i += 1) {
        cells.push({ key: `${slot}-bench-${i}`, pick: null, slot });
      }
    }
    return cells;
  });

  readonly visibleMarket = computed(() => {
    const needle = this.query().trim().toLowerCase();
    const slot = this.marketSlot();
    return this.market().filter((player) => {
      if (slot && player.slot !== slot) return false;
      if (!needle) return true;
      return (
        player.name.toLowerCase().includes(needle) || player.team_name.toLowerCase().includes(needle)
      );
    });
  });

  readonly pickerMarket = computed(() => {
    const state = this.picker();
    if (!state) return [];
    const needle = this.query().trim().toLowerCase();
    return this.market().filter((player) => {
      if (player.slot !== state.slot) return false;
      if (this.pickedIds().has(player.id) && player.id !== state.replaceId) return false;
      if (!needle) return true;
      return (
        player.name.toLowerCase().includes(needle) || player.team_name.toLowerCase().includes(needle)
      );
    });
  });

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    const id = this.competition().id;
    this.api.getFantasy(id).subscribe({
      next: (overview) => {
        this.overview.set(overview);
        this.applyTeam(overview.team);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err));
        this.loading.set(false);
      },
    });
    this.api.fantasyPlayers(id).subscribe({
      next: (body) => this.market.set(body.players),
      error: () => undefined,
    });
    this.api.fantasyStandings(id).subscribe({
      next: (body) => this.standings.set(body.rows),
      error: () => undefined,
    });
  }

  setView(value: string | undefined): void {
    if (value === 'team' || value === 'players' || value === 'league') this.view.set(value);
  }

  kit(teamId: string): [string, string] {
    let hash = 0;
    for (let i = 0; i < teamId.length; i += 1) hash = (hash * 31 + teamId.charCodeAt(i)) >>> 0;
    return KITS[hash % KITS.length];
  }

  numberOf(player: FantasyPlayer): string {
    if (player.number != null) return String(player.number);
    const parts = player.name.trim().split(/\s+/);
    return (parts.at(-1) ?? player.name).slice(0, 1).toUpperCase();
  }

  shortName(name: string): string {
    const parts = name.trim().split(/\s+/);
    return parts.at(-1) ?? name;
  }

  openPicker(slot: FantasySlot, bench: boolean, replaceId?: string): void {
    this.query.set('');
    this.picker.set({ slot, bench, replaceId });
  }

  closePicker(): void {
    this.picker.set(null);
  }

  canAdd(player: FantasyPlayer, replacing?: string): boolean {
    const others = this.picks().filter((pick) => pick.player.id !== replacing);
    if (others.some((pick) => pick.player.id === player.id)) return false;
    if (others.filter((pick) => pick.slot === player.slot).length >= SQUAD[player.slot]) return false;
    const clubLimit = this.overview()?.rules.max_per_club ?? 3;
    if (others.filter((pick) => pick.player.team_id === player.team_id).length >= clubLimit) {
      return false;
    }
    const used = others.reduce((sum, pick) => sum + Number(pick.player.price), 0);
    return used + Number(player.price) <= 100.0001;
  }

  addPlayer(player: FantasyPlayer, bench = false): void {
    if (!this.canAdd(player)) {
      void this.toast('That pick breaks the budget, club limit, or position quota.', 'danger');
      return;
    }
    const starters = this.picks().filter((pick) => pick.is_starter).length;
    const slotStarters = this.picks().filter((pick) => pick.slot === player.slot && pick.is_starter).length;
    const start = !bench && starters < 11 && slotStarters < XI[player.slot];
    this.picks.update((list) => [
      ...list,
      {
        player,
        slot: player.slot,
        is_starter: start,
        is_captain: list.length === 0,
        is_vice: list.length === 1,
        bench_order: start ? 0 : 1,
      },
    ]);
  }

  choose(player: FantasyPlayer): void {
    const state = this.picker();
    if (!state) return;
    if (state.replaceId) this.removePlayer(state.replaceId);
    this.addPlayer(player, state.bench);
    this.closePicker();
  }

  removePlayer(playerId: string): void {
    this.picks.update((list) => {
      const next = list.filter((pick) => pick.player.id !== playerId);
      if (!next.some((pick) => pick.is_captain) && next[0]) next[0].is_captain = true;
      if (!next.some((pick) => pick.is_vice) && next.find((pick) => !pick.is_captain)) {
        const vice = next.find((pick) => !pick.is_captain);
        if (vice) vice.is_vice = true;
      }
      return [...next];
    });
  }

  async actOn(pick: DraftPick): Promise<void> {
    const alert = await this.alerts.create({
      header: pick.player.name,
      subHeader: `${pick.player.team_name} · £${pick.player.price}m`,
      buttons: [
        { text: 'Captain', handler: () => this.setRole(pick.player.id, 'captain') },
        { text: 'Vice-captain', handler: () => this.setRole(pick.player.id, 'vice') },
        {
          text: pick.is_starter ? 'Move to bench' : 'Start',
          handler: () => this.toggleStart(pick),
        },
        { text: 'Replace', handler: () => this.openPicker(pick.slot, !pick.is_starter, pick.player.id) },
        { text: 'Remove', role: 'destructive', handler: () => this.removePlayer(pick.player.id) },
        { text: 'Cancel', role: 'cancel' },
      ],
    });
    await alert.present();
  }

  setRole(playerId: string, role: 'captain' | 'vice'): void {
    this.picks.update((list) =>
      list.map((pick) => {
        const selected = pick.player.id === playerId;
        return {
          ...pick,
          is_captain: selected ? role === 'captain' : role === 'captain' ? false : pick.is_captain,
          is_vice: selected ? role === 'vice' : role === 'vice' ? false : pick.is_vice,
        };
      }),
    );
  }

  toggleStart(pick: DraftPick): void {
    const starters = this.picks().filter((item) => item.is_starter).length;
    if (!pick.is_starter && starters >= 11) {
      void this.toast('Bench someone first — you already have 11 starters.', 'medium');
      return;
    }
    this.picks.update((list) =>
      list.map((item) =>
        item.player.id === pick.player.id ? { ...item, is_starter: !item.is_starter } : item,
      ),
    );
  }

  async rename(): Promise<void> {
    const alert = await this.alerts.create({
      header: 'Team name',
      inputs: [{ name: 'name', type: 'text', value: this.teamName(), attributes: { maxlength: '80' } }],
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        {
          text: 'Save',
          handler: (data: { name?: string }) => {
            const name = String(data?.name ?? '').trim();
            if (name) this.teamName.set(name);
          },
        },
      ],
    });
    await alert.present();
  }

  reset(): void {
    this.picks.set([]);
  }

  autoPick(): void {
    this.busy.set(true);
    this.api.autoPickFantasy(this.competition().id).subscribe({
      next: (body) => {
        const byId = new Map(this.market().map((player) => [player.id, player]));
        const next: DraftPick[] = [];
        for (const raw of body.picks) {
          const player = byId.get(raw.player);
          if (!player) continue;
          next.push({
            player,
            slot: raw.slot as FantasySlot,
            is_starter: raw.is_starter,
            is_captain: raw.is_captain,
            is_vice: raw.is_vice,
            bench_order: raw.bench_order,
          });
        }
        this.picks.set(next);
        this.busy.set(false);
        void this.toast('Squad filled. Save it when you are happy.', 'success');
      },
      error: (err: unknown) => {
        this.busy.set(false);
        void this.toast(extractErrorMessage(err, 'Could not auto-pick a squad.'), 'danger');
      },
    });
  }

  save(): void {
    this.busy.set(true);
    this.api
      .saveFantasy(this.competition().id, {
        name: this.teamName(),
        picks: this.picks().map((pick) => ({
          player: pick.player.id,
          slot: pick.slot,
          is_starter: pick.is_starter,
          is_captain: pick.is_captain,
          is_vice: pick.is_vice,
          bench_order: pick.bench_order,
        })),
      })
      .subscribe({
        next: (overview) => {
          this.overview.set(overview);
          this.applyTeam(overview.team);
          this.busy.set(false);
          void this.toast(
            overview.team?.complete ? 'Team saved.' : 'Draft saved. Fill 15 players to complete it.',
            'success',
          );
          this.api.fantasyStandings(this.competition().id).subscribe({
            next: (body) => this.standings.set(body.rows),
          });
        },
        error: (err: unknown) => {
          this.busy.set(false);
          void this.toast(extractErrorMessage(err, 'Could not save that team.'), 'danger');
        },
      });
  }

  private applyTeam(team: FantasyTeam | null): void {
    const name = team?.name || `${this.auth.user()?.display_name || 'My'}'s XI`;
    this.teamName.set(name);
    const picks = (team?.picks ?? []).map((player) => ({
      player,
      slot: player.slot,
      is_starter: !!player.is_starter,
      is_captain: !!player.is_captain,
      is_vice: !!player.is_vice,
      bench_order: player.bench_order ?? 0,
    }));
    this.picks.set(picks);
    this.savedSnapshot.set(this.snapshotOf(picks, name));
  }

  private snapshotOf(picks: DraftPick[], name: string): string {
    return JSON.stringify({
      name,
      picks: picks.map((pick) => ({
        id: pick.player.id,
        slot: pick.slot,
        s: pick.is_starter,
        c: pick.is_captain,
        v: pick.is_vice,
      })),
    });
  }

  private async toast(message: string, color: string): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2400 });
    await toast.present();
  }
}
