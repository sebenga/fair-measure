import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import {
  IonBackButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonSearchbar,
  IonTitle,
  IonToolbar,
} from '@ionic/angular/standalone';

import type { ProfileCard, ScoutingCatalog } from '../../core/scouting.models';
import { ScoutingService, groupBySport } from '../../core/scouting.service';

@Component({
  selector: 'fm-scouting-players',
  standalone: true,
  imports: [IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonIcon, IonSearchbar],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './scouting.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button defaultHref="/tabs/scouting" /></ion-buttons>
        <ion-title>Players</ion-title>
      </ion-toolbar>
      <ion-toolbar>
        <ion-searchbar placeholder="Search by name" [debounce]="300" (ionInput)="search($any($event).detail.value ?? '')" />
      </ion-toolbar>
    </ion-header>

    <ion-content>
      <div class="filters">
        <button type="button" class="chip" [class.on]="!sport()" (click)="setSport('')">All sports</button>
        @for (item of catalog()?.sports ?? []; track item.key) {
          <button type="button" class="chip" [class.on]="sport() === item.key" (click)="setSport(item.key)">
            {{ item.label }}
          </button>
        }
      </div>

      <p class="lede">
        {{ count() }} profile(s) you may see. Under-18s appear only with a guardian's consent, and contact always
        goes through Fair Measure.
      </p>

      @if (loading()) {
        @for (n of [0, 1, 2, 3]; track n) {
          <div class="fm-card card"><span class="fm-skeleton" style="width: 60%; height: 18px"></span></div>
        }
      } @else {
        @for (group of groups(); track group.key) {
          <h3 class="fm-section-title sport-title">
            {{ group.label }} <span class="count">{{ group.rows.length }}</span>
          </h3>
          <div class="fm-stagger">
            @for (player of group.rows; track player.id) {
                <button type="button" class="fm-card card fm-lift" (click)="open(player.id)">
                  <span class="avatar">
                    @if (player.photo_url) {
                      <img [src]="player.photo_url" alt="" />
                    } @else {
                      {{ player.name.charAt(0) }}
                    }
                  </span>
                  <span class="grow">
                    <strong>{{ player.name }}</strong>
                    <small>
                      {{ player.sport?.sport_label ?? 'No sport yet' }}
                      @if (player.sport?.primary_position_label) {
                        · {{ player.sport?.primary_position_label }}
                      }
                    </small>
                    <small>{{ player.age_group ?? '' }} {{ regionLabel(player.region) ? '· ' + regionLabel(player.region) : '' }}</small>
                    @if (teamLabel(player)) {
                      <small>{{ teamLabel(player) }}</small>
                    }
                  </span>
                  <ion-icon name="chevron-forward-outline" aria-hidden="true" />
                </button>
            }
          </div>
        } @empty {
          <div class="fm-empty">
            <ion-icon name="search-outline" aria-hidden="true" />
            <h3>No players found</h3>
            <p>Try another sport or name.</p>
          </div>
        }
      }
      <div style="height: 32px"></div>
    </ion-content>
  `,
  styles: [
    `
      .filters {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        padding: 12px 16px 0;
        scrollbar-width: none;
      }

      .filters .chip {
        flex: 0 0 auto;
      }

      .sport-title .count {
        margin-left: 4px;
        color: var(--ion-color-medium);
        font-weight: 600;
      }

      .card {
        display: flex;
        align-items: center;
        gap: 12px;
        width: calc(100% - 32px);
        border: 0;
        text-align: left;
        font: inherit;
        color: var(--ion-text-color);
        cursor: pointer;
      }

      .grow {
        flex: 1 1 auto;
        min-width: 0;
        display: grid;
        gap: 2px;

        small {
          color: var(--ion-color-medium);
        }
      }
    `,
  ],
})
export class ScoutingPlayersPage {
  private readonly scouting = inject(ScoutingService);
  private readonly router = inject(Router);

  readonly catalog = signal<ScoutingCatalog | null>(null);
  readonly players = signal<ProfileCard[]>([]);
  readonly count = signal(0);
  readonly loading = signal(true);
  readonly sport = signal('');

  /** Players grouped by sport code, in catalogue order. */
  readonly groups = computed(() =>
    groupBySport(
      this.players(),
      (player) => ({ key: player.sport?.sport ?? null, label: player.sport?.sport_label ?? 'No sport yet' }),
      this.catalog(),
    ),
  );
  private query = '';

  ionViewWillEnter(): void {
    this.scouting.catalog().subscribe((catalog) => this.catalog.set(catalog));
    this.load();
  }

  search(value: string): void {
    this.query = value.trim();
    this.load();
  }

  setSport(key: string): void {
    this.sport.set(key);
    this.load();
  }

  regionLabel(key: string): string {
    return (this.catalog()?.regions ?? []).find((region) => region.key === key)?.label ?? '';
  }

  teamLabel(player: ProfileCard): string {
    if (player.teams.length) {
      return player.teams.map((team) => team.name).join(' · ');
    }
    return player.school_or_club;
  }

  open(id: string): void {
    void this.router.navigateByUrl(`/tabs/scouting/players/${id}`);
  }

  private load(): void {
    this.loading.set(true);
    this.scouting.listProfiles({ q: this.query, sport: this.sport() }).subscribe({
      next: (page) => {
        this.players.set(page.results);
        this.count.set(page.count);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }
}
