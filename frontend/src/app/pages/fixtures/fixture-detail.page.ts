import {
  ChangeDetectionStrategy,
  Component,
  OnDestroy,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { DatePipe } from '@angular/common';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';
import {
  ActionSheetController,
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

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';
import type {
  CompetitionDetail,
  FixtureDetail,
  FixtureSide,
  ScoreEvent,
  ScoringCategory,
} from '../../core/models';
import { RealtimeService, fixtureRoom } from '../../core/realtime.service';
import { RelativeTimePipe } from '../../shared/relative-time.pipe';

@Component({
  selector: 'fm-fixture-detail',
  standalone: true,
  imports: [
    DatePipe,
    RelativeTimePipe,
    IonHeader,
    IonToolbar,
    IonTitle,
    IonButtons,
    IonBackButton,
    IonButton,
    IonIcon,
    IonContent,
    IonSpinner,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start">
          <ion-back-button [defaultHref]="backHref()" />
        </ion-buttons>
        <ion-title>{{ fixture()?.label || 'Fixture' }}</ion-title>
        <ion-buttons slot="end">
          @if (canScore()) {
            <ion-button (click)="openStatusSheet()">
              <ion-icon slot="icon-only" name="ellipsis-horizontal" aria-label="Fixture status" />
            </ion-button>
          }
        </ion-buttons>
      </ion-toolbar>
    </ion-header>

    <ion-content fullscreen="true">
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (error()) {
        <div class="fm-empty">
          <ion-icon name="alert-circle-outline" aria-hidden="true" />
          <h3>Could not load this fixture</h3>
          <p>{{ error() }}</p>
          <ion-button fill="clear" (click)="load()">Try again</ion-button>
        </div>
      } @else if (fixture(); as fx) {
        <section class="scoreboard">
          <div class="status">
            @if (fx.status === 'live') {
              <span class="fm-live">Live</span>
            } @else {
              <span class="chip">{{ statusLabel(fx.status) }}</span>
            }
            @if (fx.scheduled_at) {
              <span class="kickoff">{{ fx.scheduled_at | date: 'EEE d MMM, HH:mm' }}</span>
            }
            @if (fx.location) {
              <span class="kickoff">{{ fx.location }}</span>
            }
          </div>

          <div class="line">
            @for (side of fx.sides; track side.id) {
              <div class="team" [class.winner]="side.outcome === 'win'">
                <span class="name">{{ side.participant.name }}</span>
                <span class="score">{{ trim(side.score) }}</span>
                @if (side.forfeited) {
                  <span class="ff">forfeit</span>
                }
              </div>
            }
          </div>
        </section>

        @if (canScore() && fx.status !== 'completed' && fx.status !== 'cancelled') {
          <h3 class="fm-section-title">Record a score</h3>

          @if (categories().length === 0) {
            <div class="fm-empty compact">
              <p>No scoring categories are configured for this competition yet.</p>
            </div>
          } @else {
            @for (side of fx.sides; track side.id) {
              <div class="fm-card scorer">
                <h4>{{ side.participant.short_name || side.participant.name }}</h4>
                <div class="chips">
                  @for (category of categories(); track category.id) {
                    <button
                      type="button"
                      class="chip-button"
                      [disabled]="saving()"
                      (click)="record(side, category)"
                    >
                      <span class="label">{{ category.name }}</span>
                      @if (category.affects_score) {
                        <span class="points">+{{ trim(category.points) }}</span>
                      }
                    </button>
                  }
                </div>
              </div>
            }
          }
        }

        <h3 class="fm-section-title">
          Timeline
          @if (fx.events.length) {
            <span class="count">{{ fx.events.length }}</span>
          }
        </h3>

        @if (fx.events.length === 0) {
          <div class="fm-empty compact">
            <p>Nothing has happened yet.</p>
          </div>
        } @else {
          <div class="fm-card timeline">
            @for (event of orderedEvents(); track event.id) {
              <div class="event">
                <span class="minute">
                  {{ event.minute !== null ? event.minute + "'" : '—' }}
                </span>
                <span class="detail">
                  <strong>{{ participantName(event) }}</strong>
                  {{ event.scoring_category_name }}
                  @if (numeric(event.quantity) !== 1) {
                    <em>×{{ trim(event.quantity) }}</em>
                  }
                  @if (event.player_name) {
                    <span class="player">{{ event.player_name }}</span>
                  }
                </span>
                <span class="points">{{ signed(event.points) }}</span>
                @if (canScore()) {
                  <button
                    type="button"
                    class="undo"
                    [disabled]="saving()"
                    (click)="removeEvent(event)"
                    aria-label="Remove event"
                  >
                    <ion-icon name="close-circle-outline" />
                  </button>
                }
              </div>
            }
          </div>

          <p class="updated">Last change {{ lastChangeAt() | relativeTime }}</p>
        }
      }
    </ion-content>
  `,
  styleUrl: './fixture-detail.page.scss',
})
export class FixtureDetailPage implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly realtime = inject(RealtimeService);
  private readonly actionSheets = inject(ActionSheetController);
  private readonly toasts = inject(ToastController);

  private competitionId = '';
  private fixtureId = '';

  readonly fixture = signal<FixtureDetail | null>(null);
  readonly competition = signal<CompetitionDetail | null>(null);
  readonly loading = signal(true);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.competitionId = this.route.snapshot.paramMap.get('competitionId') ?? '';
    this.fixtureId = this.route.snapshot.paramMap.get('fixtureId') ?? '';

    this.load();
    this.realtime.subscribe(fixtureRoom(this.fixtureId));

    this.realtime
      .onAny<{ fixture_id: string }>([
        'score.recorded',
        'score.corrected',
        'score.removed',
        'fixture.updated',
        'fixture.live',
        'fixture.completed',
      ])
      .pipe(takeUntilDestroyed())
      .subscribe((message) => {
        if (message.payload.fixture_id === this.fixtureId) {
          this.reloadFixture();
        }
      });
  }

  ngOnDestroy(): void {
    if (this.fixtureId) {
      this.realtime.unsubscribe(fixtureRoom(this.fixtureId));
    }
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);

    this.api.getCompetition(this.competitionId).subscribe({
      next: (competition) => this.competition.set(competition),
      error: () => undefined,
    });

    this.api.getFixture(this.competitionId, this.fixtureId).subscribe({
      next: (fixture) => {
        this.fixture.set(fixture);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err));
        this.loading.set(false);
      },
    });
  }

  private reloadFixture(): void {
    this.api.getFixture(this.competitionId, this.fixtureId).subscribe({
      next: (fixture) => this.fixture.set(fixture),
      error: () => undefined,
    });
  }

  categories(): ScoringCategory[] {
    return this.competition()?.scoring_categories ?? [];
  }

  canScore(): boolean {
    const role = this.competition()?.my_role;
    return role === 'owner' || role === 'admin' || role === 'scorer';
  }

  backHref(): string {
    return `/competitions/${this.competitionId}?tab=fixtures`;
  }

  record(side: FixtureSide, category: ScoringCategory): void {
    if (this.saving()) return;
    this.saving.set(true);

    this.api
      .recordEvent(this.fixtureId, {
        side: side.id,
        scoring_category: category.id,
        quantity: '1',
      })
      .subscribe({
        next: () => {
          this.saving.set(false);
          this.reloadFixture();
        },
        error: async (err: unknown) => {
          this.saving.set(false);
          await this.showToast(extractErrorMessage(err, 'Could not record that.'), 'danger');
        },
      });
  }

  removeEvent(event: ScoreEvent): void {
    if (this.saving()) return;
    this.saving.set(true);

    this.api.deleteEvent(this.fixtureId, event.id).subscribe({
      next: () => {
        this.saving.set(false);
        this.reloadFixture();
      },
      error: async (err: unknown) => {
        this.saving.set(false);
        await this.showToast(extractErrorMessage(err, 'Could not remove that event.'), 'danger');
      },
    });
  }

  async openStatusSheet(): Promise<void> {
    const current = this.fixture()?.status;
    const transitions: Array<{ status: string; label: string; destructive?: boolean }> = [
      { status: 'live', label: 'Start / mark live' },
      { status: 'completed', label: 'Complete fixture' },
      { status: 'scheduled', label: 'Back to scheduled' },
      { status: 'postponed', label: 'Postpone' },
      { status: 'cancelled', label: 'Cancel fixture', destructive: true },
    ].filter((option) => option.status !== current);

    const sheet = await this.actionSheets.create({
      header: 'Fixture status',
      buttons: [
        ...transitions.map((option) => ({
          text: option.label,
          role: option.destructive ? 'destructive' : undefined,
          handler: () => this.setStatus(option.status),
        })),
        { text: 'Cancel', role: 'cancel' },
      ],
    });
    await sheet.present();
  }

  private setStatus(status: string): void {
    this.api.setFixtureStatus(this.competitionId, this.fixtureId, status).subscribe({
      next: (fixture) => this.fixture.set(fixture),
      error: async (err: unknown) => {
        await this.showToast(extractErrorMessage(err, 'Could not change the status.'), 'danger');
      },
    });
  }

  private async showToast(message: string, color: string): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2600, position: 'bottom' });
    await toast.present();
  }

  orderedEvents(): ScoreEvent[] {
    return [...(this.fixture()?.events ?? [])].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );
  }

  lastChangeAt(): string | null {
    return this.orderedEvents()[0]?.created_at ?? null;
  }

  participantName(event: ScoreEvent): string {
    const side = this.fixture()?.sides.find(
      (candidate) => candidate.participant.id === event.participant_id,
    );
    return side?.participant.short_name || side?.participant.name || '—';
  }

  statusLabel(status: string): string {
    const labels: Record<string, string> = {
      scheduled: 'Scheduled',
      live: 'Live',
      completed: 'Full time',
      postponed: 'Postponed',
      cancelled: 'Cancelled',
      forfeit: 'Forfeit',
    };
    return labels[status] ?? status;
  }

  numeric(value: string): number {
    return Number(value);
  }

  trim(value: string): string {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? String(parsed) : value;
  }

  signed(value: string): string {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return value;
    if (parsed === 0) return '0';
    return parsed > 0 ? `+${parsed}` : String(parsed);
  }
}
