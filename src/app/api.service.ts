import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private baseUrl = '/api';

  constructor(private http: HttpClient) {}

  private handleError<T>(operation = 'operation', result?: T) {
    return (error: any): Observable<T> => {
      if (error instanceof SyntaxError) {
        console.error(`${operation} failed: Invalid JSON response`, error);
      } else {
        console.error(`${operation} failed:`, error);
      }
      // Return empty result to let the app continue functioning
      return of(result as T);
    };
  }

  private generateMockCompetitions() {
    const mockCompetitions = [];
    for (let i = 1; i <= 20; i++) {
      mockCompetitions.push({
        id: i,
        name: `Sample Competition ${i}`,
        description: `This is a sample competition description for competition ${i}. Join now to compete with others!`,
        image: `https://picsum.photos/80/80?random=${i}`
      });
    }
    return mockCompetitions;
  }
  // Competitions
  getCompetitions(): Observable<any> {
    return this.http.get(`${this.baseUrl}/competitions/`).pipe(
      catchError(this.handleError('getCompetitions', this.generateMockCompetitions()))
    );
  }
  getCompetition(id: number): Observable<any> {
    return this.http.get(`${this.baseUrl}/competitions/${id}`);
  }
  createCompetition(data: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/competitions/`, data);
  }
  updateCompetition(id: number, data: any): Observable<any> {
    return this.http.put(`${this.baseUrl}/competitions/${id}`, data);
  }
  deleteCompetition(id: number): Observable<any> {
    return this.http.delete(`${this.baseUrl}/competitions/${id}`);
  }

  // Fixtures
  getFixtures(): Observable<any> {
    return this.http.get(`${this.baseUrl}/fixtures/`);
  }
  getFixture(id: number): Observable<any> {
    return this.http.get(`${this.baseUrl}/fixtures/${id}`);
  }
  createFixture(data: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/fixtures/`, data);
  }
  updateFixture(id: number, data: any): Observable<any> {
    return this.http.put(`${this.baseUrl}/fixtures/${id}`, data);
  }
  deleteFixture(id: number): Observable<any> {
    return this.http.delete(`${this.baseUrl}/fixtures/${id}`);
  }

  // League Table
  getLeagueTable(): Observable<any> {
    return this.http.get(`${this.baseUrl}/league_table/`);
  }
  getLeagueTableEntry(id: number): Observable<any> {
    return this.http.get(`${this.baseUrl}/league_table/${id}`);
  }
  createLeagueTable(data: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/league_table/`, data);
  }
  updateLeagueTable(id: number, data: any): Observable<any> {
    return this.http.put(`${this.baseUrl}/league_table/${id}`, data);
  }
  deleteLeagueTable(id: number): Observable<any> {
    return this.http.delete(`${this.baseUrl}/league_table/${id}`);
  }

  // Teams
  getTeams(): Observable<any> {
    return this.http.get(`${this.baseUrl}/teams/`);
  }
  getTeam(id: number): Observable<any> {
    return this.http.get(`${this.baseUrl}/teams/${id}`);
  }
  createTeam(data: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/teams/`, data);
  }
  updateTeam(id: number, data: any): Observable<any> {
    return this.http.put(`${this.baseUrl}/teams/${id}`, data);
  }
  deleteTeam(id: number): Observable<any> {
    return this.http.delete(`${this.baseUrl}/teams/${id}`);
  }

  // Posts
  getPosts(): Observable<any> {
    return this.http.get(`${this.baseUrl}/posts/`);
  }
  getPost(id: number): Observable<any> {
    return this.http.get(`${this.baseUrl}/posts/${id}`);
  }
  createPost(data: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/posts/`, data);
  }
  updatePost(id: number, data: any): Observable<any> {
    return this.http.put(`${this.baseUrl}/posts/${id}`, data);
  }
  deletePost(id: number): Observable<any> {
    return this.http.delete(`${this.baseUrl}/posts/${id}`);
  }

  // Add similar methods for scoring_events, scoring_categories, rules, media, point_accumulation, replies as needed
}
