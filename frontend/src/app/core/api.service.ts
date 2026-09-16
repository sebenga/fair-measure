import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import type {
  Comment,
  Competition,
  CompetitionDetail,
  CursorPaginated,
  Fixture,
  FixtureDetail,
  GenerateFixturesRequest,
  MediaAsset,
  Paginated,
  Participant,
  PointsPolicy,
  Post,
  Preset,
  ReactionKind,
  ReactionResult,
  Rule,
  ScoreEvent,
  ScoringCategory,
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

  createParticipant(competitionId: string, body: Partial<Participant>) {
    return this.http.post<Participant>(
      `${this.base}/competitions/${competitionId}/participants`,
      body,
    );
  }

  deleteParticipant(competitionId: string, participantId: string) {
    return this.http.delete<void>(
      `${this.base}/competitions/${competitionId}/participants/${participantId}`,
    );
  }

  addRosterMember(competitionId: string, participantId: string, body: Record<string, unknown>) {
    return this.http.post(
      `${this.base}/competitions/${competitionId}/participants/${participantId}/roster`,
      body,
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

  setFixtureStatus(competitionId: string, fixtureId: string, status: string) {
    return this.http.post<FixtureDetail>(
      `${this.base}/competitions/${competitionId}/fixtures/${fixtureId}/set-status`,
      { status },
    );
  }

  // --- Score events ---------------------------------------------------------

  recordEvent(fixtureId: string, body: Record<string, unknown>): Observable<ScoreEvent> {
    return this.http.post<ScoreEvent>(`${this.base}/fixtures/${fixtureId}/events`, body);
  }

  deleteEvent(fixtureId: string, eventId: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/fixtures/${fixtureId}/events/${eventId}`);
  }

  // --- Standings ------------------------------------------------------------

  getStandings(competitionId: string, query: Query = {}): Observable<StandingsResponse> {
    return this.http.get<StandingsResponse>(
      `${this.base}/competitions/${competitionId}/standings`,
      { params: toParams(query) },
    );
  }

  // --- Feed -----------------------------------------------------------------

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

  createComment(postId: string, body: string, parent?: string): Observable<Comment> {
    return this.http.post<Comment>(`${this.base}/posts/${postId}/comments`, {
      body,
      ...(parent ? { parent } : {}),
    });
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
    return this.http.get<Paginated<Record<string, unknown>>>(`${this.base}/notifications`, {
      params: toParams(query),
    });
  }

  markAllNotificationsRead() {
    return this.http.post<{ marked_read: number }>(
      `${this.base}/notifications/mark-all-read`,
      {},
    );
  }

  // --- Search ---------------------------------------------------------------

  search(query: string, type?: string, competitionId?: string) {
    return this.http.get<{ query: string; results: Record<string, unknown[]> }>(
      `${this.base}/search`,
      { params: toParams({ q: query, type, competition: competitionId }) },
    );
  }
}
