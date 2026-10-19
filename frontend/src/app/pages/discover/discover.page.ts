import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { Subject, debounceTime, distinctUntilChanged, switchMap } from 'rxjs';
import {
  IonButton,
  IonContent,
  IonHeader,
  IonIcon,
  IonSearchbar,
  IonSpinner,
  IonTitle,
  IonToolbar,
} from '@ionic/angular/standalone';

import { ApiService } from '../../core/api.service';
import { extractErrorMessage } from '../../core/error-message';
import type { Competition } from '../../core/models';
import { CompetitionCardComponent } from '../../shared/competition-card.component';

@Component({
  selector: 'fm-discover',
  standalone: true,
  imports: [
    IonHeader,
    IonToolbar,
    IonTitle,
    IonContent,
    IonSearchbar,
    IonSpinner,
    IonIcon,
    IonButton,
    CompetitionCardComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-header translucent="true">
      <ion-toolbar>
        <ion-title>Discover</ion-title>
      </ion-toolbar>
      <ion-toolbar>
        <ion-searchbar
          placeholder="Search public competitions"
          [debounce]="0"
          (ionInput)="onQuery($any($event).detail.value ?? '')"
        />
      </ion-toolbar>
    </ion-header>

    <ion-content fullscreen="true">
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (error()) {
        <div class="fm-empty">
          <ion-icon name="alert-circle-outline" aria-hidden="true" />
          <h3>Search unavailable</h3>
          <p>{{ error() }}</p>
          <ion-button fill="clear" (click)="load()">Try again</ion-button>
        </div>
      } @else if (results().length === 0) {
        <div class="fm-empty">
          <ion-icon name="search-outline" aria-hidden="true" />
          <h3>{{ query() ? 'Nothing matched' : 'No public competitions yet' }}</h3>
          <p>
            @if (query()) {
              Try a shorter search, or a sport name.
            } @else {
              Public competitions others create will show up here.
            }
          </p>
        </div>
      } @else {
        @for (competition of results(); track competition.id; let index = $index) {
          <fm-competition-card
            [style.--i]="index"
            [competition]="competition"
            (open)="open(competition)"
          />
        }
      }
    </ion-content>
  `,
  styles: [
    `
      .centered {
        display: grid;
        place-items: center;
        padding: 64px 0;
      }
    `,
  ],
})
export class DiscoverPage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private readonly queries = new Subject<string>();

  readonly results = signal<Competition[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly query = signal('');

  constructor() {
    this.queries
      .pipe(
        debounceTime(280),
        distinctUntilChanged(),
        switchMap((query) => {
          this.loading.set(true);
          this.query.set(query);
          return this.api.listCompetitions({ search: query, page_size: 30 });
        }),
        takeUntilDestroyed(),
      )
      .subscribe({
        next: (page) => {
          this.results.set(page.results);
          this.loading.set(false);
        },
        error: (err: unknown) => {
          this.error.set(extractErrorMessage(err));
          this.loading.set(false);
        },
      });
  }

  ngOnInit(): void {
    this.load();
  }

  ionViewWillEnter(): void {
    this.load(this.results().length === 0);
  }

  load(showSpinner = true): void {
    if (showSpinner) this.loading.set(true);
    this.error.set(null);

    this.api.listCompetitions({ search: this.query(), page_size: 30 }).subscribe({
      next: (page) => {
        this.results.set(page.results);
        this.loading.set(false);
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err));
        this.loading.set(false);
      },
    });
  }

  onQuery(value: string): void {
    this.queries.next(value.trim());
  }

  open(competition: Competition): void {
    void this.router.navigate(['/tabs/competitions', competition.id]);
  }
}
