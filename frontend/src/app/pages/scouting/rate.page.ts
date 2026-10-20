import { ChangeDetectionStrategy, Component, ElementRef, computed, inject, signal, viewChild } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import {
  IonBackButton,
  IonButtons,
  IonContent,
  IonFooter,
  IonHeader,
  IonIcon,
  IonSpinner,
  IonTitle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';

import { extractErrorMessage } from '../../core/error-message';
import { RatingQueueService } from '../../core/rating-queue.service';
import type {
  CatalogAttribute,
  Confidence,
  ProfileCard,
  RatingArea,
  RatingAreaKey,
  RatingClip,
  RatingContext,
  RatingMode,
  Recommendation,
  SportCatalogue,
  Watched,
} from '../../core/scouting.models';
import { ScoutingService } from '../../core/scouting.service';

const SCALE = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
const LONG_PRESS_MS = 450;

interface BarcodeDetectorLike {
  detect(source: CanvasImageSource): Promise<Array<{ rawValue: string }>>;
}

/** Pitch-side rating: pick a player, tap scores, save. Works without signal. */
@Component({
  selector: 'fm-rate',
  standalone: true,
  imports: [IonHeader, IonToolbar, IonTitle, IonButtons, IonBackButton, IonContent, IonFooter, IonIcon, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './scouting.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button defaultHref="/tabs/scouting" /></ion-buttons>
        <ion-title>Rate a player</ion-title>
        <ion-buttons slot="end">
          <button type="button" class="sync" [class]="'sync ' + queue.state()" (click)="queue.sync()" [attr.aria-label]="syncLabel()">
            <ion-icon [name]="queue.pending() ? 'cloud-upload-outline' : 'cloud-done-outline'" aria-hidden="true" />
            {{ queue.pending() ? queue.pending() : '' }}
          </button>
        </ion-buttons>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      <p class="sync-line" [class.warn]="queue.state() === 'offline' || queue.state() === 'error'">{{ syncLabel() }}</p>
      @for (row of queue.rejected(); track row.draft.client_id) {
        <div class="notice warn section">
          <span class="grow"><strong>{{ row.player_name }}</strong> was not saved: {{ row.error }}</span>
          <button type="button" class="btn ghost small" (click)="queue.discard(row.draft.client_id)">Discard</button>
        </div>
      }

      @if (!context()) {
        <section class="fm-card section">
          <h3>Who are you rating?</h3>
          <label class="field">
            Search by name
            <input type="search" [value]="query()" (input)="search($any($event.target).value)" placeholder="e.g. Thabo" autocomplete="off" />
          </label>
          <ul class="list">
            @for (row of results(); track row.id) {
              <li>
                <button type="button" class="pick" (click)="choose(row.id)">
                  <strong>{{ row.name }}</strong>
                  <small>{{ row.sport?.sport_label ?? '' }}{{ row.sport?.primary_position_label ? ' · ' + row.sport?.primary_position_label : '' }}{{ row.school_or_club ? ' · ' + row.school_or_club : '' }}</small>
                </button>
              </li>
            }
          </ul>
          <div class="row">
            <label class="field">Or type the code under their QR<input [value]="code()" (input)="code.set($any($event.target).value)" maxlength="9" placeholder="8 characters" autocapitalize="characters" /></label>
            <button type="button" class="btn ghost small align-end" [disabled]="code().trim().length < 8" (click)="lookup()">Find</button>
          </div>
          <button type="button" class="btn block" (click)="scan()">
            <ion-icon name="qr-code-outline" aria-hidden="true" />
            Scan their QR code
          </button>
          @if (scanning()) {
            <video #camera class="camera" playsinline muted></video>
            <button type="button" class="btn ghost block" (click)="stopScan()">Stop scanning</button>
          }
        </section>
      } @else if (context(); as c) {
        <section class="fm-card section player">
          <span class="grow">
            <strong>{{ c.profile.name }}</strong>
            <small>{{ sportLabel() }}{{ positionLabel() ? ' · ' + positionLabel() : '' }}</small>
          </span>
          <button type="button" class="btn ghost small" (click)="reset(true)">Change</button>
        </section>

        <div class="section">
          @if (c.sports.length > 1) {
            <div class="chips">
              @for (item of c.sports; track item.key) {
                <button type="button" class="chip" [class.on]="sport() === item.key" (click)="chooseSport(item.key)">{{ item.label }}</button>
              }
            </div>
          }
          <div class="chips">
            @for (item of c.watched; track item.key) {
              <button type="button" class="chip" [class.on]="watched() === item.key" (click)="watched.set(item.key)">{{ item.label }}</button>
            }
          </div>
          <p class="sub">How much have you seen?</p>
          <div class="chips">
            @for (item of c.confidence; track item.key) {
              <button type="button" class="chip" [class.on]="confidence() === item.key" (click)="confidence.set(item.key)" [title]="item.description">{{ item.label }} confidence</button>
            }
          </div>
          @if (c.fixtures.length) {
            <label class="field top">
              Match (optional)
              <select (change)="fixture.set($any($event.target).value)">
                <option value="">No particular match</option>
                @for (item of c.fixtures; track item.id) {
                  <option [value]="item.id" [selected]="fixture() === item.id">{{ item.label }} · {{ item.competition }}</option>
                }
              </select>
            </label>
          }
          @if (c.organisations.length > 1) {
            <label class="field top">
              For
              <select (change)="organisation.set($any($event.target).value)">
                @for (item of c.organisations; track item.id) {
                  <option [value]="item.id" [selected]="organisation() === item.id">{{ item.name }}</option>
                }
              </select>
            </label>
          }
        </div>

        <div class="segmented section" role="tablist">
          <button type="button" role="tab" [class.on]="mode() === 'quick'" (click)="mode.set('quick')">Quick · 5 areas</button>
          <button type="button" role="tab" [class.on]="mode() === 'full'" (click)="mode.set('full')">Full · every attribute</button>
        </div>
        <p class="hint">Tap a score; tap it again to skip. Press and hold a name to see what 2, 5, 8 and 10 look like.</p>

        @if (mode() === 'quick') {
          @for (area of areas(); track area.key) {
            <section class="fm-card section scale-card">
              <div class="label" (pointerdown)="pressStart(area.key)" (pointerup)="pressEnd()" (pointerleave)="pressEnd()" (contextmenu)="$event.preventDefault()">
                <strong>{{ area.label }}</strong>
                <button type="button" class="info" (click)="toggleExplain(area.key)" [attr.aria-label]="'What ' + area.label + ' scores mean'">?</button>
              </div>
              @if (explained() === area.key) {
                <ol class="anchors">
                  @for (point of anchorKeys; track point) {
                    <li><strong>{{ point }}</strong> {{ area.anchors[point] }}</li>
                  }
                </ol>
              }
              <div class="scale" role="radiogroup" [attr.aria-label]="area.label">
                @for (value of scale; track value) {
                  <button type="button" role="radio" [attr.aria-checked]="areaScores()[area.key] === value" [class.on]="areaScores()[area.key] === value" (click)="setArea(area.key, value)">{{ value }}</button>
                }
              </div>
            </section>
          }
        } @else {
          @for (area of areas(); track area.key) {
            <details class="fm-card section area" [open]="area.key === 'technical'">
              <summary>
                <strong>{{ area.label }}</strong>
                <span class="badge">{{ ratedIn(area.key) }}/{{ attributesIn(area.key).length }}</span>
              </summary>
              @for (item of attributesIn(area.key); track item.key) {
                <div class="attribute">
                  <div class="label" (pointerdown)="pressStart(item.key)" (pointerup)="pressEnd()" (pointerleave)="pressEnd()" (contextmenu)="$event.preventDefault()">
                    <span>{{ item.label }}</span>
                    <button type="button" class="info" (click)="toggleExplain(item.key)" [attr.aria-label]="'About ' + item.label">?</button>
                  </div>
                  @if (explained() === item.key) {
                    <p class="hint flush">{{ item.description }}</p>
                    <ol class="anchors">
                      @for (point of anchorKeys; track point) {
                        <li><strong>{{ point }}</strong> {{ area.anchors[point] }}</li>
                      }
                    </ol>
                  }
                  <div class="scale small" role="radiogroup" [attr.aria-label]="item.label">
                    @for (value of scale; track value) {
                      <button type="button" role="radio" [attr.aria-checked]="attributeScores()[item.key] === value" [class.on]="attributeScores()[item.key] === value" (click)="setAttribute(item.key, value)">{{ value }}</button>
                    }
                  </div>
                </div>
              }
            </details>
          }
        }

        <section class="fm-card section">
          <h3>Overall</h3>
          @for (grade of grades; track grade.key) {
            <p class="sub">{{ grade.label }}</p>
            <div class="scale" role="radiogroup" [attr.aria-label]="grade.label">
              @for (value of scale; track value) {
                <button type="button" role="radio" [class.on]="grade.get() === value" [attr.aria-checked]="grade.get() === value" (click)="grade.set(grade.get() === value ? null : value)">{{ value }}</button>
              }
            </div>
          }
          <p class="sub">Recommendation</p>
          <div class="chips">
            @for (item of c.recommendations; track item.key) {
              <button type="button" class="chip" [class.on]="recommendation() === item.key" (click)="recommendation.set(recommendation() === item.key ? '' : item.key)">{{ item.label }}</button>
            }
          </div>
        </section>

        <section class="fm-card section">
          <h3>Notes <small class="private">private to your organisation</small></h3>
          <textarea class="notes" rows="3" [value]="notes()" (input)="notes.set($any($event.target).value)" placeholder="What stood out?"></textarea>
          @for (clip of clips(); track $index; let index = $index) {
            <div class="clip">
              <span class="grow">{{ clip.title || clip.url }} @ {{ clock(clip.at_seconds) }}{{ clip.note ? ' · ' + clip.note : '' }}</span>
              <button type="button" class="btn ghost small" (click)="removeClip(index)" aria-label="Remove clip">✕</button>
            </div>
          }
          <details class="add-clip">
            <summary>Add a video clip</summary>
            @if (c.videos.length) {
              <label class="field">
                Their video
                <select (change)="clipVideo.set($any($event.target).value)">
                  <option value="">A link instead</option>
                  @for (video of c.videos; track video.id) {
                    <option [value]="video.id">{{ video.title }}</option>
                  }
                </select>
              </label>
            }
            @if (!clipVideo()) {
              <label class="field">Link<input [value]="clipUrl()" (input)="clipUrl.set($any($event.target).value)" placeholder="https://" /></label>
            }
            <div class="row">
              <label class="field">At (m:ss)<input [value]="clipAt()" (input)="clipAt.set($any($event.target).value)" placeholder="12:34" inputmode="numeric" /></label>
              <label class="field">Note<input [value]="clipNote()" (input)="clipNote.set($any($event.target).value)" placeholder="e.g. near-post finish" /></label>
            </div>
            <button type="button" class="btn ghost small" (click)="addClip(c)">Add clip</button>
          </details>
        </section>
        <div style="height: 80px"></div>
      } @else {
        <div class="centered"><ion-spinner name="crescent" /></div>
      }
    </ion-content>

    @if (context()) {
      <ion-footer>
        <ion-toolbar>
          <div class="save-bar">
            <span>{{ filled() }} score(s)</span>
            <button type="button" class="btn" [disabled]="!filled()" (click)="save()">Save rating</button>
          </div>
        </ion-toolbar>
      </ion-footer>
    }
  `,
  styles: [
    `
      .sync {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 6px 10px;
        border: 0;
        border-radius: 999px;
        background: var(--ion-color-light);
        color: var(--ion-color-success-shade);
        font: inherit;
        font-weight: 700;
      }
      .sync.offline,
      .sync.error {
        color: var(--ion-color-warning-shade);
      }
      .sync-line {
        margin: 8px 16px 0;
        font-size: 0.78rem;
        color: var(--ion-color-medium);
      }
      .sync-line.warn {
        color: var(--ion-color-warning-shade);
      }
      .notice.warn {
        display: flex;
        gap: 8px;
        align-items: center;
      }
      .grow {
        flex: 1;
        min-width: 0;
      }
      .pick {
        display: grid;
        width: 100%;
        gap: 2px;
        padding: 10px 0;
        border: 0;
        border-bottom: 1px solid var(--ion-color-step-50, #f1f2f4);
        background: none;
        color: inherit;
        font: inherit;
        text-align: left;
      }
      .pick small,
      .player small {
        color: var(--ion-color-medium);
      }
      .align-end {
        align-self: end;
        margin-bottom: 10px;
      }
      .camera {
        width: 100%;
        margin: 10px 0;
        border-radius: 12px;
        background: #000;
      }
      .player {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .player .grow {
        display: grid;
      }
      .chips + .chips,
      .sub {
        margin-top: 10px;
      }
      .sub {
        margin-bottom: 6px;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--ion-color-medium);
      }
      .field.top {
        margin-top: 10px;
      }
      .label {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        margin-bottom: 8px;
        user-select: none;
        -webkit-user-select: none;
        -webkit-touch-callout: none;
      }
      .info {
        width: 28px;
        height: 28px;
        border: 1px solid var(--ion-color-step-150, #dfe2e6);
        border-radius: 50%;
        background: none;
        color: var(--ion-color-medium);
        font-weight: 800;
      }
      .scale {
        display: grid;
        grid-template-columns: repeat(10, 1fr);
        gap: 4px;
      }
      .scale button {
        min-height: 44px;
        border: 1.5px solid var(--ion-color-step-150, #dfe2e6);
        border-radius: 10px;
        background: var(--ion-background-color, #fff);
        color: var(--ion-text-color);
        font: inherit;
        font-weight: 700;
        touch-action: manipulation;
      }
      .scale.small button {
        min-height: 38px;
      }
      .scale button.on {
        border-color: var(--ion-color-primary);
        background: var(--ion-color-primary);
        color: var(--ion-color-primary-contrast);
      }
      .anchors {
        display: grid;
        gap: 4px;
        margin: 0 0 10px;
        padding: 8px 10px;
        border-radius: 10px;
        background: var(--ion-color-light);
        color: var(--ion-color-light-contrast);
        list-style: none;
        font-size: 0.8rem;
      }
      .anchors strong {
        color: var(--ion-color-primary);
        margin-right: 4px;
      }
      .area summary {
        display: flex;
        justify-content: space-between;
        align-items: center;
        cursor: pointer;
      }
      .attribute {
        padding: 10px 0;
        border-bottom: 1px solid var(--ion-color-step-50, #f1f2f4);
      }
      .private {
        font-weight: 500;
        font-size: 0.75rem;
        color: var(--ion-color-medium);
      }
      .notes {
        width: 100%;
        padding: 10px;
        border: 1px solid var(--ion-color-step-200, #d7d8da);
        border-radius: 10px;
        font: inherit;
        background: var(--ion-background-color, #fff);
        color: var(--ion-text-color);
      }
      .clip {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 6px 0;
        font-size: 0.85rem;
      }
      .add-clip {
        margin-top: 8px;
      }
      .add-clip summary {
        cursor: pointer;
        color: var(--ion-color-primary);
        font-weight: 650;
        margin-bottom: 8px;
      }
      .hint.flush {
        margin: 0 0 6px;
      }
      .save-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 6px 16px;
      }
    `,
  ],
})
export class RatePage {
  private readonly scouting = inject(ScoutingService);
  readonly queue = inject(RatingQueueService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastController);
  private readonly camera = viewChild<ElementRef<HTMLVideoElement>>('camera');

  readonly scale = SCALE;
  readonly anchorKeys: Array<'2' | '5' | '8' | '10'> = ['2', '5', '8', '10'];
  readonly query = signal('');
  readonly code = signal('');
  readonly results = signal<ProfileCard[]>([]);
  readonly scanning = signal(false);
  readonly context = signal<RatingContext | null>(null);
  readonly catalogue = signal<SportCatalogue | null>(null);
  readonly areaInfo = signal<RatingArea[]>([]);
  readonly sport = signal('');
  readonly organisation = signal('');
  readonly fixture = signal('');
  readonly mode = signal<RatingMode>('quick');
  readonly watched = signal<Watched>('live');
  readonly confidence = signal<Confidence>('medium');
  readonly areaScores = signal<Partial<Record<RatingAreaKey, number>>>({});
  readonly attributeScores = signal<Record<string, number>>({});
  readonly currentAbility = signal<number | null>(null);
  readonly potential = signal<number | null>(null);
  readonly recommendation = signal<Recommendation | ''>('');
  readonly notes = signal('');
  readonly clips = signal<RatingClip[]>([]);
  readonly clipVideo = signal('');
  readonly clipUrl = signal('');
  readonly clipAt = signal('');
  readonly clipNote = signal('');
  readonly explained = signal('');
  private pressTimer: ReturnType<typeof setTimeout> | null = null;
  private searchTimer: ReturnType<typeof setTimeout> | null = null;
  private stream: MediaStream | null = null;

  readonly grades = [
    { key: 'current', label: 'Current ability', get: () => this.currentAbility(), set: (value: number | null) => this.currentAbility.set(value) },
    { key: 'potential', label: 'Potential', get: () => this.potential(), set: (value: number | null) => this.potential.set(value) },
  ];

  readonly areas = computed(() => {
    const fromSport = this.catalogue()?.areas;
    return fromSport ?? (this.areaInfo() as Array<RatingArea & { attributes?: CatalogAttribute[] }>);
  });

  readonly position = computed(() => this.context()?.sports.find((item) => item.key === this.sport())?.position ?? '');

  readonly filled = computed(() => {
    const scores = this.mode() === 'quick' ? Object.keys(this.areaScores()).length : Object.keys(this.attributeScores()).length;
    return scores + (this.currentAbility() ? 1 : 0) + (this.potential() ? 1 : 0) + (this.recommendation() ? 1 : 0);
  });

  readonly syncLabel = computed(() => {
    const pending = this.queue.pending();
    const state = this.queue.state();
    if (state === 'syncing') return `Sending ${pending} rating(s)…`;
    if (pending && state === 'offline') return `No signal: ${pending} rating(s) saved on this phone, they send when you are back online.`;
    if (pending && state === 'error') return `${pending} rating(s) saved on this phone; retrying shortly.`;
    if (pending) return `${pending} rating(s) waiting to send.`;
    return this.queue.lastSynced() ? 'All ratings synced.' : 'Ratings save on this phone first, then sync.';
  });

  ionViewWillEnter(): void {
    this.scouting.catalog().subscribe({ next: (catalog) => this.areaInfo.set(catalog.areas ?? []) });
    const profile = this.route.snapshot.queryParamMap.get('profile');
    if (profile) this.choose(profile);
    this.queue.sync();
  }

  ionViewWillLeave(): void {
    this.stopScan();
  }

  search(value: string): void {
    this.query.set(value);
    if (this.searchTimer) clearTimeout(this.searchTimer);
    if (value.trim().length < 2) {
      this.results.set([]);
      return;
    }
    this.searchTimer = setTimeout(() => {
      this.scouting.listProfiles({ q: value.trim() }).subscribe({ next: (page) => this.results.set(page.results.slice(0, 12)) });
    }, 250);
  }

  lookup(): void {
    this.scouting.lookupCode(this.code().trim()).subscribe({
      next: (row) => this.choose(row.id),
      error: async (err: unknown) => this.toast(extractErrorMessage(err, 'No player has that code.'), 'danger'),
    });
  }

  choose(profileId: string): void {
    this.stopScan();
    this.context.set(null);
    this.scouting.ratingContext(profileId).subscribe({
      next: (context) => {
        this.context.set(context);
        this.organisation.set(context.organisations[0]?.id ?? '');
        this.chooseSport(context.sports[0]?.key ?? '');
      },
      error: async (err: unknown) => {
        await this.toast(extractErrorMessage(err, 'You cannot rate this player.'), 'danger');
      },
    });
  }

  chooseSport(sport: string): void {
    this.sport.set(sport);
    this.catalogue.set(null);
    this.attributeScores.set({});
    if (sport) this.scouting.sportCatalogue(sport).subscribe({ next: (row) => this.catalogue.set(row) });
  }

  sportLabel(): string {
    return this.context()?.sports.find((item) => item.key === this.sport())?.label ?? '';
  }

  positionLabel(): string {
    const key = this.position();
    return this.catalogue()?.positions.find((item) => item.key === key)?.label ?? key;
  }

  attributesIn(area: string): CatalogAttribute[] {
    const position = this.position();
    const row = this.catalogue()?.areas.find((item) => item.key === area);
    return (row?.attributes ?? []).filter(
      (item) => !item.applies_to_positions?.length || !position || item.applies_to_positions.includes(position),
    );
  }

  ratedIn(area: string): number {
    const scores = this.attributeScores();
    return this.attributesIn(area).filter((item) => scores[item.key] !== undefined).length;
  }

  setArea(key: RatingAreaKey, value: number): void {
    this.areaScores.update((current) => {
      const next = { ...current };
      if (next[key] === value) delete next[key];
      else next[key] = value;
      return next;
    });
  }

  setAttribute(key: string, value: number): void {
    this.attributeScores.update((current) => {
      const next = { ...current };
      if (next[key] === value) delete next[key];
      else next[key] = value;
      return next;
    });
  }

  pressStart(key: string): void {
    this.pressEnd();
    this.pressTimer = setTimeout(() => this.explained.set(key), LONG_PRESS_MS);
  }

  pressEnd(): void {
    if (this.pressTimer) clearTimeout(this.pressTimer);
    this.pressTimer = null;
  }

  toggleExplain(key: string): void {
    this.explained.set(this.explained() === key ? '' : key);
  }

  clock(seconds: number): string {
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
  }

  async addClip(context: RatingContext): Promise<void> {
    const [minutes, seconds] = this.clipAt().includes(':') ? this.clipAt().split(':') : ['0', this.clipAt()];
    const at = Number(minutes) * 60 + Number(seconds);
    if (!Number.isFinite(at) || at < 0) {
      await this.toast('Give the clip time as m:ss, e.g. 12:34.', 'danger');
      return;
    }
    const video = context.videos.find((item) => item.id === this.clipVideo());
    if (!video && !/^https?:\/\//.test(this.clipUrl().trim())) {
      await this.toast('Choose one of their videos or paste a link.', 'danger');
      return;
    }
    this.clips.update((rows) => [
      ...rows,
      { video: video?.id ?? null, title: video?.title ?? '', url: video ? '' : this.clipUrl().trim(), at_seconds: at, note: this.clipNote().trim() },
    ]);
    this.clipUrl.set('');
    this.clipAt.set('');
    this.clipNote.set('');
  }

  removeClip(index: number): void {
    this.clips.update((rows) => rows.filter((_, at) => at !== index));
  }

  async save(): Promise<void> {
    const context = this.context();
    if (!context || !this.filled()) return;
    this.queue.save(
      {
        client_id: RatingQueueService.newId(),
        profile: context.profile.id,
        organisation: this.organisation() || undefined,
        sport: this.sport(),
        position: this.position() || undefined,
        fixture: this.fixture() || undefined,
        mode: this.mode(),
        watched: this.watched(),
        confidence: this.confidence(),
        area_scores: this.mode() === 'quick' ? this.areaScores() : {},
        attribute_scores: this.mode() === 'full' ? this.attributeScores() : {},
        current_ability: this.currentAbility(),
        potential: this.potential(),
        recommendation: this.recommendation(),
        notes: this.notes().trim(),
        clips: this.clips(),
        observed_at: new Date().toISOString(),
      },
      context.profile.name,
    );
    await this.toast(`Rating of ${context.profile.name} saved on this phone.`, 'success');
    this.reset(false);
  }

  /** Clear the scores; keep the player and match unless changing player. */
  reset(changePlayer: boolean): void {
    this.areaScores.set({});
    this.attributeScores.set({});
    this.currentAbility.set(null);
    this.potential.set(null);
    this.recommendation.set('');
    this.notes.set('');
    this.clips.set([]);
    this.explained.set('');
    if (changePlayer) {
      this.context.set(null);
      this.catalogue.set(null);
      this.fixture.set('');
      void this.router.navigate([], { queryParams: {} });
    }
  }

  async scan(): Promise<void> {
    const Detector = (window as unknown as { BarcodeDetector?: new (options: { formats: string[] }) => BarcodeDetectorLike }).BarcodeDetector;
    if (!Detector || !navigator.mediaDevices?.getUserMedia) {
      await this.toast('This browser cannot scan QR codes. Type the 8-character code under the QR instead.', 'danger');
      return;
    }
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
    } catch {
      await this.toast('Allow the camera to scan, or type the code instead.', 'danger');
      return;
    }
    this.scanning.set(true);
    const detector = new Detector({ formats: ['qr_code'] });
    setTimeout(() => {
      const video = this.camera()?.nativeElement;
      if (!video || !this.stream) return;
      video.srcObject = this.stream;
      void video.play();
      const tick = async () => {
        if (!this.scanning()) return;
        try {
          const found = await detector.detect(video);
          const link = found[0]?.rawValue ?? '';
          const match = /profile=([0-9a-f-]{36})/i.exec(link);
          if (match) {
            this.choose(match[1]);
            return;
          }
        } catch {
          // Not ready yet; keep looking.
        }
        requestAnimationFrame(() => void tick());
      };
      void tick();
    }, 50);
  }

  stopScan(): void {
    this.scanning.set(false);
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
  }

  private async toast(message: string, color: 'success' | 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2400, position: 'top' });
    await toast.present();
  }
}
