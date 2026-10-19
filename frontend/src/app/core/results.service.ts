import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import type { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import type {
  CombinationRow,
  CombinationStatRow,
  EntryData,
  Horse,
  OfficialsResponse,
  ResultSheet,
} from './results.models';

@Injectable({ providedIn: 'root' })
export class ResultsService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;

  // --- Officials --------------------------------------------------------------

  officials(competitionId: string): Observable<OfficialsResponse> {
    return this.http.get<OfficialsResponse>(`${this.base}/competitions/${competitionId}/officials`);
  }

  appointOfficial(competitionId: string, user: string, title: string) {
    return this.http.post<{ officials: OfficialsResponse['officials'] }>(
      `${this.base}/competitions/${competitionId}/officials`,
      { user, title },
    );
  }

  removeOfficial(competitionId: string, officialId: string) {
    return this.http.delete<{ officials: OfficialsResponse['officials'] }>(
      `${this.base}/competitions/${competitionId}/officials/${officialId}`,
    );
  }

  // --- Events and result sheets -----------------------------------------------

  createEvent(competitionId: string, body: { label: string; scheduled_at?: string | null }) {
    return this.http.post<ResultSheet>(`${this.base}/competitions/${competitionId}/events`, body);
  }

  sheet(fixtureId: string): Observable<ResultSheet> {
    return this.http.get<ResultSheet>(`${this.base}/fixtures/${fixtureId}/results`);
  }

  save(
    fixtureId: string,
    entries: Array<{ side: string; data: EntryData }>,
    options: { reason?: string; config?: Record<string, unknown> } = {},
  ): Observable<ResultSheet> {
    return this.http.put<ResultSheet>(`${this.base}/fixtures/${fixtureId}/results`, {
      entries,
      ...options,
    });
  }

  setStatus(fixtureId: string, body: { side: string; status: string; reason: string; welfare?: boolean }) {
    return this.http.post<ResultSheet>(`${this.base}/fixtures/${fixtureId}/results/status`, body);
  }

  finalise(fixtureId: string): Observable<ResultSheet> {
    return this.http.post<ResultSheet>(`${this.base}/fixtures/${fixtureId}/results/finalise`, {});
  }

  stats(competitionId: string, by: 'horse' | 'rider' | 'trainer') {
    return this.http.get<{ by: string; rows: CombinationStatRow[] }>(
      `${this.base}/competitions/${competitionId}/combination-stats`,
      { params: new HttpParams().set('by', by) },
    );
  }

  // --- Horses and combinations --------------------------------------------------

  horses(q = ''): Observable<Horse[]> {
    const params = q.trim() ? new HttpParams().set('q', q.trim()) : undefined;
    return this.http.get<Horse[]>(`${this.base}/horses`, { params });
  }

  horse(id: string): Observable<Horse> {
    return this.http.get<Horse>(`${this.base}/horses/${id}`);
  }

  createHorse(body: Partial<Horse>): Observable<Horse> {
    return this.http.post<Horse>(`${this.base}/horses`, body);
  }

  updateHorse(id: string, body: Partial<Horse>): Observable<Horse> {
    return this.http.patch<Horse>(`${this.base}/horses/${id}`, body);
  }

  combinations(competitionId: string): Observable<CombinationRow[]> {
    return this.http.get<CombinationRow[]>(`${this.base}/competitions/${competitionId}/combinations`);
  }

  addCombination(
    competitionId: string,
    body: { horse: string; rider?: string; rider_name?: string; trainer?: string; trainer_name?: string },
  ) {
    return this.http.post<{ participant_id: string; name: string }>(
      `${this.base}/competitions/${competitionId}/combinations`,
      body,
    );
  }
}
