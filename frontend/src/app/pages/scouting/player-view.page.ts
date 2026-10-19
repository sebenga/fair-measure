import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
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
import type {
  Measurement,
  PlayerProfile,
  ScoutProfileView,
  ScoutingCatalog,
} from '../../core/scouting.models';
import { ScoutingService } from '../../core/scouting.service';

type Viewable = PlayerProfile | ScoutProfileView;

@Component({
  selector: 'fm-scouting-player-view',
  standalone: true,
  imports: [DatePipe, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonIcon, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './scouting.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button defaultHref="/tabs/scouting/players" /></ion-buttons>
        <ion-title>Player</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (error()) {
        <div class="fm-empty">
          <ion-icon name="eye-off-outline" aria-hidden="true" />
          <h3>Not available</h3>
          <p>{{ error() }}</p>
        </div>
      } @else if (player(); as p) {
        @if (previewNote()) {
          <div class="notice info">{{ previewNote() }}</div>
        }

        <section class="header fm-enter">
          <span class="avatar large">
            @if (p.photo_url) {
              <img [src]="p.photo_url" alt="" />
            } @else {
              {{ p.first_name.charAt(0) }}{{ p.last_name.charAt(0) }}
            }
          </span>
          <h2>{{ p.first_name }} {{ p.last_name }}</h2>
          <p>
            @if (showAge(p)) {
              {{ p.age }} years ·
            }
            {{ p.age_group?.label ?? '' }}
            {{ regionLabel(p.region) ? '· ' + regionLabel(p.region) : '' }}
          </p>
          <p class="sub">{{ p.school_or_club }}{{ p.nationality ? ' · ' + p.nationality : '' }}</p>
          <div class="chips centre">
            @for (sport of p.sports; track sport.id) {
              <span class="badge info">{{ sport.sport_label }}{{ sport.primary_position_label ? ' · ' + sport.primary_position_label : '' }}</span>
            }
          </div>
        </section>

        <div class="notice">
          <ion-icon name="lock-closed-outline" aria-hidden="true" />
          {{ contactNote(p) }}
        </div>

        @if (p.bio) {
          <section class="fm-card section"><h3>About</h3><p class="body">{{ p.bio }}</p></section>
        }

        @if (p.sports.length) {
          <section class="fm-card section">
            <h3>Positions</h3>
            @for (sport of p.sports; track sport.id) {
              <p class="body">
                <strong>{{ sport.sport_label }}:</strong> {{ sport.primary_position_label || 'No main position' }}
                @if (sport.secondary_positions.length) {
                  <span class="muted">· also {{ secondaryLabels(sport.sport, sport.secondary_positions) }}</span>
                }
              </p>
            }
          </section>
        }

        @if (measurements().length) {
          <section class="fm-card section">
            <h3>Physical</h3>
            <ul class="list">
              @for (item of measurements(); track item.id) {
                <li class="list-row">
                  <div class="grow">
                    <strong>{{ item.label }}: {{ item.value !== null ? trim(item.value) + ' ' + item.unit : item.text_value }}</strong>
                    <small>Measured {{ item.measured_on | date: 'd MMM y' }}</small>
                  </div>
                  <span class="badge" [class.ok]="item.verified">{{ item.verified ? 'Verified · ' + item.verified_by_name : 'Self-reported' }}</span>
                </li>
              }
            </ul>
          </section>
        }

        @if (isCoach() && p.access === 'scout') {
          <form class="fm-card section" (submit)="recordVerified($event, p.id)">
            <h3>Coach: record a verified measurement</h3>
            <p class="hint">Only works for players on a team you coach. It is shown as verified by you.</p>
            <div class="row">
              <label class="field">
                Measurement
                <select (change)="coachKind.set($any($event.target).value); coachValue.set('')">
                  @for (spec of catalog()?.measurements ?? []; track spec.key) {
                    <option [value]="spec.key" [selected]="spec.key === coachKind()">{{ spec.label }}</option>
                  }
                </select>
              </label>
              @if (coachSpec()?.kind === 'choice') {
                <label class="field">
                  Value
                  <select (change)="coachValue.set($any($event.target).value)">
                    <option value="">Choose</option>
                    @for (choice of coachSpec()?.choices ?? []; track choice) {
                      <option [value]="choice" [selected]="choice === coachValue()">{{ choice }}</option>
                    }
                  </select>
                </label>
              } @else {
                <label class="field">
                  Value ({{ coachSpec()?.unit }})
                  <input type="number" inputmode="decimal" min="0" step="0.1" [value]="coachValue()" (input)="coachValue.set($any($event.target).value)" />
                </label>
              }
            </div>
            <label class="field">Measured on<input type="date" [value]="coachDate()" (input)="coachDate.set($any($event.target).value)" /></label>
            <button type="submit" class="btn block" [disabled]="!coachValue() || busy()">Save verified</button>
          </form>
        }

        @if (availability(); as status) {
          <section class="fm-card section">
            <h3>Availability</h3>
            <p class="body">{{ availabilityLabel(status.status) }}{{ status.note ? ' · ' + status.note : '' }}</p>
          </section>
        }

        @if (p.videos.length) {
          <section class="fm-card section">
            <h3>Highlights</h3>
            <ul class="list">
              @for (video of p.videos; track video.id) {
                <li class="list-row">
                  <ion-icon name="videocam" aria-hidden="true" />
                  <div class="grow">
                    @if (video.playback_url) {
                      <a [href]="video.playback_url" target="_blank" rel="noopener">{{ video.title }}</a>
                    } @else {
                      <strong>{{ video.title }}</strong>
                      <small>Processing…</small>
                    }
                  </div>
                </li>
              }
            </ul>
          </section>
        }

        @if (p.injuries.length) {
          <section class="fm-card section">
            <h3>Shared injury history</h3>
            <ul class="list">
              @for (injury of p.injuries; track injury.id) {
                <li class="list-row">
                  <div class="grow">
                    <strong>{{ injury.description }}</strong>
                    <small>{{ injury.injured_on ? (injury.injured_on | date: 'd MMM y') : 'Date unknown' }}</small>
                  </div>
                </li>
              }
            </ul>
          </section>
        }

        <p class="lede">Last updated {{ p.updated_at | date: 'd MMM y' }}. Ratings, stats and reports arrive in later phases.</p>
      }
      <div style="height: 32px"></div>
    </ion-content>
  `,
  styles: [
    `
      .header {
        display: grid;
        justify-items: center;
        gap: 4px;
        margin: 16px;
        text-align: center;

        h2 {
          margin: 8px 0 0;
          font-size: 1.35rem;
        }

        p {
          margin: 0;
          color: var(--ion-color-medium);
        }

        .sub {
          font-size: 0.86rem;
        }

        .centre {
          justify-content: center;
          margin-top: 8px;
        }
      }

      .notice {
        display: flex;
        gap: 8px;
        align-items: center;
      }

      .body {
        margin: 0 0 6px;
        line-height: 1.5;
      }

      .muted {
        color: var(--ion-color-medium);
      }
    `,
  ],
})
export class ScoutingPlayerViewPage {
  private readonly scouting = inject(ScoutingService);
  private readonly route = inject(ActivatedRoute);
  private readonly toasts = inject(ToastController);

  readonly catalog = signal<ScoutingCatalog | null>(null);
  readonly player = signal<Viewable | null>(null);
  readonly loading = signal(true);
  readonly error = signal('');

  readonly measurements = computed<Measurement[]>(() => this.player()?.measurements ?? []);
  readonly isCoach = computed(() => (this.scouting.me()?.role_keys ?? []).includes('coach'));
  readonly busy = signal(false);
  readonly coachKind = signal('height');
  readonly coachValue = signal('');
  readonly coachDate = signal(new Date().toISOString().slice(0, 10));
  readonly coachSpec = computed(() =>
    (this.catalog()?.measurements ?? []).find((spec) => spec.key === this.coachKind()),
  );
  readonly availability = computed(() => {
    const player = this.player();
    if (!player) return null;
    if (typeof player.availability === 'string') {
      return { status: player.availability, note: (player as PlayerProfile).availability_note };
    }
    return player.availability;
  });

  ionViewWillEnter(): void {
    this.load();
    if (!this.scouting.me()) this.scouting.loadMe().subscribe();
  }

  private load(): void {
    const id = this.route.snapshot.paramMap.get('id') ?? '';
    this.scouting.catalog().subscribe((catalog) => this.catalog.set(catalog));
    const asScout = this.route.snapshot.queryParamMap.get('as') === 'scout';
    this.scouting.getProfile(id, asScout).subscribe({
      next: (player) => {
        this.player.set(player);
        this.loading.set(false);
      },
      error: async (err: unknown) => {
        this.loading.set(false);
        this.error.set(extractErrorMessage(err, 'This profile is private or does not exist.'));
        const toast = await this.toasts.create({ message: this.error(), duration: 2000, position: 'top' });
        await toast.present();
      },
    });
  }

  recordVerified(event: Event, profileId: string): void {
    event.preventDefault();
    const spec = this.coachSpec();
    if (!spec || !this.coachValue()) return;
    const body =
      spec.kind === 'choice'
        ? { kind: spec.key, text_value: this.coachValue(), measured_on: this.coachDate() }
        : { kind: spec.key, value: this.coachValue(), measured_on: this.coachDate() };
    this.busy.set(true);
    this.scouting.coachMeasurement(profileId, body).subscribe({
      next: async () => {
        this.busy.set(false);
        this.coachValue.set('');
        await this.say(`${spec.label} saved as verified.`, 'success');
        this.load();
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.say(extractErrorMessage(err, 'Could not save that.'), 'danger');
      },
    });
  }

  private async say(message: string, color: 'success' | 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2400, position: 'top' });
    await toast.present();
  }

  previewNote(): string {
    const player = this.player();
    if (player && 'preview' in player && player.preview) {
      return player.effective_visibility === 'private'
        ? 'Preview: right now scouts cannot see your profile at all. This is what they would see once it is visible.'
        : 'Preview: this is exactly what a scout sees. Your contact details and private injuries are not included.';
    }
    const access = player?.access;
    if (access === 'owner') {
      const visibility = (this.player() as PlayerProfile).effective_visibility;
      return visibility === 'private'
        ? 'Only you (and your guardian) can see this. Scouts see nothing until you make it visible.'
        : 'This is your own profile. Scouts see the same, without your injuries unless you shared them.';
    }
    if (access === 'guardian') return 'You are viewing as this player\u2019s guardian.';
    return '';
  }

  showAge(player: Viewable): boolean {
    return player.access !== 'public' && player.age !== undefined && player.age !== null;
  }

  contactNote(player: Viewable): string {
    if (player.access === 'owner' || player.access === 'guardian') {
      return 'Your phone number and email are never shown to scouts.';
    }
    return (player as ScoutProfileView).contact;
  }

  regionLabel(key: string): string {
    return (this.catalog()?.regions ?? []).find((region) => region.key === key)?.label ?? '';
  }

  secondaryLabels(sportKey: string, keys: string[]): string {
    const positions = (this.catalog()?.sports ?? []).find((sport) => sport.key === sportKey)?.positions ?? [];
    return keys.map((key) => positions.find((position) => position.key === key)?.label ?? key).join(', ');
  }

  availabilityLabel(status: string): string {
    return (
      { available: 'Available', limited: 'Limited availability', unavailable: 'Not available', injured: 'Injured' }[
        status
      ] ?? status
    );
  }

  trim(value: string): string {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? String(parsed) : value;
  }
}
