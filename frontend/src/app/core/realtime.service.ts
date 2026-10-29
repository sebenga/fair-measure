import { HttpClient } from '@angular/common/http';
import { DestroyRef, Injectable, inject, signal } from '@angular/core';
import { Observable, Subject, filter, map } from 'rxjs';
import { io, type Socket } from 'socket.io-client';

import { environment } from '../../environments/environment';
import { AuthService } from './auth.service';

export interface RealtimeMessage<T = Record<string, unknown>> {
  event: string;
  payload: T;
  ts: number;
}

/** Every event the gateway can relay. Mirrors the names Django publishes. */
const RELAYED_EVENTS = [
  'competition.updated',
  'fixture.created',
  'fixture.updated',
  'fixture.deleted',
  'fixture.live',
  'fixture.completed',
  'fixtures.generated',
  'score.recorded',
  'score.corrected',
  'score.removed',
  'standings.updated',
  'standings.stale',
  'post.created',
  'post.deleted',
  'comment.created',
  'media.updated',
  'games.medals',
] as const;

@Injectable({ providedIn: 'root' })
export class RealtimeService {
  private readonly auth = inject(AuthService);
  private readonly destroyRef = inject(DestroyRef);

  private socket: Socket | null = null;
  private readonly messages = new Subject<RealtimeMessage>();
  private readonly http = inject(HttpClient);
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private pollSince = 0;
  private polling = false;
  private pollingDisabled = false;
  private seenEvents = new Set<string>();

  /** Rooms we want to be in, re-sent after every reconnect. */
  private readonly desiredRooms = new Set<string>();

  readonly connected = signal(false);

  constructor() {
    this.destroyRef.onDestroy(() => this.disconnect());
  }

  connect(): void {
    if (!environment.realtimeUrl) {
      this.startPolling();
      return;
    }
    if (this.socket?.connected) return;

    const token = this.auth.getAccessToken();
    if (!token) return;

    this.socket = io(environment.realtimeUrl, {
      path: '/socket.io',
      transports: ['websocket', 'polling'],
      auth: { token },
      reconnection: true,
      reconnectionAttempts: Infinity,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 15_000,
      randomizationFactor: 0.4,
    });

    this.socket.on('connect', () => {
      this.connected.set(true);
      // Room membership lives on the server and is lost on disconnect, so
      // re-subscribe rather than assuming the gateway remembered us.
      if (this.desiredRooms.size > 0) {
        this.socket?.emit('subscribe', [...this.desiredRooms]);
      }
    });

    this.socket.on('disconnect', () => this.connected.set(false));

    this.socket.on('connect_error', (error: Error) => {
      this.connected.set(false);
      // An expired access token is the usual cause; refresh and try once more.
      if (error.message.toLowerCase().includes('token')) {
        this.auth.refresh().subscribe({
          next: () => this.reconnectWithFreshToken(),
          error: () => this.disconnect(),
        });
      }
    });

    for (const event of RELAYED_EVENTS) {
      this.socket.on(event, (message: RealtimeMessage) => this.messages.next(message));
    }
  }

  private reconnectWithFreshToken(): void {
    const token = this.auth.getAccessToken();
    if (!this.socket || !token) return;
    this.socket.auth = { token };
    this.socket.connect();
  }

  subscribe(...rooms: string[]): void {
    for (const room of rooms) {
      this.desiredRooms.add(room);
    }
    this.connect();
    if (this.socket?.connected) {
      this.socket.emit('subscribe', rooms);
    }
  }

  unsubscribe(...rooms: string[]): void {
    for (const room of rooms) {
      this.desiredRooms.delete(room);
    }
    this.socket?.emit('unsubscribe', rooms);
  }

  /** Stream of every relayed event. */
  events(): Observable<RealtimeMessage> {
    return this.messages.asObservable();
  }

  /** Stream narrowed to one event name, with the payload unwrapped. */
  on<T = Record<string, unknown>>(event: string): Observable<T> {
    return this.messages.asObservable().pipe(
      filter((message) => message.event === event),
      map((message) => message.payload as T),
    );
  }

  /** Stream narrowed to several event names. */
  onAny<T = Record<string, unknown>>(events: string[]): Observable<RealtimeMessage<T>> {
    return this.messages
      .asObservable()
      .pipe(filter((message) => events.includes(message.event))) as Observable<
      RealtimeMessage<T>
    >;
  }

  disconnect(): void {
    this.socket?.removeAllListeners();
    this.socket?.disconnect();
    this.socket = null;
    this.stopPolling();
    this.desiredRooms.clear();
    this.connected.set(false);
  }

  // Builds without a gateway (the single Render service) poll Django for the
  // same events instead of holding a socket.
  private startPolling(): void {
    if (this.pollTimer !== null || this.pollingDisabled) return;
    this.pollTimer = setInterval(() => this.poll(), POLL_EVERY_MS);
    this.poll();
  }

  private stopPolling(): void {
    if (this.pollTimer !== null) clearInterval(this.pollTimer);
    this.pollTimer = null;
    this.pollSince = 0;
    this.seenEvents.clear();
  }

  private poll(): void {
    if (this.polling || document.hidden) return;
    const rooms = [...this.desiredRooms];
    this.polling = true;
    const params: Record<string, string> = { rooms: rooms.join(',') };
    // Overlap the window: an event is stamped before its transaction commits.
    if (this.pollSince > 0) params['since'] = String(this.pollSince - POLL_OVERLAP_MS);
    this.http
      .get<PolledEvents>(`${environment.apiBaseUrl}/realtime/events`, { params })
      .subscribe({
        next: (response) => {
          this.polling = false;
          if (!response.enabled) {
            this.pollingDisabled = true;
            this.stopPolling();
            this.connected.set(false);
            return;
          }
          this.connected.set(true);
          this.pollSince = response.now;
          for (const event of response.events) {
            if (this.seenEvents.has(event.id)) continue;
            this.seenEvents.add(event.id);
            this.messages.next({ event: event.event, payload: event.payload, ts: event.ts });
          }
          if (this.seenEvents.size > 1000) {
            this.seenEvents = new Set([...this.seenEvents].slice(-500));
          }
        },
        error: () => {
          this.polling = false;
          this.connected.set(false);
        },
      });
  }
}

const POLL_EVERY_MS = 5_000;
const POLL_OVERLAP_MS = 5_000;

interface PolledEvents {
  enabled: boolean;
  now: number;
  events: { id: string; event: string; payload: Record<string, unknown>; ts: number }[];
}

export function competitionRoom(id: string): string {
  return `competition:${id}`;
}

export function gamesRoom(id: string): string {
  return `games:${id}`;
}

export function fixtureRoom(id: string): string {
  return `fixture:${id}`;
}
