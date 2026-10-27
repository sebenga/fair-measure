import { HttpErrorResponse } from '@angular/common/http';

import type { ApiError } from './models';

/**
 * Turn an HTTP failure into something worth showing a person.
 *
 * The API wraps every error as `{ error: { code, message, detail } }`, and
 * `detail` is usually DRF's per-field map. The first field message is far more
 * useful than a generic "Request failed", so prefer it when present.
 */
export function extractErrorMessage(error: unknown, fallback = 'Something went wrong.'): string {
  if (!(error instanceof HttpErrorResponse)) {
    return fallback;
  }

  if (error.status === 0) {
    return 'Could not reach the server. Check your connection and try again.';
  }

  if (typeof error.error === 'string' && error.error.includes('<html')) {
    return 'The server sent a page instead of data. Retry in a moment.';
  }

  const body = error.error as Partial<ApiError> | undefined;
  const envelope = body?.error;
  if (!envelope) {
    return fallback;
  }

  const fieldMessage = firstFieldMessage(envelope.detail);
  if (fieldMessage) {
    return fieldMessage;
  }

  return envelope.message || fallback;
}

function firstFieldMessage(detail: unknown): string | null {
  if (!detail) return null;

  if (Array.isArray(detail)) {
    const first = detail[0];
    return typeof first === 'string' ? first : null;
  }

  if (typeof detail === 'object') {
    for (const value of Object.values(detail as Record<string, unknown>)) {
      if (typeof value === 'string') return value;
      if (Array.isArray(value) && typeof value[0] === 'string') return value[0];
    }
  }

  return null;
}
