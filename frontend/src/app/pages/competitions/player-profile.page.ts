import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
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
} from '@ionic/angular/standalone';

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';
import type { PlayerLeagueProfile } from '../../core/models';

@Component({
  selector: 'fm-player-profile',
  standalone: true,
  imports: [
    DatePipe,
    RouterLink,
    IonHeader,
    IonToolbar,
    IonButtons,
    IonBackButton,
    IonTitle,
    IonContent,
    IonButton,
    IonIcon,
    IonSpinner,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start">
          <ion-back-button [defaultHref]="backHref()" />
        </ion-buttons>
        <ion-title>{{ card()?.profile?.display_name || 'Profile' }}</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (error()) {
        <div class="fm-empty">
          <ion-icon name="alert-circle-outline" aria-hidden="true" />
          <h3>Could not open this profile</h3>
          <p>{{ error() }}</p>
          <ion-button fill="clear" (click)="load()">Try again</ion-button>
        </div>
      } @else if (card(); as current) {
        <div class="identity">
          <div class="mark" aria-hidden="true">{{ initials(current.profile.display_name) }}</div>
          <h2>{{ current.profile.display_name }}</h2>
          @if (current.profile.headline) {
            <p class="headline">{{ current.profile.headline }}</p>
          }
          @if (place(current); as where) {
            <p>{{ where }}</p>
          }
          @if (current.team) {
            <a [routerLink]="teamHref(current.team.id)">{{ current.team.name }}</a>
          } @else {
            <p>Not on a team in this league</p>
          }
        </div>

        <h3 class="fm-section-title">Bio</h3>
        <p class="copy">{{ current.profile.bio || 'No bio yet.' }}</p>

        @if (details(current).length) {
          <h3 class="fm-section-title">Background</h3>
          @for (detail of details(current); track detail.label) {
            <section class="block">
              <h4>{{ detail.label }}</h4>
              <p>{{ detail.value }}</p>
            </section>
          }
        }

        <h3 class="fm-section-title">League stats</h3>
        @if (current.totals.length === 0) {
          <p class="copy">No scores recorded for this profile in this league yet.</p>
        } @else {
          <div class="fm-card stats">
            @for (total of current.totals; track total.category) {
              <div class="stat">
                <span>{{ total.category }}</span>
                <strong>{{ trim(total.count) }}</strong>
                <em>{{ signed(total.points) }}</em>
              </div>
            }
          </div>
        }

        <h3 class="fm-section-title">Timeline</h3>
        @if (current.timeline.length === 0) {
          <p class="copy">Nothing on the timeline yet.</p>
        } @else {
          <div class="fm-card timeline">
            @for (event of current.timeline; track event.id) {
              <a class="event" [routerLink]="fixtureHref(event.fixture_id)">
                <span class="minute">{{ event.minute !== null ? event.minute + "'" : '—' }}</span>
                <span class="detail">
                  <strong>{{ event.category }}</strong>
                  {{ event.fixture_label }}
                  <span class="when">{{ event.created_at | date: 'd MMM, HH:mm' }}</span>
                </span>
                <span class="points">{{ signed(event.points) }}</span>
              </a>
            }
          </div>
        }

        <h3 class="fm-section-title">Ratings</h3>
        @if (current.ratings.length === 0) {
          <p class="copy">No rating for a game in this league yet.</p>
        } @else {
          <div class="fm-card ratings">
            @for (rating of current.ratings; track rating.fixture_id) {
              <a class="rating" [routerLink]="fixtureHref(rating.fixture_id)">
                <span>
                  {{ rating.fixture_label }}
                  @if (rating.scheduled_at) {
                    <em>{{ rating.scheduled_at | date: 'd MMM' }}</em>
                  }
                </span>
                <strong>{{ trim(rating.rating) }}</strong>
              </a>
            }
          </div>
        }
      }
    </ion-content>
  `,
  styleUrl: './player-profile.page.scss',
})
export class PlayerProfilePage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);

  private competitionId = '';
  private userId = '';

  readonly card = signal<PlayerLeagueProfile | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.competitionId = this.route.snapshot.paramMap.get('id') ?? '';
    this.userId = this.route.snapshot.paramMap.get('userId') ?? '';
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(null);
    this.api.getPlayerProfile(this.competitionId, this.userId).subscribe({
      next: (card) => {
        this.card.set(card);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err));
        this.loading.set(false);
      },
    });
  }

  backHref(): string {
    return `/tabs/competitions/${this.competitionId}/setup`;
  }

  teamHref(teamId: string): string[] {
    return ['/tabs/competitions', this.competitionId, 'teams', teamId];
  }

  fixtureHref(fixtureId: string): string[] {
    return ['/tabs/competitions', this.competitionId, 'fixtures', fixtureId];
  }

  initials(name: string): string {
    const parts = name.trim().split(/\s+/).slice(0, 2);
    return parts.map((part) => part.charAt(0).toUpperCase()).join('') || 'P';
  }

  place(card: PlayerLeagueProfile): string {
    return [card.profile.city, card.profile.country].filter(Boolean).join(', ');
  }

  details(card: PlayerLeagueProfile): Array<{ label: string; value: string }> {
    const profile = card.profile;
    return [
      ['Experience', profile.experience],
      ['Education', profile.education],
      ['Skills', profile.skills],
      ['Languages', profile.languages],
    ]
      .filter((entry): entry is [string, string] => !!entry[1])
      .map(([label, value]) => ({ label, value }));
  }

  trim(value: string): string {
    const numeric = Number(value);
    if (Number.isNaN(numeric)) return value;
    return String(numeric);
  }

  signed(value: string): string {
    const numeric = Number(value);
    if (Number.isNaN(numeric) || numeric === 0) return this.trim(value);
    return numeric > 0 ? `+${this.trim(value)}` : this.trim(value);
  }
}
