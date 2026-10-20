import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Router } from '@angular/router';
import { AlertController, IonIcon, IonSpinner, ToastController } from '@ionic/angular/standalone';

import { extractErrorMessage } from '../../core/error-message';
import type {
  IdentityDocument,
  IdentityDocumentKind,
  PlayerProfile,
  ScoutingCatalog,
  TeamMembership,
} from '../../core/scouting.models';
import { ScoutingService, groupBySport } from '../../core/scouting.service';

const DOCUMENT_KINDS: Array<{ kind: IdentityDocumentKind; label: string; icon: string }> = [
  { kind: 'passport', label: 'Passport', icon: 'globe-outline' },
  { kind: 'national_id', label: 'ID document', icon: 'card-outline' },
];

/**
 * The talent side of the main profile: the talent profile itself, every team the
 * person plays for (accepted invites included), and optional identity documents.
 */
@Component({
  selector: 'fm-profile-talent',
  standalone: true,
  imports: [DatePipe, IonIcon, IonSpinner],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h3 class="fm-section-title">Talent profile</h3>
    @if (loadingTalent()) {
      <div class="card fm-card"><span class="fm-skeleton" style="width: 55%; height: 18px"></span></div>
    } @else if (talent(); as t) {
      <section class="card fm-card fm-enter">
        <div class="talent-head">
          <div>
            <strong>{{ t.first_name }} {{ t.last_name }}</strong>
            <small>
              {{ t.age_group?.label ?? 'Add your date of birth' }}
              · {{ visibilityLabel(t.effective_visibility) }}
            </small>
          </div>
          <span class="badge" [class.ok]="t.effective_visibility !== 'private'">
            {{ t.effective_visibility === 'private' ? 'Hidden from scouts' : 'Visible to scouts' }}
          </span>
        </div>
        @if (t.sports.length) {
          <div class="chips">
            @for (sport of t.sports; track sport.id) {
              <span class="chip-mini">
                {{ sport.sport_label }}{{ sport.primary_position_label ? ' · ' + sport.primary_position_label : '' }}
              </span>
            }
          </div>
        } @else {
          <p class="muted">No sport added yet.</p>
        }
        <div class="actions">
          <button type="button" class="btn" (click)="go('/tabs/scouting/profile')">Edit talent profile</button>
          <button type="button" class="btn ghost" (click)="go('/tabs/scouting/players/' + t.id + '/report')">
            My scouting report
          </button>
        </div>
      </section>
    } @else {
      <section class="card fm-card fm-enter">
        <p class="lede">
          Add a talent profile to be found by scouts. Your name and date of birth from this page are filled in for
          you, and nothing is shown until you choose who can see it.
        </p>
        <button type="button" class="btn block" (click)="go('/tabs/scouting/profile')">Create my talent profile</button>
      </section>
    }

    <h3 class="fm-section-title">My teams</h3>
    @if (pendingInvites() > 0) {
      <p class="hint">
        {{ pendingInvites() }} team invite(s) waiting. Open the competition to accept; the team then shows here.
      </p>
    }
    @for (group of teamGroups(); track group.key) {
      <section class="card fm-card team-group">
        <p class="sport-title">{{ group.label }} <span class="count">{{ group.rows.length }}</span></p>
        @for (team of group.rows; track team.id) {
          <button type="button" class="team-row" (click)="go('/tabs/competitions/' + team.competition_id)">
            <span class="grow">
              <strong>{{ team.name }}</strong>
              <small>
                {{ team.competition }}{{ team.position ? ' · ' + team.position : '' }}{{
                  team.number !== null ? ' · #' + team.number : ''
                }}
              </small>
            </span>
            @if (team.open_to_scouts) {
              <ion-icon name="ribbon-outline" class="scouted" aria-label="Open to scouts" />
            }
            <ion-icon name="chevron-forward-outline" aria-hidden="true" />
          </button>
        }
      </section>
    } @empty {
      <p class="hint">You are not on a team yet. Accept a team invite and it appears here.</p>
    }

    <h3 class="fm-section-title">My horses</h3>
    <section class="card fm-card">
      <p class="lede">Register the horses you own, train or ride, so they can be entered with their rider.</p>
      <button type="button" class="btn ghost" (click)="go('/tabs/horses')">Open my horses</button>
    </section>

    <h3 class="fm-section-title">Identity documents</h3>
    <p class="hint">
      Optional. Only you can open these: scouts, teams and competition admins never see them or know they exist.
      Upload a PDF or a photo, up to 10 MB.
    </p>
    <section class="card fm-card">
      @for (slot of kinds; track slot.kind) {
        <div class="doc-row">
          <ion-icon [name]="slot.icon" aria-hidden="true" />
          <span class="grow">
            <strong>{{ slot.label }}</strong>
            @if (documentFor(slot.kind); as doc) {
              <small>{{ doc.original_name || slot.label }} · {{ size(doc.size_bytes) }} · added {{ doc.uploaded_at | date: 'd MMM y' }}</small>
            } @else {
              <small>Not uploaded</small>
            }
          </span>
          @if (busyKind() === slot.kind) {
            <ion-spinner name="crescent" />
          } @else {
            @if (documentFor(slot.kind); as doc) {
              <button type="button" class="btn ghost small" (click)="view(doc)">View</button>
              <button type="button" class="btn ghost small" (click)="picker.click()">Replace</button>
              <button type="button" class="btn danger small" (click)="remove(doc)" [attr.aria-label]="'Delete ' + slot.label">
                Delete
              </button>
            } @else {
              <button type="button" class="btn small" (click)="picker.click()">Upload</button>
            }
          }
          <input
            #picker
            type="file"
            hidden
            accept="application/pdf,image/jpeg,image/png,image/webp,image/heic"
            (change)="upload(slot.kind, $event)"
          />
        </div>
      }
    </section>
  `,
  styles: [
    `
      :host {
        display: block;
      }

      .card {
        margin: 0 16px 12px;
        padding: 14px 16px;
      }

      .talent-head {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 10px;

        div {
          display: grid;
          gap: 2px;
        }

        small {
          color: var(--ion-color-medium);
        }
      }

      .chips {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin: 10px 0 4px;
      }

      .chip-mini,
      .badge {
        display: inline-flex;
        align-items: center;
        padding: 3px 9px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
        background: var(--ion-color-light);
        color: var(--ion-color-medium-shade);
      }

      .badge.ok {
        background: color-mix(in srgb, var(--ion-color-success) 16%, transparent);
        color: var(--ion-color-success-shade);
      }

      .actions {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 12px;
      }

      .btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 40px;
        padding: 8px 16px;
        border: 0;
        border-radius: 999px;
        background: var(--ion-color-primary);
        color: var(--ion-color-primary-contrast);
        font: inherit;
        font-weight: 700;
        cursor: pointer;
        transition: transform 0.15s var(--fm-ease-spring, ease);

        &:active {
          transform: scale(0.95);
        }

        &.ghost {
          background: var(--ion-color-light);
          color: var(--ion-color-light-contrast);
        }

        &.danger {
          background: color-mix(in srgb, var(--ion-color-danger) 12%, transparent);
          color: var(--ion-color-danger);
        }

        &.small {
          min-height: 32px;
          padding: 5px 12px;
          font-size: 0.8rem;
        }

        &.block {
          width: 100%;
        }
      }

      .lede,
      .muted {
        margin: 0 0 12px;
        color: var(--ion-color-medium);
        font-size: 0.88rem;
        line-height: 1.45;
      }

      .hint {
        margin: -4px 20px 8px;
        font-size: 0.82rem;
        color: var(--ion-color-medium);
      }

      .team-group {
        padding: 8px 6px;
      }

      .sport-title {
        margin: 4px 10px 4px;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: var(--ion-color-primary);

        .count {
          margin-left: 4px;
          color: var(--ion-color-medium);
        }
      }

      .team-row {
        display: flex;
        align-items: center;
        gap: 10px;
        width: 100%;
        padding: 10px;
        border: 0;
        border-radius: 12px;
        background: none;
        color: inherit;
        font: inherit;
        text-align: left;
        cursor: pointer;

        &:hover {
          background: var(--ion-color-light);
          color: var(--ion-color-light-contrast);
        }

        .scouted {
          color: var(--ion-color-primary);
        }
      }

      .grow {
        flex: 1 1 auto;
        min-width: 0;
        display: grid;
        gap: 2px;

        small {
          color: var(--ion-color-medium);
          font-size: 0.8rem;
        }
      }

      .doc-row {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 8px;
        padding: 10px 0;
        border-bottom: 1px solid var(--ion-color-step-50, #f1f2f4);

        &:last-child {
          border-bottom: 0;
        }

        > ion-icon {
          font-size: 1.3rem;
          color: var(--ion-color-primary);
        }
      }
    `,
  ],
})
export class ProfileTalentComponent {
  private readonly scouting = inject(ScoutingService);
  private readonly router = inject(Router);
  private readonly toasts = inject(ToastController);
  private readonly alerts = inject(AlertController);

  readonly kinds = DOCUMENT_KINDS;
  readonly catalog = signal<ScoutingCatalog | null>(null);
  readonly talent = signal<PlayerProfile | null>(null);
  readonly loadingTalent = signal(true);
  readonly teams = signal<TeamMembership[]>([]);
  readonly pendingInvites = signal(0);
  readonly documents = signal<IdentityDocument[]>([]);
  readonly busyKind = signal<IdentityDocumentKind | null>(null);

  readonly teamGroups = computed(() =>
    groupBySport(this.teams(), (team) => ({ key: team.sport_key, label: team.sport_label }), this.catalog()),
  );

  /** Called by the profile page every time it is shown, so accepted invites appear straight away. */
  refresh(): void {
    this.scouting.catalog().subscribe({ next: (catalog) => this.catalog.set(catalog) });
    // Ask "me" first so people without a talent profile never trigger a 404.
    this.scouting.loadMe().subscribe({
      next: (me) => {
        if (!me.profile_id) {
          this.talent.set(null);
          this.loadingTalent.set(false);
          return;
        }
        this.scouting.myProfile().subscribe({
          next: (profile) => {
            this.talent.set(profile);
            this.loadingTalent.set(false);
          },
          error: (err: unknown) => {
            if (err instanceof HttpErrorResponse && err.status === 404) this.talent.set(null);
            this.loadingTalent.set(false);
          },
        });
      },
      error: () => this.loadingTalent.set(false),
    });
    this.scouting.teamMemberships().subscribe({
      next: (result) => {
        this.teams.set(result.teams);
        this.pendingInvites.set(result.pending_invites);
      },
    });
    this.scouting.documents().subscribe({ next: (rows) => this.documents.set(rows) });
  }

  documentFor(kind: IdentityDocumentKind): IdentityDocument | undefined {
    return this.documents().find((doc) => doc.kind === kind);
  }

  upload(kind: IdentityDocumentKind, event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    this.busyKind.set(kind);
    this.scouting.uploadDocument(kind, file).subscribe({
      next: async (doc) => {
        this.documents.update((rows) => [...rows.filter((row) => row.kind !== kind), doc]);
        this.busyKind.set(null);
        await this.toast(`${doc.kind_label} saved. Only you can open it.`, 'success');
      },
      error: async (err: unknown) => {
        this.busyKind.set(null);
        await this.toast(extractErrorMessage(err, 'Could not upload that file.'), 'danger');
      },
    });
  }

  view(doc: IdentityDocument): void {
    // Opened as a blob: the file never has a shareable link.
    const opened = window.open('', '_blank');
    this.scouting.documentFile(doc.id).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        if (opened) opened.location.href = url;
        else window.location.assign(url);
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
      },
      error: async () => {
        opened?.close();
        await this.toast('Could not open that document.', 'danger');
      },
    });
  }

  async remove(doc: IdentityDocument): Promise<void> {
    const alert = await this.alerts.create({
      header: `Delete your ${doc.kind_label.toLowerCase()}?`,
      message: 'The file is removed for good.',
      buttons: [
        { text: 'Keep it', role: 'cancel' },
        {
          text: 'Delete',
          role: 'destructive',
          handler: () => {
            this.busyKind.set(doc.kind);
            this.scouting.deleteDocument(doc.id).subscribe({
              next: () => {
                this.documents.update((rows) => rows.filter((row) => row.id !== doc.id));
                this.busyKind.set(null);
              },
              error: () => this.busyKind.set(null),
            });
          },
        },
      ],
    });
    await alert.present();
  }

  go(path: string): void {
    void this.router.navigateByUrl(path);
  }

  visibilityLabel(value: string): string {
    return { private: 'Only you', scouts: 'Scouts only', public: 'Public' }[value] ?? value;
  }

  size(bytes: number): string {
    if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  private async toast(message: string, color: 'success' | 'danger'): Promise<void> {
    const toast = await this.toasts.create({ message, color, duration: 2400, position: 'top' });
    await toast.present();
  }
}
