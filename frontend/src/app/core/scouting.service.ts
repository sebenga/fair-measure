import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Observable, of, tap } from 'rxjs';

import { environment } from '../../environments/environment';
import type {
  ConsentRecord,
  GuardianLink,
  Measurement,
  Organisation,
  PlayerProfile,
  ProfileCard,
  ScoutProfileView,
  ScoutingCatalog,
  ScoutingMe,
  ScoutingRole,
  Visibility,
} from './scouting.models';

@Injectable({ providedIn: 'root' })
export class ScoutingService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/scouting`;
  private catalogCache: ScoutingCatalog | null = null;

  /** Latest "me" response, so the tab badge and hub stay in step. */
  readonly me = signal<ScoutingMe | null>(null);

  catalog(): Observable<ScoutingCatalog> {
    if (this.catalogCache) return of(this.catalogCache);
    return this.http
      .get<ScoutingCatalog>(`${this.base}/catalog`)
      .pipe(tap((catalog) => (this.catalogCache = catalog)));
  }

  loadMe(): Observable<ScoutingMe> {
    return this.http.get<ScoutingMe>(`${this.base}/me`).pipe(tap((me) => this.me.set(me)));
  }

  myTeams(): Observable<Array<{ id: string; name: string; competition: string }>> {
    return this.http.get<Array<{ id: string; name: string; competition: string }>>(
      `${this.base}/me/teams`,
    );
  }

  becomeCoach(team: string): Observable<ScoutingRole> {
    return this.http.post<ScoutingRole>(`${this.base}/roles/coach`, { team });
  }

  leaveRole(roleId: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/roles/${roleId}`);
  }

  // --- My profile -----------------------------------------------------------

  myProfile(): Observable<PlayerProfile> {
    return this.http.get<PlayerProfile>(`${this.base}/profile`);
  }

  createProfile(body: Partial<PlayerProfile>): Observable<PlayerProfile> {
    return this.http.post<PlayerProfile>(`${this.base}/profile`, body);
  }

  updateProfile(body: Partial<PlayerProfile>): Observable<PlayerProfile> {
    return this.http.patch<PlayerProfile>(`${this.base}/profile`, body);
  }

  addSport(body: { sport: string; primary_position?: string; secondary_positions?: string[] }) {
    return this.http.post<PlayerProfile>(`${this.base}/profile/sports`, body);
  }

  updateSport(id: string, body: { primary_position?: string; secondary_positions?: string[]; is_primary?: boolean }) {
    return this.http.patch<PlayerProfile>(`${this.base}/profile/sports/${id}`, body);
  }

  removeSport(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/profile/sports/${id}`);
  }

  addMeasurement(body: { kind: string; value?: string; text_value?: string; measured_on: string }) {
    return this.http.post<PlayerProfile>(`${this.base}/profile/measurements`, body);
  }

  removeMeasurement(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/profile/measurements/${id}`);
  }

  addInjury(body: { description: string; injured_on?: string | null; shared_with_scouts?: boolean }) {
    return this.http.post<PlayerProfile>(`${this.base}/profile/injuries`, body);
  }

  updateInjury(id: string, body: { shared_with_scouts?: boolean; recovered_on?: string | null }) {
    return this.http.patch<PlayerProfile>(`${this.base}/profile/injuries/${id}`, body);
  }

  removeInjury(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/profile/injuries/${id}`);
  }

  addVideo(body: { title: string; url?: string; media_asset?: string }) {
    return this.http.post<PlayerProfile>(`${this.base}/profile/videos`, body);
  }

  removeVideo(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/profile/videos/${id}`);
  }

  inviteGuardian(email: string, relationship: string) {
    return this.http.post<PlayerProfile>(`${this.base}/profile/guardians`, { email, relationship });
  }

  removeGuardian(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/profile/guardians/${id}`);
  }

  myConsents(): Observable<ConsentRecord[]> {
    return this.http.get<ConsentRecord[]>(`${this.base}/profile/consents`);
  }

  // --- Guardian -------------------------------------------------------------

  guardianLinks(): Observable<GuardianLink[]> {
    return this.http.get<GuardianLink[]>(`${this.base}/guardian/links`);
  }

  acceptGuardian(id: string): Observable<GuardianLink> {
    return this.http.post<GuardianLink>(`${this.base}/guardian/links/${id}/accept`, {});
  }

  declineGuardian(id: string): Observable<void> {
    return this.http.post<void>(`${this.base}/guardian/links/${id}/decline`, {});
  }

  grantConsent(profileId: string, body: { visibility: Visibility; sections: string[]; note: string }) {
    return this.http.post<PlayerProfile>(`${this.base}/guardian/profiles/${profileId}/consent`, body);
  }

  revokeConsent(profileId: string): Observable<PlayerProfile> {
    return this.http.delete<PlayerProfile>(`${this.base}/guardian/profiles/${profileId}/consent`);
  }

  guardianConsents(profileId: string): Observable<ConsentRecord[]> {
    return this.http.get<ConsentRecord[]>(`${this.base}/guardian/profiles/${profileId}/consents`);
  }

  // --- Viewing --------------------------------------------------------------

  listProfiles(query: { q?: string; sport?: string } = {}) {
    let params = new HttpParams();
    if (query.q) params = params.set('q', query.q);
    if (query.sport) params = params.set('sport', query.sport);
    return this.http.get<{ count: number; results: ProfileCard[] }>(`${this.base}/profiles`, { params });
  }

  getProfile(id: string, asScout = false): Observable<PlayerProfile | ScoutProfileView> {
    const params = asScout ? new HttpParams().set('as', 'scout') : undefined;
    return this.http.get<PlayerProfile | ScoutProfileView>(`${this.base}/profiles/${id}`, { params });
  }

  coachMeasurement(profileId: string, body: { kind: string; value?: string; text_value?: string; measured_on: string }) {
    return this.http.post<Measurement>(`${this.base}/profiles/${profileId}/measurements`, body);
  }

  // --- Organisations --------------------------------------------------------

  organisations(): Observable<Organisation[]> {
    return this.http.get<Organisation[]>(`${this.base}/organisations`);
  }

  createOrganisation(body: { name: string; kind: string; region: string }) {
    return this.http.post<Organisation>(`${this.base}/organisations`, body);
  }

  members(organisationId: string): Observable<ScoutingRole[]> {
    return this.http.get<ScoutingRole[]>(`${this.base}/organisations/${organisationId}/members`);
  }

  addMember(organisationId: string, email: string, role: 'scout' | 'scout_admin') {
    return this.http.post<ScoutingRole>(`${this.base}/organisations/${organisationId}/members`, {
      email,
      role,
    });
  }

  removeMember(organisationId: string, roleId: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/organisations/${organisationId}/members/${roleId}`);
  }
}

/** Plain-language descriptions of each scouting role, shown in the hub. */
export const ROLE_GUIDE: Array<{
  key: 'player' | 'guardian' | 'scout' | 'scout_admin' | 'coach';
  title: string;
  icon: string;
  summary: string;
  can: string[];
}> = [
  {
    key: 'player',
    title: 'Player',
    icon: 'person-outline',
    summary: 'You own your talent profile and decide who can see it.',
    can: [
      'Add sports, positions, measurements and highlight videos',
      'Choose private, scouts only, or public, and change it any time',
      'Keep injuries private, or share one with scouts',
      'Under 18: invite a parent or guardian to approve consent',
    ],
  },
  {
    key: 'guardian',
    title: 'Parent / guardian',
    icon: 'shield-checkmark-outline',
    summary: 'For a player under 18. Nothing is shown to scouts until you agree.',
    can: [
      'Confirm you are the guardian when a player invites you',
      'Choose scouts only or public, and which sections are shared',
      'Revoke consent at any time; every decision is recorded',
    ],
  },
  {
    key: 'scout',
    title: 'Scout',
    icon: 'eye-outline',
    summary: 'Find and assess players for your club, academy, school or agency.',
    can: [
      'Search profiles that players (and guardians) made visible to scouts',
      'See verified and self-reported measurements, with dates',
      'Never see phone numbers or email addresses; contact goes through the app',
    ],
  },
  {
    key: 'scout_admin',
    title: 'Scout admin',
    icon: 'business-outline',
    summary: "Runs an organisation's scouting team.",
    can: [
      'Create the organisation and add or remove its scouts',
      'Everything a scout can do',
      'Later: shortlists and reports for the organisation',
    ],
  },
  {
    key: 'coach',
    title: 'Coach',
    icon: 'clipboard-outline',
    summary: 'Coaches a team you manage or a team in a competition you run.',
    can: [
      "Record verified measurements for your team's players",
      'Later: verified test results and match stats',
    ],
  },
];
