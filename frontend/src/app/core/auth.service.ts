import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';

import { environment } from '../../environments/environment';
import type { AuthResponse, User } from './models';

const ACCESS_KEY = 'fm.access';
const REFRESH_KEY = 'fm.refresh';
const USER_KEY = 'fm.user';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly base = environment.apiBaseUrl;

  private readonly accessToken = signal<string | null>(localStorage.getItem(ACCESS_KEY));
  private readonly currentUser = signal<User | null>(readStoredUser());

  readonly user = this.currentUser.asReadonly();
  readonly isAuthenticated = computed(() => this.accessToken() !== null);

  getAccessToken(): string | null {
    return this.accessToken();
  }

  getRefreshToken(): string | null {
    return localStorage.getItem(REFRESH_KEY);
  }

  login(email: string, password: string): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${this.base}/auth/login`, { email, password })
      .pipe(tap((response) => this.persist(response)));
  }

  register(email: string, password: string, displayName: string): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${this.base}/auth/register`, {
        email,
        password,
        display_name: displayName,
      })
      .pipe(tap((response) => this.persist(response)));
  }

  /** Exchange a Google ID token from the native or web Google client. */
  loginWithGoogle(idToken: string): Observable<AuthResponse> {
    return this.http
      .post<AuthResponse>(`${this.base}/auth/google`, { id_token: idToken })
      .pipe(tap((response) => this.persist(response)));
  }

  refresh(): Observable<{ access: string; refresh?: string }> {
    const refresh = this.getRefreshToken();
    return this.http
      .post<{ access: string; refresh?: string }>(`${this.base}/auth/refresh`, { refresh })
      .pipe(
        tap((response) => {
          localStorage.setItem(ACCESS_KEY, response.access);
          this.accessToken.set(response.access);
          // ROTATE_REFRESH_TOKENS is on server-side, so store the new one.
          if (response.refresh) {
            localStorage.setItem(REFRESH_KEY, response.refresh);
          }
        }),
      );
  }

  loadProfile(): Observable<User> {
    return this.http
      .get<User>(`${this.base}/auth/me`)
      .pipe(tap((user) => this.setUser(user)));
  }

  updateProfile(
    changes: Partial<
      Pick<
        User,
        | 'display_name'
        | 'bio'
        | 'avatar_url'
        | 'given_name'
        | 'family_name'
        | 'date_of_birth'
        | 'id_number'
        | 'phone'
        | 'city'
        | 'country'
        | 'headline'
        | 'website'
        | 'experience'
        | 'education'
        | 'skills'
        | 'languages'
      >
    >,
  ) {
    return this.http
      .patch<User>(`${this.base}/auth/me`, changes)
      .pipe(tap((user) => this.setUser(user)));
  }

  logout(redirect = true): void {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
    this.accessToken.set(null);
    this.currentUser.set(null);
    if (redirect) {
      void this.router.navigate(['/login']);
    }
  }

  private persist(response: AuthResponse): void {
    localStorage.setItem(ACCESS_KEY, response.access);
    localStorage.setItem(REFRESH_KEY, response.refresh);
    this.accessToken.set(response.access);
    this.setUser(response.user);
  }

  private setUser(user: User): void {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    this.currentUser.set(user);
  }
}

function readStoredUser(): User | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    // A corrupt entry should log the user out rather than crash the boot.
    localStorage.removeItem(USER_KEY);
    return null;
  }
}
