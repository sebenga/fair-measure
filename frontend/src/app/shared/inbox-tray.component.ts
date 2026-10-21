import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { IonButton, IonIcon } from '@ionic/angular/standalone';

import { ApiService } from '../core/api.service';
import type { AppNotification } from '../core/models';

@Component({
  selector: 'fm-inbox-tray',
  standalone: true,
  imports: [DatePipe, IonButton, IonIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="bell-wrap">
      <ion-button fill="clear" (click)="toggle()" [attr.aria-expanded]="open()">
        <ion-icon
          slot="icon-only"
          [name]="unread() ? 'notifications' : 'notifications-outline'"
          aria-label="Notifications"
        />
      </ion-button>
      @if (unread()) {
        <span class="dot" aria-hidden="true">{{ unread() > 9 ? '9+' : unread() }}</span>
      }
    </div>

    @if (open()) {
      <div class="sheet" role="dialog" aria-label="Notifications">
        <header>
          <strong>Notifications</strong>
          @if (unread()) {
            <button type="button" (click)="markAll()">Mark all read</button>
          }
        </header>
        @if (items().length === 0) {
          <p class="empty">Nothing waiting. Match scores, scout contact and league news land here.</p>
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
    }
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

      .sheet {
        position: absolute;
        top: calc(100% + 4px);
        right: 8px;
        z-index: 30;
        width: min(360px, calc(100vw - 24px));
        max-height: 70vh;
        overflow: auto;
        padding: 12px 12px 8px;
        border-radius: 16px;
        background: var(--ion-card-background, #fff);
        box-shadow: var(--fm-shadow);
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
    `,
  ],
})
export class InboxTrayComponent {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  readonly open = signal(false);
  readonly items = signal<AppNotification[]>([]);
  readonly unread = computed(() => this.items().filter((item) => !item.read_at).length);

  refresh(): void {
    this.api.listNotifications({ page_size: 20 }).subscribe({
      next: (page) => this.items.set(page.results),
      error: () => undefined,
    });
  }

  toggle(): void {
    this.open.update((value) => !value);
    if (this.open() && !this.items().length) this.refresh();
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

  label(kind: string): string {
    if (kind.includes('contact')) return 'Scout';
    if (kind.includes('guardian')) return 'Guardian';
    if (kind.includes('search')) return 'Alert';
    if (kind.includes('squad') || kind.includes('league')) return 'League';
    if (kind.includes('score') || kind.includes('fixture')) return 'Match';
    if (kind.includes('feed') || kind.includes('announce')) return 'News';
    return 'Update';
  }
}

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
