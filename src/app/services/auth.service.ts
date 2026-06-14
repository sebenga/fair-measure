import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError, map } from 'rxjs/operators';

export interface UserSession {
  id: string;
  email: string;
  name: string;
  full_name?: string;
  user_id?: string;
}

interface AuthApiResponse {
  user: {
    id: string;
    email: string;
    fullName: string;
    full_name?: string;
    displayName?: string;
  };
  accessToken: string;
  tokenType?: string;
}

/** Raw JSON from the API (camelCase or snake_case). */
type AuthApiPayload = {
  user?: {
    id?: string;
    email?: string;
    fullName?: string;
    full_name?: string;
    displayName?: string;
  };
  accessToken?: string;
  access_token?: string;
  tokenType?: string;
  token_type?: string;
};

export interface RegisterRequest {
  email: string;
  password: string;
  fullName: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly baseUrl = '/api/auth';
  /** Legacy keys — cleared on startup so reload never restores a session. */
  private readonly currentUserKey = 'currentUser';
  private readonly tokenKey = 'accessToken';

  private session: UserSession | null = null;
  private accessToken: string | null = null;

  constructor(private http: HttpClient) {
    this.restoreSession();
    this.clearLegacyStorage();
  }

  register(data: RegisterRequest): Observable<UserSession> {
    return this.http
      .post<AuthApiResponse>(`${this.baseUrl}/register`, {
        email: data.email.trim().toLowerCase(),
        password: data.password,
        fullName: data.fullName.trim(),
      })
      .pipe(
        map((res) => this.persistAuthResponse(res)),
        catchError((err) => this.handleError(err))
      );
  }

  login(data: LoginRequest): Observable<UserSession> {
    return this.http
      .post<AuthApiPayload>(`${this.baseUrl}/login`, {
        email: data.email.trim().toLowerCase(),
        password: data.password,
      })
      .pipe(
        map((res) => {
          if (!res || typeof res !== 'object') {
            throw new Error('Invalid login response from server.');
          }
          return this.persistAuthResponse(res);
        }),
        catchError((err) => this.handleError(err))
      );
  }

  logout(): void {
    this.session = null;
    this.accessToken = null;
    sessionStorage.removeItem(this.tokenKey);
    sessionStorage.removeItem(this.currentUserKey);
    this.clearLegacyStorage();
  }

  isLoggedIn(): boolean {
    return !!this.accessToken;
  }

  getCurrentUser(): UserSession | null {
    return this.session;
  }

  getOwnerId(): string {
    const user = this.getCurrentUser();
    return user?.id || user?.user_id || '';
  }

  getAccessToken(): string | null {
    return this.accessToken;
  }

  private persistAuthResponse(payload: AuthApiPayload | AuthApiResponse): UserSession {
    const body =
      payload && typeof payload === 'object' && 'data' in payload
        ? (payload as { data: AuthApiPayload }).data
        : payload;
    const res = this.normalizeAuthResponse(body as AuthApiPayload);
    const session = this.toSession(res);
    this.session = session;
    this.accessToken = res.accessToken;
    sessionStorage.setItem(this.tokenKey, res.accessToken);
    sessionStorage.setItem(this.currentUserKey, JSON.stringify(session));
    return session;
  }

  private restoreSession(): void {
    const token = sessionStorage.getItem(this.tokenKey);
    const raw = sessionStorage.getItem(this.currentUserKey);
    if (!token || !raw) {
      return;
    }
    try {
      this.accessToken = token;
      this.session = JSON.parse(raw) as UserSession;
    } catch {
      this.logout();
    }
  }

  private clearLegacyStorage(): void {
    localStorage.removeItem(this.currentUserKey);
    localStorage.removeItem(this.tokenKey);
  }

  private normalizeAuthResponse(payload: AuthApiPayload): AuthApiResponse {
    const user = payload.user as AuthApiPayload['user'] & { _id?: string };
    const accessToken = payload.accessToken ?? payload.access_token;
    const userId = user?.id ?? user?._id;
    const fullName =
      user?.fullName ?? user?.full_name ?? user?.displayName ?? user?.email ?? '';

    if (!userId || !user?.email || !accessToken) {
      throw new Error('Invalid login response from server.');
    }

    return {
      user: {
        id: userId,
        email: user.email,
        fullName,
      },
      accessToken,
      tokenType: payload.tokenType ?? payload.token_type,
    };
  }

  private toSession(res: AuthApiResponse): UserSession {
    return {
      id: res.user.id,
      user_id: res.user.id,
      email: res.user.email,
      name: res.user.fullName || res.user.email,
      full_name: res.user.fullName,
    };
  }

  private handleError(error: HttpErrorResponse | Error): Observable<never> {
    let message = 'Something went wrong. Please try again.';

    if (error instanceof HttpErrorResponse) {
      if (error.status === 401) {
        message = 'Invalid email or password.';
      } else if (error.status === 400) {
        message =
          typeof error.error?.detail === 'string'
            ? error.error.detail
            : 'Invalid request.';
      } else if (error.status === 0) {
        message = 'Cannot reach the API. Is the backend running on port 8000?';
      } else if (typeof error.error?.detail === 'string') {
        message = error.error.detail;
      }
    } else if (error.message) {
      message = error.message;
    }

    return throwError(() => new Error(message));
  }
}
