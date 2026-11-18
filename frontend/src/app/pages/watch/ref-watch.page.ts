import { CommonModule } from '@angular/common';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { IonContent } from '@ionic/angular/standalone';
import { firstValueFrom } from 'rxjs';

import { environment } from '../../environments/environment';

type WatchSide = { id: string; name: string; score: string; is_home: boolean };
type WatchCategory = {
  id: string;
  code: string;
  name: string;
  affects_score: boolean;
  points: string;
};
type QueuedEvent = {
  client_uuid: string;
  side: string;
  scoring_category: string;
  quantity: string;
  minute: number | null;
  second: number | null;
  period: string;
  note: string;
  created_at: string;
};

const DB_NAME = 'fm-watch';
const STORE = 'queue';

@Component({
  selector: 'fm-ref-watch',
  standalone: true,
  imports: [CommonModule, IonContent],
  template: `
    <ion-content [fullscreen]="true" class="watch-shell">
      <div class="pad">
        <header>
          <p class="sync" [attr.data-state]="syncState()">{{ syncLabel() }}</p>
          <h1>{{ home()?.name || 'Home' }} {{ home()?.score || '0' }} – {{ away()?.score || '0' }} {{ away()?.name || 'Away' }}</h1>
          <p class="phase">{{ state()?.phase || state()?.status || '—' }}</p>
        </header>

        @if (!token()) {
          <section class="pair">
            <label>
              Pair code
              <input
                inputmode="numeric"
                maxlength="6"
                [value]="codeInput()"
                (input)="onCode($event)"
              />
            </label>
            <button type="button" class="big" (click)="claim()">Pair watch</button>
            @if (error()) {
              <p class="err">{{ error() }}</p>
            }
          </section>
        } @else {
          <section class="clock">
            <button type="button" class="big" (click)="phase('kick_off')">Start</button>
            <button type="button" class="big ghost" (click)="phase('end_half')">End period</button>
          </section>

          <section class="score">
            <button type="button" class="big home" (click)="plus(home())">Home +</button>
            <button type="button" class="big away" (click)="plus(away())">Away +</button>
          </section>

          @if (picker().length) {
            <section class="picker">
              @for (cat of picker(); track cat.id) {
                <button type="button" (click)="pickCategory(cat)">{{ cat.name }}</button>
              }
            </section>
          }

          <section class="cards">
            <button type="button" class="big warn" (click)="startCard('yellow-card')">Yellow</button>
            <button type="button" class="big danger" (click)="startCard('red-card')">Red</button>
          </section>

          @if (needNumber()) {
            <section class="pad-num">
              <p>Shirt</p>
              <div class="keys">
                @for (n of digits; track n) {
                  <button type="button" (click)="typeDigit(n)">{{ n }}</button>
                }
                <button type="button" (click)="clearDigit()">C</button>
                <button type="button" (click)="confirmCard()">OK</button>
              </div>
              <p class="num">{{ shirt() || '—' }}</p>
            </section>
          }

          <button type="button" class="link" (click)="flush()">Sync now</button>
          @if (error()) {
            <p class="err">{{ error() }}</p>
          }
        }
      </div>
    </ion-content>
  `,
  styles: [
    `
      :host {
        --watch-bg: #0b0d10;
        --watch-fg: #f4f6f8;
        --watch-accent: #f5c518;
        --watch-home: #2ecc71;
        --watch-away: #3498db;
        --watch-danger: #e74c3c;
      }
      .watch-shell {
        --background: var(--watch-bg);
        color: var(--watch-fg);
        font-family: 'Segoe UI', system-ui, sans-serif;
      }
      .pad {
        padding: 10px;
        display: grid;
        gap: 10px;
      }
      header h1 {
        margin: 4px 0;
        font-size: 1.1rem;
        line-height: 1.2;
        text-align: center;
      }
      .phase,
      .sync {
        text-align: center;
        margin: 0;
        font-size: 0.75rem;
        opacity: 0.8;
      }
      .sync[data-state='offline'] {
        color: var(--watch-danger);
      }
      .sync[data-state='ok'] {
        color: var(--watch-home);
      }
      .big {
        width: 100%;
        min-height: 52px;
        border: 0;
        border-radius: 12px;
        font-size: 1.15rem;
        font-weight: 800;
        background: var(--watch-accent);
        color: #111;
      }
      .big.ghost {
        background: #222831;
        color: var(--watch-fg);
      }
      .big.home {
        background: var(--watch-home);
      }
      .big.away {
        background: var(--watch-away);
        color: #fff;
      }
      .big.warn {
        background: #f1c40f;
      }
      .big.danger {
        background: var(--watch-danger);
        color: #fff;
      }
      .score,
      .clock,
      .cards {
        display: grid;
        gap: 8px;
        grid-template-columns: 1fr 1fr;
      }
      .picker {
        display: grid;
        gap: 6px;
      }
      .picker button,
      .keys button {
        min-height: 40px;
        border-radius: 10px;
        border: 1px solid #333;
        background: #1a1f26;
        color: var(--watch-fg);
        font-weight: 700;
      }
      .keys {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 6px;
      }
      .pair input {
        width: 100%;
        min-height: 48px;
        font-size: 1.4rem;
        letter-spacing: 0.3em;
        text-align: center;
        border-radius: 10px;
        border: 1px solid #444;
        background: #111;
        color: #fff;
      }
      .err {
        color: var(--watch-danger);
        text-align: center;
      }
      .link {
        background: transparent;
        border: 0;
        color: var(--watch-accent);
        text-decoration: underline;
      }
      .num {
        text-align: center;
        font-size: 1.6rem;
        font-weight: 800;
      }
    `,
  ],
})
export class RefWatchPage implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;
  private wake: WakeLockSentinel | null = null;
  private flushTimer: number | null = null;

  readonly matchId = signal('');
  readonly token = signal('');
  readonly codeInput = signal('');
  readonly state = signal<{
    status?: string;
    phase?: string;
    sides?: WatchSide[];
    categories?: WatchCategory[];
    sport?: string;
    competition_id?: string;
  } | null>(null);
  readonly syncState = signal<'ok' | 'pending' | 'offline'>('pending');
  readonly error = signal('');
  readonly picker = signal<WatchCategory[]>([]);
  readonly pendingSide = signal<WatchSide | null>(null);
  readonly needNumber = signal(false);
  readonly shirt = signal('');
  readonly cardCode = signal('');
  readonly digits = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'];

  home = () => this.state()?.sides?.find((side) => side.is_home) ?? this.state()?.sides?.[0] ?? null;
  away = () =>
    this.state()?.sides?.find((side) => !side.is_home) ?? this.state()?.sides?.[1] ?? null;

  syncLabel(): string {
    if (this.syncState() === 'offline') return 'Offline — queueing';
    if (this.syncState() === 'pending') return 'Syncing…';
    return 'Synced';
  }

  async ngOnInit(): Promise<void> {
    this.matchId.set(this.route.snapshot.paramMap.get('matchId') ?? '');
    const code = this.route.snapshot.queryParamMap.get('code') ?? '';
    if (code) this.codeInput.set(code);
    const saved = localStorage.getItem(this.tokenKey());
    if (saved) this.token.set(saved);
    await this.openDb();
    await this.requestWakeLock();
    window.addEventListener('online', this.onOnline);
    this.flushTimer = window.setInterval(() => void this.flush(), 15000);
    if (this.token()) {
      await this.refresh();
      await this.flush();
    } else if (code) {
      await this.claim();
    }
  }

  ngOnDestroy(): void {
    window.removeEventListener('online', this.onOnline);
    if (this.flushTimer) window.clearInterval(this.flushTimer);
    void this.wake?.release();
  }

  private readonly onOnline = () => void this.flush();

  private tokenKey(): string {
    return `fm-watch-token:${this.matchId()}`;
  }

  onCode(event: Event): void {
    const value = String((event.target as HTMLInputElement).value || '')
      .replace(/\D/g, '')
      .slice(0, 6);
    this.codeInput.set(value);
  }

  async claim(): Promise<void> {
    this.error.set('');
    try {
      const body = await firstValueFrom(
        this.http.post<{ token: string }>(`${this.base}/fixtures/${this.matchId()}/watch/claim`, {
          code: this.codeInput(),
        }),
      );
      this.token.set(body.token);
      localStorage.setItem(this.tokenKey(), body.token);
      await this.refresh();
      this.buzz([40, 40, 40]);
    } catch {
      this.error.set('Could not pair. Check the code.');
    }
  }

  async refresh(): Promise<void> {
    try {
      const state = await firstValueFrom(
        this.http.get(`${this.base}/fixtures/${this.matchId()}/watch/state`, {
          headers: this.authHeaders(),
        }),
      );
      this.state.set(state as never);
      this.syncState.set(navigator.onLine ? 'ok' : 'offline');
    } catch {
      this.syncState.set('offline');
    }
  }

  async phase(action: string): Promise<void> {
    // Clock actions still go through the phone API when online; offline they wait in notes.
    if (!navigator.onLine) {
      this.error.set('Clock changes need a connection. Score events still queue offline.');
      this.buzz([80]);
      return;
    }
    try {
      const competitionId = this.state()?.competition_id;
      if (!competitionId) throw new Error('missing competition');
      await firstValueFrom(
        this.http.post(
          `${this.base}/competitions/${competitionId}/fixtures/${this.matchId()}/phase`,
          { action },
          { headers: this.authHeaders() },
        ),
      );
      await this.refresh();
      if (action === 'end_half' || action === 'end_game') this.buzz([120, 60, 120]);
    } catch {
      this.error.set('Could not change the period.');
    }
  }

  plus(side: WatchSide | null): void {
    if (!side) return;
    const cats = (this.state()?.categories ?? []).filter((cat) => cat.affects_score);
    const sport = (this.state()?.sport || '').toLowerCase();
    if (sport.includes('rugby') && cats.length > 1) {
      this.pendingSide.set(side);
      this.picker.set(cats.slice(0, 6));
      return;
    }
    const goal = cats.find((cat) => cat.code === 'goal') ?? cats[0];
    if (!goal) return;
    void this.queueEvent(side, goal);
  }

  pickCategory(cat: WatchCategory): void {
    const side = this.pendingSide();
    this.picker.set([]);
    if (!side) return;
    void this.queueEvent(side, cat);
  }

  startCard(code: string): void {
    this.cardCode.set(code);
    this.shirt.set('');
    this.needNumber.set(true);
  }

  typeDigit(n: string): void {
    this.shirt.set((this.shirt() + n).slice(0, 2));
  }

  clearDigit(): void {
    this.shirt.set('');
  }

  async confirmCard(): Promise<void> {
    const cat = (this.state()?.categories ?? []).find((item) => item.code === this.cardCode());
    const side = this.home();
    this.needNumber.set(false);
    if (!cat || !side) return;
    await this.queueEvent(side, cat, `Shirt ${this.shirt()}`);
    this.shirt.set('');
  }

  private async queueEvent(side: WatchSide, cat: WatchCategory, note = ''): Promise<void> {
    const event: QueuedEvent = {
      client_uuid: crypto.randomUUID(),
      side: side.id,
      scoring_category: cat.id,
      quantity: '1',
      minute: null,
      second: null,
      period: this.state()?.phase || '',
      note,
      created_at: new Date().toISOString(),
    };
    await this.putQueue(event);
    this.syncState.set(navigator.onLine ? 'pending' : 'offline');
    this.buzz([30]);
    await this.flush();
    await this.refresh();
  }

  async flush(): Promise<void> {
    if (!this.token() || !navigator.onLine) {
      this.syncState.set(this.token() ? 'offline' : 'pending');
      return;
    }
    const events = await this.allQueue();
    if (!events.length) {
      this.syncState.set('ok');
      return;
    }
    try {
      const result = await firstValueFrom(
        this.http.post<{ created: string[]; skipped: string[] }>(
          `${this.base}/fixtures/${this.matchId()}/watch/sync`,
          { events },
          { headers: this.authHeaders() },
        ),
      );
      const done = new Set([...(result.created || []), ...(result.skipped || [])]);
      for (const event of events) {
        if (done.has(event.client_uuid) || result.created?.length || result.skipped?.length) {
          // Drop anything the server acknowledged by uuid presence in either list after remap.
        }
      }
      // Clear all pushed events: server dedupes by uuid on retry.
      for (const event of events) await this.deleteQueue(event.client_uuid);
      this.syncState.set('ok');
      this.error.set('');
    } catch {
      this.syncState.set('offline');
    }
  }

  private authHeaders(): HttpHeaders {
    return new HttpHeaders({ Authorization: `Bearer ${this.token()}` });
  }

  private buzz(pattern: number[]): void {
    try {
      navigator.vibrate?.(pattern);
    } catch {
      /* ignore */
    }
  }

  private async requestWakeLock(): Promise<void> {
    try {
      this.wake = (await navigator.wakeLock?.request('screen')) ?? null;
    } catch {
      this.wake = null;
    }
  }

  private db: IDBDatabase | null = null;

  private openDb(): Promise<void> {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: 'client_uuid' });
      };
      req.onsuccess = () => {
        this.db = req.result;
        resolve();
      };
      req.onerror = () => reject(req.error);
    });
  }

  private putQueue(event: QueuedEvent): Promise<void> {
    return new Promise((resolve, reject) => {
      const tx = this.db!.transaction(STORE, 'readwrite');
      tx.objectStore(STORE).put(event);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }

  private allQueue(): Promise<QueuedEvent[]> {
    return new Promise((resolve, reject) => {
      const tx = this.db!.transaction(STORE, 'readonly');
      const req = tx.objectStore(STORE).getAll();
      req.onsuccess = () => resolve(req.result as QueuedEvent[]);
      req.onerror = () => reject(req.error);
    });
  }

  private deleteQueue(id: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const tx = this.db!.transaction(STORE, 'readwrite');
      tx.objectStore(STORE).delete(id);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    });
  }
}
