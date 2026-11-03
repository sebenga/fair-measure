import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { ToastController } from '@ionic/angular/standalone';
import { TimeoutError, timeout, retry, timer, catchError, throwError } from 'rxjs';

import { isApiUrl } from './api-url';
import { extractErrorMessage } from './error-message';

const TIMEOUT_MS = 15_000;
// A sleeping free Render instance can take close to a minute to answer the first write.
const WRITE_TIMEOUT_MS = 60_000;
const AUTH_TIMEOUT_MS = 45_000;
const QUIET = [
  '/auth/login',
  '/auth/register',
  '/auth/refresh',
  '/auth/google',
  '/healthz',
  '/realtime/events',
];
const AUTH = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/google'];

export const reliabilityInterceptor: HttpInterceptorFn = (request, next) => {
  const toasts = inject(ToastController);
  const isApi = isApiUrl(request.url);
  const quiet = QUIET.some((path) => request.url.includes(path));
  const authCall = AUTH.some((path) => request.url.includes(path));
  const isRead = request.method === 'GET' || request.method === 'HEAD';
  const retried = isRead && isApi && !quiet ? 2 : 0;
  const limit = authCall ? AUTH_TIMEOUT_MS : isRead ? TIMEOUT_MS : WRITE_TIMEOUT_MS;

  return next(request).pipe(
    timeout({ first: limit }),
    retry({
      count: retried,
      delay: (error, retryCount) => {
        // 4xx answers (expired sign-in, not found, validation) will not change on a second try.
        if (error instanceof HttpErrorResponse && error.status >= 400 && error.status < 500) {
          return throwError(() => error);
        }
        return timer(400 * 2 ** (retryCount - 1));
      },
    }),
    catchError((error: unknown) => {
      // Pages show their own "not found" state for a missing record, so a read 404 needs no toast.
      const missing = error instanceof HttpErrorResponse && error.status === 404 && isRead;
      const shown =
        (error instanceof HttpErrorResponse && error.status !== 401 && !missing) ||
        error instanceof TimeoutError;
      if (isApi && !quiet && shown) {
        void showToast(toasts, extractErrorMessage(error));
      }
      return throwError(() => error);
    }),
  );
};

async function showToast(toasts: ToastController, message: string): Promise<void> {
  try {
    const toast = await toasts.create({ message, duration: 2800, color: 'danger' });
    await toast.present();
  } catch {
    // Ionic is not ready during the first boot request.
  }
}
