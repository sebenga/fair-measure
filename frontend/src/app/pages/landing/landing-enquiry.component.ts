import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { IonIcon } from '@ionic/angular/standalone';
import { addIcons } from 'ionicons';
import {
  arrowForwardOutline,
  briefcaseOutline,
  checkmarkCircle,
  megaphoneOutline,
  peopleOutline,
  schoolOutline,
  shirtOutline,
  trophyOutline,
} from 'ionicons/icons';

import { ApiService } from '../../core/api.service';

type Audience = 'corporate' | 'government';

const PERKS = [
  {
    icon: 'megaphone-outline',
    title: 'Your logo where fans look',
    body: 'The sponsor showcase, league feeds and match-day pages.',
  },
  {
    icon: 'shirt-outline',
    title: 'Kit, naming rights and merchandise',
    body: 'Put your colours on the cup, the jerseys and the trophy.',
  },
  {
    icon: 'trophy-outline',
    title: 'Staff leagues and KPI cups',
    body: 'Score teams on targets, safety or wellness and review the table together.',
  },
  {
    icon: 'people-outline',
    title: 'School and civic programmes',
    body: 'Ward to provincial competitions with public tables for residents.',
  },
];

const INTERESTS: Record<Audience, string[]> = {
  corporate: ['Sponsorship', 'Staff league', 'KPI league', 'Merchandise', 'Broadcast board'],
  government: ['School programme', 'Municipal league', 'Provincial programme', 'Clean-up challenge', 'Talent pathway'],
};

/** The partnerships pitch and enquiry form at the foot of the landing page. */
@Component({
  selector: 'fm-landing-enquiry',
  standalone: true,
  imports: [IonIcon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="panel">
      <aside class="pitch">
        <img src="assets/landing/gov-programme.jpg" alt="" loading="lazy" decoding="async" />
        <div class="pitch-copy">
          <p class="eyebrow">Partnerships</p>
          <h2>Put your name where the community plays</h2>
          <p class="lede">
            From the Saturday league to the boardroom KPI cup, partners sit in the middle of the
            moments people share.
          </p>
          <ul class="perks">
            @for (perk of perks; track perk.title) {
              <li>
                <span class="icon"><ion-icon [name]="perk.icon" aria-hidden="true" /></span>
                <span>
                  <strong>{{ perk.title }}</strong>
                  <small>{{ perk.body }}</small>
                </span>
              </li>
            }
          </ul>
          <p class="who">
            @for (who of audiences; track who) {
              <span>{{ who }}</span>
            }
          </p>
        </div>
      </aside>

      <div class="form-card">
        @if (sent()) {
          <div class="done" role="status">
            <ion-icon name="checkmark-circle" aria-hidden="true" />
            <h3>Thanks, {{ sentName() }}.</h3>
            <p>Your enquiry is with partnerships. We will reply by email or on your cellphone.</p>
            <button type="button" class="ghost" (click)="reset()">Send another enquiry</button>
          </div>
        } @else {
          <h3>Book a corporate or government slot</h3>
          <p class="hint">Tell us who you are and what you would like to run or sponsor.</p>
          <form (submit)="submit($event)" novalidate>
            <div class="audience" role="radiogroup" aria-label="Who is enquiring">
              <button
                type="button"
                role="radio"
                [attr.aria-checked]="audience() === 'corporate'"
                [class.selected]="audience() === 'corporate'"
                (click)="choose('corporate')"
              >
                <ion-icon name="briefcase-outline" aria-hidden="true" />
                <span><strong>Corporate</strong><small>Brands, companies, staff leagues</small></span>
              </button>
              <button
                type="button"
                role="radio"
                [attr.aria-checked]="audience() === 'government'"
                [class.selected]="audience() === 'government'"
                (click)="choose('government')"
              >
                <ion-icon name="school-outline" aria-hidden="true" />
                <span><strong>Government</strong><small>Schools, municipalities, provinces</small></span>
              </button>
            </div>

            <fieldset class="interests">
              <legend>I'm interested in</legend>
              @for (interest of interests[audience()]; track interest) {
                <button
                  type="button"
                  [class.on]="picked().includes(interest)"
                  [attr.aria-pressed]="picked().includes(interest)"
                  (click)="toggle(interest)"
                >
                  {{ interest }}
                </button>
              }
            </fieldset>

            <div class="fields">
              <label>
                Organisation
                <input name="organisation" required maxlength="200" autocomplete="organization" [disabled]="sending()" />
              </label>
              <label>
                Your name
                <input name="contact_name" required maxlength="160" autocomplete="name" [disabled]="sending()" />
              </label>
              <label>
                Email
                <input name="email" type="email" required autocomplete="email" [disabled]="sending()" />
              </label>
              <label>
                Cellphone number
                <input name="phone" type="tel" required maxlength="32" autocomplete="tel" [disabled]="sending()" />
              </label>
              <label class="wide">
                What would you like to run or sponsor?
                <textarea
                  name="message"
                  required
                  minlength="12"
                  rows="4"
                  [placeholder]="placeholder()"
                  [disabled]="sending()"
                ></textarea>
              </label>
            </div>

            @if (error()) {
              <p class="error" role="alert">{{ error() }}</p>
            }
            <button type="submit" class="primary" [disabled]="sending()">
              {{ sending() ? 'Sending…' : 'Send enquiry' }}
              @if (!sending()) {
                <ion-icon name="arrow-forward-outline" aria-hidden="true" />
              }
            </button>
          </form>
        }
      </div>
    </div>
  `,
  styles: `
    :host {
      display: block;
    }
    .panel {
      display: grid;
      overflow: hidden;
      border-radius: 24px;
      background: var(--fm-surface, #fff);
      box-shadow: 0 14px 36px rgb(15 23 42 / 10%);
    }
    .pitch {
      position: relative;
      color: #fff;
      background: #0b1220;
    }
    .pitch > img {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .pitch::after {
      content: '';
      position: absolute;
      inset: 0;
      background:
        linear-gradient(160deg, rgb(15 118 110 / 88%) 0%, rgb(4 10 22 / 88%) 70%),
        linear-gradient(0deg, rgb(4 10 22 / 50%), transparent);
    }
    .pitch-copy {
      position: relative;
      z-index: 1;
      display: grid;
      gap: 14px;
      padding: 28px 22px;
    }
    .eyebrow {
      margin: 0;
      color: #5eead4;
      font-size: 0.72rem;
      font-weight: 800;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    h2 {
      margin: 0;
      font-size: clamp(1.5rem, 3.4vw, 2.2rem);
      line-height: 1.1;
      letter-spacing: -0.02em;
    }
    .lede {
      margin: 0;
      color: rgb(255 255 255 / 82%);
      line-height: 1.55;
    }
    .perks {
      display: grid;
      gap: 12px;
      margin: 4px 0 0;
      padding: 0;
      list-style: none;
    }
    .perks li {
      display: grid;
      grid-template-columns: 38px 1fr;
      gap: 12px;
      align-items: start;
    }
    .perks .icon {
      display: grid;
      place-items: center;
      width: 38px;
      height: 38px;
      border-radius: 12px;
      background: rgb(255 255 255 / 14%);
      font-size: 1.2rem;
    }
    .perks strong,
    .perks small {
      display: block;
    }
    .perks small {
      margin-top: 2px;
      color: rgb(255 255 255 / 72%);
      line-height: 1.4;
    }
    .who {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin: 4px 0 0;
    }
    .who span {
      padding: 4px 10px;
      border: 1px solid rgb(255 255 255 / 30%);
      border-radius: 999px;
      font-size: 0.74rem;
      font-weight: 700;
    }
    .form-card {
      padding: 24px 20px 26px;
    }
    h3 {
      margin: 0;
      font-size: 1.2rem;
    }
    .hint {
      margin: 6px 0 16px;
      color: var(--ion-color-medium);
    }
    form {
      display: grid;
      gap: 16px;
    }
    .audience {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }
    .audience button {
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 10px;
      align-items: center;
      padding: 12px;
      border: 1.5px solid var(--fm-line, #e2e8f0);
      border-radius: 14px;
      background: var(--fm-chip-bg, #f1f5f9);
      color: var(--fm-ink, #0f172a);
      font: inherit;
      text-align: left;
      cursor: pointer;
    }
    .audience ion-icon {
      font-size: 1.4rem;
      color: #0f766e;
    }
    .audience strong,
    .audience small {
      display: block;
    }
    .audience small {
      color: var(--ion-color-medium);
      font-size: 0.74rem;
    }
    .audience button.selected {
      border-color: #0f766e;
      background: var(--fm-chip-selected, #e6f4f2);
      box-shadow: 0 0 0 3px rgb(15 118 110 / 14%);
    }
    .interests {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin: 0;
      padding: 0;
      border: 0;
    }
    legend {
      width: 100%;
      margin-bottom: 8px;
      font-size: 0.82rem;
      font-weight: 700;
    }
    .interests button {
      padding: 7px 12px;
      border: 1px solid var(--fm-line, #e2e8f0);
      border-radius: 999px;
      background: transparent;
      color: var(--fm-ink, #0f172a);
      font: inherit;
      font-size: 0.82rem;
      font-weight: 650;
      cursor: pointer;
    }
    .interests button.on {
      border-color: #ea580c;
      background: #ea580c;
      color: #fff;
    }
    .fields {
      display: grid;
      gap: 12px;
    }
    label {
      display: grid;
      gap: 6px;
      font-size: 0.82rem;
      font-weight: 650;
    }
    input,
    textarea {
      box-sizing: border-box;
      width: 100%;
      padding: 11px 12px;
      border: 1px solid var(--fm-line, #e2e8f0);
      border-radius: 12px;
      background: var(--fm-field-bg, #fff);
      color: var(--fm-ink, #0f172a);
      font: inherit;
    }
    input:focus,
    textarea:focus {
      outline: 2px solid rgb(15 118 110 / 35%);
      border-color: #0f766e;
    }
    .error {
      margin: 0;
      color: var(--ion-color-danger);
      font-size: 0.86rem;
    }
    .primary,
    .ghost {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      min-height: 46px;
      padding: 0 18px;
      border-radius: 999px;
      font: inherit;
      font-weight: 800;
      cursor: pointer;
    }
    .primary {
      border: 0;
      background: linear-gradient(90deg, #0f766e, #0d9488);
      color: #fff;
      box-shadow: 0 8px 18px rgb(15 118 110 / 28%);
    }
    .primary:disabled {
      opacity: 0.6;
      cursor: default;
    }
    .ghost {
      border: 1px solid var(--fm-line, #e2e8f0);
      background: transparent;
      color: var(--fm-ink, #0f172a);
    }
    .done {
      display: grid;
      justify-items: start;
      gap: 10px;
      padding: 20px 0;
    }
    .done ion-icon {
      font-size: 3rem;
      color: #16a34a;
    }
    .done p {
      margin: 0;
      color: var(--ion-color-medium);
      line-height: 1.5;
    }
    @media (min-width: 880px) {
      .panel {
        grid-template-columns: 0.95fr 1.05fr;
      }
      .pitch-copy {
        padding: 40px 36px;
      }
      .form-card {
        padding: 36px;
      }
      .fields {
        grid-template-columns: 1fr 1fr;
      }
      .fields .wide {
        grid-column: 1 / -1;
      }
    }
  `,
})
export class LandingEnquiryComponent {
  private readonly api = inject(ApiService);

  readonly perks = PERKS;
  readonly interests = INTERESTS;
  readonly audiences = ['Clubs', 'Schools', 'Municipalities', 'Companies', 'Brands'];
  readonly audience = signal<Audience>('corporate');
  readonly picked = signal<string[]>([]);
  readonly sending = signal(false);
  readonly sent = signal(false);
  readonly sentName = signal('');
  readonly error = signal<string | null>(null);

  constructor() {
    addIcons({
      arrowForwardOutline,
      briefcaseOutline,
      checkmarkCircle,
          megaphoneOutline,
      peopleOutline,
      schoolOutline,
      shirtOutline,
      trophyOutline,
    });
  }

  choose(audience: Audience): void {
    if (this.audience() === audience) return;
    this.audience.set(audience);
    this.picked.set([]);
  }

  toggle(interest: string): void {
    this.picked.update((list) =>
      list.includes(interest) ? list.filter((item) => item !== interest) : [...list, interest],
    );
  }

  placeholder(): string {
    return this.audience() === 'government'
      ? 'e.g. A district schools cup for 40 schools, with public tables for parents.'
      : 'e.g. A quarterly KPI league for 6 branches, and our logo on the Saturday league.';
  }

  submit(event: Event): void {
    event.preventDefault();
    const form = event.target as HTMLFormElement;
    const data = new FormData(form);
    const value = (key: string) => String(data.get(key) ?? '').trim();
    const note = value('message');
    const interests = this.picked();
    const message = interests.length ? `Interested in: ${interests.join(', ')}.\n\n${note}` : note;
    if (!value('organisation') || !value('contact_name') || !value('email') || value('phone').length < 7 || note.length < 12) {
      this.error.set('Fill in the organisation, your name, email, cellphone and a short note.');
      return;
    }
    this.sending.set(true);
    this.error.set(null);
    this.api
      .sendEnquiry({
        audience: this.audience(),
        organisation: value('organisation'),
        contact_name: value('contact_name'),
        email: value('email'),
        phone: value('phone'),
        message,
      })
      .subscribe({
        next: () => {
          this.sending.set(false);
          this.sentName.set(value('contact_name').split(/\s+/)[0]);
          this.sent.set(true);
          form.reset();
          this.picked.set([]);
        },
        error: () => {
          this.sending.set(false);
          this.error.set('Could not send that just now. Try again in a moment.');
        },
      });
  }

  reset(): void {
    this.sent.set(false);
    this.error.set(null);
  }
}
