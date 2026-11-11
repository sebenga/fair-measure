import { Injectable, computed, effect, inject, signal, untracked } from '@angular/core';
import { ToastController } from '@ionic/angular/standalone';
import { Router } from '@angular/router';
import { Subject } from 'rxjs';

import { ApiService } from './api.service';
import { AuthService } from './auth.service';
import { extractErrorMessage } from './error-message';
import type { CompetitionInvite, TeamPick } from './models';
import { RealtimeService, userRoom } from './realtime.service';

/**
 * Invites waiting for the signed-in person's answer, shared by the notification bell
 * and My leagues so answering in one place clears it everywhere.
 */
@Injectable({ providedIn: 'root' })
export class InvitesService {
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly realtime = inject(RealtimeService);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastController);

  readonly pending = signal<CompetitionInvite[]>([]);
  /** Team places offered to this person; accepting one also joins the competition. */
  readonly teamPicks = signal<TeamPick[]>([]);
  readonly count = computed(() => this.pending().length + this.teamPicks().length);
  readonly answering = signal<string | null>(null);
  /** Something new arrived for this person: a fresh notification or invite. */
  readonly arrived = new Subject<void>();

  private room: string | null = null;

  constructor() {
    effect(() => {
      const user = this.auth.user();
      untracked(() => this.follow(user?.id ?? null));
    });
    this.realtime.on('notification.created').subscribe(() => {
      this.refresh();
      this.arrived.next();
    });
  }

  refresh(): void {
    if (!this.auth.isAuthenticated()) {
      this.pending.set([]);
      this.teamPicks.set([]);
      return;
    }
    this.api.myInvites().subscribe({
      next: (rows) => this.pending.set(rows),
      error: () => undefined,
    });
    this.api.myPendingTeamPicks().subscribe({
      next: (rows) => this.teamPicks.set(rows),
      error: () => undefined,
    });
  }

  answerPick(pick: TeamPick, answer: 'accept' | 'decline'): void {
    if (this.answering()) return;
    this.answering.set(pick.id);
    const request =
      answer === 'accept'
        ? this.api.acceptTeamPick(pick.competition, pick.id)
        : this.api.declineTeamPick(pick.competition, pick.id);
    request.subscribe({
      next: async () => {
        this.answering.set(null);
        this.teamPicks.update((rows) => rows.filter((row) => row.id !== pick.id));
        this.arrived.next();
        await this.say(
          answer === 'accept' ? `You joined ${pick.team_name}.` : 'Team invite declined.',
          'success',
        );
        if (answer === 'accept') void this.router.navigate(['/tabs/competitions', pick.competition]);
      },
      error: async (err: unknown) => {
        this.answering.set(null);
        this.refresh();
        await this.say(extractErrorMessage(err, 'Could not answer that invite.'), 'danger');
      },
    });
  }

  private async say(message: string, color: 'success' | 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2600 });
    await toast.present();
  }

  accept(invite: CompetitionInvite): void {
    this.answer(invite, 'accept');
  }

  decline(invite: CompetitionInvite): void {
    this.answer(invite, 'decline');
  }

  private answer(invite: CompetitionInvite, answer: 'accept' | 'decline'): void {
    if (this.answering()) return;
    this.answering.set(invite.id);
    this.api.answerInvite(invite.id, answer).subscribe({
      next: async () => {
        this.answering.set(null);
        this.pending.update((rows) => rows.filter((row) => row.id !== invite.id));
        this.arrived.next();
        await this.say(
          answer === 'accept'
            ? `You joined ${invite.competition_name}.`
            : `You declined the invite to ${invite.competition_name}.`,
          'success',
        );
        if (answer === 'accept') {
          void this.router.navigate(['/tabs/competitions', invite.competition]);
        }
      },
      error: async (err: unknown) => {
        this.answering.set(null);
        this.refresh();
        await this.say(extractErrorMessage(err, 'Could not answer that invite.'), 'danger');
      },
    });
  }

  /** Listens on the person's own channel, so a new invite shows up without a reload. */
  private follow(userId: string | null): void {
    if (this.room) this.realtime.unsubscribe(this.room);
    this.room = userId ? userRoom(userId) : null;
    if (this.room) this.realtime.subscribe(this.room);
    this.refresh();
  }
}
