import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
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
import { Observable } from 'rxjs';

import { extractErrorMessage } from '../../core/error-message';
import type {
  CatalogSport,
  ConsentRecord,
  PlayerProfile,
  PlayerSport,
  ScoutingCatalog,
  Visibility,
} from '../../core/scouting.models';
import { ScoutingService } from '../../core/scouting.service';
import { UploadService } from '../../core/upload.service';

type Identity = Pick<
  PlayerProfile,
  | 'first_name'
  | 'last_name'
  | 'photo_url'
  | 'date_of_birth'
  | 'gender_category'
  | 'nationality'
  | 'region'
  | 'school_or_club'
  | 'bio'
  | 'availability'
  | 'availability_note'
>;

const EMPTY_IDENTITY: Identity = {
  first_name: '',
  last_name: '',
  photo_url: '',
  date_of_birth: null,
  gender_category: '',
  nationality: '',
  region: '',
  school_or_club: '',
  bio: '',
  availability: 'available',
  availability_note: '',
};

@Component({
  selector: 'fm-talent-profile',
  standalone: true,
  imports: [DatePipe, IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonIcon, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './scouting.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button defaultHref="/tabs/scouting" /></ion-buttons>
        <ion-title>{{ profile() ? 'My talent profile' : 'Create talent profile' }}</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else {
        @if (profile(); as p) {
          <section class="summary fm-enter">
            <span class="avatar large">
              @if (p.photo_url) {
                <img [src]="p.photo_url" alt="" />
              } @else {
                {{ initials(p.first_name, p.last_name) }}
              }
            </span>
            <div>
              <h2>{{ p.first_name }} {{ p.last_name }}</h2>
              <p>
                @if (p.age !== null) {
                  {{ p.age }} years ·
                }
                {{ p.age_group?.label ?? 'Add your date of birth' }}
              </p>
              <span class="badge" [class.ok]="p.effective_visibility !== 'private'" [class.warn]="p.effective_visibility === 'private'">
                {{ visibilityLabel(p.effective_visibility) }}
              </span>
            </div>
          </section>

          @if (p.consent_status.needed) {
            <div class="notice" [class.ok]="p.consent_status.granted">
              @if (p.consent_status.missing_date_of_birth) {
                Add your date of birth. Profiles without one stay private so we can protect minors.
              } @else if (p.consent_status.granted) {
                A guardian consented to <strong>{{ visibilityLabel(p.consent_status.visibility ?? 'private') }}</strong>.
                Your profile is shown at the lower of their choice and yours.
              } @else {
                You are under {{ catalog()?.age_of_consent ?? 18 }}. Scouts cannot see your profile until a
                parent or guardian approves it. Invite them below.
              }
            </div>
          }
        } @else {
          <p class="lede">
            Your talent profile is what scouts see. You decide how visible it is, and phone numbers and
            email addresses are never shown to anyone.
          </p>
        }

        <form class="fm-card section" (submit)="saveIdentity($event)">
          <h3>About you</h3>
          <div class="row">
            <label class="field">First name<input required [value]="draft().first_name" (input)="set('first_name', $event)" /></label>
            <label class="field">Last name<input [value]="draft().last_name" (input)="set('last_name', $event)" /></label>
          </div>
          <div class="row">
            <label class="field">Date of birth<input type="date" [value]="draft().date_of_birth ?? ''" (input)="set('date_of_birth', $event)" /></label>
            <label class="field">
              Category
              <select [value]="draft().gender_category" (change)="set('gender_category', $event)">
                <option value="">Choose</option>
                @for (item of catalog()?.gender_categories ?? []; track item.key) {
                  <option [value]="item.key" [selected]="item.key === draft().gender_category">{{ item.label }}</option>
                }
              </select>
            </label>
          </div>
          <div class="row">
            <label class="field">Nationality<input [value]="draft().nationality" (input)="set('nationality', $event)" /></label>
            <label class="field">
              Province / region
              <select [value]="draft().region" (change)="set('region', $event)">
                <option value="">Choose</option>
                @for (item of catalog()?.regions ?? []; track item.key) {
                  <option [value]="item.key" [selected]="item.key === draft().region">{{ item.label }}</option>
                }
              </select>
            </label>
          </div>
          <label class="field">School or club<input [value]="draft().school_or_club" (input)="set('school_or_club', $event)" /></label>
          <label class="field">Photo link<input type="url" placeholder="https://" [value]="draft().photo_url" (input)="set('photo_url', $event)" /></label>
          <label class="field">About me<textarea maxlength="1000" [value]="draft().bio" (input)="set('bio', $event)"></textarea></label>
          <div class="row">
            <label class="field">
              Availability
              <select [value]="draft().availability" (change)="set('availability', $event)">
                <option value="available" [selected]="draft().availability === 'available'">Available</option>
                <option value="limited" [selected]="draft().availability === 'limited'">Limited</option>
                <option value="unavailable" [selected]="draft().availability === 'unavailable'">Not available</option>
                <option value="injured" [selected]="draft().availability === 'injured'">Injured</option>
              </select>
            </label>
            <label class="field">Note<input maxlength="200" [value]="draft().availability_note" (input)="set('availability_note', $event)" /></label>
          </div>
          <button type="submit" class="btn block" [disabled]="busy() || !draft().first_name.trim()">
            {{ profile() ? 'Save changes' : 'Create my profile' }}
          </button>
        </form>

        @if (profile(); as p) {
          <section class="fm-card section">
            <h3>Who can see my profile</h3>
            <p class="hint">You can change this at any time. Choosing "Only me" hides it from everyone straight away.</p>
            <div class="segmented" role="radiogroup" aria-label="Visibility">
              @for (option of visibilityOptions; track option.key) {
                <button type="button" role="radio" [attr.aria-checked]="p.visibility === option.key" [class.on]="p.visibility === option.key" (click)="setVisibility(option.key)">
                  {{ option.label }}
                </button>
              }
            </div>
          </section>

          <section class="fm-card section">
            <h3>Sports and positions</h3>
            @for (sport of p.sports; track sport.id) {
              <div class="sport">
                <div class="sport-head">
                  <strong>{{ sport.sport_label }}</strong>
                  @if (sport.is_primary) {
                    <span class="badge info">Main sport</span>
                  } @else {
                    <button type="button" class="btn ghost small" (click)="makePrimary(sport)">Make main</button>
                  }
                  <button type="button" class="btn danger small" (click)="removeSport(sport)" aria-label="Remove sport">Remove</button>
                </div>
                <p class="hint">Main position</p>
                <div class="chips">
                  @for (position of positionsOf(sport.sport); track position.key) {
                    <button type="button" class="chip" [class.on]="sport.primary_position === position.key" (click)="setPrimaryPosition(sport, position.key)">
                      {{ position.label }}
                    </button>
                  }
                </div>
                <p class="hint">Other positions</p>
                <div class="chips">
                  @for (position of positionsOf(sport.sport); track position.key) {
                    @if (position.key !== sport.primary_position) {
                      <button type="button" class="chip" [class.on]="sport.secondary_positions.includes(position.key)" (click)="toggleSecondary(sport, position.key)">
                        {{ position.label }}
                      </button>
                    }
                  }
                </div>
              </div>
            }
            <div class="row add">
              <label class="field">
                Add a sport
                <select [value]="newSport()" (change)="newSport.set($any($event.target).value)">
                  <option value="">Choose</option>
                  @for (sport of availableSports(); track sport.key) {
                    <option [value]="sport.key">{{ sport.label }}</option>
                  }
                </select>
              </label>
              <button type="button" class="btn ghost" [disabled]="!newSport() || busy()" (click)="addSport()">Add</button>
            </div>
          </section>

          <section class="fm-card section">
            <h3>Physical</h3>
            <p class="hint">Each entry is dated. A coach on your team can add verified ones; yours show as self-reported.</p>
            <ul class="list">
              @for (item of p.measurements; track item.id) {
                <li class="list-row">
                  <div class="grow">
                    <strong>{{ item.label }}: {{ item.value !== null ? trim(item.value) + ' ' + item.unit : item.text_value }}</strong>
                    <small>{{ item.measured_on | date: 'd MMM y' }}</small>
                  </div>
                  @if (item.verified) {
                    <span class="badge ok">Verified · {{ item.verified_by_name }}</span>
                  } @else {
                    <span class="badge">Self-reported</span>
                    <button type="button" class="btn danger small" (click)="removeMeasurement(item.id)" aria-label="Remove">✕</button>
                  }
                </li>
              } @empty {
                <li class="hint">No measurements yet.</li>
              }
            </ul>
            <div class="row">
              <label class="field">
                Measurement
                <select [value]="measureKind()" (change)="measureKind.set($any($event.target).value); measureValue.set('')">
                  @for (spec of catalog()?.measurements ?? []; track spec.key) {
                    <option [value]="spec.key" [selected]="spec.key === measureKind()">{{ spec.label }}</option>
                  }
                </select>
              </label>
              @if (measureSpec()?.kind === 'choice') {
                <label class="field">
                  Value
                  <select [value]="measureValue()" (change)="measureValue.set($any($event.target).value)">
                    <option value="">Choose</option>
                    @for (choice of measureSpec()?.choices ?? []; track choice) {
                      <option [value]="choice">{{ choice }}</option>
                    }
                  </select>
                </label>
              } @else {
                <label class="field">
                  Value ({{ measureSpec()?.unit }})
                  <input type="number" inputmode="decimal" min="0" step="0.1" [value]="measureValue()" (input)="measureValue.set($any($event.target).value)" />
                </label>
              }
            </div>
            <div class="row">
              <label class="field">Date<input type="date" [value]="measureDate()" (input)="measureDate.set($any($event.target).value)" /></label>
              <button type="button" class="btn ghost" [disabled]="!measureValue() || busy()" (click)="addMeasurement()">Add</button>
            </div>
          </section>

          <section class="fm-card section">
            <h3>Highlight videos</h3>
            <ul class="list">
              @for (video of p.videos; track video.id) {
                <li class="list-row">
                  <ion-icon name="videocam" aria-hidden="true" />
                  <div class="grow">
                    <strong>{{ video.title }}</strong>
                    <small>{{ video.status === 'ready' ? video.playback_url : 'Processing…' }}</small>
                  </div>
                  <button type="button" class="btn danger small" (click)="removeVideo(video.id)" aria-label="Remove video">✕</button>
                </li>
              } @empty {
                <li class="hint">Add a link to a match clip or upload one.</li>
              }
            </ul>
            <label class="field">Title<input maxlength="160" [value]="videoTitle()" (input)="videoTitle.set($any($event.target).value)" /></label>
            <label class="field">Link<input type="url" placeholder="https://" [value]="videoUrl()" (input)="videoUrl.set($any($event.target).value)" /></label>
            <div class="row">
              <button type="button" class="btn ghost" [disabled]="!videoTitle().trim() || !videoUrl().trim() || busy()" (click)="addVideoLink()">Add link</button>
              <label class="btn ghost upload">
                Upload video
                <input type="file" accept="video/*" (change)="uploadVideo($event)" hidden />
              </label>
            </div>
          </section>

          <section class="fm-card section">
            <h3>Injury history</h3>
            <p class="hint">Private by default. Only you and your guardian see these unless you share one with scouts.</p>
            <ul class="list">
              @for (injury of p.injuries; track injury.id) {
                <li class="list-row">
                  <div class="grow">
                    <strong>{{ injury.description }}</strong>
                    <small>{{ injury.injured_on ? (injury.injured_on | date: 'd MMM y') : 'Date unknown' }}</small>
                  </div>
                  <button type="button" class="chip" [class.on]="injury.shared_with_scouts" (click)="toggleInjury(injury.id, !injury.shared_with_scouts)">
                    {{ injury.shared_with_scouts ? 'Shared' : 'Private' }}
                  </button>
                  <button type="button" class="btn danger small" (click)="removeInjury(injury.id)" aria-label="Remove injury">✕</button>
                </li>
              } @empty {
                <li class="hint">No injuries recorded.</li>
              }
            </ul>
            <div class="row">
              <label class="field">What happened<input maxlength="200" [value]="injuryText()" (input)="injuryText.set($any($event.target).value)" /></label>
              <label class="field">When<input type="date" [value]="injuryDate()" (input)="injuryDate.set($any($event.target).value)" /></label>
            </div>
            <button type="button" class="btn ghost block" [disabled]="!injuryText().trim() || busy()" (click)="addInjury()">Add injury</button>
          </section>

          <section class="fm-card section">
            <h3>Parent or guardian</h3>
            <p class="hint">
              Needed if you are under {{ catalog()?.age_of_consent ?? 18 }}. They approve what scouts may see, and can
              withdraw it at any time.
            </p>
            <ul class="list">
              @for (link of p.guardians; track link.id) {
                @if (link.status !== 'revoked') {
                  <li class="list-row">
                    <div class="grow">
                      <strong>{{ link.guardian_name || link.invited_email }}</strong>
                      <small>{{ link.relationship || 'Guardian' }}</small>
                    </div>
                    <span class="badge" [class.ok]="link.status === 'active'" [class.warn]="link.status === 'pending'">
                      {{ link.status === 'active' ? 'Confirmed' : 'Waiting' }}
                    </span>
                    <button type="button" class="btn danger small" (click)="removeGuardian(link.id)" aria-label="Remove guardian">✕</button>
                  </li>
                }
              }
            </ul>
            <div class="row">
              <label class="field">Their email<input type="email" [value]="guardianEmail()" (input)="guardianEmail.set($any($event.target).value)" /></label>
              <label class="field">Relationship<input placeholder="Mother, father…" [value]="guardianRelationship()" (input)="guardianRelationship.set($any($event.target).value)" /></label>
            </div>
            <button type="button" class="btn ghost block" [disabled]="!guardianEmail().includes('@') || busy()" (click)="inviteGuardian()">
              Invite guardian
            </button>
          </section>

          <section class="fm-card section">
            <h3>Consent history</h3>
            <p class="hint">Every change to who can see your profile is recorded here.</p>
            <ul class="list">
              @for (record of consents(); track record.id) {
                <li class="list-row">
                  <div class="grow">
                    <strong>{{ record.action === 'granted' ? 'Shared' : 'Withdrawn' }} by {{ record.given_by_name || record.given_as }}</strong>
                    <small>{{ record.created_at | date: 'd MMM y, HH:mm' }}{{ record.visibility ? ' · ' + visibilityLabel(record.visibility) : '' }}</small>
                  </div>
                </li>
              } @empty {
                <li class="hint">Nothing yet.</li>
              }
            </ul>
          </section>

          <div class="section">
            <button type="button" class="btn ghost block" (click)="preview()">See it as a scout would</button>
          </div>
        }
        <div style="height: 32px"></div>
      }
    </ion-content>
  `,
  styles: [
    `
      .summary {
        display: flex;
        align-items: center;
        gap: 14px;
        margin: 12px 16px;

        h2 {
          margin: 0;
          font-size: 1.25rem;
        }

        p {
          margin: 2px 0 6px;
          color: var(--ion-color-medium);
        }
      }

      .sport {
        padding: 10px 0 14px;
        border-bottom: 1px solid var(--ion-color-step-50, #f1f2f4);
      }

      .sport-head {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 6px;

        strong {
          flex: 1 1 auto;
        }
      }

      .sport .hint {
        margin: 10px 0 6px;
      }

      .add,
      .row {
        align-items: end;
      }

      .row > .btn {
        margin-bottom: 12px;
      }

      .upload {
        margin-bottom: 12px;
      }
    `,
  ],
})
export class TalentProfilePage {
  private readonly scouting = inject(ScoutingService);
  private readonly uploads = inject(UploadService);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastController);

  readonly catalog = signal<ScoutingCatalog | null>(null);
  readonly profile = signal<PlayerProfile | null>(null);
  readonly consents = signal<ConsentRecord[]>([]);
  readonly draft = signal<Identity>({ ...EMPTY_IDENTITY });
  readonly loading = signal(true);
  readonly busy = signal(false);

  readonly newSport = signal('');
  readonly measureKind = signal('height');
  readonly measureValue = signal('');
  readonly measureDate = signal(new Date().toISOString().slice(0, 10));
  readonly videoTitle = signal('');
  readonly videoUrl = signal('');
  readonly injuryText = signal('');
  readonly injuryDate = signal('');
  readonly guardianEmail = signal('');
  readonly guardianRelationship = signal('');

  readonly visibilityOptions: Array<{ key: Visibility; label: string }> = [
    { key: 'private', label: 'Only me' },
    { key: 'scouts', label: 'Scouts' },
    { key: 'public', label: 'Public' },
  ];

  readonly measureSpec = computed(() =>
    (this.catalog()?.measurements ?? []).find((spec) => spec.key === this.measureKind()),
  );

  readonly availableSports = computed<CatalogSport[]>(() => {
    const taken = new Set((this.profile()?.sports ?? []).map((sport) => sport.sport));
    return (this.catalog()?.sports ?? []).filter((sport) => !taken.has(sport.key));
  });

  ionViewWillEnter(): void {
    this.scouting.catalog().subscribe((catalog) => this.catalog.set(catalog));
    this.scouting.myProfile().subscribe({
      next: (profile) => this.applyProfile(profile),
      error: (err: unknown) => {
        this.loading.set(false);
        if (err instanceof HttpErrorResponse && err.status === 404) return;
        void this.toast(extractErrorMessage(err, 'Could not load your profile.'), 'danger');
      },
    });
  }

  private applyProfile(profile: PlayerProfile): void {
    this.profile.set(profile);
    this.draft.set({
      first_name: profile.first_name,
      last_name: profile.last_name,
      photo_url: profile.photo_url,
      date_of_birth: profile.date_of_birth,
      gender_category: profile.gender_category,
      nationality: profile.nationality,
      region: profile.region,
      school_or_club: profile.school_or_club,
      bio: profile.bio,
      availability: profile.availability,
      availability_note: profile.availability_note,
    });
    this.loading.set(false);
    this.scouting.myConsents().subscribe((rows) => this.consents.set(rows));
  }

  set(field: keyof Identity, event: Event): void {
    const value = (event.target as HTMLInputElement).value;
    this.draft.update((current) => ({ ...current, [field]: field === 'date_of_birth' ? value || null : value }));
  }

  saveIdentity(event: Event): void {
    event.preventDefault();
    const body = this.draft();
    const request = this.profile() ? this.scouting.updateProfile(body) : this.scouting.createProfile(body);
    this.run(request, this.profile() ? 'Saved.' : 'Profile created. Add your sports next.');
  }

  setVisibility(visibility: Visibility): void {
    if (this.profile()?.visibility === visibility) return;
    this.run(this.scouting.updateProfile({ visibility }), `Visibility: ${this.visibilityLabel(visibility)}.`);
  }

  positionsOf(sportKey: string) {
    return (this.catalog()?.sports ?? []).find((sport) => sport.key === sportKey)?.positions ?? [];
  }

  addSport(): void {
    const sport = this.newSport();
    if (!sport) return;
    this.newSport.set('');
    this.run(this.scouting.addSport({ sport }));
  }

  makePrimary(sport: PlayerSport): void {
    this.run(this.scouting.updateSport(sport.id, { is_primary: true }));
  }

  setPrimaryPosition(sport: PlayerSport, key: string): void {
    this.run(this.scouting.updateSport(sport.id, { primary_position: key }));
  }

  toggleSecondary(sport: PlayerSport, key: string): void {
    const current = new Set(sport.secondary_positions);
    if (current.has(key)) current.delete(key);
    else current.add(key);
    this.run(this.scouting.updateSport(sport.id, { secondary_positions: [...current] }));
  }

  removeSport(sport: PlayerSport): void {
    this.runThenReload(this.scouting.removeSport(sport.id));
  }

  addMeasurement(): void {
    const spec = this.measureSpec();
    if (!spec) return;
    const body =
      spec.kind === 'choice'
        ? { kind: spec.key, text_value: this.measureValue(), measured_on: this.measureDate() }
        : { kind: spec.key, value: this.measureValue(), measured_on: this.measureDate() };
    this.measureValue.set('');
    this.run(this.scouting.addMeasurement(body), `${spec.label} added.`);
  }

  removeMeasurement(id: string): void {
    this.runThenReload(this.scouting.removeMeasurement(id));
  }

  addVideoLink(): void {
    this.run(
      this.scouting.addVideo({ title: this.videoTitle().trim(), url: this.videoUrl().trim() }),
      'Video added.',
    );
    this.videoTitle.set('');
    this.videoUrl.set('');
  }

  uploadVideo(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    const title = this.videoTitle().trim() || file.name;
    this.busy.set(true);
    this.uploads.upload({ file }).subscribe({
      next: (asset) => {
        this.busy.set(false);
        this.videoTitle.set('');
        this.run(this.scouting.addVideo({ title, media_asset: asset.id }), 'Video uploaded. It may take a moment to process.');
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Video upload is not available. Add a link instead.'), 'danger');
      },
    });
  }

  removeVideo(id: string): void {
    this.runThenReload(this.scouting.removeVideo(id));
  }

  addInjury(): void {
    this.run(
      this.scouting.addInjury({ description: this.injuryText().trim(), injured_on: this.injuryDate() || null }),
      'Injury added. It stays private.',
    );
    this.injuryText.set('');
    this.injuryDate.set('');
  }

  toggleInjury(id: string, shared: boolean): void {
    this.run(this.scouting.updateInjury(id, { shared_with_scouts: shared }), shared ? 'Shared with scouts.' : 'Private again.');
  }

  removeInjury(id: string): void {
    this.runThenReload(this.scouting.removeInjury(id));
  }

  inviteGuardian(): void {
    this.run(
      this.scouting.inviteGuardian(this.guardianEmail().trim(), this.guardianRelationship().trim()),
      'Invitation sent. They confirm it from the Scouting tab.',
    );
    this.guardianEmail.set('');
    this.guardianRelationship.set('');
  }

  removeGuardian(id: string): void {
    this.runThenReload(this.scouting.removeGuardian(id));
  }

  preview(): void {
    const id = this.profile()?.id;
    if (id) void this.router.navigateByUrl(`/tabs/scouting/players/${id}?as=scout`);
  }

  visibilityLabel(value: string): string {
    return value === 'public' ? 'Public' : value === 'scouts' ? 'Scouts only' : 'Only me';
  }

  initials(first: string, last: string): string {
    return `${first.charAt(0)}${last.charAt(0)}`.toUpperCase();
  }

  trim(value: string): string {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? String(parsed) : value;
  }

  private run(request: Observable<PlayerProfile>, success?: string): void {
    if (this.busy()) return;
    this.busy.set(true);
    request.subscribe({
      next: async (profile) => {
        this.busy.set(false);
        this.applyProfile(profile);
        if (success) await this.toast(success, 'success');
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'That did not save.'), 'danger');
      },
    });
  }

  private runThenReload(request: Observable<void>): void {
    if (this.busy()) return;
    this.busy.set(true);
    request.subscribe({
      next: () => {
        this.busy.set(false);
        this.scouting.myProfile().subscribe((profile) => this.applyProfile(profile));
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'That could not be removed.'), 'danger');
      },
    });
  }

  private async toast(message: string, color: 'success' | 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2400, position: 'top' });
    await toast.present();
  }
}
