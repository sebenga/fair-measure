import { ErrorHandler, Injectable } from '@angular/core';

@Injectable()
export class FairMeasureErrorHandler implements ErrorHandler {
  handleError(error: unknown): void {
    console.error(error);
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
