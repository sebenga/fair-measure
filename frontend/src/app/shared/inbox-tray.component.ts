import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { IonButton, IonIcon, IonPopover } from '@ionic/angular/standalone';

import { ApiService } from '../core/api.service';
import { InvitesService } from '../core/invites.service';
import type { AppNotification, CompetitionInvite } from '../core/models';

@Component({
  selector: 'fm-inbox-tray',
  standalone: true,
  imports: [DatePipe, IonButton, IonIcon, IonPopover],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="bell-wrap">
      <ion-button fill="clear" (click)="toggle($event)" [attr.aria-expanded]="open()">
        <ion-icon
          slot="icon-only"
          [name]="unread() ? 'notifications' : 'notifications-outline'"
          aria-label="Notifications"
        />
      </ion-button>
      @if (waiting()) {
        <span class="dot" aria-hidden="true">{{ waiting() > 9 ? '9+' : waiting() }}</span>
      }
    </div>

    <!-- A popover is drawn above the page; inside the header it would be clipped. -->
    <ion-popover
      class="inbox-popover"
      [isOpen]="open()"
      [event]="openedBy"
      side="bottom"
      alignment="end"
      (didDismiss)="open.set(false)"
    >
      <ng-template>
      <div class="sheet" role="dialog" aria-label="Notifications">
        <header>
          <strong>Notifications</strong>
          @if (unread()) {
            <button type="button" (click)="markAll()">Mark all read</button>
          }
        </header>
        @if (invites.count()) {
          <section class="invites" aria-label="Invitations">
            <p class="section">Invitations</p>
            @for (invite of invites.pending(); track invite.id) {
              <article class="invite">
                <span class="kind">{{ invite.competition_is_private ? 'Private competition' : 'Competition' }}</span>
                <strong>{{ invite.invited_by_name || 'An organiser' }} invited you to {{ invite.competition_name }}</strong>
                <small>Join as {{ roleWords(invite) }}.</small>
                <div class="answer">
                  <button
                    type="button"
                    class="accept"
                    [disabled]="invites.answering() === invite.id"
                    (click)="accept(invite)"
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    class="decline"
                    [disabled]="invites.answering() === invite.id"
                    (click)="invites.decline(invite)"
                  >
                    Decline
                  </button>
                </div>
              </article>
            }
            @for (pick of invites.teamPicks(); track pick.id) {
              <article class="invite">
                <span class="kind">Team</span>
                <strong>{{ pick.team_name }} picked you in {{ pick.competition_name }}</strong>
                <small>Accept to join the team and the competition.</small>
                <div class="answer">
                  <button
                    type="button"
                    class="accept"
                    [disabled]="invites.answering() === pick.id"
                    (click)="open.set(false); invites.answerPick(pick, 'accept')"
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    class="decline"
                    [disabled]="invites.answering() === pick.id"
                    (click)="invites.answerPick(pick, 'decline')"
                  >
                    Decline
                  </button>
                </div>
              </article>
            }
          </section>
        }
        @if (items().length === 0) {
          @if (!invites.count()) {
            <p class="empty">Nothing waiting. Invites, match scores, scout contact and league news land here.</p>
          }
        } @else {
          <ul>
            @for (item of items(); track item.id) {
              <li [class.unread]="!item.read_at">
                <button type="button" (click)="openItem(item)">
                  <span class="kind">{{ label(item.kind) }}</span>
                  <strong>{{ item.title }}</strong>
                  @if (item.body) {
                    <small>{{ item.body }}</small>
                  }
                  <time>{{ item.created_at | date: 'MMM d, HH:mm' }}</time>
                </button>
              </li>
            }
          </ul>
        }
      </div>
      </ng-template>
    </ion-popover>
  `,
  styles: [
    `
      :host {
        position: relative;
        display: block;
      }

      .bell-wrap {
        position: relative;
      }

      .dot {
        position: absolute;
        top: 4px;
        right: 4px;
        min-width: 16px;
        height: 16px;
        padding: 0 4px;
        border-radius: 999px;
        background: var(--ion-color-danger);
        color: #fff;
        font-size: 0.62rem;
        font-weight: 800;
        display: grid;
        place-items: center;
      }

      ion-popover.inbox-popover {
        --width: min(360px, calc(100vw - 24px));
        --max-height: 70vh;
        --border-radius: 16px;
        --box-shadow: var(--fm-shadow);
      }

      .sheet {
        max-height: 70vh;
        overflow: auto;
        padding: 12px 12px 8px;
        background: var(--ion-card-background, #fff);
      }

      header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;
      }

      header button {
        border: 0;
        background: none;
        color: var(--ion-color-primary);
        font: inherit;
        font-size: 0.8rem;
        font-weight: 650;
      }

      .empty {
        margin: 8px 0 12px;
        color: var(--ion-color-medium);
        font-size: 0.88rem;
        line-height: 1.45;
      }

      ul {
        list-style: none;
        margin: 0;
        padding: 0;
      }

      li button {
        display: grid;
        gap: 2px;
        width: 100%;
        margin-bottom: 6px;
        padding: 10px 10px;
        border: 0;
        border-radius: 12px;
        background: var(--ion-color-step-50, #f4f5f8);
        color: inherit;
        font: inherit;
        text-align: left;
        cursor: pointer;
      }

      li.unread button {
        background: color-mix(in srgb, var(--ion-color-primary) 12%, transparent);
      }

      .kind,
      time {
        font-size: 0.68rem;
        font-weight: 750;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: var(--ion-color-medium);
      }

      small {
        color: var(--ion-color-medium);
      }

      .section {
        margin: 0 0 6px;
        font-size: 0.7rem;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--ion-color-primary);
      }

      .invite {
        display: grid;
        gap: 2px;
        margin-bottom: 8px;
        padding: 10px;
        border: 1px solid color-mix(in srgb, var(--ion-color-primary) 35%, transparent);
        border-radius: 12px;
        background: color-mix(in srgb, var(--ion-color-primary) 8%, transparent);
        overflow-wrap: anywhere;
      }

      .answer {
        display: flex;
        gap: 8px;
        margin-top: 8px;
      }

      .answer button {
        flex: 1;
        min-height: 36px;
        border-radius: 999px;
        font: inherit;
        font-weight: 700;
        cursor: pointer;
      }

      .answer .accept {
        border: 0;
        background: var(--ion-color-primary);
        color: var(--ion-color-primary-contrast);
      }

      .answer .decline {
        border: 1px solid var(--ion-color-medium);
        background: transparent;
        color: var(--ion-text-color);
      }

      .answer button:disabled {
        opacity: 0.6;
      }
    `,
  ],
})
export class InboxTrayComponent {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  readonly invites = inject(InvitesService);

  readonly open = signal(false);
  readonly items = signal<AppNotification[]>([]);
  readonly unread = computed(() => this.items().filter((item) => !item.read_at).length);
  /**
   * The red count on the bell: unread news plus invites that still need an answer. An
   * invite's own notification is not counted again; the invite stands for it.
   */
  readonly waiting = computed(
    () =>
      this.items().filter((item) => !item.read_at && !INVITE_KINDS.has(item.kind)).length +
      this.invites.count(),
  );

  constructor() {
    this.refresh();
    this.invites.arrived.pipe(takeUntilDestroyed()).subscribe(() => this.refresh());
  }

  refresh(): void {
    this.invites.refresh();
    this.api.listNotifications({ page_size: 20 }).subscribe({
      next: (page) => this.items.set(page.results),
      error: () => undefined,
    });
  }

  /** The tap that opened the bell, so the popover points at it. */
  openedBy: Event | undefined;

  toggle(event: Event): void {
    this.openedBy = event;
    this.open.update((value) => !value);
    if (this.open()) this.refresh();
  }

  markAll(): void {
    this.api.markAllNotificationsRead().subscribe({
      next: () =>
        this.items.update((rows) =>
          rows.map((row) => ({ ...row, read_at: row.read_at ?? new Date().toISOString() })),
        ),
    });
  }

  openItem(item: AppNotification): void {
    if (!item.read_at) {
      this.api.markNotificationRead(item.id).subscribe({
        next: (updated) =>
          this.items.update((rows) => rows.map((row) => (row.id === updated.id ? updated : row))),
      });
    }
    this.open.set(false);
    void this.router.navigateByUrl(pathFor(item));
  }

  accept(invite: CompetitionInvite): void {
    this.open.set(false);
    this.invites.accept(invite);
  }

  roleWords(invite: CompetitionInvite): string {
    if (invite.role === 'admin') return 'an admin';
    if (invite.role === 'scorer') return 'a scorer';
    return 'a member';
  }

  label(kind: string): string {
    if (kind.includes('contact')) return 'Scout';
    if (kind.includes('guardian')) return 'Guardian';
    if (kind.includes('search')) return 'Alert';
    if (kind.startsWith('competition-invite')) return 'Invite';
    if (kind.includes('invite') || kind.includes('pick')) return 'Team';
    if (kind.includes('squad') || kind.includes('league')) return 'League';
    if (kind.includes('score') || kind.includes('fixture')) return 'Match';
    if (kind.includes('feed') || kind.includes('announce')) return 'News';
    return 'Update';
  }
}

const INVITE_KINDS = new Set(['competition-invite', 'team-invite']);

export function pathFor(item: AppNotification): string {
  const explicit = item.data?.['path'];
  if (typeof explicit === 'string' && explicit.startsWith('/')) return explicit;
  if (item.kind.includes('contact')) return '/tabs/scouting/requests';
  if (item.kind.includes('guardian')) return '/tabs/scouting/guardian';
  if (item.kind.includes('search')) return '/tabs/scouting/search';
  if (item.kind.includes('squad') || item.kind.includes('league.scout')) return '/tabs/scouting/leagues';
  if (item.competition) return `/tabs/competitions/${item.competition}`;
  return '/tabs/discover';
}
