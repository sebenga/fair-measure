import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private baseUrl = 'http://127.0.0.1:8001';

  constructor(private http: HttpClient) {}

  // Competitions
  getCompetitions(): Observable<any> {
    return this.http.get(`${this.baseUrl}/competitions/`);
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
