import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';
import {
  AlertController,
  IonBackButton,
  IonButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonSpinner,
  IonTitle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';
import type { Observable } from 'rxjs';

import { extractErrorMessage } from '../../core/error-message';
import type {
  EvidenceConfidence,
  LeagueCandidate,
  LeagueCandidates,
  LeagueScout,
  LeagueSquad,
  LeagueSquadResponse,
  SquadPick,
} from '../../core/scouting.models';
import { SELECTOR_GUIDE, ScoutingService } from '../../core/scouting.service';

const CONFIDENCE_LABEL: Record<EvidenceConfidence, string> = {
  strong: 'Strong evidence',
  some: 'Some evidence',
  thin: 'Team results only',
  none: 'No data yet',
};

const SOURCE_LABEL: Record<string, string> = {
  form: 'match ratings',
  output: 'points per game, against the best in the same position group',
  team: 'team results',
};

@Component({
  selector: 'fm-league-squad',
  standalone: true,
  imports: [
    DatePipe,
    IonHeader,
    IonToolbar,
    IonTitle,
    IonButtons,
    IonBackButton,
    IonButton,
    IonContent,
    IonIcon,
    IonSpinner,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  styleUrl: './scouting.scss',
  template: `
    <ion-header>
      <ion-toolbar>
        <ion-buttons slot="start"><ion-back-button defaultHref="/tabs/scouting/leagues" /></ion-buttons>
        <ion-title>League squad</ion-title>
        <ion-buttons slot="end">
          @if (squad()) {
            <ion-button (click)="savePdf()">
              <ion-icon slot="start" name="print-outline" aria-hidden="true" />
              Save as PDF
            </ion-button>
          }
        </ion-buttons>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (error()) {
        <div class="fm-empty">
          <ion-icon name="alert-circle-outline" aria-hidden="true" />
          <h3>League unavailable</h3>
          <p>{{ error() }}</p>
        </div>
      } @else {
        @if (squad(); as s) {
          <section class="hero fm-enter">
            <p class="kicker">{{ s.sport }} · {{ s.competition }}</p>
            <h2>{{ s.name }}</h2>
            <div class="hero-row">
              <span class="badge" [class.ok]="s.status === 'published'" [class.warn]="s.status === 'draft'">
                {{ s.status === 'published' ? 'Published' : 'Draft · only selectors see this' }}
              </span>
              <span class="count">{{ s.filled }} / {{ s.size }} players</span>
            </div>
            <div class="progress" aria-hidden="true">
              <span [style.width.%]="(s.filled / s.size) * 100"></span>
            </div>
            <p class="stamp">
              @if (s.published_at && s.status === 'published') {
                Named {{ s.published_at | date: 'd MMM y' }}.
              }
              @if (s.generated_at) {
                Picked from league data on {{ s.generated_at | date: 'd MMM y, HH:mm' }}.
              }
            </p>
            @if (s.notes) {
              <p class="notes">{{ s.notes }}</p>
            }
          </section>

          @if (s.can_edit) {
            <section class="fm-card section no-print">
              <h3>Selector tools</h3>
              <div class="tools">
                <button type="button" class="btn" [disabled]="busy()" (click)="generate()">
                  <ion-icon name="refresh-outline" aria-hidden="true" />
                  Re-pick from data
                </button>
                @if (s.status === 'draft') {
                  <button type="button" class="btn ghost" [disabled]="busy() || !s.filled" (click)="publish()">
                    <ion-icon name="megaphone-outline" aria-hidden="true" />
                    Publish squad
                  </button>
                } @else {
                  <button type="button" class="btn ghost" [disabled]="busy()" (click)="unpublish()">
                    <ion-icon name="arrow-undo-outline" aria-hidden="true" />
                    Back to draft
                  </button>
                }
              </div>
              <p class="hint">Re-picking keeps players you locked and never brings back players you dropped.</p>
              <div class="row">
                <label class="field">
                  Squad size
                  <input type="number" min="5" max="60" [value]="s.size" (change)="setSize($event)" />
                </label>
                <label class="field">
                  Name
                  <input maxlength="120" [value]="s.name" (change)="setName($event)" />
                </label>
              </div>
              <label class="field">
                Selector's notes
                <textarea maxlength="4000" [value]="s.notes" (change)="setNotes($event)" placeholder="Shown with the published squad"></textarea>
              </label>
            </section>

            @if (s.warnings.length) {
              <div class="notice no-print">
                <strong>Before you publish</strong>
                <ul>
                  @for (line of s.warnings; track line) {
                    <li>{{ line }}</li>
                  }
                </ul>
              </div>
            }
          }

          @for (group of s.groups; track group.key) {
            <section class="group">
              <header>
                <h3>{{ group.label }}</h3>
                <span class="badge" [class.warn]="group.picks.length < group.min">
                  {{ group.picks.length }}{{ group.max ? ' of ' + group.min + '–' + group.max : '' }}
                </span>
              </header>
              <div class="picks fm-stagger">
                @for (pick of group.picks; track pick.id) {
                  <article class="pick fm-card" [class.locked]="pick.locked">
                    <button type="button" class="who" (click)="openPlayer(pick)" [disabled]="!pick.profile_id">
                      <span class="avatar">
                        @if (pick.photo_url) {
                          <img [src]="pick.photo_url" alt="" />
                        } @else {
                          {{ initials(pick.name) }}
                        }
                      </span>
                      <span class="grow">
                        <strong>{{ pick.name }}</strong>
                        <small>{{ pick.team }}{{ pick.position ? ' · ' + pick.position : '' }}</small>
                      </span>
                      <span class="score" [attr.data-level]="level(pick.score)">
                        {{ pick.score ?? '–' }}
                      </span>
                    </button>
                    <p class="why">{{ pick.summary[0] }}</p>
                    <div class="pick-foot">
                      <span class="chip-mini" [attr.data-confidence]="pick.confidence">{{ confidence(pick.confidence) }}</span>
                      @if (pick.locked) {
                        <span class="chip-mini"><ion-icon name="lock-closed-outline" aria-hidden="true" /> Selector's pick</span>
                      }
                      @if (s.can_edit) {
                        <span class="spacer"></span>
                        <select class="move no-print" [attr.aria-label]="'Move ' + pick.name" (change)="move(pick, $event)">
                          @for (option of s.groups; track option.key) {
                            <option [value]="option.key" [selected]="option.key === pick.group_key">{{ option.label }}</option>
                          }
                        </select>
                        <button type="button" class="icon-btn no-print" (click)="toggleLock(pick)" [attr.aria-label]="(pick.locked ? 'Unlock ' : 'Lock ') + pick.name">
                          <ion-icon [name]="pick.locked ? 'lock-open-outline' : 'lock-closed-outline'" />
                        </button>
                        <button type="button" class="icon-btn danger no-print" (click)="drop(pick)" [attr.aria-label]="'Drop ' + pick.name">
                          <ion-icon name="remove-circle-outline" />
                        </button>
                      }
                    </div>
                  </article>
                } @empty {
                  <p class="hint">Nobody picked here yet.</p>
                }
              </div>
            </section>
          }
        } @else {
          <div class="fm-empty fm-enter">
            <ion-icon name="shirt-outline" aria-hidden="true" />
            <h3>No squad named yet</h3>
            @if (canEdit()) {
              <p>Pick the league's best players from its match ratings, tagged scores and team results. You can change every pick before you publish.</p>
              <button type="button" class="btn" [disabled]="busy()" (click)="generate()">Pick the best squad</button>
            } @else {
              <p>The league's selectors have not published a squad.</p>
            }
          </div>
        }

        @if (pool(); as c) {
          <section class="fm-card section no-print">
            <h3>Ranked candidates</h3>
            <p class="hint">
              {{ c.counts.eligible }} of {{ c.counts.rostered }} rostered players can be considered.
              @if (c.counts.private + c.counts.no_profile > 0) {
                {{ c.counts.private + c.counts.no_profile }} are left out: no talent profile, a private profile, or an under-18 still waiting for a guardian's consent.
              }
            </p>
            <div class="filters">
              <button type="button" class="chip" [class.on]="!groupFilter()" (click)="groupFilter.set('')">All</button>
              @for (group of c.groups; track group.key) {
                <button type="button" class="chip" [class.on]="groupFilter() === group.key" (click)="groupFilter.set(group.key)">{{ group.label }}</button>
              }
            </div>
            <ol class="ranking">
              @for (row of filteredCandidates(); track row.user_id; let index = $index) {
                <li [class.in]="row.in_squad" [class.out]="!row.available || row.excluded">
                  <span class="rank">{{ index + 1 }}</span>
                  <span class="grow">
                    <strong>{{ row.name }}</strong>
                    <small>{{ row.team }}{{ row.position ? ' · ' + row.position : '' }}</small>
                    <small class="muted">{{ row.summary.join(' · ') }}</small>
                  </span>
                  <span class="score" [attr.data-level]="level(row.score)">{{ row.score ?? '–' }}</span>
                  @if (row.in_squad) {
                    <span class="badge ok">In squad</span>
                  } @else if (!row.available) {
                    <span class="badge warn">{{ availabilityLabel(row.availability) }}</span>
                  } @else if (row.excluded && canEdit()) {
                    <button type="button" class="btn ghost small" (click)="restore(row)">Allow again</button>
                  } @else if (canEdit() && squad()) {
                    <button type="button" class="btn small" [disabled]="busy() || isFull()" (click)="add(row)">Add</button>
                  }
                </li>
              } @empty {
                <li class="muted">No eligible players in this group.</li>
              }
            </ol>
          </section>

          <section class="fm-card section">
            <h3>How the score works</h3>
            <p class="hint">Out of 10, built only from data recorded in this league. Nothing is estimated.</p>
            <ul class="facts">
              @for (entry of weightList(c); track entry.key) {
                <li><strong>{{ entry.percent }}%</strong> {{ entry.label }}</li>
              }
            </ul>
            <p class="hint">
              When a source is missing for a player it is left out and the others count for more. Injured and
              unavailable players are not picked automatically.
            </p>
          </section>
        }

        <section class="fm-card section no-print">
          <h3>League scouts</h3>
          @for (scout of scouts(); track scout.id) {
            <p class="scout-row">
              <ion-icon name="ribbon-outline" aria-hidden="true" />
              <strong>{{ scout.name }}</strong>
              <span class="muted">{{ scout.organisation ?? 'Independent scout' }}</span>
            </p>
          } @empty {
            <p class="hint">No scouts attached to this league yet.</p>
          }
          @if (canManageScouts()) {
            <button type="button" class="btn ghost small" (click)="openSetup()">Manage league scouts</button>
          }
        </section>

        <section class="fm-card section guide no-print">
          <header>
            <span class="icon"><ion-icon [name]="guide.icon" aria-hidden="true" /></span>
            <div>
              <h4>{{ guide.title }}</h4>
              <p>{{ guide.summary }}</p>
            </div>
          </header>
          <ul>
            @for (line of guide.can; track line) {
              <li>{{ line }}</li>
            }
          </ul>
          <p class="hint">Every scout sees the ranked candidates. Everyone who can see the league sees the published squad.</p>
        </section>
      }
      <div style="height: 32px"></div>
    </ion-content>
  `,
  styles: [
    `
      .hero {
        margin: 16px;
        padding: 18px;
        border-radius: 20px;
        color: #fff;
        background: linear-gradient(135deg, var(--ion-color-primary), var(--ion-color-secondary));

        h2 {
          margin: 2px 0 10px;
          font-size: 1.45rem;
          font-weight: 800;
        }

        .kicker {
          margin: 0;
          font-size: 0.72rem;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          opacity: 0.85;
        }

        .badge {
          background: rgb(255 255 255 / 0.22);
          color: #fff;
        }

        .stamp,
        .notes {
          margin: 10px 0 0;
          font-size: 0.82rem;
          opacity: 0.92;
        }

        .notes {
          white-space: pre-wrap;
        }
      }

      .hero-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 8px;

        .count {
          font-weight: 800;
        }
      }

      .progress {
        height: 8px;
        margin-top: 10px;
        border-radius: 999px;
        background: rgb(255 255 255 / 0.25);
        overflow: hidden;

        span {
          display: block;
          height: 100%;
          border-radius: inherit;
          background: #fff;
          transition: width 0.5s cubic-bezier(0.2, 0.8, 0.2, 1);
        }
      }

      .tools {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 8px;
      }

      .notice ul {
        margin: 6px 0 0;
        padding-left: 18px;
      }

      .group {
        margin: 18px 16px 0;

        > header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;

          h3 {
            margin: 0;
            font-size: 1rem;
            font-weight: 800;
          }
        }
      }

      .picks {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
        gap: 10px;
      }

      .pick {
        margin: 0;
        padding: 12px;
        border: 1.5px solid transparent;

        &.locked {
          border-color: color-mix(in srgb, var(--ion-color-primary) 40%, transparent);
        }
      }

      .who {
        display: flex;
        align-items: center;
        gap: 10px;
        width: 100%;
        padding: 0;
        border: 0;
        background: none;
        color: inherit;
        font: inherit;
        text-align: left;
        cursor: pointer;

        &:disabled {
          cursor: default;
        }

        .avatar {
          width: 40px;
          height: 40px;
          font-size: 0.85rem;
        }
      }

      .grow {
        flex: 1 1 auto;
        min-width: 0;
        display: grid;
        gap: 1px;

        strong {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        small {
          color: var(--ion-color-medium);
          font-size: 0.78rem;
        }
      }

      .score {
        flex: 0 0 auto;
        min-width: 44px;
        padding: 6px 8px;
        border-radius: 12px;
        text-align: center;
        font-weight: 800;
        background: var(--ion-color-light);

        &[data-level='high'] {
          background: color-mix(in srgb, var(--ion-color-success) 20%, transparent);
          color: var(--ion-color-success-shade);
        }

        &[data-level='mid'] {
          background: color-mix(in srgb, var(--ion-color-warning) 24%, transparent);
          color: var(--ion-color-warning-shade);
        }
      }

      .why {
        margin: 8px 0 6px;
        font-size: 0.8rem;
        color: var(--ion-color-medium);
      }

      .pick-foot {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 6px;

        .spacer {
          flex: 1 1 auto;
        }
      }

      .chip-mini {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 0.68rem;
        font-weight: 700;
        background: var(--ion-color-light);
        color: var(--ion-color-medium-shade);

        &[data-confidence='strong'] {
          background: color-mix(in srgb, var(--ion-color-success) 16%, transparent);
          color: var(--ion-color-success-shade);
        }

        &[data-confidence='thin'],
        &[data-confidence='none'] {
          background: color-mix(in srgb, var(--ion-color-warning) 18%, transparent);
          color: var(--ion-color-warning-shade);
        }
      }

      .move {
        max-width: 130px;
        min-height: 30px;
        padding: 2px 6px;
        border: 1px solid var(--ion-color-step-200, #d7d8da);
        border-radius: 8px;
        background: var(--ion-background-color, #fff);
        color: var(--ion-text-color);
        font: inherit;
        font-size: 0.75rem;
      }

      .icon-btn {
        display: grid;
        place-items: center;
        width: 30px;
        height: 30px;
        padding: 0;
        border: 0;
        border-radius: 50%;
        background: var(--ion-color-light);
        color: var(--ion-text-color);
        cursor: pointer;

        &.danger {
          color: var(--ion-color-danger);
        }
      }

      .filters {
        display: flex;
        gap: 8px;
        overflow-x: auto;
        margin-bottom: 8px;
        scrollbar-width: none;

        .chip {
          flex: 0 0 auto;
        }
      }

      .ranking {
        display: grid;
        gap: 2px;
        margin: 0;
        padding: 0;
        list-style: none;

        li {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px 0;
          border-bottom: 1px solid var(--ion-color-step-50, #f1f2f4);

          &.in .rank {
            background: color-mix(in srgb, var(--ion-color-success) 18%, transparent);
            color: var(--ion-color-success-shade);
          }

          &.out {
            opacity: 0.6;
          }
        }

        .rank {
          flex: 0 0 auto;
          display: grid;
          place-items: center;
          width: 28px;
          height: 28px;
          border-radius: 50%;
          background: var(--ion-color-light);
          font-size: 0.75rem;
          font-weight: 800;
        }

        .muted {
          color: var(--ion-color-medium);
        }
      }

      .scout-row {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 0 0 8px;

        ion-icon {
          color: var(--ion-color-primary);
        }

        .muted {
          color: var(--ion-color-medium);
          font-size: 0.85rem;
        }
      }

      .facts {
        margin: 0 0 8px;
        padding-left: 18px;
        line-height: 1.6;
      }

      .guide {
        header {
          display: flex;
          gap: 12px;
          align-items: flex-start;
        }

        .icon {
          display: grid;
          place-items: center;
          width: 40px;
          height: 40px;
          border-radius: 12px;
          background: color-mix(in srgb, var(--ion-color-primary) 12%, transparent);
          color: var(--ion-color-primary);
          font-size: 1.2rem;
        }

        h4 {
          margin: 0;
        }

        p {
          margin: 2px 0 0;
          color: var(--ion-color-medium);
          font-size: 0.86rem;
        }

        ul {
          margin: 10px 0;
          padding-left: 18px;
          line-height: 1.55;
          font-size: 0.88rem;
        }
      }

      @media print {
        .hero {
          color: #000;
          background: none;
          border: 2px solid #222;

          .badge {
            color: #000;
            border: 1px solid #999;
          }
        }

        .progress {
          display: none;
        }

        .pick {
          break-inside: avoid;
          border: 1px solid #ccc;
        }
      }
    `,
  ],
})
export class LeagueSquadPage {
  private readonly scouting = inject(ScoutingService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastController);
  private readonly alerts = inject(AlertController);

  readonly guide = SELECTOR_GUIDE;
  readonly squad = signal<LeagueSquad | null>(null);
  readonly canEdit = signal(false);
  readonly pool = signal<LeagueCandidates | null>(null);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly groupFilter = signal('');
  readonly scouts = signal<LeagueScout[]>([]);
  readonly canManageScouts = signal(false);

  private readonly leagueId = computed(() => this.route.snapshot.paramMap.get('id') ?? '');

  readonly filteredCandidates = computed<LeagueCandidate[]>(() => {
    const rows = this.pool()?.results ?? [];
    const filter = this.groupFilter();
    return filter ? rows.filter((row) => (row.group_key ?? 'other') === filter) : rows;
  });

  readonly isFull = computed(() => {
    const squad = this.squad();
    return !squad || squad.filled >= squad.size;
  });

  ionViewWillEnter(): void {
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.scouting.squad(this.leagueId()).subscribe({
      next: (response) => {
        this.apply(response);
        this.loading.set(false);
        this.loadCandidates();
        this.scouting.leagueScouts(this.leagueId()).subscribe({
          next: (result) => {
            this.scouts.set(result.scouts);
            this.canManageScouts.set(result.can_manage);
          },
        });
      },
      error: (err: unknown) => {
        this.error.set(extractErrorMessage(err, 'This league is not available to you.'));
        this.loading.set(false);
      },
    });
  }

  private loadCandidates(): void {
    this.scouting.candidates(this.leagueId()).subscribe({
      next: (pool) => this.pool.set(pool),
      // Only selectors and scouts get the ranking; everyone else just sees the squad.
      error: () => this.pool.set(null),
    });
  }

  private apply(response: LeagueSquadResponse): void {
    this.squad.set(response.squad);
    this.canEdit.set(response.squad?.can_edit ?? response.can_edit ?? false);
  }

  generate(): void {
    this.run(this.scouting.generateSquad(this.leagueId()), 'Squad picked from the league data.');
  }

  async publish(): Promise<void> {
    const squad = this.squad();
    if (!squad) return;
    const alert = await this.alerts.create({
      header: 'Publish the squad?',
      message: `Everyone who can see ${squad.competition} will see it, and the ${squad.filled} selected players are told.`,
      buttons: [
        { text: 'Not yet', role: 'cancel' },
        {
          text: 'Publish',
          handler: () => this.run(this.scouting.publishSquad(this.leagueId()), 'Squad published.'),
        },
      ],
    });
    await alert.present();
  }

  unpublish(): void {
    this.run(this.scouting.unpublishSquad(this.leagueId()), 'Back to draft.');
  }

  setSize(event: Event): void {
    const size = Number((event.target as HTMLInputElement).value);
    if (!Number.isFinite(size)) return;
    this.run(this.scouting.updateSquad(this.leagueId(), { size }), `Squad size set to ${size}.`);
  }

  setName(event: Event): void {
    const name = (event.target as HTMLInputElement).value.trim();
    if (name) this.run(this.scouting.updateSquad(this.leagueId(), { name }));
  }

  setNotes(event: Event): void {
    this.run(
      this.scouting.updateSquad(this.leagueId(), { notes: (event.target as HTMLTextAreaElement).value }),
      'Notes saved.',
    );
  }

  toggleLock(pick: SquadPick): void {
    this.run(this.scouting.updatePick(this.leagueId(), pick.id, { locked: !pick.locked }));
  }

  move(pick: SquadPick, event: Event): void {
    const group = (event.target as HTMLSelectElement).value;
    if (group !== pick.group_key) {
      this.run(this.scouting.updatePick(this.leagueId(), pick.id, { group_key: group }), `${pick.name} moved.`);
    }
  }

  drop(pick: SquadPick): void {
    this.run(this.scouting.dropPick(this.leagueId(), pick.id), `${pick.name} dropped. Re-picking will leave them out.`);
  }

  add(row: LeagueCandidate): void {
    this.run(this.scouting.addPick(this.leagueId(), row.user_id, row.group_key), `${row.name} added and locked.`);
  }

  restore(row: LeagueCandidate): void {
    this.run(this.scouting.restorePlayer(this.leagueId(), row.user_id), `${row.name} can be picked again.`);
  }

  openSetup(): void {
    void this.router.navigateByUrl(`/tabs/competitions/${this.leagueId()}/setup`);
  }

  openPlayer(pick: SquadPick): void {
    if (pick.profile_id) void this.router.navigateByUrl(`/tabs/scouting/players/${pick.profile_id}/report`);
  }

  savePdf(): void {
    this.scouting.squad(this.leagueId(), true).subscribe({
      next: (response) => {
        this.apply(response);
        setTimeout(() => window.print(), 50);
      },
    });
  }

  initials(name: string): string {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((part) => part.charAt(0).toUpperCase())
      .join('');
  }

  level(score: string | null): 'high' | 'mid' | 'low' {
    const value = Number(score ?? 0);
    if (value >= 7) return 'high';
    if (value >= 4) return 'mid';
    return 'low';
  }

  confidence(value: EvidenceConfidence): string {
    return CONFIDENCE_LABEL[value] ?? value;
  }

  availabilityLabel(status: string): string {
    return { injured: 'Injured', unavailable: 'Not available', limited: 'Limited' }[status] ?? status;
  }

  weightList(pool: LeagueCandidates): Array<{ key: string; percent: number; label: string }> {
    return Object.entries(pool.weights).map(([key, weight]) => ({
      key,
      percent: Math.round(weight * 100),
      label: SOURCE_LABEL[key] ?? key,
    }));
  }

  private run(request: Observable<LeagueSquadResponse>, success?: string): void {
    if (this.busy()) return;
    this.busy.set(true);
    request.subscribe({
      next: async (response) => {
        this.apply(response);
        this.busy.set(false);
        this.loadCandidates();
        if (success) await this.toast(success, 'success');
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'That did not save.'), 'danger');
      },
    });
  }

  private async toast(message: string, color: 'success' | 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2400, position: 'top' });
    await toast.present();
  }
}
