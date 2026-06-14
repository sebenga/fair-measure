import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError, map } from 'rxjs/operators';

export interface CompetitionPayload {
  id?: string;
  name: string;
  author: string;
  owner_id: string;
  date_created: string;
  logo_location: string;
  is_private: boolean;
  type: string;
  rules: { name: string; description: string }[];
  scoring_categories: { name: string; description: string; points: number }[];
  point_accumulation: { win: number; lose: number; draw: number };
  participants: string[];
  fixtures: string[];
  league_table: string[];
  posts: string[];
  photos: string[];
  videos: string[];
  default_photo_repositories?: string[];
  default_video_repositories?: string[];
}

export interface CompetitionCard {
  id: string;
  name: string;
  description: string;
  image: string;
  author?: string;
  type?: string;
  is_private?: boolean;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private baseUrl = '/api';

  constructor(private http: HttpClient) {}

  getCompetitions(): Observable<CompetitionCard[]> {
    return this.http.get<CompetitionPayload[]>(`${this.baseUrl}/competitions/`).pipe(
      map((list) => (Array.isArray(list) ? list : []).map((c) => this.toCard(c))),
      catchError((err) => {
        console.error('getCompetitions failed:', err);
        return throwError(() => err);
      })
    );
  }

  createCompetition(data: CompetitionPayload): Observable<CompetitionPayload> {
    return this.http.post<CompetitionPayload>(`${this.baseUrl}/competitions/`, data).pipe(
      catchError((err) => {
        console.error('createCompetition failed:', err);
        return throwError(() => err);
      })
    );
  }

  getCompetition(id: string): Observable<CompetitionPayload> {
    return this.http.get<CompetitionPayload>(`${this.baseUrl}/competitions/${id}`);
  }

  private toCard(c: CompetitionPayload): CompetitionCard {
    const firstRule = c.rules?.[0];
    return {
      id: c.id || '',
      name: c.name,
      description: firstRule?.description || `${c.type || 'Competition'} · by ${c.author || 'Unknown'}`,
      image: c.logo_location || 'https://via.placeholder.com/80?text=Competition',
      author: c.author,
      type: c.type,
      is_private: c.is_private,
    };
  }
}
