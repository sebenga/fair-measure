import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
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
  IonSearchbar,
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
import type { CompetitionDetail, Membership, Participant, ProfileSummary, TeamPick } from '../../core/models';

@Component({
  selector: 'fm-team-profile',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
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
    IonButton,
    IonIcon,
    IonNote,
    IonSearchbar,
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
          <p class="hint">This entrant is not a team. Name a team from Setup, then pick profiles here.</p>
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

          <h3 class="fm-section-title">Members ({{ current.roster.length }}{{ squadLabel() }})</h3>
          <p class="hint">
            @if (teamEntry() === 'draft') {
              Players join through the draft. A player accepts before they count toward the 14.
            } @else if (teamEntry() === 'pick') {
              {{ current.roster.length }} of 14 players have accepted.
            } @else {
              A player joins after they accept a pick. Someone already on a team, or waiting on another pick, stays unavailable.
            }
          </p>

          @if (current.roster.length === 0) {
            <div class="fm-empty">
              <ion-icon name="people-outline" aria-hidden="true" />
              <h3>No members yet</h3>
              <p>Pick a profile. They accept before they are on the team.</p>
            </div>
          } @else {
            <ion-list inset="true">
              @for (member of current.roster; track member.id) {
                <ion-item
                  [button]="!!member.user"
                  [detail]="!!member.user"
                  [routerLink]="member.user ? playerHref(member.user) : null"
                >
                  <ion-label>
                    <h2>{{ member.name }}</h2>
                    <p>{{ member.user ? 'Open bio and league stats' : 'Member' }}</p>
                  </ion-label>
                  @if (canManage()) {
                    <ion-button
                      slot="end"
                      fill="clear"
                      color="danger"
                      size="small"
                      (click)="$event.stopPropagation(); $event.preventDefault(); removeMember(member.id, member.name)"
                    >
                      <ion-icon slot="icon-only" name="trash-outline" aria-label="Remove" />
                    </ion-button>
                  }
                </ion-item>
              }
            </ion-list>
          }

          @if (pendingPicks().length) {
            <h3 class="fm-section-title">Waiting to accept</h3>
            <ion-list inset="true">
              @for (pick of pendingPicks(); track pick.id) {
                <ion-item>
                  <ion-label>
                    <h2>{{ pick.user_display_name || pick.user_email }}</h2>
                    <p>Waiting for them to accept</p>
                  </ion-label>
                  @if (pick.user === meId()) {
                    <ion-button slot="end" size="small" (click)="acceptPick(pick)" [disabled]="busy()">
                      Accept
                    </ion-button>
                    <ion-button slot="end" size="small" fill="outline" (click)="declinePick(pick)" [disabled]="busy()">
                      Decline
                    </ion-button>
                  } @else if (canManage()) {
                    <ion-button slot="end" size="small" fill="clear" (click)="declinePick(pick)" [disabled]="busy()">
                      Withdraw
                    </ion-button>
                  }
                </ion-item>
              }
            </ion-list>
          }

          @if (canManage() && teamEntry() !== 'draft') {
            <h3 class="fm-section-title">Pick a profile</h3>
            <ion-searchbar
              placeholder="Search profiles"
              [debounce]="150"
              (ionInput)="profileQuery.set($any($event.detail.value) ?? '')"
            />
            <ion-list class="profiles" lines="none">
              @for (profile of visibleProfiles(); track profile.id) {
                <ion-item [button]="true" [detail]="true" [routerLink]="playerHref(profile.id)">
                  <ion-label>
                    <h2>{{ profile.display_name || profile.email }}</h2>
                    <p>{{ profileNote(profile) }}</p>
                  </ion-label>
                  <ion-button
                    slot="end"
                    size="small"
                    [disabled]="profileBlocked(profile.id) || busy()"
                    (click)="$event.stopPropagation(); $event.preventDefault(); pickProfile(profile)"
                  >
                    Pick
                  </ion-button>
                </ion-item>
              }
            </ion-list>
            @if (profiles().length && visibleProfiles().length === 0) {
              <p class="hint">No profiles match that search.</p>
            }

            <form class="invite" (submit)="addByEmail($event)">
              <ion-input
                type="email"
                [(ngModel)]="inviteEmail"
                name="email"
                placeholder="Email of a Fair Measure account"
              />
              <ion-button type="submit" size="small" [disabled]="busy() || !inviteEmail.trim()">
                Pick by email
              </ion-button>
            </form>
            <ion-note class="footnote">
              They join the league and accept the pick before they are on the team.
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
  readonly profiles = signal<ProfileSummary[]>([]);
  readonly picks = signal<TeamPick[]>([]);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly profileQuery = signal('');

  readonly pendingPicks = computed(() => this.picks().filter((pick) => pick.status === 'pending'));

  readonly visibleProfiles = computed(() => {
    const query = this.profileQuery().trim().toLowerCase();
    const profiles = this.profiles();
    if (!query) return profiles;
    return profiles.filter((profile) => {
      const name = (profile.display_name || '').toLowerCase();
      const email = (profile.email || '').toLowerCase();
      const bio = (profile.bio || '').toLowerCase();
      const headline = (profile.headline || '').toLowerCase();
      return (
        name.includes(query) ||
        email.includes(query) ||
        bio.includes(query) ||
        headline.includes(query)
      );
    });
  });

  description = '';
  inviteEmail = '';

  meId(): string | undefined {
    return this.auth.user()?.id;
  }

  teamEntry(): 'pick' | 'draft' | null {
    const value = this.competition()?.settings_json?.['team_entry'];
    return value === 'pick' || value === 'draft' ? value : null;
  }

  squadLabel(): string {
    return this.teamEntry() ? ' of 14' : '';
  }

  readonly canManage = computed(() => {
    const role = this.competition()?.my_role;
    const team = this.team();
    const me = this.auth.user()?.id;
    return role === 'owner' || role === 'admin' || (!!team?.managed_by && team.managed_by === me);
  });

  readonly reservedIds = computed(() => {
    const taken = new Set(
      (this.team()?.roster ?? []).map((member) => member.user).filter((id): id is string => !!id),
    );
    for (const pick of this.pendingPicks()) taken.add(pick.user);
    const teamId = this.team()?.id;
    for (const participant of this.competition()?.participants ?? []) {
      if (participant.id === teamId) continue;
      for (const member of participant.roster) {
        if (member.user) taken.add(member.user);
      }
    }
    return taken;
  });

  playerHref(userId: string): string[] {
    return ['/tabs/competitions', this.competitionId, 'players', userId];
  }

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

  profileBlocked(id: string): boolean {
    if (this.reservedIds().has(id)) return true;
    const membership = this.memberships().find((item) => item.user.id === id);
    if (!membership || membership.role === 'member') return false;
    if (membership.role === 'owner' || membership.role === 'admin') {
      return membership.user.id !== this.meId();
    }
    return true;
  }

  profileNote(profile: ProfileSummary): string {
    if (this.pendingPicks().some((pick) => pick.user === profile.id)) return 'Waiting to accept';
    if (this.reservedIds().has(profile.id)) return 'Already on a team';
    if (!this.profileBlocked(profile.id)) return profile.email;
    const membership = this.memberships().find((item) => item.user.id === profile.id);
    if (membership?.role === 'owner' || membership?.role === 'admin') return 'Joins their own team';
    return "Can't join a team";
  }

  pickProfile(profile: ProfileSummary): void {
    if (this.profileBlocked(profile.id) || this.busy()) return;
    this.offer(profile.id);
  }

  acceptPick(pick: TeamPick): void {
    if (this.busy()) return;
    this.busy.set(true);
    this.api.acceptTeamPick(this.competitionId, pick.id).subscribe({
      next: () => {
        this.busy.set(false);
        this.refreshTeam();
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not accept that pick.'), 'danger');
      },
    });
  }

  declinePick(pick: TeamPick): void {
    if (this.busy()) return;
    this.busy.set(true);
    this.api.declineTeamPick(this.competitionId, pick.id).subscribe({
      next: () => {
        this.busy.set(false);
        this.refreshTeam();
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not decline that pick.'), 'danger');
      },
    });
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
        this.offer(membership.user.id);
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
      profiles: this.api.listProfiles(),
      picks: this.api.listTeamPicks(this.competitionId, this.participantId),
    }).subscribe({
      next: ({ competition, team, members, profiles, picks }) => {
        this.competition.set(competition);
        this.team.set(team);
        this.memberships.set(members.results);
        this.profiles.set(profiles.results);
        this.picks.set(picks);
        this.description = team.description;
        this.loading.set(false);
      },
      error: async (err: unknown) => {
        this.loading.set(false);
        await this.toast(extractErrorMessage(err, 'Could not open this team.'), 'danger');
      },
    });
  }

  private offer(userId: string): void {
    this.busy.set(true);
    this.api.offerTeamPick(this.competitionId, this.participantId, userId).subscribe({
      next: () => {
        this.busy.set(false);
        this.refreshTeam();
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not pick that profile.'), 'danger');
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
        const selfAdmin =
          !!membership &&
          (membership.role === 'admin' || membership.role === 'owner') &&
          membership.user.id === this.meId();
        if (!membership || (membership.role !== 'member' && !selfAdmin)) {
          this.busy.set(false);
          void this.toast('That profile cannot join this team.', 'danger');
          return;
        }
        this.inviteEmail = '';
        this.offer(membership.user.id);
      },
      error: async (err: unknown) => {
        this.busy.set(false);
        await this.toast(extractErrorMessage(err, 'Could not look up that member.'), 'danger');
      },
    });
  }

  private refreshTeam(): void {
    forkJoin({
      competition: this.api.getCompetition(this.competitionId),
      team: this.api.getParticipant(this.competitionId, this.participantId),
      picks: this.api.listTeamPicks(this.competitionId, this.participantId),
    }).subscribe({
      next: ({ competition, team, picks }) => {
        this.competition.set(competition);
        this.team.set(team);
        this.picks.set(picks);
        this.description = team.description;
      },
    });
  }

  private async toast(message: string, color: string): Promise<void> {
    const toast = await this.toasts.create({ message, duration: 2500, color, position: 'bottom' });
    await toast.present();
  }
}
