import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';

import { environment } from '../../environments/environment';

export type GamesKind = 'summer' | 'winter' | 'custom';
export type MedalRanking = 'gold_first' | 'total_first';
export type MedalKind = 'gold' | 'silver' | 'bronze';

export interface Games {
  id: string;
  name: string;
  edition: string;
  kind: GamesKind;
  host: string;
  starts_on: string | null;
  ends_on: string | null;
  logo_url: string;
  medal_table_ranking: MedalRanking;
  status: 'draft' | 'live' | 'completed';
  is_private: boolean;
  team_label: string;
  placing_points: number[];
  can_manage: boolean;
  event_count: number;
  noc_count: number;
  created_at: string;
}

export interface CatalogEvent {
  key: string;
  name: string;
  gender: string;
  kind: 'individual' | 'team';
  available: boolean;
  added: boolean;
}

export interface CatalogSport {
  key: string;
  label: string;
  season: 'summer' | 'winter';
  federation: string;
  federation_name: string;
  note: string;
  available: boolean;
  disciplines: Array<{ name: string; preset: string; available: boolean; events: CatalogEvent[] }>;
}

export interface GamesEventRow {
  id: string;
  sport_key: string;
  sport: string;
  discipline: string;
  name: string;
  gender: string;
  kind: 'individual' | 'team';
  venue: string;
  scheduled_at: string | null;
  preset_key: string;
  round_format: string;
  medal_type: 'standard' | 'bronze_match' | 'two_bronze';
  custom: boolean;
  status: 'scheduled' | 'in_progress' | 'medals_awarded';
  competition_id: string;
  entries: number;
}

export interface MedalRow {
  medal: MedalKind;
  rank: number;
  noc: string;
  entrant: string;
}

export interface RoundResult {
  participant_id: string;
  name: string;
  noc: string;
  noc_id: string | null;
  athlete_id: string | null;
  position: number;
  rank: number | null;
  mark: string;
  status: string;
  qualified: string;
  outcome?: string;
}

export interface EventRound {
  fixture_id: string;
  label: string;
  round: number | null;
  status: string;
  scheduled_at: string | null;
  final: boolean;
  start_list: Array<{ position: number; name: string; noc: string }>;
  results: RoundResult[];
}

export type RecordScope = 'games' | 'national' | 'world';

export interface GamesRecord {
  id: string;
  event_id: string;
  event: string;
  scope: RecordScope;
  scope_label: string;
  mark: string;
  previous_mark: string;
  holder: string;
  noc: string;
  athlete_id: string | null;
  set_on: string | null;
  note: string;
}

export interface GamesEventDetail extends Omit<GamesEventRow, 'entries'> {
  governing_body: string;
  rulebook: string;
  locked: boolean;
  qualification_rule: string;
  qualification_mark: string;
  rounds: EventRound[];
  records: GamesRecord[];
  can_add_records: boolean;
  games_id: string;
  preset_label: string;
  result_type: string | null;
  format: string;
  final_fixture: string | null;
  bronze_fixture: string | null;
  entries: EventEntry[];
  can_manage: boolean;
  medals: MedalRow[];
  medal_log: Array<{ reason: string; before: MedalRow[]; after: MedalRow[]; created_at: string }>;
  fixtures: Array<{
    id: string;
    label: string;
    round: number | null;
    status: string;
    scheduled_at: string | null;
    sides: Array<{ name: string; score: string; outcome: string }>;
  }>;
}

export interface EventEntry {
  id: string;
  participant_id: string;
  name: string;
  noc: string;
  noc_id: string;
  athlete_id: string | null;
}

export interface Noc {
  id: string;
  name: string;
  code: string;
  flag_url: string;
  colour: string;
}

export interface Athlete {
  id: string;
  name: string;
  noc: string;
  noc_id: string;
}

export interface MedalTableRow {
  noc_id: string;
  code: string;
  name: string;
  flag_url: string;
  colour: string;
  gold: number;
  silver: number;
  bronze: number;
  total: number;
  rank: number;
}

export interface MedalsResponse {
  ranking: MedalRanking;
  table: MedalTableRow[];
  by_sport: Array<{ sport: string; nocs: Array<{ code: string; gold: number; silver: number; bronze: number }> }>;
  feed: Array<{ event_id: string; event: string; medal: MedalKind; noc: string; entrant: string; awarded_at: string }>;
  points_table: PointsRow[];
}

export interface MedalLine {
  event_id: string;
  event: string;
  sport: string;
  medal: MedalKind;
  entrant: string;
}

export interface ResultLine {
  event_id: string;
  event: string;
  result_type: string;
  round: string;
  fixture_status: string;
  final: boolean;
  rank: number | null;
  mark: string;
  status: string;
  qualified: string;
}

export interface NocPage extends Noc {
  athletes: Array<{ id: string; name: string; events: number }>;
  entries: Array<{ event_id: string; event: string; entrant: string; athlete_id: string | null }>;
  results: ResultLine[];
  medals: MedalLine[];
  medals_by_sport: Array<{ sport: string; gold: number; silver: number; bronze: number }>;
  records: GamesRecord[];
}

export interface PersonalBest {
  event: string;
  mark: string;
  date: string;
}

export interface AthletePage {
  id: string;
  name: string;
  noc: string;
  noc_id: string;
  noc_name: string;
  events: Array<{ id: string; sport_key: string; sport: string; name: string; venue: string; scheduled_at: string | null; status: string }>;
  results: ResultLine[];
  personal_bests: PersonalBest[];
  best_at_games: Array<{ event_id: string; event: string; mark: string }>;
  medals: MedalLine[];
  records: GamesRecord[];
  scouting_profile_id: string | null;
  can_manage: boolean;
}

export type FollowTarget = 'noc' | 'sport' | 'athlete';

export interface GamesFollow {
  id: string;
  target: FollowTarget;
  noc_id: string | null;
  athlete_id: string | null;
  sport_key: string;
  label: string;
}

export interface PointsRow {
  noc_id: string;
  code: string;
  name: string;
  colour: string;
  points: string;
  placings: number;
  gold: number;
  silver: number;
  bronze: number;
  rank: number;
}

export interface Session {
  id: string;
  sport_key: string;
  sport: string;
  name: string;
  venue: string;
  scheduled_at: string | null;
  status: string;
  fixture_id: string | null;
  session: string;
  at?: string;
  fixture_status?: string;
}

export interface GamesOverview extends Games {
  countdown: { state: 'unscheduled' | 'upcoming' | 'live' | 'finished'; days_to_go: number | null; day: number | null };
  today: Session[];
  live: Session[];
  medal_table: MedalTableRow[];
  latest_medals: MedalsResponse['feed'];
  points_table: PointsRow[];
  records: GamesRecord[];
  following: GamesFollow[];
}

export type ReportKind = 'medal-table' | 'results-book' | 'noc-summary' | 'daily';

export interface GamesReport {
  title: string;
  subtitle: string;
  sections: Array<{ heading: string; columns: string[]; rows: string[][] }>;
}

@Injectable({ providedIn: 'root' })
export class GamesService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/games`;

  list(): Observable<Games[]> {
    return this.http.get<Games[]>(this.base);
  }

  create(body: Partial<Games>): Observable<Games> {
    return this.http.post<Games>(this.base, body);
  }

  get(id: string): Observable<Games> {
    return this.http.get<Games>(`${this.base}/${id}`);
  }

  catalog(gamesId: string, season?: string): Observable<CatalogSport[]> {
    let params = new HttpParams().set('games', gamesId);
    if (season) params = params.set('season', season);
    return this.http.get<CatalogSport[]>(`${this.base}/catalog`, { params });
  }

  addSports(gamesId: string, body: { events?: string[]; sports?: string[]; season?: string }) {
    return this.http.post<{ created: GamesEventRow[]; skipped: string[]; unavailable: string[] }>(
      `${this.base}/${gamesId}/sports`,
      body,
    );
  }

  events(gamesId: string): Observable<GamesEventRow[]> {
    return this.http.get<GamesEventRow[]>(`${this.base}/${gamesId}/events`);
  }

  addCustomEvent(gamesId: string, body: { sport: string; name: string; preset: string; kind?: string }) {
    return this.http.post<GamesEventRow>(`${this.base}/${gamesId}/events`, body);
  }

  event(gamesId: string, eventId: string): Observable<GamesEventDetail> {
    return this.http.get<GamesEventDetail>(`${this.base}/${gamesId}/events/${eventId}`);
  }

  removeEvent(gamesId: string, eventId: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${gamesId}/events/${eventId}`);
  }

  addEntry(gamesId: string, eventId: string, body: { noc: string; athlete?: string }) {
    return this.http.post<EventEntry>(`${this.base}/${gamesId}/events/${eventId}/entries`, body);
  }

  bronzeMatch(gamesId: string, eventId: string) {
    return this.http.post<{ fixture_id: string }>(`${this.base}/${gamesId}/events/${eventId}/bronze-match`, {});
  }

  nocs(gamesId: string): Observable<Noc[]> {
    return this.http.get<Noc[]>(`${this.base}/${gamesId}/nocs`);
  }

  addNoc(gamesId: string, body: { name: string; code: string; colour?: string }) {
    return this.http.post<Noc>(`${this.base}/${gamesId}/nocs`, body);
  }

  noc(gamesId: string, nocId: string): Observable<NocPage> {
    return this.http.get<NocPage>(`${this.base}/${gamesId}/nocs/${nocId}`);
  }

  athletes(gamesId: string): Observable<Athlete[]> {
    return this.http.get<Athlete[]>(`${this.base}/${gamesId}/athletes`);
  }

  addAthlete(gamesId: string, body: { noc: string; name: string }) {
    return this.http.post<Athlete>(`${this.base}/${gamesId}/athletes`, body);
  }

  medals(gamesId: string): Observable<MedalsResponse> {
    return this.http.get<MedalsResponse>(`${this.base}/${gamesId}/medals`);
  }

  schedule(gamesId: string): Observable<Array<{ day: string; events: GamesEventRow[] }>> {
    return this.http.get<Array<{ day: string; events: GamesEventRow[] }>>(`${this.base}/${gamesId}/schedule`);
  }

  overview(gamesId: string): Observable<GamesOverview> {
    return this.http.get<GamesOverview>(`${this.base}/${gamesId}/overview`);
  }

  updateEvent(gamesId: string, eventId: string, body: Record<string, unknown>) {
    return this.http.patch<GamesEventDetail>(`${this.base}/${gamesId}/events/${eventId}`, body);
  }

  athlete(gamesId: string, athleteId: string): Observable<AthletePage> {
    return this.http.get<AthletePage>(`${this.base}/${gamesId}/athletes/${athleteId}`);
  }

  updateAthlete(gamesId: string, athleteId: string, body: { name?: string; personal_bests?: PersonalBest[] }) {
    return this.http.patch<AthletePage>(`${this.base}/${gamesId}/athletes/${athleteId}`, body);
  }

  addRecord(gamesId: string, eventId: string, body: Record<string, unknown>) {
    return this.http.post<GamesRecord>(`${this.base}/${gamesId}/events/${eventId}/records`, body);
  }

  removeRecord(gamesId: string, recordId: string) {
    return this.http.delete<void>(`${this.base}/${gamesId}/records/${recordId}`);
  }

  follows(gamesId: string): Observable<GamesFollow[]> {
    return this.http.get<GamesFollow[]>(`${this.base}/${gamesId}/follows`);
  }

  follow(gamesId: string, body: { target: FollowTarget; noc?: string; athlete?: string; sport_key?: string }) {
    return this.http.post<GamesFollow>(`${this.base}/${gamesId}/follows`, body);
  }

  unfollow(gamesId: string, followId: string) {
    return this.http.delete<void>(`${this.base}/${gamesId}/follows/${followId}`);
  }

  report(gamesId: string, kind: ReportKind, params: Record<string, string> = {}): Observable<GamesReport> {
    return this.http.get<GamesReport>(`${this.base}/${gamesId}/reports/${kind}`, { params });
  }

  reportCsv(gamesId: string, kind: ReportKind, params: Record<string, string> = {}): Observable<Blob> {
    return this.http.get(`${this.base}/${gamesId}/reports/${kind}`, {
      params: { ...params, export: 'csv' },
      responseType: 'blob',
    });
  }
}
