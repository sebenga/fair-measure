import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import {
  IonBackButton,
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
import type { AthletePage, PersonalBest } from '../../core/games.service';
import { GamesService } from '../../core/games.service';
import { GamesFollowComponent } from './games-follow.component';

@Component({
  selector: 'fm-games-athlete',
  standalone: true,
  imports: [DatePipe, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonIcon, IonSpinner, GamesFollowComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './games.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button [defaultHref]="backHref()" /></ion-buttons>
        <ion-title>{{ athlete()?.name ?? 'Athlete' }}</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (athlete(); as a) {
        <section class="hero fm-enter">
          <p class="kicker">{{ a.noc }} · {{ a.noc_name }}</p>
          <h2>{{ a.name }}</h2>
          <p>{{ a.events.length }} event(s) · {{ a.medals.length }} medal(s){{ a.records.length ? ' · ' + a.records.length + ' record(s)' : '' }}</p>
        </section>

        <div class="actions">
          <fm-games-follow [gamesId]="gamesId()" target="athlete" [ref]="a.id" />
          <button type="button" class="btn ghost small" (click)="go('nocs/' + a.noc_id)">{{ a.noc }} team page</button>
          @if (a.scouting_profile_id) {
            <button type="button" class="btn ghost small" (click)="openProfile(a.scouting_profile_id)">
              <ion-icon name="person-outline" aria-hidden="true" />
              Scouting profile
            </button>
          }
        </div>

        @if (a.medals.length) {
          <section class="fm-card section">
            <h3>Medals</h3>
            <ul class="list">
              @for (medal of a.medals; track $index) {
                <li>
                  <button type="button" class="row-btn" (click)="go('events/' + medal.event_id)">
                    <span [class]="'dot ' + medal.medal">{{ medal.medal.charAt(0).toUpperCase() }}</span>
                    <span class="grow"><strong>{{ medal.event }}</strong></span>
                  </button>
                </li>
              }
            </ul>
          </section>
        }

        <section class="fm-card section">
          <h3>Events and results</h3>
          @for (event of a.events; track event.id) {
            <button type="button" class="row-btn" (click)="go('events/' + event.id)">
              <span class="grow">
                <strong>{{ event.sport }}: {{ event.name }}</strong>
                <small>{{ event.venue || 'Venue to be confirmed' }}{{ event.scheduled_at ? ' · ' + (event.scheduled_at | date: 'EEE d MMM, HH:mm') : '' }}</small>
              </span>
            </button>
            <ul class="list rounds">
              @for (row of resultsFor(event.id); track $index) {
                <li>
                  <span>{{ row.round }}</span>
                  <strong>{{ row.status || (row.rank ? placeLabel(row.rank) : '–') }}</strong>
                  <span>{{ row.mark }}{{ row.qualified ? ' ' + row.qualified : '' }}{{ row.final ? '' : ' (provisional)' }}</span>
                </li>
              } @empty {
                <li class="hint">No results yet.</li>
              }
            </ul>
          } @empty {
            <p class="hint">Not entered in any event yet.</p>
          }
        </section>

        <section class="fm-card section">
          <h3>Personal bests</h3>
          @if (a.best_at_games.length) {
            <p class="sub">Best at these Games</p>
            <ul class="list">
              @for (best of a.best_at_games; track best.event_id) {
                <li class="pb"><span>{{ best.event }}</span><strong>{{ best.mark }}</strong></li>
              }
            </ul>
          }
          <p class="sub">Before the Games</p>
          @if (a.can_manage) {
            @for (row of draft(); track $index; let index = $index) {
              <div class="pb-edit">
                <label class="field">Event<input [value]="row.event" (input)="setDraft(index, 'event', $event)" placeholder="e.g. 100 m" /></label>
                <label class="field">Mark<input [value]="row.mark" (input)="setDraft(index, 'mark', $event)" placeholder="e.g. 9.85" /></label>
                <label class="field">Date<input type="date" [value]="row.date" (input)="setDraft(index, 'date', $event)" /></label>
                <button type="button" class="btn ghost small" (click)="removeDraft(index)" aria-label="Remove this best">✕</button>
              </div>
            }
            <div class="actions flush">
              <button type="button" class="btn ghost small" (click)="addDraft()">Add a best</button>
              <button type="button" class="btn small" [disabled]="busy()" (click)="saveBests()">Save personal bests</button>
            </div>
          } @else {
            <ul class="list">
              @for (best of a.personal_bests; track $index) {
                <li class="pb"><span>{{ best.event }}{{ best.date ? ' · ' + (best.date | date: 'd MMM y') : '' }}</span><strong>{{ best.mark }}</strong></li>
              } @empty {
                <li class="hint">None recorded.</li>
              }
            </ul>
          }
        </section>

        @if (a.records.length) {
          <section class="fm-card section">
            <h3>Records</h3>
            <ul class="list">
              @for (record of a.records; track record.id) {
                <li class="pb"><span><span class="badge warn">{{ record.scope_label }}</span> {{ record.event }}</span><strong>{{ record.mark }}</strong></li>
              }
            </ul>
          </section>
        }
      }
      <div style="height: 32px"></div>
    </ion-content>
  `,
  styles: [
    `
      .rounds {
        margin: 0 0 12px 12px;
      }
      .rounds li,
      .pb {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        padding: 6px 0;
        border-bottom: 1px solid var(--ion-color-step-50, #f1f2f4);
        font-size: 0.88rem;
      }
      .sub {
        margin: 10px 0 4px;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--ion-color-medium);
      }
      .pb-edit {
        display: grid;
        grid-template-columns: 2fr 1fr 1.2fr auto;
        gap: 8px;
        align-items: end;
      }
      .actions.flush {
        margin: 8px 0 0;
      }
    `,
  ],
})
export class GamesAthletePage {
  private readonly service = inject(GamesService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastController);

  readonly athlete = signal<AthletePage | null>(null);
  readonly draft = signal<PersonalBest[]>([]);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly gamesId = computed(() => this.route.snapshot.paramMap.get('id') ?? '');
  private readonly athleteId = computed(() => this.route.snapshot.paramMap.get('athleteId') ?? '');
  readonly backHref = computed(() => `/tabs/games/${this.gamesId()}`);

  ionViewWillEnter(): void {
    this.service.athlete(this.gamesId(), this.athleteId()).subscribe({
      next: (athlete) => this.show(athlete),
      error: () => this.loading.set(false),
    });
  }

  private show(athlete: AthletePage): void {
    this.athlete.set(athlete);
    this.draft.set(athlete.personal_bests.map((row) => ({ ...row })));
    this.loading.set(false);
  }

  resultsFor(eventId: string) {
    return (this.athlete()?.results ?? []).filter((row) => row.event_id === eventId);
  }

  placeLabel(rank: number): string {
    const suffix = rank % 100 >= 11 && rank % 100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[rank % 10] ?? 'th';
    return `${rank}${suffix}`;
  }

  setDraft(index: number, field: keyof PersonalBest, event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.draft.update((rows) => rows.map((row, at) => (at === index ? { ...row, [field]: value } : row)));
  }

  addDraft(): void {
    this.draft.update((rows) => [...rows, { event: '', mark: '', date: '' }]);
  }

  removeDraft(index: number): void {
    this.draft.update((rows) => rows.filter((_, at) => at !== index));
  }

  saveBests(): void {
    const rows = this.draft().filter((row) => row.event.trim() && row.mark.trim());
    this.busy.set(true);
    this.service.updateAthlete(this.gamesId(), this.athleteId(), { personal_bests: rows }).subscribe({
      next: async (athlete) => {
        this.busy.set(false);
        this.show(athlete);
        await this.toast('Personal bests saved.', 'success');
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not save the personal bests.'), 'danger');
      },
    });
  }

  go(path: string): void {
    void this.router.navigateByUrl(`/tabs/games/${this.gamesId()}/${path}`);
  }

  openProfile(profileId: string): void {
    void this.router.navigateByUrl(`/tabs/scouting/players/${profileId}`);
  }

  private async toast(message: string, color: 'success' | 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2400, position: 'top' });
    await toast.present();
  }
}
