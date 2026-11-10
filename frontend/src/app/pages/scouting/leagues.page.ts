import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import {
  IonBackButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonTitle,
  IonToolbar,
} from '@ionic/angular/standalone';

import type { LeagueSummary, ScoutingCatalog } from '../../core/scouting.models';
import { SELECTOR_GUIDE, ScoutingService, groupBySport } from '../../core/scouting.service';

@Component({
  selector: 'fm-scouting-leagues',
  standalone: true,
  imports: [IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './scouting.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button defaultHref="/tabs/scouting" /></ion-buttons>
        <ion-title>League squads</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      <p class="lede">
        Every sport league that is open to scouts can name a squad of its best players, picked the way
        national selectors would: by position, from the league's own match data. {{ guide.summary }}
      </p>

      @if (loading()) {
        @for (n of [0, 1, 2]; track n) {
          <div class="fm-card card"><span class="fm-skeleton" style="width: 60%; height: 18px"></span></div>
        }
      } @else {
        @for (group of groups(); track group.key) {
        <h3 class="fm-section-title sport-title">{{ group.label }} <span class="count">{{ group.rows.length }}</span></h3>
        <div class="fm-stagger">
          @for (league of group.rows; track league.id) {
            <button type="button" class="fm-card card fm-lift" [class.closed]="!league.open_to_scouts" (click)="open(league)">
              <span class="icon"><ion-icon [name]="league.open_to_scouts ? 'shirt-outline' : 'eye-off-outline'" aria-hidden="true" /></span>
              <span class="grow">
                <strong>{{ league.name }}</strong>
                <small>
                  {{ league.sport || 'Sport not set' }} · {{ league.teams }} team(s)
                  @if (league.open_to_scouts) {
                    · {{ league.scouts }} league scout(s)
                  }
                </small>
                <small>
                  @if (!league.open_to_scouts) {
                    <span class="badge">Closed to scouts</span> Turn it on in Setup → Scouting
                  } @else if (league.squad_status === 'published') {
                    <span class="badge ok">Squad of {{ league.squad_filled }} named</span>
                  } @else if (league.squad_status === 'draft') {
                    <span class="badge warn">Draft · {{ league.squad_filled }}/{{ league.squad_size }}</span>
                  } @else if (league.can_select) {
                    <span class="badge info">Pick the best {{ league.squad_size }}</span>
                  } @else {
                    No squad yet
                  }
                </small>
              </span>
              @if (league.i_scout_it) {
                <span class="badge info">You scout it</span>
              } @else if (league.can_select) {
                <span class="badge">Selector</span>
              }
              <ion-icon name="chevron-forward-outline" aria-hidden="true" />
            </button>
          }
        </div>
        } @empty {
          <div class="fm-empty">
            <ion-icon name="shirt-outline" aria-hidden="true" />
            <h3>No leagues open to scouts</h3>
            <p>A sport competition's owner can open it to scouts in Setup → Scouting, or when creating it.</p>
          </div>
        }
      }
      <div style="height: 32px"></div>
    </ion-content>
  `,
  styles: [
    `
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

      .sport-title .count {
        margin-left: 4px;
        color: var(--ion-color-medium);
        font-weight: 600;
      }

      .card.closed .icon {
        background: var(--ion-color-light);
        color: var(--ion-color-medium);
      }

      .icon {
        display: grid;
        place-items: center;
        width: 44px;
        height: 44px;
        flex: 0 0 auto;
        border-radius: 14px;
        background: color-mix(in srgb, var(--ion-color-primary) 12%, transparent);
        color: var(--ion-color-primary);
        font-size: 1.3rem;
      }

      .grow {
        flex: 1 1 auto;
        min-width: 0;
        display: grid;
        gap: 3px;

        small {
          color: var(--ion-color-medium);
        }
      }
    `,
  ],
})
export class ScoutingLeaguesPage {
  private readonly scouting = inject(ScoutingService);
  private readonly router = inject(Router);

  readonly guide = SELECTOR_GUIDE;
  readonly leagues = signal<LeagueSummary[]>([]);
  readonly loading = signal(true);
  readonly catalog = signal<ScoutingCatalog | null>(null);

  /** Leagues grouped by sport code, in catalogue order. */
  readonly groups = computed(() =>
    groupBySport(
      this.leagues(),
      (league) => ({ key: league.sport_key, label: league.sport || 'Other' }),
      this.catalog(),
    ),
  );

  ionViewWillEnter(): void {
    this.scouting.catalog().subscribe({ next: (catalog) => this.catalog.set(catalog) });
    this.scouting.leagues().subscribe({
      next: (rows) => {
        this.leagues.set(rows);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  open(league: LeagueSummary): void {
    const target = league.open_to_scouts
      ? `/tabs/scouting/leagues/${league.id}`
      : `/tabs/competitions/${league.id}/setup`;
    void this.router.navigateByUrl(target);
  }
}
