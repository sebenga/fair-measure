import { HttpErrorResponse } from '@angular/common/http';
import { ErrorHandler, Injectable } from '@angular/core';
import { TimeoutError } from 'rxjs';

/** Failed requests are already reported by the reliability interceptor's toast; they are not screen crashes. */
function isRequestFailure(error: unknown): boolean {
  const inner = (error as { rejection?: unknown } | null)?.rejection ?? error;
  return inner instanceof HttpErrorResponse || inner instanceof TimeoutError;
}

@Injectable()
export class FairMeasureErrorHandler implements ErrorHandler {
  handleError(error: unknown): void {
    console.error(error);
    if (isRequestFailure(error)) return;
    if (document.documentElement.classList.contains('fm-booted')) {
      const banner = document.getElementById('fm-runtime-error');
      const detail = document.getElementById('fm-runtime-error-detail');
      if (detail) {
        const message = error instanceof Error ? error.message : '';
        detail.textContent = message && message.length < 180 ? message : '';
      }
      if (banner) banner.hidden = false;
      return;
    }
    const show = (window as Window & { __fmShowBootError?: (message: string) => void })
      .__fmShowBootError;
    const message = error instanceof Error ? error.message : 'The app hit an unexpected error.';
    show?.(message);
  }
}
