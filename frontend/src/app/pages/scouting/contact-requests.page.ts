import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import {
  IonBackButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonSpinner,
  IonTitle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';

import { extractErrorMessage } from '../../core/error-message';
import type { ContactRequestRow } from '../../core/scouting.models';
import { ScoutingService } from '../../core/scouting.service';

/** Contact requests: players and guardians answer them; scouts follow what they sent. */
@Component({
  selector: 'fm-contact-requests',
  standalone: true,
  imports: [DatePipe, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './scouting.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button defaultHref="/tabs/scouting" /></ion-buttons>
        <ion-title>Contact requests</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (isScout()) {
        <div class="segmented section" role="tablist">
          <button type="button" role="tab" [class.on]="box() === 'received'" (click)="show('received')">Received</button>
          <button type="button" role="tab" [class.on]="box() === 'sent'" (click)="show('sent')">Sent by my organisation</button>
        </div>
      }
      <p class="lede">
        @if (box() === 'received') {
          Scouts ask here before they get in touch. Your phone number and email are never shared; if you say yes,
          you decide what to tell them.
        } @else {
          Requests to players go to their guardian when the player is under 18.
        }
      </p>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else {
        @for (row of rows(); track row.id) {
          <section class="fm-card section request">
            <header>
              <strong>{{ box() === 'received' ? row.organisation.name : row.player.name }}</strong>
              <span class="badge" [class.ok]="row.status === 'accepted'" [class.warn]="row.status === 'pending'">{{ row.status_label }}</span>
            </header>
            <small>
              {{ row.created_at | date: 'd MMM y' }} · from {{ row.requested_by?.name }}{{ row.to_guardian ? ' · about ' + row.player.name + ' (sent to you as guardian)' : '' }}
            </small>
            <p class="body">{{ row.message }}</p>
            @if (row.response) {
              <p class="reply"><strong>Reply:</strong> {{ row.response }}</p>
            }
            @if (row.can_respond) {
              <textarea rows="2" [value]="replies()[row.id] ?? ''" (input)="reply(row.id, $any($event.target).value)" placeholder="Optional message, e.g. 'Message my coach on the app'"></textarea>
              <div class="actions-row">
                <button type="button" class="btn" [disabled]="busy()" (click)="answer(row, true)">Accept</button>
                <button type="button" class="btn ghost" [disabled]="busy()" (click)="answer(row, false)">Decline</button>
              </div>
            }
            @if (box() === 'sent' && row.status === 'pending') {
              <button type="button" class="btn ghost small" (click)="withdraw(row)">Withdraw</button>
            }
          </section>
        } @empty {
          <p class="lede">No requests yet.</p>
        }
      }
    </ion-content>
  `,
  styles: [
    `
      .request header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 8px;
      }
      .request small {
        color: var(--ion-color-medium);
      }
      .body {
        margin: 8px 0;
        line-height: 1.5;
      }
      .reply {
        margin: 0 0 8px;
        padding: 8px 10px;
        border-radius: 10px;
        background: var(--ion-color-light);
        color: var(--ion-color-light-contrast);
        font-size: 0.88rem;
      }
      textarea {
        width: 100%;
        padding: 8px 10px;
        border: 1px solid var(--ion-color-step-200, #d7d8da);
        border-radius: 10px;
        font: inherit;
        background: var(--ion-background-color, #fff);
        color: var(--ion-text-color);
      }
      .actions-row {
        display: flex;
        gap: 8px;
        margin-top: 8px;
      }
    `,
  ],
})
export class ContactRequestsPage {
  private readonly scouting = inject(ScoutingService);
  private readonly toasts = inject(ToastController);

  readonly box = signal<'received' | 'sent'>('received');
  readonly rows = signal<ContactRequestRow[]>([]);
  readonly replies = signal<Partial<Record<string, string>>>({});
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly isScout = computed(() =>
    (this.scouting.me()?.role_keys ?? []).some((role) => role === 'scout' || role === 'scout_admin'),
  );

  ionViewWillEnter(): void {
    if (!this.scouting.me()) this.scouting.loadMe().subscribe();
    this.show(this.box());
  }

  show(box: 'received' | 'sent'): void {
    this.box.set(box);
    this.loading.set(true);
    this.scouting.contactRequests(box).subscribe({
      next: (rows) => {
        this.rows.set(rows);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  reply(id: string, value: string): void {
    this.replies.update((current) => ({ ...current, [id]: value }));
  }

  answer(row: ContactRequestRow, accept: boolean): void {
    this.busy.set(true);
    this.scouting.respondToContact(row.id, accept, (this.replies()[row.id] ?? '').trim()).subscribe({
      next: async () => {
        this.busy.set(false);
        this.show(this.box());
        await this.toast(accept ? `${row.organisation.name} has been told you are happy to talk.` : 'Declined.', 'success');
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not answer.'), 'danger');
      },
    });
  }

  withdraw(row: ContactRequestRow): void {
    this.scouting.withdrawContact(row.id).subscribe({ next: () => this.show('sent') });
  }

  private async toast(message: string, color: 'success' | 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2600, position: 'top' });
    await toast.present();
  }
}
