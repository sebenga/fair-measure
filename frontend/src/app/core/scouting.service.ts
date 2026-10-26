import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Observable, of, tap } from 'rxjs';

import { environment } from '../../environments/environment';
import type {
  TalentReport,
  TalentReportKind,
  ConsentRecord,
  GuardianLink,
  IdentityDocument,
  IdentityDocumentKind,
  LeagueCandidates,
  LeagueScouts,
  LeagueSquadResponse,
  LeagueSummary,
  Measurement,
  ScoutingReport,
  Organisation,
  PlayerProfile,
  ProfileCard,
  ProfileTeam,
  ScoutProfileView,
  CompareResponse,
  ContactRequestRow,
  PlayerStats,
  SavedSearch,
  SearchFilters,
  SearchResult,
  Shortlist,
  ShortlistEntry,
  ShortlistLogRow,
  ShortlistStatus,
  ProfileRatings,
  RatingContext,
  RatingDraft,
  RecordablePlayers,
  ScoutingCatalog,
  SportCatalogue,
  TestResultRow,
  ScoutingMe,
  ScoutingRole,
  TeamMemberships,
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

  private readonly sportCache = new Map<string, SportCatalogue>();

  /** One sport's areas, attributes, physical tests and match stats. */
  sportCatalogue(sport: string): Observable<SportCatalogue> {
    const cached = this.sportCache.get(sport);
    if (cached) return of(cached);
    return this.http
      .get<SportCatalogue>(`${this.base}/catalog/${sport}`)
      .pipe(tap((row) => this.sportCache.set(sport, row)));
  }

  profileStats(profileId: string, filters: { sport?: string; season?: number; competition?: string } = {}) {
    let params = new HttpParams();
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null && value !== '') params = params.set(key, String(value));
    }
    return this.http.get<PlayerStats>(`${this.base}/profiles/${profileId}/stats`, { params });
  }

  recordTest(
    profileId: string,
    body: { sport: string; test_key: string; value: number; tested_on: string; venue?: string; note?: string },
  ) {
    return this.http.post<TestResultRow & { test: string }>(`${this.base}/profiles/${profileId}/tests`, body);
  }

  removeTest(resultId: string) {
    return this.http.delete<void>(`${this.base}/tests/${resultId}`);
  }

  ratingContext(profileId: string): Observable<RatingContext> {
    return this.http.get<RatingContext>(`${this.base}/profiles/${profileId}/rating-context`);
  }

  syncRatings(drafts: RatingDraft[]) {
    return this.http.post<{ results: Array<{ client_id: string; status: 'created' | 'duplicate' | 'rejected'; id?: string; error?: string }> }>(
      `${this.base}/ratings/sync`,
      { ratings: drafts },
    );
  }

  profileRatings(profileId: string, organisation?: string): Observable<ProfileRatings> {
    let params = new HttpParams();
    if (organisation) params = params.set('organisation', organisation);
    return this.http.get<ProfileRatings>(`${this.base}/profiles/${profileId}/ratings`, { params });
  }

  lookupCode(code: string): Observable<{ id: string; name: string }> {
    return this.http.get<{ id: string; name: string }>(`${this.base}/profiles/lookup`, { params: { code } });
  }

  qrUrl(profileId: string): string {
    return `${this.base}/profiles/${profileId}/qr`;
  }

  search(filters: SearchFilters) {
    return this.http.post<{ count: number; results: SearchResult[] }>(`${this.base}/search`, { filters });
  }

  savedSearches(): Observable<SavedSearch[]> {
    return this.http.get<SavedSearch[]>(`${this.base}/saved-searches`);
  }

  saveSearch(body: { name: string; filters: SearchFilters; alerts: boolean }) {
    return this.http.post<SavedSearch>(`${this.base}/saved-searches`, body);
  }

  updateSavedSearch(id: string, body: Partial<{ name: string; alerts: boolean; filters: SearchFilters }>) {
    return this.http.patch<SavedSearch>(`${this.base}/saved-searches/${id}`, body);
  }

  deleteSavedSearch(id: string) {
    return this.http.delete<void>(`${this.base}/saved-searches/${id}`);
  }

  compare(profileIds: string[], sport?: string): Observable<CompareResponse> {
    let params = new HttpParams().set('profiles', profileIds.join(','));
    if (sport) params = params.set('sport', sport);
    return this.http.get<CompareResponse>(`${this.base}/compare`, { params });
  }

  shortlists(profileId?: string): Observable<Shortlist[]> {
    const params = profileId ? new HttpParams().set('profile', profileId) : undefined;
    return this.http.get<Shortlist[]>(`${this.base}/shortlists`, { params });
  }

  createShortlist(body: { name: string; description?: string }) {
    return this.http.post<Shortlist>(`${this.base}/shortlists`, body);
  }

  shortlist(id: string): Observable<Shortlist> {
    return this.http.get<Shortlist>(`${this.base}/shortlists/${id}`);
  }

  deleteShortlist(id: string) {
    return this.http.delete<void>(`${this.base}/shortlists/${id}`);
  }

  addToShortlist(id: string, profileId: string) {
    return this.http.post<ShortlistEntry>(`${this.base}/shortlists/${id}/entries`, { profile: profileId });
  }

  updateShortlistEntry(id: string, entryId: string, body: { status?: ShortlistStatus; assigned_to?: string | null }) {
    return this.http.patch<ShortlistEntry>(`${this.base}/shortlists/${id}/entries/${entryId}`, body);
  }

  removeFromShortlist(id: string, entryId: string) {
    return this.http.delete<void>(`${this.base}/shortlists/${id}/entries/${entryId}`);
  }

  commentOnEntry(id: string, entryId: string, body: string) {
    return this.http.post<ShortlistEntry>(`${this.base}/shortlists/${id}/entries/${entryId}/comments`, { body });
  }

  shortlistLog(id: string): Observable<ShortlistLogRow[]> {
    return this.http.get<ShortlistLogRow[]>(`${this.base}/shortlists/${id}/log`);
  }

  requestContact(profileId: string, message: string) {
    return this.http.post<ContactRequestRow>(`${this.base}/profiles/${profileId}/contact`, { message });
  }

  contactRequests(box: 'received' | 'sent'): Observable<ContactRequestRow[]> {
    return this.http.get<ContactRequestRow[]>(`${this.base}/contact-requests`, { params: { box } });
  }

  respondToContact(id: string, accept: boolean, message: string) {
    return this.http.post<ContactRequestRow>(`${this.base}/contact-requests/${id}/respond`, { accept, message });
  }

  withdrawContact(id: string) {
    return this.http.post<ContactRequestRow>(`${this.base}/contact-requests/${id}/withdraw`, {});
  }

  recordablePlayers(): Observable<RecordablePlayers> {
    return this.http.get<RecordablePlayers>(`${this.base}/tests/players`);
  }

  loadMe(): Observable<ScoutingMe> {
    return this.http.get<ScoutingMe>(`${this.base}/me`).pipe(tap((me) => this.me.set(me)));
  }

  myTeams(): Observable<Array<{ id: string; name: string; competition: string }>> {
    return this.http.get<Array<{ id: string; name: string; competition: string }>>(
      `${this.base}/me/teams`,
    );
  }

  teamMemberships(): Observable<TeamMemberships> {
    return this.http.get<TeamMemberships>(`${this.base}/me/team-memberships`);
  }

  // --- Identity documents (optional; only the owner can ever download them) --

  documents(): Observable<IdentityDocument[]> {
    return this.http.get<IdentityDocument[]>(`${environment.apiBaseUrl}/auth/me/documents`);
  }

  uploadDocument(kind: IdentityDocumentKind, file: File): Observable<IdentityDocument> {
    const form = new FormData();
    form.append('kind', kind);
    form.append('file', file, file.name);
    return this.http.post<IdentityDocument>(`${environment.apiBaseUrl}/auth/me/documents`, form);
  }

  deleteDocument(id: string): Observable<void> {
    return this.http.delete<void>(`${environment.apiBaseUrl}/auth/me/documents/${id}`);
  }

  documentFile(id: string): Observable<Blob> {
    return this.http.get(`${environment.apiBaseUrl}/auth/me/documents/${id}/file`, {
      responseType: 'blob',
    });
  }

  searchTeams(q = ''): Observable<ProfileTeam[]> {
    let params = new HttpParams();
    if (q.trim()) params = params.set('q', q.trim());
    return this.http.get<ProfileTeam[]>(`${this.base}/teams`, { params });
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

  createProfile(body: Partial<PlayerProfile> & { team_ids?: string[] }): Observable<PlayerProfile> {
    return this.http.post<PlayerProfile>(`${this.base}/profile`, body);
  }

  updateProfile(body: Partial<PlayerProfile> & { team_ids?: string[] }): Observable<PlayerProfile> {
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

  // --- Reports and league squads --------------------------------------------

  /** A Phase 6 talent report, as shown on screen. */
  talentReport(kind: TalentReportKind, params: Record<string, string>): Observable<TalentReport> {
    return this.http.get<TalentReport>(`${this.base}/reports/${kind}`, { params: new HttpParams({ fromObject: params }) });
  }

  /** The same report as a PDF. The server logs every export. */
  talentReportPdf(kind: TalentReportKind, params: Record<string, string>): Observable<Blob> {
    return this.http.get(`${this.base}/reports/${kind}/pdf`, {
      params: new HttpParams({ fromObject: params }),
      responseType: 'blob',
    });
  }

  report(profileId: string, exporting = false): Observable<ScoutingReport> {
    const params = exporting ? new HttpParams().set('export', '1') : undefined;
    return this.http.get<ScoutingReport>(`${this.base}/profiles/${profileId}/report`, { params });
  }

  leagues(): Observable<LeagueSummary[]> {
    return this.http.get<LeagueSummary[]>(`${this.base}/leagues`);
  }

  squad(leagueId: string, exporting = false): Observable<LeagueSquadResponse> {
    const params = exporting ? new HttpParams().set('export', '1') : undefined;
    return this.http.get<LeagueSquadResponse>(`${this.base}/leagues/${leagueId}/squad`, { params });
  }

  updateSquad(leagueId: string, body: { name?: string; notes?: string; size?: number }) {
    return this.http.patch<LeagueSquadResponse>(`${this.base}/leagues/${leagueId}/squad`, body);
  }

  generateSquad(leagueId: string): Observable<LeagueSquadResponse> {
    return this.http.post<LeagueSquadResponse>(`${this.base}/leagues/${leagueId}/squad/generate`, {});
  }

  publishSquad(leagueId: string): Observable<LeagueSquadResponse> {
    return this.http.post<LeagueSquadResponse>(`${this.base}/leagues/${leagueId}/squad/publish`, {});
  }

  unpublishSquad(leagueId: string): Observable<LeagueSquadResponse> {
    return this.http.delete<LeagueSquadResponse>(`${this.base}/leagues/${leagueId}/squad/publish`);
  }

  addPick(leagueId: string, user: string, groupKey?: string | null) {
    return this.http.post<LeagueSquadResponse>(`${this.base}/leagues/${leagueId}/squad/picks`, {
      user,
      ...(groupKey ? { group_key: groupKey } : {}),
    });
  }

  updatePick(leagueId: string, pickId: string, body: { locked?: boolean; group_key?: string }) {
    return this.http.patch<LeagueSquadResponse>(
      `${this.base}/leagues/${leagueId}/squad/picks/${pickId}`,
      body,
    );
  }

  dropPick(leagueId: string, pickId: string): Observable<LeagueSquadResponse> {
    return this.http.delete<LeagueSquadResponse>(`${this.base}/leagues/${leagueId}/squad/picks/${pickId}`);
  }

  restorePlayer(leagueId: string, userId: string): Observable<LeagueSquadResponse> {
    return this.http.delete<LeagueSquadResponse>(
      `${this.base}/leagues/${leagueId}/squad/excluded/${userId}`,
    );
  }

  candidates(leagueId: string): Observable<LeagueCandidates> {
    return this.http.get<LeagueCandidates>(`${this.base}/leagues/${leagueId}/candidates`);
  }

  leagueScouts(leagueId: string): Observable<LeagueScouts> {
    return this.http.get<LeagueScouts>(`${this.base}/leagues/${leagueId}/scouts`);
  }

  addLeagueScout(leagueId: string, email: string): Observable<LeagueScouts> {
    return this.http.post<LeagueScouts>(`${this.base}/leagues/${leagueId}/scouts`, { email });
  }

  removeLeagueScout(leagueId: string, scoutId: string): Observable<LeagueScouts> {
    return this.http.delete<LeagueScouts>(`${this.base}/leagues/${leagueId}/scouts/${scoutId}`);
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
    summary: 'Scouts see your Fair Measure profile. You decide who can see it.',
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
      'Open a scouting report for any player you can see, and save it as a PDF',
      "See every league's ranked candidates behind its squad",
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
      'Everything a scout can do, including scouting reports and league rankings',
      'Later: shortlists for the organisation',
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

/** Not a scouting role: owners and admins of a competition pick its squad. */
export const SELECTOR_GUIDE = {
  title: 'League selector',
  icon: 'shirt-outline',
  summary:
    "In a league open to scouts, its owner, admins and league scouts pick its squad, like national selectors.",
  can: [
    'Open a sport competition to scouts when creating it, or later in Setup → Scouting',
    'Attach scouts to the league; they help pick the squad',
    "Pick the league's best players from match ratings, tagged scores and team results",
    'Lock a player in, move them to another position group, or drop them',
    'Publish the squad: everyone who can see the league sees it, and the players are told',
  ],
};

/** Same matching as the backend: case-insensitive, "_" and "-" count as spaces. */
export function scoutingSportFor(sport: string, catalog: ScoutingCatalog | null): string | null {
  const norm = (text: string) => text.toLowerCase().replace(/[_-]/g, ' ').split(/\s+/).filter(Boolean).join(' ');
  const wanted = norm(sport || '');
  if (!wanted || !catalog?.competition_sports) return null;
  for (const [key, aliases] of Object.entries(catalog.competition_sports)) {
    if (norm(key) === wanted || aliases.some((alias) => norm(alias) === wanted)) return key;
  }
  return null;
}

/** Groups rows under their sport, in catalogue order, with "Other" last. */
export function groupBySport<T>(
  rows: T[],
  sportOf: (row: T) => { key: string | null; label: string },
  catalog: ScoutingCatalog | null,
): Array<{ key: string; label: string; rows: T[] }> {
  const order = (catalog?.sports ?? []).map((sport) => sport.key);
  const groups = new Map<string, { key: string; label: string; rows: T[] }>();
  for (const row of rows) {
    const sport = sportOf(row);
    const key = sport.key ?? `other:${sport.label.toLowerCase()}`;
    const group = groups.get(key) ?? { key, label: sport.label, rows: [] };
    group.rows.push(row);
    groups.set(key, group);
  }
  const rank = (key: string) => {
    const index = order.indexOf(key);
    return index === -1 ? order.length + 1 : index;
  };
  return [...groups.values()].sort((a, b) => rank(a.key) - rank(b.key) || a.label.localeCompare(b.label));
}
