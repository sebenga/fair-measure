import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class CompetitionsService {
  private apiUrl = 'http://127.0.0.1:8001/competitions/';

  constructor(private http: HttpClient) {}

  getCompetitions(): Observable<any> {
    return this.http.get<any>(this.apiUrl);
  }
}
