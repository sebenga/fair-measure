import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { ToastController } from '@ionic/angular/standalone';
import { timeout, retry, timer, catchError, throwError } from 'rxjs';

import { environment } from '../../environments/environment';
import { extractErrorMessage } from './error-message';

const TIMEOUT_MS = 15_000;
const QUIET = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/google', '/healthz'];

export const reliabilityInterceptor: HttpInterceptorFn = (request, next) => {
  const toasts = inject(ToastController);
  const isApi = request.url.startsWith(environment.apiBaseUrl);
  const quiet = QUIET.some((path) => request.url.includes(path));
  const retried = request.method === 'GET' && isApi ? 2 : 0;

  return next(request).pipe(
    timeout({ first: TIMEOUT_MS }),
    retry({
      count: retried,
      delay: (_error, retryCount) => timer(400 * 2 ** (retryCount - 1)),
    }),
    catchError((error: unknown) => {
      if (isApi && !quiet && error instanceof HttpErrorResponse && error.status !== 401) {
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
