import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import {
  AlertController,
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
  ConsentRecord,
  GuardianLink,
  PlayerProfile,
  ScoutingCatalog,
  Visibility,
} from '../../core/scouting.models';
import { ScoutingService } from '../../core/scouting.service';

interface Decision {
  visibility: Visibility;
  sections: Set<string>;
  note: string;
}

@Component({
  selector: 'fm-guardian-consent',
  standalone: true,
  imports: [DatePipe, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonIcon, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './scouting.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button defaultHref="/tabs/scouting" /></ion-buttons>
        <ion-title>Guardian consent</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      <p class="lede">
        Players under {{ catalog()?.age_of_consent ?? 18 }} stay hidden from scouts until you agree. You choose how
        visible they are and what is shared. Contact details are never shown, and you can withdraw consent at any time.
      </p>

      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (links().length === 0) {
        <div class="fm-empty">
          <ion-icon name="shield-checkmark-outline" aria-hidden="true" />
          <h3>No requests</h3>
          <p>When a player invites this email address as their guardian, it shows up here.</p>
        </div>
      } @else {
        @for (link of links(); track link.id) {
          <article class="fm-card section fm-enter">
            <header class="who">
              <span class="avatar">{{ link.player_name.charAt(0) }}</span>
              <div class="grow">
                <h3>{{ link.player_name }}</h3>
                <p class="hint">{{ link.player_age_group ?? 'Age not set' }} · you are listed as {{ link.relationship || 'guardian' }}</p>
              </div>
              <span class="badge" [class.ok]="link.status === 'active'" [class.warn]="link.status === 'pending'">
                {{ link.status === 'active' ? 'Confirmed' : 'Needs you' }}
              </span>
            </header>

            @if (link.status === 'pending') {
              <p class="hint">Are you this player's parent or legal guardian?</p>
              <div class="row">
                <button type="button" class="btn ghost" [disabled]="busy()" (click)="decline(link)">No, decline</button>
                <button type="button" class="btn" [disabled]="busy()" (click)="accept(link)">Yes, I am</button>
              </div>
            } @else if (profiles()[link.profile_id]; as profile) {
              <div class="notice" [class.ok]="profile.consent_status.granted">
                @if (profile.consent_status.granted) {
                  Consent given: <strong>{{ label(profile.consent_status.visibility ?? 'private') }}</strong>.
                  Scouts currently see this profile as <strong>{{ label(profile.effective_visibility) }}</strong>.
                } @else {
                  No consent yet. The profile is hidden from scouts.
                }
              </div>

              <h4>What the player has added</h4>
              <ul class="facts">
                <li>{{ profile.sports.length }} sport(s): {{ sportNames(profile) || 'none yet' }}</li>
                <li>{{ profile.measurements.length }} measurement(s), {{ profile.videos.length }} video(s)</li>
                <li>Their own setting: {{ label(profile.visibility) }}</li>
              </ul>

              <h4>Who may see it</h4>
              <div class="segmented">
                @for (option of options; track option.key) {
                  <button type="button" [class.on]="decision(link).visibility === option.key" (click)="setVisibility(link, option.key)">
                    {{ option.label }}
                  </button>
                }
              </div>

              <h4>What is shared</h4>
              <div class="chips">
                @for (section of catalog()?.consent_sections ?? []; track section.key) {
                  <button
                    type="button"
                    class="chip"
                    [class.on]="section.required || decision(link).sections.has(section.key)"
                    [class.locked]="section.required"
                    [disabled]="section.required"
                    (click)="toggleSection(link, section.key)"
                  >
                    {{ section.required ? '✓ ' : '' }}{{ section.label }}
                  </button>
                }
              </div>
              <p class="hint">Injuries are never shared by consent; the player shares one at a time.</p>

              <label class="field">
                Note (optional)
                <input maxlength="280" [value]="decision(link).note" (input)="setNote(link, $any($event.target).value)" />
              </label>

              <div class="row">
                @if (profile.consent_status.granted) {
                  <button type="button" class="btn danger" [disabled]="busy()" (click)="revoke(link)">Withdraw consent</button>
                } @else {
                  <span></span>
                }
                <button type="button" class="btn" [disabled]="busy()" (click)="grant(link)">
                  {{ profile.consent_status.granted ? 'Update consent' : 'Give consent' }}
                </button>
              </div>

              <h4>History</h4>
              <ul class="list">
                @for (record of history()[link.profile_id] ?? []; track record.id) {
                  <li class="list-row">
                    <div class="grow">
                      <strong>{{ record.action === 'granted' ? 'Shared' : 'Withdrawn' }} by {{ record.given_by_name || record.given_as }}</strong>
                      <small>{{ record.created_at | date: 'd MMM y, HH:mm' }}{{ record.visibility ? ' · ' + label(record.visibility) : '' }}</small>
                    </div>
                  </li>
                } @empty {
                  <li class="hint">No decisions yet.</li>
                }
              </ul>
            }
          </article>
        }
      }
      <div style="height: 32px"></div>
    </ion-content>
  `,
  styles: [
    `
      .who {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 10px;

        h3 {
          margin: 0;
        }

        .hint {
          margin: 0;
        }

        .grow {
          flex: 1 1 auto;
        }
      }

      h4 {
        margin: 16px 0 8px;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--ion-color-medium);
      }

      .notice {
        margin: 0;
      }

      .facts {
        margin: 0;
        padding-left: 1.1rem;
        font-size: 0.88rem;
        line-height: 1.6;
      }
    `,
  ],
})
export class GuardianPage {
  private readonly scouting = inject(ScoutingService);
  private readonly toasts = inject(ToastController);
  private readonly alerts = inject(AlertController);

  readonly catalog = signal<ScoutingCatalog | null>(null);
  readonly links = signal<GuardianLink[]>([]);
  readonly profiles = signal<Partial<Record<string, PlayerProfile>>>({});
  readonly history = signal<Partial<Record<string, ConsentRecord[]>>>({});
  readonly decisions = signal<Record<string, Decision>>({});
  readonly loading = signal(true);
  readonly busy = signal(false);

  readonly options: Array<{ key: Visibility; label: string }> = [
    { key: 'scouts', label: 'Scouts only' },
    { key: 'public', label: 'Public' },
  ];

  ionViewWillEnter(): void {
    this.scouting.catalog().subscribe((catalog) => this.catalog.set(catalog));
    this.load();
  }

  private load(): void {
    this.scouting.guardianLinks().subscribe({
      next: (links) => {
        this.links.set(links);
        this.loading.set(false);
        for (const link of links.filter((item) => item.status === 'active')) this.loadProfile(link.profile_id);
      },
      error: async (err: unknown) => {
        this.loading.set(false);
        await this.toast(extractErrorMessage(err, 'Could not load guardian requests.'), 'danger');
      },
    });
  }

  private loadProfile(profileId: string): void {
    this.scouting.getProfile(profileId).subscribe((profile) => this.applyProfile(profile as PlayerProfile));
    this.scouting
      .guardianConsents(profileId)
      .subscribe((rows) => this.history.update((all) => ({ ...all, [profileId]: rows })));
  }

  private applyProfile(profile: PlayerProfile): void {
    this.profiles.update((all) => ({ ...all, [profile.id]: profile }));
    const status = profile.consent_status;
    this.decisions.update((all) => ({
      ...all,
      [profile.id]: {
        visibility: status.visibility && status.visibility !== 'private' ? status.visibility : 'scouts',
        sections: new Set(status.sections),
        note: '',
      },
    }));
  }

  decision(link: GuardianLink): Decision {
    return this.decisions()[link.profile_id] ?? { visibility: 'scouts', sections: new Set(), note: '' };
  }

  private patch(link: GuardianLink, change: Partial<Decision>): void {
    this.decisions.update((all) => ({ ...all, [link.profile_id]: { ...this.decision(link), ...change } }));
  }

  setVisibility(link: GuardianLink, visibility: Visibility): void {
    this.patch(link, { visibility });
  }

  toggleSection(link: GuardianLink, key: string): void {
    const sections = new Set(this.decision(link).sections);
    if (sections.has(key)) sections.delete(key);
    else sections.add(key);
    this.patch(link, { sections });
  }

  setNote(link: GuardianLink, note: string): void {
    this.patch(link, { note });
  }

  accept(link: GuardianLink): void {
    this.busy.set(true);
    this.scouting.acceptGuardian(link.id).subscribe({
      next: async () => {
        this.busy.set(false);
        await this.toast('Confirmed. Now choose what scouts may see.', 'success');
        this.load();
      },
      error: (err: unknown) => this.fail(err),
    });
  }

  decline(link: GuardianLink): void {
    this.busy.set(true);
    this.scouting.declineGuardian(link.id).subscribe({
      next: () => {
        this.busy.set(false);
        this.load();
      },
      error: (err: unknown) => this.fail(err),
    });
  }

  grant(link: GuardianLink): void {
    const decision = this.decision(link);
    this.busy.set(true);
    this.scouting
      .grantConsent(link.profile_id, {
        visibility: decision.visibility,
        sections: [...decision.sections],
        note: decision.note,
      })
      .subscribe({
        next: async (profile) => {
          this.busy.set(false);
          this.applyProfile(profile);
          this.loadProfile(link.profile_id);
          await this.toast('Consent recorded.', 'success');
        },
        error: (err: unknown) => this.fail(err),
      });
  }

  async revoke(link: GuardianLink): Promise<void> {
    const alert = await this.alerts.create({
      header: 'Withdraw consent?',
      message: `${link.player_name}'s profile will be hidden from scouts straight away.`,
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        {
          text: 'Withdraw',
          role: 'destructive',
          handler: () => {
            this.busy.set(true);
            this.scouting.revokeConsent(link.profile_id).subscribe({
              next: async (profile) => {
                this.busy.set(false);
                this.applyProfile(profile);
                this.loadProfile(link.profile_id);
                await this.toast('Consent withdrawn. The profile is hidden.', 'success');
              },
              error: (err: unknown) => this.fail(err),
            });
          },
        },
      ],
    });
    await alert.present();
  }

  label(value: string): string {
    return value === 'public' ? 'Public' : value === 'scouts' ? 'Scouts only' : 'Hidden';
  }

  sportNames(profile: PlayerProfile): string {
    return profile.sports.map((sport) => sport.sport_label).join(', ');
  }

  private async fail(err: unknown): Promise<void> {
    this.busy.set(false);
    await this.toast(extractErrorMessage(err, 'That did not save.'), 'danger');
  }

  private async toast(message: string, color: 'success' | 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2400, position: 'top' });
    await toast.present();
  }
}
