import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { EMPTY, Observable, expand, reduce } from 'rxjs';

import { environment } from '../../environments/environment';
import type {
  AppNotification,
  Comment,
  Competition,
  CompetitionDetail,
  CursorPaginated,
  Fixture,
  FixtureAwards,
  FixtureDetail,
  GenerateFixturesRequest,
  MatchDay,
  MatchRaters,
  MatchReportData,
  NextSeasonRequest,
  NextSeasonResponse,
  PlayerStatsTable,
  MediaAsset,
  Membership,
  Paginated,
  Participant,
  ProfileSummary,
  PointsPolicy,
  RosterMember,
  TeamPick,
  Post,
  Preset,
  ReactionKind,
  ReactionResult,
  Rule,
  PlayerLeagueProfile,
  DraftBoard,
  FantasyOverview,
  FantasyPlayer,
  FantasyStandingRow,
  ScoreEvent,
  ScoreAssistEntry,
  ScoringCategory,
  ScrabbleBoard,
  StandingsResponse,
  UploadTarget,
} from './models';

type Query = Record<string, string | number | boolean | undefined | null>;

function toParams(query: Query = {}): HttpParams {
  let params = new HttpParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== '') {
      params = params.set(key, String(value));
    }
  }
  return params;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;

  // --- Competitions ---------------------------------------------------------

  listCompetitions(query: Query = {}): Observable<Paginated<Competition>> {
    return this.http.get<Paginated<Competition>>(`${this.base}/competitions`, {
      params: toParams(query),
    });
  }

  getCompetition(id: string): Observable<CompetitionDetail> {
    return this.http.get<CompetitionDetail>(`${this.base}/competitions/${id}`);
  }

  createCompetition(body: Record<string, unknown>): Observable<CompetitionDetail> {
    return this.http.post<CompetitionDetail>(`${this.base}/competitions`, body);
  }

  updateCompetition(id: string, body: Record<string, unknown>): Observable<CompetitionDetail> {
    return this.http.patch<CompetitionDetail>(`${this.base}/competitions/${id}`, body);
  }

  deleteCompetition(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/competitions/${id}`);
  }

  listPresets(): Observable<Preset[]> {
    return this.http.get<Preset[]>(`${this.base}/competitions/presets`);
  }

  applyPreset(id: string, preset: string, replaceExisting = false) {
    return this.http.post<CompetitionDetail>(`${this.base}/competitions/${id}/apply-preset`, {
      preset,
      replace_existing: replaceExisting,
    });
  }

  joinCompetition(id: string) {
    return this.http.post(`${this.base}/competitions/${id}/join`, {});
  }

  leaveCompetition(id: string) {
    return this.http.post(`${this.base}/competitions/${id}/leave`, {});
  }

  scheduleNextSeason(id: string, body: NextSeasonRequest) {
    return this.http.post<NextSeasonResponse>(`${this.base}/competitions/${id}/next-season`, body);
  }

  // --- Scoring configuration ------------------------------------------------

  listScoringCategories(competitionId: string): Observable<Paginated<ScoringCategory>> {
    return this.http.get<Paginated<ScoringCategory>>(
      `${this.base}/competitions/${competitionId}/scoring-categories`,
    );
  }

  createScoringCategory(competitionId: string, body: Partial<ScoringCategory>) {
    return this.http.post<ScoringCategory>(
      `${this.base}/competitions/${competitionId}/scoring-categories`,
      body,
    );
  }

  updateScoringCategory(
    competitionId: string,
    categoryId: string,
    body: Partial<ScoringCategory>,
  ) {
    return this.http.patch<ScoringCategory>(
      `${this.base}/competitions/${competitionId}/scoring-categories/${categoryId}`,
      body,
    );
  }

  deleteScoringCategory(competitionId: string, categoryId: string) {
    return this.http.delete<void>(
      `${this.base}/competitions/${competitionId}/scoring-categories/${categoryId}`,
    );
  }

  createRule(competitionId: string, body: Partial<Rule>) {
    return this.http.post<Rule>(`${this.base}/competitions/${competitionId}/rules`, body);
  }

  deleteRule(competitionId: string, ruleId: string) {
    return this.http.delete<void>(`${this.base}/competitions/${competitionId}/rules/${ruleId}`);
  }

  getPointsPolicy(competitionId: string): Observable<PointsPolicy> {
    return this.http.get<PointsPolicy>(
      `${this.base}/competitions/${competitionId}/points-policy`,
    );
  }

  updatePointsPolicy(competitionId: string, body: Partial<PointsPolicy>) {
    return this.http.patch<PointsPolicy>(
      `${this.base}/competitions/${competitionId}/points-policy`,
      body,
    );
  }

  // --- Participants ---------------------------------------------------------

  listParticipants(competitionId: string): Observable<Paginated<Participant>> {
    return this.http.get<Paginated<Participant>>(
      `${this.base}/competitions/${competitionId}/participants`,
    );
  }

  createParticipant(
    competitionId: string,
    body: Partial<Participant> & { member_ids?: string[]; user?: string },
  ) {
    return this.http.post<Participant>(
      `${this.base}/competitions/${competitionId}/participants`,
      body,
    );
  }

  getParticipant(competitionId: string, participantId: string) {
    return this.http.get<Participant>(
      `${this.base}/competitions/${competitionId}/participants/${participantId}`,
    );
  }

  updateParticipant(competitionId: string, participantId: string, body: Partial<Participant>) {
    return this.http.patch<Participant>(
      `${this.base}/competitions/${competitionId}/participants/${participantId}`,
      body,
    );
  }

  deleteParticipant(competitionId: string, participantId: string) {
    return this.http.delete<void>(
      `${this.base}/competitions/${competitionId}/participants/${participantId}`,
    );
  }

  addRosterMember(competitionId: string, participantId: string, body: Record<string, unknown>) {
    return this.http.post<RosterMember>(
      `${this.base}/competitions/${competitionId}/participants/${participantId}/roster`,
      body,
    );
  }

  updateRosterMember(
    competitionId: string,
    participantId: string,
    memberId: string,
    body: Record<string, unknown>,
  ) {
    return this.http.patch<RosterMember>(
      `${this.base}/competitions/${competitionId}/participants/${participantId}/roster/${memberId}`,
      body,
    );
  }

  fixtureAwards(competitionId: string, fixtureId: string) {
    return this.http.get<FixtureAwards>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/awards`,
    );
  }

  setFixtureAward(competitionId: string, fixtureId: string, body: Record<string, unknown>) {
    return this.http.put<FixtureAwards>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/awards`,
      body,
    );
  }

  teamSheets(competitionId: string, fixtureId: string) {
    return this.http.get<MatchDay>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/team-sheets`,
    );
  }

  saveTeamSheet(
    competitionId: string,
    fixtureId: string,
    sideId: string,
    body: Record<string, unknown>,
  ) {
    return this.http.put<MatchDay>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/team-sheets/${sideId}`,
      body,
    );
  }

  recordSubstitution(competitionId: string, fixtureId: string, body: Record<string, unknown>) {
    return this.http.post<MatchDay>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/substitutions`,
      body,
    );
  }

  deleteSubstitution(competitionId: string, fixtureId: string, substitutionId: string) {
    return this.http.delete<MatchDay>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/substitutions/${substitutionId}`,
    );
  }

  matchRaters(competitionId: string, fixtureId: string, query = '') {
    return this.http.get<MatchRaters>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/raters`,
      { params: toParams({ q: query || undefined }) },
    );
  }

  appointRater(competitionId: string, fixtureId: string, userId: string) {
    return this.http.post<MatchRaters>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/raters`,
      { user: userId },
    );
  }

  removeRater(competitionId: string, fixtureId: string, userId: string) {
    return this.http.delete<MatchRaters>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/raters`,
      { params: toParams({ user: userId }) },
    );
  }

  submitRatings(
    competitionId: string,
    fixtureId: string,
    ratings: Array<{ player: string; rating: string }>,
  ) {
    return this.http.put<MatchRaters>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/raters/ratings`,
      { ratings },
    );
  }

  recordPlayerStat(
    competitionId: string,
    fixtureId: string,
    body: { player: string; code?: string; delta?: number; minutes?: number },
  ) {
    return this.http.post<MatchRaters>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/raters/stats`,
      body,
    );
  }

  matchReport(competitionId: string, fixtureId: string) {
    return this.http.get<MatchReportData>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/report`,
    );
  }

  saveMatchReport(competitionId: string, fixtureId: string, body: Record<string, unknown>) {
    return this.http.put<MatchReportData>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/report`,
      body,
    );
  }

  playerStats(competitionId: string) {
    return this.http.get<PlayerStatsTable>(`${this.base}/competitions/${competitionId}/player-stats`);
  }

  removeRosterMember(competitionId: string, participantId: string, memberId: string) {
    return this.http.delete<void>(
      `${this.base}/competitions/${competitionId}/participants/${participantId}/roster/${memberId}`,
    );
  }

  listTeamPicks(competitionId: string, participantId: string): Observable<TeamPick[]> {
    return this.http.get<TeamPick[]>(
      `${this.base}/competitions/${competitionId}/participants/${participantId}/picks`,
    );
  }

  offerTeamPick(competitionId: string, participantId: string, userId: string) {
    return this.http.post<TeamPick>(
      `${this.base}/competitions/${competitionId}/participants/${participantId}/picks`,
      { user: userId },
    );
  }

  myPendingTeamPicks(): Observable<TeamPick[]> {
    return this.http.get<TeamPick[]>(`${this.base}/me/team-picks`);
  }

  myTeamPicks(competitionId: string): Observable<TeamPick[]> {
    return this.http.get<TeamPick[]>(`${this.base}/competitions/${competitionId}/picks`);
  }

  acceptTeamPick(competitionId: string, pickId: string) {
    return this.http.post<TeamPick>(
      `${this.base}/competitions/${competitionId}/picks/${pickId}/accept`,
      {},
    );
  }

  declineTeamPick(competitionId: string, pickId: string) {
    return this.http.post<TeamPick>(
      `${this.base}/competitions/${competitionId}/picks/${pickId}/decline`,
      {},
    );
  }

  getDraft(competitionId: string): Observable<DraftBoard> {
    return this.http.get<DraftBoard>(`${this.base}/competitions/${competitionId}/draft`);
  }

  draftPlayer(competitionId: string, userId: string) {
    return this.http.post<DraftBoard>(
      `${this.base}/competitions/${competitionId}/draft`,
      { user: userId },
    );
  }

  listMembers(competitionId: string): Observable<Paginated<Membership>> {
    return this.http.get<Paginated<Membership>>(
      `${this.base}/competitions/${competitionId}/members`,
      { params: toParams({ page_size: 100 }) },
    );
  }

  inviteMember(competitionId: string, body: { email?: string; user_id?: string; role?: string }) {
    return this.http.post<Membership>(`${this.base}/competitions/${competitionId}/members`, body);
  }

  updateMember(competitionId: string, membershipId: string, body: { role: string }) {
    return this.http.patch<Membership>(
      `${this.base}/competitions/${competitionId}/members/${membershipId}`,
      body,
    );
  }

  assignReferee(competitionId: string, fixtureId: string, userId: string) {
    return this.http.post<FixtureDetail>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/referees`,
      { user: userId },
    );
  }

  removeReferee(competitionId: string, fixtureId: string, userId: string) {
    return this.http.delete<FixtureDetail>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/referees`,
      { params: toParams({ user: userId }) },
    );
  }

  getPlayerProfile(competitionId: string, userId: string): Observable<PlayerLeagueProfile> {
    return this.http.get<PlayerLeagueProfile>(
      `${this.base}/competitions/${competitionId}/players/${userId}`,
    );
  }

  listProfiles(): Observable<Paginated<ProfileSummary>> {
    const first = this.http.get<Paginated<ProfileSummary>>(`${this.base}/auth/profiles`, {
      params: toParams({ page_size: 100 }),
    });
    return first.pipe(
      expand((page) =>
        page.next ? this.http.get<Paginated<ProfileSummary>>(page.next) : EMPTY,
      ),
      reduce(
        (all, page) => ({
          count: page.count,
          next: null,
          previous: null,
          results: all.results.concat(page.results),
        }),
        { count: 0, next: null, previous: null, results: [] as ProfileSummary[] },
      ),
    );
  }

  // --- Fixtures -------------------------------------------------------------

  listFixtures(competitionId: string, query: Query = {}): Observable<Paginated<Fixture>> {
    return this.http.get<Paginated<Fixture>>(
      `${this.base}/competitions/${competitionId}/fixtures`,
      { params: toParams(query) },
    );
  }

  getFixture(competitionId: string, fixtureId: string): Observable<FixtureDetail> {
    return this.http.get<FixtureDetail>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}`,
    );
  }

  createFixture(competitionId: string, body: Record<string, unknown>) {
    return this.http.post<Fixture>(`${this.base}/competitions/${competitionId}/fixtures`, body);
  }

  updateFixture(competitionId: string, fixtureId: string, body: Record<string, unknown>) {
    return this.http.patch<Fixture>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}`,
      body,
    );
  }

  generateFixtures(competitionId: string, body: GenerateFixturesRequest): Observable<Fixture[]> {
    return this.http.post<Fixture[]>(
      `${this.base}/competitions/${competitionId}/fixtures/generate`,
      body,
    );
  }

  advanceKnockout(competitionId: string) {
    return this.http.post<{
      advanced: boolean;
      detail?: string;
      round_number?: number;
      fixtures?: string[];
    }>(`${this.base}/competitions/${competitionId}/advance`, {});
  }

  generateDemoLeague(competitionId: string) {
    return this.http.post<{
      active: boolean;
      deleted?: boolean;
      expires_at?: string;
      teams: number;
      fixtures: number;
      played: number;
      officials?: number;
      picks?: number;
      ratings?: number;
      squad?: number;
      fantasy?: number;
      competition: CompetitionDetail;
    }>(`${this.base}/competitions/${competitionId}/demo-league`, {});
  }

  clearDemoLeague(competitionId: string) {
    return this.http.delete<{
      active: boolean;
      deleted?: boolean;
      teams: number;
      fixtures: number;
      competition?: CompetitionDetail;
    }>(`${this.base}/competitions/${competitionId}/demo-league`);
  }

  startCup(competitionId: string, body: { name?: string; stage?: string } = {}) {
    return this.http.post<{
      stage: { id: string; name: string };
      fixtures: Fixture[];
    }>(`${this.base}/competitions/${competitionId}/start-cup`, body);
  }

  setFixtureStatus(competitionId: string, fixtureId: string, status: string) {
    return this.http.post<FixtureDetail>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/set-status`,
      { status },
    );
  }

  // --- Score events ---------------------------------------------------------

  getScrabbleBoard(competitionId: string, fixtureId: string): Observable<ScrabbleBoard> {
    return this.http.get<ScrabbleBoard>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/scrabble`,
    );
  }

  previewScrabbleMove(competitionId: string, fixtureId: string, body: Record<string, unknown>) {
    return this.http.post<{ words: Array<{ breakdown: string; total: number }>; bingo: boolean; bingo_bonus: number; total: number }>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/scrabble/preview`,
      body,
    );
  }

  recordScrabbleMove(competitionId: string, fixtureId: string, body: Record<string, unknown>) {
    return this.http.post<ScrabbleBoard>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/scrabble/moves`,
      body,
    );
  }

  updateScrabbleMove(competitionId: string, fixtureId: string, moveId: string, body: Record<string, unknown>) {
    return this.http.patch<ScrabbleBoard>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/scrabble/moves/${moveId}`,
      body,
    );
  }

  deleteScrabbleMove(competitionId: string, fixtureId: string, moveId: string) {
    return this.http.delete<ScrabbleBoard>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/scrabble/moves/${moveId}`,
    );
  }

  applyScrabbleRacks(competitionId: string, fixtureId: string, body: Record<string, unknown>) {
    return this.http.post<ScrabbleBoard>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/scrabble/racks`,
      body,
    );
  }

  recordEvent(fixtureId: string, body: Record<string, unknown>): Observable<ScoreEvent> {
    return this.http.post<ScoreEvent>(`${this.base}/fixtures/${fixtureId}/events`, body);
  }

  /** Remove a recorded score. A counted official result also needs the reason, which is logged. */
  deleteEvent(fixtureId: string, eventId: string, reason?: string): Observable<void> {
    const params = reason ? new HttpParams().set('amendment_reason', reason) : undefined;
    return this.http.delete<void>(`${this.base}/fixtures/${fixtureId}/events/${eventId}`, { params });
  }

  listScoreAssist(competitionId: string): Observable<ScoreAssistEntry[]> {
    return this.http.get<ScoreAssistEntry[]>(`${this.base}/competitions/${competitionId}/score-assist`);
  }

  recordScoreAssist(competitionId: string, body: Record<string, unknown>) {
    return this.http.post<{ id: string; awarded?: string; label?: string }>(
      `${this.base}/competitions/${competitionId}/score-assist`,
      body,
    );
  }

  // --- Standings ------------------------------------------------------------

  getStandings(competitionId: string, query: Query = {}): Observable<StandingsResponse> {
    return this.http.get<StandingsResponse>(
      `${this.base}/competitions/${competitionId}/standings`,
      { params: toParams(query) },
    );
  }

  // --- Feed -----------------------------------------------------------------

  listDiscoverPosts(query: Query = {}): Observable<CursorPaginated<Post>> {
    return this.http.get<CursorPaginated<Post>>(`${this.base}/discover/posts`, {
      params: toParams(query),
    });
  }

  listPosts(competitionId: string, query: Query = {}): Observable<CursorPaginated<Post>> {
    return this.http.get<CursorPaginated<Post>>(
      `${this.base}/competitions/${competitionId}/posts`,
      { params: toParams(query) },
    );
  }

  /** Follow a cursor-pagination `next` URL verbatim. */
  loadMorePosts(url: string): Observable<CursorPaginated<Post>> {
    return this.http.get<CursorPaginated<Post>>(url);
  }

  createPost(competitionId: string, body: Record<string, unknown>): Observable<Post> {
    return this.http.post<Post>(`${this.base}/competitions/${competitionId}/posts`, body);
  }

  deletePost(competitionId: string, postId: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/competitions/${competitionId}/posts/${postId}`);
  }

  reactToPost(
    competitionId: string,
    postId: string,
    kind: ReactionKind,
  ): Observable<ReactionResult> {
    return this.http.post<ReactionResult>(
      `${this.base}/competitions/${competitionId}/posts/${postId}/react`,
      { kind },
    );
  }

  listComments(postId: string, query: Query = {}): Observable<Paginated<Comment>> {
    return this.http.get<Paginated<Comment>>(`${this.base}/posts/${postId}/comments`, {
      params: toParams(query),
    });
  }

  createComment(
    postId: string,
    body: string,
    parent?: string | null,
    mediaAssetIds: string[] = [],
  ): Observable<Comment> {
    return this.http.post<Comment>(`${this.base}/posts/${postId}/comments`, {
      body,
      ...(parent ? { parent } : {}),
      ...(mediaAssetIds.length ? { media_asset_ids: mediaAssetIds } : {}),
    });
  }

  deleteComment(postId: string, commentId: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/posts/${postId}/comments/${commentId}`);
  }

  reactToComment(postId: string, commentId: string, kind: ReactionKind): Observable<ReactionResult> {
    return this.http.post<ReactionResult>(
      `${this.base}/posts/${postId}/comments/${commentId}/react`,
      { kind },
    );
  }

  // --- Media ----------------------------------------------------------------

  requestUpload(body: Record<string, unknown>): Observable<UploadTarget> {
    return this.http.post<UploadTarget>(`${this.base}/media/request-upload`, body);
  }

  completeUpload(mediaId: string, body: Record<string, unknown> = {}): Observable<MediaAsset> {
    return this.http.post<MediaAsset>(`${this.base}/media/${mediaId}/complete`, body);
  }

  getMediaAsset(mediaId: string): Observable<MediaAsset> {
    return this.http.get<MediaAsset>(`${this.base}/media/${mediaId}`);
  }

  // --- Notifications --------------------------------------------------------

  registerDevice(token: string, platform: 'ios' | 'android' | 'web', deviceName = '') {
    return this.http.post(`${this.base}/devices`, {
      token,
      platform,
      device_name: deviceName,
    });
  }

  listNotifications(query: Query = {}) {
    return this.http.get<Paginated<AppNotification>>(`${this.base}/notifications`, {
      params: toParams(query),
    });
  }

  markNotificationRead(id: string) {
    return this.http.post<AppNotification>(`${this.base}/notifications/${id}/read`, {});
  }

  markAllNotificationsRead() {
    return this.http.post<{ marked_read: number }>(
      `${this.base}/notifications/mark-all-read`,
      {},
    );
  }

  // --- Fantasy --------------------------------------------------------------

  getFantasy(competitionId: string) {
    return this.http.get<FantasyOverview>(`${this.base}/competitions/${competitionId}/fantasy`);
  }

  saveFantasy(
    competitionId: string,
    body: {
      name: string;
      picks: Array<{
        player: string;
        slot: string;
        is_starter: boolean;
        is_captain: boolean;
        is_vice: boolean;
        bench_order: number;
      }>;
    },
  ) {
    return this.http.put<FantasyOverview>(`${this.base}/competitions/${competitionId}/fantasy`, body);
  }

  fantasyPlayers(
    competitionId: string,
    query: { q?: string; slot?: string; club?: string } = {},
  ) {
    return this.http.get<{ players: FantasyPlayer[]; count: number }>(
      `${this.base}/competitions/${competitionId}/fantasy/players`,
      { params: toParams(query) },
    );
  }

  fantasyStandings(competitionId: string) {
    return this.http.get<{ rows: FantasyStandingRow[]; count: number }>(
      `${this.base}/competitions/${competitionId}/fantasy/standings`,
    );
  }

  autoPickFantasy(competitionId: string) {
    return this.http.post<{
      picks: Array<{
        player: string;
        slot: string;
        is_starter: boolean;
        is_captain: boolean;
        is_vice: boolean;
        bench_order: number;
      }>;
    }>(`${this.base}/competitions/${competitionId}/fantasy/auto-pick`, {});
  }

  // --- Search ---------------------------------------------------------------

  search(query: string, type?: string, competitionId?: string) {
    return this.http.get<{ query: string; results: Record<string, unknown[]> }>(
      `${this.base}/search`,
      { params: toParams({ q: query, type, competition: competitionId }) },
    );
  }
}
