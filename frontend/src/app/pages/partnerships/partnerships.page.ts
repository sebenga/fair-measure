import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import {
  IonBackButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonTitle,
  IonToolbar,
} from '@ionic/angular/standalone';
import { catchError, of } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import {
  FALLBACK_CORPORATE,
  FALLBACK_GOVERNMENT,
  FALLBACK_LOGOS,
} from '../../core/marketing-fallbacks';
import type { MarketingAudience, MarketingPlacement } from '../../core/models';

@Component({
  selector: 'fm-partnerships',
  standalone: true,
  imports: [IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './partnerships.page.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start">
          <ion-back-button [defaultHref]="backHref()" />
        </ion-buttons>
        <ion-title>Partnerships</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      <div class="page">
        <header class="hero">
          <p>Commercial</p>
          <h1>Book a corporate or government slot</h1>
          <p class="lede">
            Workplace leagues, civic programmes, naming rights and public results — one place to
            brief partnerships as this catalogue grows.
          </p>
        </header>

        <div class="layout">
          <div class="tracks">
            <section>
              <p class="kicker">Corporate</p>
              <h2>Workplace and brand</h2>
              <div class="offers">
                @for (ad of corporate(); track ad.id) {
                  <button
                    type="button"
                    class="offer"
                    data-kind="corporate"
                    [class.selected]="selectedId() === ad.id"
                    (click)="selectPlacement(ad)"
                  >
                    <span>Corporate</span>
                    <strong>{{ ad.name }}</strong>
                    <small>{{ ad.tagline || ad.body }}</small>
                  </button>
                }
              </div>
            </section>

            <section>
              <p class="kicker">Government</p>
              <h2>Schools, municipalities and programmes</h2>
              <div class="offers">
                @for (ad of government(); track ad.id) {
                  <button
                    type="button"
                    class="offer"
                    data-kind="government"
                    [class.selected]="selectedId() === ad.id"
                    (click)="selectPlacement(ad)"
                  >
                    <span>Government</span>
                    <strong>{{ ad.name }}</strong>
                    <small>{{ ad.tagline || ad.body }}</small>
                  </button>
                }
              </div>
            </section>

            @if (logos().length) {
              <section class="partners">
                <p class="kicker">Partners</p>
                <h2>Already on the public pages</h2>
                <div class="logo-row">
                  @for (logo of logos(); track logo.id) {
                    <span>{{ logo.name }}</span>
                  }
                </div>
              </section>
            }
          </div>

          <form class="enquire" id="enquire" (submit)="submitEnquiry($event)">
            <p class="kicker">Enquire</p>
            <h2>Tell us what you want to run</h2>
            <div class="audience">
              <button
                type="button"
                [class.selected]="enquiryAudience() === 'corporate'"
                (click)="setAudience('corporate')"
              >
                Corporate
              </button>
              <button
                type="button"
                [class.selected]="enquiryAudience() === 'government'"
                (click)="setAudience('government')"
              >
                Government
              </button>
            </div>
            <label>
              Organisation
              <input name="organisation" required maxlength="200" [disabled]="enquirySending()" />
            </label>
            <label>
              Your name
              <input
                name="contact_name"
                required
                maxlength="160"
                [value]="auth.user()?.display_name || ''"
                [disabled]="enquirySending()"
              />
            </label>
            <label>
              Email
              <input
                name="email"
                type="email"
                required
                [value]="auth.user()?.email || ''"
                [disabled]="enquirySending()"
              />
            </label>
            <label>
              What would you like to run or sponsor?
              <textarea
                name="message"
                required
                minlength="12"
                rows="5"
                [value]="draftMessage()"
                [disabled]="enquirySending()"
              ></textarea>
            </label>
            @if (enquiryError()) {
              <p class="hint" role="alert">{{ enquiryError() }}</p>
            }
            @if (enquirySent()) {
              <p class="hint">Received. Partnerships will come back to you.</p>
            }
            <button type="submit" [disabled]="enquirySending()">
              {{ enquirySending() ? 'Sending…' : 'Send enquiry' }}
            </button>
          </form>
        </div>
      </div>
    </ion-content>
  `,
})
export class PartnershipsPage {
  private readonly api = inject(ApiService);
  readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  readonly placements = signal<MarketingPlacement[]>([]);
  readonly selectedId = signal('');
  readonly enquiryAudience = signal<MarketingAudience>('corporate');
  readonly draftMessage = signal('');
  readonly enquirySending = signal(false);
  readonly enquirySent = signal(false);
  readonly enquiryError = signal<string | null>(null);

  readonly corporate = computed(() => {
    const rows = this.placements().filter(
      (item) => item.audience === 'corporate' && item.slot === 'feature',
    );
    return rows.length ? rows : FALLBACK_CORPORATE;
  });
  readonly government = computed(() => {
    const rows = this.placements().filter(
      (item) => item.audience === 'government' && item.slot === 'feature',
    );
    return rows.length ? rows : FALLBACK_GOVERNMENT;
  });
  readonly logos = computed(() => {
    const rows = this.placements().filter((item) => item.slot === 'logo');
    return rows.length ? rows : FALLBACK_LOGOS;
  });

  constructor() {
    this.api.listPlacements().pipe(catchError(() => of([] as MarketingPlacement[]))).subscribe({
      next: (rows) => this.placements.set(rows),
    });

    this.route.queryParamMap.pipe(takeUntilDestroyed()).subscribe((params) => {
      const audience = params.get('audience');
      if (audience === 'government' || audience === 'corporate') {
        this.enquiryAudience.set(audience);
      }
      const placementId = params.get('placement');
      if (placementId) this.selectedId.set(placementId);
    });
  }

  backHref(): string {
    return this.auth.isAuthenticated() ? '/tabs/discover' : '/';
  }

  setAudience(audience: 'corporate' | 'government'): void {
    this.enquiryAudience.set(audience);
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { audience },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
  }

  selectPlacement(placement: MarketingPlacement): void {
    this.selectedId.set(placement.id);
    this.enquiryAudience.set(placement.audience === 'government' ? 'government' : 'corporate');
    this.draftMessage.set(
      [placement.name, placement.tagline, placement.body].filter(Boolean).join(' — '),
    );
    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { audience: this.enquiryAudience(), placement: placement.id },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
    document.getElementById('enquire')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  submitEnquiry(event: Event): void {
    event.preventDefault();
    const form = event.target as HTMLFormElement;
    const data = new FormData(form);
    const organisation = String(data.get('organisation') ?? '').trim();
    const contact_name = String(data.get('contact_name') ?? '').trim();
    const email = String(data.get('email') ?? '').trim();
    const message = String(data.get('message') ?? '').trim();
    if (!organisation || !contact_name || !email || message.length < 12) {
      this.enquiryError.set('Fill in the organisation, your name, email and a short note.');
      return;
    }
    this.enquirySending.set(true);
    this.enquiryError.set(null);
    this.api
      .sendEnquiry({
        audience: this.enquiryAudience() === 'government' ? 'government' : 'corporate',
        organisation,
        contact_name,
        email,
        message,
      })
      .subscribe({
        next: () => {
          this.enquirySending.set(false);
          this.enquirySent.set(true);
          this.draftMessage.set('');
          form.reset();
        },
        error: () => {
          this.enquirySending.set(false);
          this.enquiryError.set('Could not send that just now. Try again.');
        },
      });
  }
}
