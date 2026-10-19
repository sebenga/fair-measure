import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
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
} from '@ionic/angular/standalone';

import type { NocPage } from '../../core/games.service';
import { GamesService } from '../../core/games.service';
import { GamesFollowComponent } from './games-follow.component';

@Component({
  selector: 'fm-games-noc',
  standalone: true,
  imports: [IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonIcon, IonSpinner, GamesFollowComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './games.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button [defaultHref]="backHref()" /></ion-buttons>
        <ion-title>{{ noc()?.name ?? 'NOC' }}</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (noc(); as n) {
        <section class="hero fm-enter" [style.background]="n.colour ? 'linear-gradient(135deg, ' + n.colour + ', #0b3d91)' : null">
          <p class="kicker">{{ n.code }}</p>
          <h2>{{ n.name }}</h2>
          <p>
            {{ total('gold') }} gold · {{ total('silver') }} silver · {{ total('bronze') }} bronze ·
            {{ n.athletes.length }} athlete(s)
          </p>
        </section>

        <div class="actions">
          <fm-games-follow [gamesId]="gamesId()" target="noc" [ref]="n.id" [label]="n.code" />
          <button type="button" class="btn ghost small" (click)="go('reports/noc-summary?noc=' + n.id)">
            <ion-icon name="document-text-outline" aria-hidden="true" />
            Summary report
          </button>
        </div>

        <section class="fm-card section">
          <h3>Medals by sport</h3>
          <table class="medal-table">
            <thead>
              <tr>
                <th class="noc">Sport</th>
                <th><span class="dot gold">G</span></th>
                <th><span class="dot silver">S</span></th>
                <th><span class="dot bronze">B</span></th>
              </tr>
            </thead>
            <tbody>
              @for (row of n.medals_by_sport; track row.sport) {
                <tr>
                  <td class="noc">{{ row.sport }}</td>
                  <td>{{ row.gold }}</td>
                  <td>{{ row.silver }}</td>
                  <td>{{ row.bronze }}</td>
                </tr>
              } @empty {
                <tr><td colspan="4" class="hint">No medals yet.</td></tr>
              }
            </tbody>
          </table>
        </section>

        <section class="fm-card section">
          <h3>Medals</h3>
          <ul class="list">
            @for (medal of n.medals; track $index) {
              <li>
                <button type="button" class="row-btn" (click)="go('events/' + medal.event_id)">
                  <span [class]="'dot ' + medal.medal">{{ medal.medal.charAt(0).toUpperCase() }}</span>
                  <span class="grow"><strong>{{ medal.entrant }}</strong><small>{{ medal.event }}</small></span>
                </button>
              </li>
            } @empty {
              <li class="hint">No medals yet.</li>
            }
          </ul>
        </section>

        <section class="fm-card section">
          <h3>Athletes</h3>
          <ul class="list">
            @for (athlete of n.athletes; track athlete.id) {
              <li>
                <button type="button" class="row-btn" (click)="go('athletes/' + athlete.id)">
                  <span class="grow"><strong>{{ athlete.name }}</strong><small>{{ athlete.events }} event(s)</small></span>
                  <ion-icon name="chevron-forward-outline" aria-hidden="true" />
                </button>
              </li>
            } @empty {
              <li class="hint">No athletes yet.</li>
            }
          </ul>
        </section>

        <section class="fm-card section">
          <h3>Results</h3>
          <ul class="list">
            @for (row of n.results; track $index) {
              <li>
                <button type="button" class="row-btn" (click)="go('events/' + row.event_id)">
                  <strong class="place">{{ row.status || (row.rank ?? '–') }}</strong>
                  <span class="grow">
                    <strong>{{ row.event }}</strong>
                    <small>{{ row.round }}{{ row.mark ? ' · ' + row.mark : '' }}{{ row.qualified ? ' · ' + row.qualified : '' }}{{ row.final ? '' : ' · provisional' }}</small>
                  </span>
                </button>
              </li>
            } @empty {
              <li class="hint">No results yet.</li>
            }
          </ul>
        </section>

        @if (n.records.length) {
          <section class="fm-card section">
            <h3>Records</h3>
            <ul class="list">
              @for (record of n.records; track record.id) {
                <li class="record"><span class="badge warn">{{ record.scope_label }}</span> {{ record.event }} · <strong>{{ record.mark }}</strong> · {{ record.holder }}</li>
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
      .place {
        min-width: 34px;
        text-align: center;
        font-variant-numeric: tabular-nums;
      }
      .record {
        font-size: 0.88rem;
      }
    `,
  ],
})
export class GamesNocPage {
  private readonly service = inject(GamesService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  readonly noc = signal<NocPage | null>(null);
  readonly loading = signal(true);
  readonly gamesId = computed(() => this.route.snapshot.paramMap.get('id') ?? '');
  readonly backHref = computed(() => `/tabs/games/${this.gamesId()}`);

  ionViewWillEnter(): void {
    this.service.noc(this.gamesId(), this.route.snapshot.paramMap.get('nocId') ?? '').subscribe({
      next: (noc) => {
        this.noc.set(noc);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  total(kind: 'gold' | 'silver' | 'bronze'): number {
    return (this.noc()?.medals ?? []).filter((medal) => medal.medal === kind).length;
  }

  go(path: string): void {
    void this.router.navigateByUrl(`/tabs/games/${this.gamesId()}/${path}`);
  }
}
