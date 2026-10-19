import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Router } from '@angular/router';
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
import type { Games, GamesKind, MedalRanking } from '../../core/games.service';
import { GamesService } from '../../core/games.service';

@Component({
  selector: 'fm-games-list',
  standalone: true,
  imports: [DatePipe, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonIcon, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './games.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button defaultHref="/tabs/competitions" /></ion-buttons>
        <ion-title>Games</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      <p class="lede">
        A multi-sport Games groups many events, each scored by its sport's locked rules. Medals roll up into one
        medal table by country, house, school or province.
      </p>

      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else {
        <ul class="list section">
          @for (games of list(); track games.id) {
            <li>
              <button type="button" class="row-btn fm-card" (click)="open(games.id)">
                <ion-icon name="trophy-outline" aria-hidden="true" />
                <span class="grow">
                  <strong>{{ games.name }}</strong>
                  <small>
                    {{ kindLabel(games.kind) }}{{ games.host ? ' · ' + games.host : '' }}
                    @if (games.starts_on) {
                      · {{ games.starts_on | date: 'd MMM' }}–{{ games.ends_on | date: 'd MMM y' }}
                    }
                  </small>
                  <small>{{ games.event_count }} events · {{ games.noc_count }} NOCs</small>
                </span>
                <span class="badge" [class.ok]="games.status === 'live'">{{ games.status }}</span>
              </button>
            </li>
          } @empty {
            <li class="hint">No Games yet. Create one below.</li>
          }
        </ul>
      }

      <form class="fm-card section" (submit)="create($event)">
        <h3>Create a Games</h3>
        <label class="field">Name<input [value]="name()" (input)="name.set($any($event.target).value)" placeholder="e.g. Schools Summer Games 2026" /></label>
        <div class="row">
          <label class="field">Edition<input [value]="edition()" (input)="edition.set($any($event.target).value)" placeholder="e.g. 3rd" /></label>
          <label class="field">Host<input [value]="host()" (input)="host.set($any($event.target).value)" placeholder="City or venue" /></label>
        </div>
        <div class="row">
          <label class="field">Starts<input type="date" [value]="startsOn()" (input)="startsOn.set($any($event.target).value)" /></label>
          <label class="field">Ends<input type="date" [value]="endsOn()" (input)="endsOn.set($any($event.target).value)" /></label>
        </div>
        <p class="hint">Type</p>
        <div class="choice">
          @for (option of kinds; track option.key) {
            <button type="button" [class.on]="kind() === option.key" (click)="kind.set(option.key)">
              <strong>{{ option.label }}</strong>
              <small>{{ option.note }}</small>
            </button>
          }
        </div>
        @if (kind() === 'custom') {
          <div class="row">
            <label class="field">Teams are called<input [value]="teamLabel()" (input)="teamLabel.set($any($event.target).value)" placeholder="House, School or Province" /></label>
            <label class="field">Points per place (best first)<input [value]="placingPoints()" (input)="placingPoints.set($any($event.target).value)" placeholder="e.g. 5, 3, 1" /></label>
          </div>
          <p class="hint">Each place earns these points towards an overall points table, shown alongside the medal table. Equal places earn the same points.</p>
        }
        <p class="hint">Medal table ranking. This is locked once the Games is created.</p>
        <div class="choice">
          <button type="button" [class.on]="ranking() === 'gold_first'" (click)="ranking.set('gold_first')">
            <strong>Golds first</strong>
            <small>The IOC standard: golds, then silvers, then bronzes.</small>
          </button>
          <button type="button" [class.on]="ranking() === 'total_first'" (click)="ranking.set('total_first')">
            <strong>Total medals first</strong>
            <small>Most medals of any colour, then golds.</small>
          </button>
        </div>
        <button type="submit" class="btn block" [disabled]="busy() || !name().trim()">Create the Games</button>
      </form>
      <div style="height: 32px"></div>
    </ion-content>
  `,
})
export class GamesListPage {
  private readonly games = inject(GamesService);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastController);

  readonly kinds: Array<{ key: GamesKind; label: string; note: string }> = [
    { key: 'summer', label: 'Summer', note: 'Olympic Summer sports' },
    { key: 'winter', label: 'Winter', note: 'Olympic Winter sports' },
    { key: 'custom', label: 'Local games', note: 'Schools, houses, provinces' },
  ];
  readonly list = signal<Games[]>([]);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly name = signal('');
  readonly edition = signal('');
  readonly host = signal('');
  readonly startsOn = signal('');
  readonly endsOn = signal('');
  readonly kind = signal<GamesKind>('summer');
  readonly ranking = signal<MedalRanking>('gold_first');
  readonly teamLabel = signal('House');
  readonly placingPoints = signal('5, 3, 1');

  ionViewWillEnter(): void {
    this.games.list().subscribe({
      next: (rows) => {
        this.list.set(rows);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  kindLabel(kind: GamesKind): string {
    return this.kinds.find((option) => option.key === kind)?.label ?? kind;
  }

  open(id: string): void {
    void this.router.navigateByUrl(`/tabs/games/${id}`);
  }

  create(event: Event): void {
    event.preventDefault();
    if (this.busy() || !this.name().trim()) return;
    this.busy.set(true);
    this.games
      .create({
        name: this.name().trim(),
        edition: this.edition().trim(),
        host: this.host().trim(),
        starts_on: this.startsOn() || null,
        ends_on: this.endsOn() || null,
        kind: this.kind(),
        medal_table_ranking: this.ranking(),
        ...(this.kind() === 'custom'
          ? {
              team_label: this.teamLabel().trim(),
              placing_points: this.placingPoints()
                .split(',')
                .map((item) => item.trim())
                .filter(Boolean)
                .map(Number),
            }
          : {}),
      })
      .subscribe({
        next: (games) => {
          this.busy.set(false);
          void this.router.navigateByUrl(`/tabs/games/${games.id}`);
        },
        error: async (err: unknown) => {
          this.busy.set(false);
          const toast = await this.toasts.create({
            message: extractErrorMessage(err, 'Could not create the Games.'),
            color: 'danger',
            duration: 2600,
            position: 'top',
          });
          await toast.present();
        },
      });
  }
}
