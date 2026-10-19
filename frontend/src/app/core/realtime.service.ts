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

  /** Rooms we want to be in, re-sent after every reconnect. */
  private readonly desiredRooms = new Set<string>();

  readonly connected = signal(false);

  constructor() {
    this.destroyRef.onDestroy(() => this.disconnect());
  }

  connect(): void {
    if (this.socket?.connected) return;

    const token = this.auth.getAccessToken();
    if (!token) return;

    this.socket = io(environment.realtimeUrl, {
      transports: ['websocket'],
      auth: { token },
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 10_000,
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
    this.desiredRooms.clear();
    this.connected.set(false);
  }
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
