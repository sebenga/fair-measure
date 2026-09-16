import {
  HttpErrorResponse,
  HttpEvent,
  HttpHandlerFn,
  HttpRequest,
} from '@angular/common/http';
import { inject } from '@angular/core';
import { BehaviorSubject, Observable, throwError } from 'rxjs';
import { catchError, filter, switchMap, take } from 'rxjs/operators';

import { environment } from '../../environments/environment';
import { AuthService } from './auth.service';

// Shared across concurrent requests so a burst of 401s triggers one refresh
// rather than one per request.
let refreshing = false;
const refreshed = new BehaviorSubject<string | null>(null);

const PUBLIC_PATHS = ['/auth/login', '/auth/register', '/auth/google', '/auth/refresh'];

export function authInterceptor(
  request: HttpRequest<unknown>,
  next: HttpHandlerFn,
): Observable<HttpEvent<unknown>> {
  const auth = inject(AuthService);

  const isOurApi = request.url.startsWith(environment.apiBaseUrl);
  const isPublic = PUBLIC_PATHS.some((path) => request.url.includes(path));

  const token = auth.getAccessToken();
  const authorised =
    isOurApi && !isPublic && token ? withToken(request, token) : request;

  return next(authorised).pipe(
    catchError((error: unknown) => {
      const shouldRefresh =
        error instanceof HttpErrorResponse &&
        error.status === 401 &&
        isOurApi &&
        !isPublic &&
        auth.getRefreshToken() !== null;

      if (!shouldRefresh) {
        return throwError(() => error);
      }
      return retryWithFreshToken(request, next, auth);
    }),
  );
}

function withToken(request: HttpRequest<unknown>, token: string): HttpRequest<unknown> {
  return request.clone({ setHeaders: { Authorization: `Bearer ${token}` } });
}

function retryWithFreshToken(
  request: HttpRequest<unknown>,
  next: HttpHandlerFn,
  auth: AuthService,
): Observable<HttpEvent<unknown>> {
  if (refreshing) {
    // Wait for the in-flight refresh instead of starting another one.
    return refreshed.pipe(
      filter((token): token is string => token !== null),
      take(1),
      switchMap((token) => next(withToken(request, token))),
    );
  }

  refreshing = true;
  refreshed.next(null);

  return auth.refresh().pipe(
    switchMap((response) => {
      refreshing = false;
      refreshed.next(response.access);
      return next(withToken(request, response.access));
    }),
    catchError((error: unknown) => {
      refreshing = false;
      // The refresh token is expired or revoked; there is nothing left to try.
      auth.logout();
      return throwError(() => error);
    }),
  );
}
