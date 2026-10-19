import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';

import type { QueuedRating, RatingDraft } from './scouting.models';
import { ScoutingService } from './scouting.service';

const STORAGE_KEY = 'fm.scoutRatings.queue';
const RETRY_MS = 30_000;

export type SyncState = 'idle' | 'syncing' | 'offline' | 'error';

/**
 * Ratings saved on the phone first, then sent when there is signal.
 *
 * Every rating gets its client_id when it is saved, so sending it again after a
 * dropped connection never stores it twice: the server answers "duplicate".
 */
@Injectable({ providedIn: 'root' })
export class RatingQueueService {
  private readonly scouting = inject(ScoutingService);
  private timer: ReturnType<typeof setInterval> | null = null;

  readonly queue = signal<QueuedRating[]>(this.read());
  readonly state = signal<SyncState>('idle');
  readonly lastSynced = signal<string | null>(null);
  readonly pending = computed(() => this.queue().filter((row) => row.status === 'pending').length);
  readonly rejected = computed(() => this.queue().filter((row) => row.status === 'rejected'));

  constructor() {
    if (typeof window !== 'undefined') {
      window.addEventListener('online', () => this.sync());
      window.addEventListener('offline', () => this.state.set('offline'));
      this.timer = setInterval(() => this.sync(), RETRY_MS);
    }
    queueMicrotask(() => this.sync());
  }

  static newId(): string {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char) => {
      const random = (Math.random() * 16) | 0;
      return (char === 'x' ? random : (random & 0x3) | 0x8).toString(16);
    });
  }

  /** Keep the rating on the phone, then try to send it straight away. */
  save(draft: RatingDraft, playerName: string): void {
    this.write([
      ...this.queue(),
      { draft, player_name: playerName, status: 'pending', queued_at: new Date().toISOString() },
    ]);
    this.sync();
  }

  discard(clientId: string): void {
    this.write(this.queue().filter((row) => row.draft.client_id !== clientId));
  }

  sync(): void {
    const pending = this.queue().filter((row) => row.status === 'pending');
    if (!pending.length || this.state() === 'syncing') {
      if (!pending.length && this.state() !== 'syncing') this.state.set('idle');
      return;
    }
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      this.state.set('offline');
      return;
    }
    this.state.set('syncing');
    this.scouting.syncRatings(pending.map((row) => row.draft)).subscribe({
      next: ({ results }) => {
        const outcome = new Map(results.map((row) => [row.client_id, row]));
        this.write(
          this.queue().flatMap((row) => {
            const result = outcome.get(row.draft.client_id);
            if (!result) return [row];
            if (result.status === 'rejected') return [{ ...row, status: 'rejected' as const, error: result.error }];
            return []; // created or already stored: done
          }),
        );
        this.lastSynced.set(new Date().toISOString());
        this.state.set('idle');
      },
      error: (err: unknown) => {
        // No signal or the server is busy: keep everything and try again later.
        const offline = err instanceof HttpErrorResponse && err.status === 0;
        this.state.set(offline ? 'offline' : 'error');
      },
    });
  }

  private read(): QueuedRating[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? (JSON.parse(raw) as QueuedRating[]) : [];
    } catch {
      return [];
    }
  }

  private write(rows: QueuedRating[]): void {
    this.queue.set(rows);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(rows));
    } catch {
      // Storage full or blocked: the queue still lives in memory for this session.
    }
  }
}
