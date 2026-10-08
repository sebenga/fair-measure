import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute } from '@angular/router';
import {
  AlertController,
  IonBackButton,
  IonButton,
  IonButtons,
  IonContent,
  IonHeader,
  IonIcon,
  IonInput,
  IonItem,
  IonLabel,
  IonList,
  IonNote,
  IonSelect,
  IonSelectOption,
  IonSpinner,
  IonTextarea,
  IonTitle,
  IonToolbar,
  ToastController,
} from '@ionic/angular/standalone';
import { forkJoin } from 'rxjs';

import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { extractErrorMessage } from '../../core/error-message';
import type { CompetitionDetail, Membership, Participant } from '../../core/models';

@Component({
  selector: 'fm-team-profile',
  standalone: true,
  imports: [
    FormsModule,
    IonHeader,
    IonToolbar,
    IonButtons,
    IonBackButton,
    IonTitle,
    IonContent,
    IonList,
    IonItem,
    IonLabel,
    IonInput,
    IonTextarea,
    IonSelect,
    IonSelectOption,
    IonButton,
    IonIcon,
    IonNote,
    IonSpinner,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ion-header translucent="true">
      <ion-toolbar>
        <ion-buttons slot="start">
          <ion-back-button [defaultHref]="backHref()" />
        </ion-buttons>
        <ion-title>{{ team()?.name || 'Team' }}</ion-title>
      </ion-toolbar>
    </ion-header>

    <ion-content>
      @if (loading()) {
        <div class="centered"><ion-spinner name="crescent" /></div>
      } @else if (team(); as current) {
        <div class="identity">
          <div class="mark" aria-hidden="true">{{ initials(current.name) }}</div>
          <h2>{{ current.name }}</h2>
          <p>Team</p>
        </div>

        @if (current.kind !== 'team') {
          <p class="hint">This entrant is not a team. Create a team from Setup by picking profiles.</p>
        } @else {
          <h3 class="fm-section-title">About</h3>
          @if (canManage()) {
            <ion-list inset="true">
              <ion-item>
                <ion-textarea
                  label="Description"
                  labelPlacement="stacked"
                  [(ngModel)]="description"
                  [autoGrow]="true"
                  maxlength="500"
                />
              </ion-item>
            </ion-list>
            <ion-button expand="block" class="action" fill="outline" (click)="saveAbout()" [disabled]="busy()">
              Save
            </ion-button>
          } @else if (current.description) {
            <p class="hint">{{ current.description }}</p>
          }

          <h3 class="fm-section-title">Members ({{ current.roster.length }})</h3>
          <p class="hint">
            These profiles make up the team. You can add yourself to one team in this league.
          </p>

          @if (current.roster.length === 0) {
            <div class="fm-empty">
              <ion-icon name="people-outline" aria-hidden="true" />
              <h3>No members yet</h3>
              <p>Add people who have the Member role.</p>
            </div>
          } @else {
            <ion-list inset="true">
              @for (member of current.roster; track member.id) {
                <ion-item>
                  <ion-label>
                    <h2>{{ member.name }}</h2>
                    <p>Member</p>
                  </ion-label>
                  @if (canManage() && current.roster.length > 2) {
                    <ion-button
                      slot="end"
                      fill="clear"
                      color="danger"
                      size="small"
                      (click)="removeMember(member.id, member.name)"
                    >
                      <ion-icon slot="icon-only" name="trash-outline" aria-label="Remove" />
                    </ion-button>
                  }
                </ion-item>
              }
            </ion-list>
          }

          @if (canManage()) {
            <h3 class="fm-section-title">Add a member</h3>
            @if (availableMembers().length) {
              <ion-list inset="true">
                <ion-item>
                  <ion-select label="League member" labelPlacement="stacked" [(ngModel)]="selectedMemberId">
                    @for (membership of availableMembers(); track membership.id) {
                      <ion-select-option [value]="membership.user.id">
                        {{ membership.user.display_name || membership.member_email }}
                      </ion-select-option>
                    }
                  </ion-select>
                </ion-item>
              </ion-list>
              <ion-button expand="block" class="action" (click)="addSelected()" [disabled]="busy() || !selectedMemberId">
                Add to team
              </ion-button>
            } @else {
              <p class="hint">Every current member is already on this team. Invite someone by email.</p>
            }

            <form class="invite" (submit)="addByEmail($event)">
              <ion-input
                type="email"
                [(ngModel)]="inviteEmail"
                name="email"
                placeholder="Email of a Fair Measure account"
              />
              <ion-button type="submit" size="small" [disabled]="busy() || !inviteEmail.trim()">
                Invite
              </ion-button>
            </form>
            <ion-note class="footnote">
              Inviting adds them as a Member of the league, then onto this team.
            </ion-note>
          }
        }
      }
    </ion-content>
  `,
  styleUrl: './team-profile.page.scss',
})
export class TeamProfilePage implements OnInit {
  private readonly api = inject(ApiService);
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly alerts = inject(AlertController);
  private readonly toasts = inject(ToastController);

  private competitionId = '';
  private participantId = '';

  readonly competition = signal<CompetitionDetail | null>(null);
  readonly team = signal<Participant | null>(null);
  readonly memberships = signal<Membership[]>([]);
  readonly loading = signal(true);
  readonly busy = signal(false);

  description = '';
  inviteEmail = '';
  selectedMemberId = '';

  readonly canManage = computed(() => {
    const role = this.competition()?.my_role;
    const team = this.team();
    const me = this.auth.user()?.id;
    return role === 'owner' || role === 'admin' || (!!team?.managed_by && team.managed_by === me);
  });

  readonly availableMembers = computed(() => {
    const taken = new Set(
      (this.team()?.roster ?? []).map((member) => member.user).filter((id): id is string => !!id),
    );
    const me = this.auth.user()?.id;
    const teamId = this.team()?.id;
    const elsewhere = new Set(
      (this.competition()?.participants ?? [])
        .filter((participant) => participant.id !== teamId)
        .flatMap((participant) => participant.roster.map((member) => member.user))
        .filter((id): id is string => !!id),
    );
    return this.memberships().filter((membership) => {
      if (taken.has(membership.user.id)) return false;
      if (membership.role === 'member') return true;
      return (
        (membership.role === 'admin' || membership.role === 'owner') &&
        membership.user.id === me &&
        !elsewhere.has(membership.user.id)
      );
    });
  });

  ngOnInit(): void {
    this.competitionId = this.route.snapshot.paramMap.get('id') ?? '';
    this.participantId = this.route.snapshot.paramMap.get('participantId') ?? '';
    this.load();
  }

  backHref(): string {
    return `/tabs/competitions/${this.competitionId}/setup`;
  }

  initials(name: string): string {
    const parts = name.trim().split(/\s+/).slice(0, 2);
    return parts.map((part) => part.charAt(0).toUpperCase()).join('') || 'T';
  }

  saveAbout(): void {
    const team = this.team();
    if (!team || this.busy()) return;
    this.busy.set(true);
    this.api
      .updateParticipant(this.competitionId, team.id, { description: this.description.trim() })
      .subscribe({
        next: (updated) => {
          this.team.set(updated);
          this.description = updated.description;
          this.busy.set(false);
          void this.toast('Team profile saved.', 'success');
        },
        error: async (err: unknown) => {
          this.busy.set(false);
          await this.toast(extractErrorMessage(err, 'Could not save the team.'), 'danger');
        },
      });
  }

  addSelected(): void {
    const membership = this.availableMembers().find((item) => item.user.id === this.selectedMemberId);
    if (!membership || this.busy()) return;
    this.attach(membership.user.id, membership.user.display_name || membership.member_email);
  }

  addByEmail(event: Event): void {
    event.preventDefault();
    const email = this.inviteEmail.trim();
    if (!email || this.busy()) return;
    this.busy.set(true);
    this.api.inviteMember(this.competitionId, { email, role: 'member' }).subscribe({
      next: (membership) => {
        this.memberships.update((current) => [...current, membership]);
        this.inviteEmail = '';
        this.attach(membership.user.id, membership.user.display_name || email);
      },
      error: (err: unknown) => {
        const message = extractErrorMessage(err, 'Could not invite that person.');
        if (message.toLowerCase().includes('already a member')) {
          this.attachExisting(email);
          return;
        }
        this.busy.set(false);
        void this.toast(message, 'danger');
      },
    });
  }

  async removeMember(memberId: string, name: string): Promise<void> {
    const alert = await this.alerts.create({
      header: `Remove ${name}?`,
      message: 'They stay a member of the league.',
      buttons: [
        { text: 'Cancel', role: 'cancel' },
        {
          text: 'Remove',
          role: 'destructive',
          handler: () => {
            this.busy.set(true);
            this.api.removeRosterMember(this.competitionId, this.participantId, memberId).subscribe({
              next: () => {
                this.busy.set(false);
                this.refreshTeam();
              },
              error: async (err: unknown) => {
                this.busy.set(false);
                await this.toast(extractErrorMessage(err, 'Could not remove that member.'), 'danger');
              },
            });
          },
        },
      ],
    });
    await alert.present();
  }

  private load(): void {
    this.loading.set(true);
    forkJoin({
      competition: this.api.getCompetition(this.competitionId),
      team: this.api.getParticipant(this.competitionId, this.participantId),
      members: this.api.listMembers(this.competitionId),
    }).subscribe({
      next: ({ competition, team, members }) => {
        this.competition.set(competition);
        this.team.set(team);
        this.memberships.set(members.results);
        this.description = team.description;
        this.loading.set(false);
        this.pickDefaultMember();
      },
      error: async (err: unknown) => {
        this.loading.set(false);
        await this.toast(extractErrorMessage(err, 'Could not open this team.'), 'danger');
      },
    });
  }

  private attach(userId: string, name: string): void {
    this.busy.set(true);
    this.api
      .addRosterMember(this.competitionId, this.participantId, { user: userId, name })
      .subscribe({
        next: () => {
          this.busy.set(false);
          this.refreshTeam();
        },
        error: async (err: unknown) => {
          this.busy.set(false);
          await this.toast(extractErrorMessage(err, 'Could not add that member.'), 'danger');
        },
      });
  }

  private attachExisting(email: string): void {
    this.api.listMembers(this.competitionId).subscribe({
      next: (page) => {
        this.memberships.set(page.results);
        const membership = page.results.find(
          (item) => item.member_email.toLowerCase() === email.toLowerCase(),
        );
        const me = this.auth.user()?.id;
        const selfAdmin =
          !!membership &&
          (membership.role === 'admin' || membership.role === 'owner') &&
          membership.user.id === me;
        if (!membership || (membership.role !== 'member' && !selfAdmin)) {
          this.busy.set(false);
          void this.toast('That profile cannot join this team.', 'danger');
          return;
        }
        this.inviteEmail = '';
        this.attach(membership.user.id, membership.user.display_name || email);
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not look up that member.'), 'danger');
      },
    });
  }

  private refreshTeam(): void {
    this.api.getParticipant(this.competitionId, this.participantId).subscribe({
      next: (team) => {
        this.team.set(team);
        this.description = team.description;
        this.pickDefaultMember();
      },
    });
  }

  private pickDefaultMember(): void {
    const available = this.availableMembers();
    if (!available.some((membership) => membership.user.id === this.selectedMemberId)) {
      this.selectedMemberId = available[0]?.user.id ?? '';
    }
  }

  private async toast(message: string, color: string): Promise<void> {
    const toast = await this.toasts.create({ message, duration: 2500, color, position: 'bottom' });
    await toast.present();
  }
}
