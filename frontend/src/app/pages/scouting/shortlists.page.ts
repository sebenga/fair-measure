import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import {
  IonBackButton,
  IonButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonSpinner,
  IonTitle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';

import { extractErrorMessage } from '../../core/error-message';
import type { Shortlist, ShortlistEntry, ShortlistLogRow, ShortlistStatus } from '../../core/scouting.models';
import { ScoutingService } from '../../core/scouting.service';

const STATUSES: Array<{ key: ShortlistStatus; label: string }> = [
  { key: 'watching', label: 'Watching' },
  { key: 'contacted', label: 'Contacted' },
  { key: 'trial_booked', label: 'Trial booked' },
  { key: 'signed', label: 'Signed' },
  { key: 'rejected', label: 'Rejected' },
];

/** Shortlists per organisation; with an id, one shortlist with its players and log. */
@Component({
  selector: 'fm-shortlists',
  standalone: true,
  imports: [DatePipe, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonButton, IonIcon, IonContent, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './scouting.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button [defaultHref]="listId() ? '/tabs/scouting/shortlists' : '/tabs/scouting'" /></ion-buttons>
        <ion-title>{{ current()?.name ?? 'Shortlists' }}</ion-title>
        <ion-buttons slot="end">
          @if (current(); as list) {
            <ion-button (click)="openReport(list.id)">
              <ion-icon slot="start" name="document-text-outline" aria-hidden="true" />
              Report
            </ion-button>
          }
        </ion-buttons>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (listId() && current(); as list) {
        <p class="lede">{{ list.organisation.name }}{{ list.description ? ' · ' + list.description : '' }} · {{ list.count }} player(s)</p>
        <div class="segmented section" role="tablist">
          <button type="button" role="tab" [class.on]="tab() === 'players'" (click)="tab.set('players')">Players</button>
          <button type="button" role="tab" [class.on]="tab() === 'log'" (click)="showLog()">Change log</button>
        </div>
        @if (tab() === 'players') {
          @for (entry of list.entries ?? []; track entry.id) {
            <section class="fm-card section entry">
              <header>
                <button type="button" class="grow open" (click)="open(entry.profile.id)">
                  <strong>{{ entry.profile.name }}</strong>
                  <small>{{ entry.profile.sport?.primary_position_label ?? '' }}{{ entry.profile.age_group ? ' · ' + entry.profile.age_group : '' }}{{ entry.contact ? ' · contact ' + entry.contact.status : '' }}</small>
                </button>
                <button type="button" class="btn ghost small" (click)="remove(list, entry)">Remove</button>
              </header>
              <div class="chips">
                @for (status of statuses; track status.key) {
                  <button type="button" class="chip" [class.on]="entry.status === status.key" (click)="setStatus(list, entry, status.key)">{{ status.label }}</button>
                }
              </div>
              <label class="field top">
                Assigned scout
                <select (change)="assign(list, entry, $any($event.target).value)">
                  <option value="" [selected]="!entry.assigned_to">Nobody yet</option>
                  @for (scout of list.scouts ?? []; track scout.id) {
                    <option [value]="scout.id" [selected]="entry.assigned_to?.id === scout.id">{{ scout.name }}</option>
                  }
                </select>
              </label>
              @for (comment of entry.comments; track comment.id) {
                <p class="comment"><strong>{{ comment.author?.name }}</strong> · {{ comment.created_at | date: 'd MMM' }}<br />{{ comment.body }}</p>
              }
              <div class="comment-row">
                <input [value]="drafts()[entry.id] ?? ''" (input)="draft(entry.id, $any($event.target).value)" placeholder="Add a comment" />
                <button type="button" class="btn small" [disabled]="!(drafts()[entry.id] ?? '').trim()" (click)="comment(list, entry)">Post</button>
              </div>
            </section>
          } @empty {
            <p class="lede">No players yet. Add them from Talent search or a player's page.</p>
          }
        } @else {
          <ul class="list section">
            @for (row of log(); track row.id) {
              <li class="fm-card log-row">
                <strong>{{ row.action_label }} · {{ row.player }}</strong>
                <small>{{ row.actor?.name ?? 'Someone' }} · {{ row.created_at | date: 'd MMM y, HH:mm' }}</small>
                @if (describe(row); as text) {
                  <span>{{ text }}</span>
                }
              </li>
            } @empty {
              <li class="hint">Nothing changed yet.</li>
            }
          </ul>
        }
      } @else {
        <ul class="list section">
          @for (list of lists(); track list.id) {
            <li>
              <button type="button" class="fm-card list-card" (click)="openList(list.id)">
                <strong>{{ list.name }}</strong>
                <small>{{ list.organisation.name }} · {{ list.count }} player(s)</small>
                <span class="chips">
                  @for (status of statuses; track status.key) {
                    @if (list.statuses[status.key]) {
                      <span class="badge">{{ status.label }} {{ list.statuses[status.key] }}</span>
                    }
                  }
                </span>
              </button>
            </li>
          } @empty {
            <li class="lede">No shortlists yet.</li>
          }
        </ul>
        <form class="fm-card section" (submit)="create($event)">
          <h3>New shortlist</h3>
          <label class="field">Name<input [value]="name()" (input)="name.set($any($event.target).value)" placeholder="e.g. Winter trials" /></label>
          <label class="field">Description<input [value]="description()" (input)="description.set($any($event.target).value)" placeholder="Optional" /></label>
          <button type="submit" class="btn" [disabled]="!name().trim()">Create</button>
        </form>
      }
      <div style="height: 32px"></div>
    </ion-content>
  `,
  styles: [
    `
      .list-card {
        display: grid;
        gap: 4px;
        width: 100%;
        padding: 12px 14px;
        border: 0;
        color: inherit;
        font: inherit;
        text-align: left;
      }
      .list-card small,
      .open small,
      .log-row small {
        color: var(--ion-color-medium);
      }
      .entry header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
      }
      .open {
        display: grid;
        gap: 2px;
        border: 0;
        background: none;
        color: inherit;
        font: inherit;
        text-align: left;
      }
      .grow {
        flex: 1;
      }
      .field.top {
        margin-top: 10px;
      }
      .comment {
        margin: 8px 0 0;
        padding: 8px 10px;
        border-radius: 10px;
        background: var(--ion-color-light);
        font-size: 0.85rem;
      }
      .comment-row {
        display: flex;
        gap: 8px;
        margin-top: 8px;
      }
      .comment-row input {
        flex: 1;
        min-height: 38px;
        padding: 6px 10px;
        border: 1px solid var(--ion-color-step-200, #d7d8da);
        border-radius: 10px;
        font: inherit;
        background: var(--ion-background-color, #fff);
        color: var(--ion-text-color);
      }
      .log-row {
        display: grid;
        gap: 2px;
        padding: 10px 12px;
        font-size: 0.88rem;
      }
    `,
  ],
})
export class ShortlistsPage {
  private readonly scouting = inject(ScoutingService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastController);

  readonly statuses = STATUSES;
  readonly lists = signal<Shortlist[]>([]);

  openReport(id: string): void {
    void this.router.navigate(['/tabs/scouting/reports/shortlist'], { queryParams: { shortlist: id } });
  }
  readonly current = signal<Shortlist | null>(null);
  readonly log = signal<ShortlistLogRow[]>([]);
  readonly tab = signal<'players' | 'log'>('players');
  readonly loading = signal(true);
  readonly name = signal('');
  readonly description = signal('');
  readonly drafts = signal<Partial<Record<string, string>>>({});
  readonly listId = computed(() => this.route.snapshot.paramMap.get('id') ?? '');

  ionViewWillEnter(): void {
    this.load();
  }

  private load(): void {
    const id = this.listId();
    if (id) {
      this.scouting.shortlist(id).subscribe({
        next: (list) => {
          this.current.set(list);
          this.loading.set(false);
          if (this.tab() === 'log') this.showLog();
        },
        error: async (err: unknown) => {
          this.loading.set(false);
          await this.toast(extractErrorMessage(err, 'That shortlist is not available.'), 'danger');
        },
      });
      return;
    }
    this.scouting.shortlists().subscribe({
      next: (rows) => {
        this.lists.set(rows);
        this.loading.set(false);
      },
      error: async (err: unknown) => {
        this.loading.set(false);
        await this.toast(extractErrorMessage(err, 'Join a scouting organisation to use shortlists.'), 'danger');
      },
    });
  }

  showLog(): void {
    this.tab.set('log');
    const list = this.current();
    if (list) this.scouting.shortlistLog(list.id).subscribe({ next: (rows) => this.log.set(rows) });
  }

  create(event: Event): void {
    event.preventDefault();
    this.scouting.createShortlist({ name: this.name().trim(), description: this.description().trim() }).subscribe({
      next: (list) => {
        this.name.set('');
        this.description.set('');
        this.openList(list.id);
      },
      error: async (err: unknown) => this.toast(extractErrorMessage(err, 'Could not create the shortlist.'), 'danger'),
    });
  }

  openList(id: string): void {
    void this.router.navigate(['/tabs/scouting/shortlists', id]);
  }

  open(profileId: string): void {
    void this.router.navigate(['/tabs/scouting/players', profileId]);
  }

  setStatus(list: Shortlist, entry: ShortlistEntry, status: ShortlistStatus): void {
    if (entry.status === status) return;
    this.scouting.updateShortlistEntry(list.id, entry.id, { status }).subscribe({
      next: () => this.load(),
      error: async (err: unknown) => this.toast(extractErrorMessage(err, 'Could not change the status.'), 'danger'),
    });
  }

  assign(list: Shortlist, entry: ShortlistEntry, scoutId: string): void {
    this.scouting.updateShortlistEntry(list.id, entry.id, { assigned_to: scoutId || null }).subscribe({
      next: () => this.load(),
      error: async (err: unknown) => this.toast(extractErrorMessage(err, 'Could not assign that scout.'), 'danger'),
    });
  }

  draft(entryId: string, value: string): void {
    this.drafts.update((current) => ({ ...current, [entryId]: value }));
  }

  comment(list: Shortlist, entry: ShortlistEntry): void {
    const body = (this.drafts()[entry.id] ?? '').trim();
    this.scouting.commentOnEntry(list.id, entry.id, body).subscribe({
      next: () => {
        this.draft(entry.id, '');
        this.load();
      },
      error: async (err: unknown) => this.toast(extractErrorMessage(err, 'Could not post the comment.'), 'danger'),
    });
  }

  remove(list: Shortlist, entry: ShortlistEntry): void {
    this.scouting.removeFromShortlist(list.id, entry.id).subscribe({
      next: async () => {
        this.load();
        await this.toast(`${entry.profile.name} removed. The change log keeps the history.`, 'success');
      },
    });
  }

  describe(row: ShortlistLogRow): string {
    const label = (value: unknown) => STATUSES.find((item) => item.key === value)?.label ?? String(value ?? '');
    if (row.action === 'status') return `${label(row.before['status'])} → ${label(row.after['status'])}`;
    if (row.action === 'assigned') {
      const name = (value: unknown) => (value as { name?: string } | null)?.name ?? 'nobody';
      return `${name(row.before['assigned_to'])} → ${name(row.after['assigned_to'])}`;
    }
    if (row.action === 'commented') return `"${row.after['comment']}"`;
    if (row.action === 'contacted') return row.after['to_guardian'] ? 'Sent to the guardian' : 'Sent to the player';
    return '';
  }

  private async toast(message: string, color: 'success' | 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2400, position: 'top' });
    await toast.present();
  }
}
