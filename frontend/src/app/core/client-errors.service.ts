import { HttpErrorResponse } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { TimeoutError } from 'rxjs';

import { environment } from '../../environments/environment';
import { AuthService } from './auth.service';
import { extractErrorMessage } from './error-message';

const MAX_PER_VISIT = 20;
export const CLIENT_ERRORS_PATH = '/client-errors';

interface ClientErrorReport {
  kind: 'crash' | 'request';
  message: string;
  stack?: string;
  method?: string;
  endpoint?: string;
  status?: number;
  detail?: string;
}

/**
 * Sends crashes and failed requests to the server log, so a failure that only
 * happens on one phone or browser can be read on Render like any other error.
 */
@Injectable({ providedIn: 'root' })
export class ClientErrorsService {
  private readonly auth = inject(AuthService);
  private readonly seen = new Set<string>();

  constructor() {
    if (typeof window === 'undefined') return;
    window.addEventListener('error', (event) =>
      this.crash(event.error ?? event.message, event.filename ? `${event.filename}:${event.lineno}` : ''),
    );
    window.addEventListener('unhandledrejection', (event) => this.crash(event.reason));
  }

  crash(error: unknown, where = ''): void {
    const inner = (error as { rejection?: unknown } | null)?.rejection ?? error;
    if (inner instanceof HttpErrorResponse || inner instanceof TimeoutError) return;
    const message = inner instanceof Error ? inner.message : String(inner ?? 'Unknown error');
    const stack = inner instanceof Error ? inner.stack ?? '' : where;
    this.send({ kind: 'crash', message, stack });
  }

  /** Failed saves, server errors, timeouts and dropped connections. Missing records and expired sign-ins are expected. */
  request(method: string, url: string, error: unknown): void {
    if (url.includes(CLIENT_ERRORS_PATH)) return;
    const status = error instanceof HttpErrorResponse ? error.status : undefined;
    const isRead = method === 'GET' || method === 'HEAD';
    if (status === 401 || (status === 404 && isRead)) return;
    if (status !== undefined && status >= 400 && status < 500 && isRead) return;
    this.send({
      kind: 'request',
      message: error instanceof TimeoutError ? 'Request timed out' : `HTTP ${status ?? '?'}`,
      method,
      endpoint: pathOf(url),
      status,
      detail: extractErrorMessage(error),
    });
  }

  private send(report: ClientErrorReport): void {
    try {
      const key = `${report.kind}|${report.message}|${report.endpoint ?? ''}|${report.status ?? ''}`;
      if (this.seen.has(key) || this.seen.size >= MAX_PER_VISIT) return;
      this.seen.add(key);
      const token = this.auth.getAccessToken();
      void fetch(`${environment.apiBaseUrl}${CLIENT_ERRORS_PATH}`, {
        method: 'POST',
        keepalive: true,
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          ...report,
          page: location.pathname,
          user_agent: navigator.userAgent,
        }),
      }).catch(() => undefined);
    } catch {
      // Reporting must never break the app.
    }
  }
}

/** The API path without origin or query string (queries can carry tokens). */
function pathOf(url: string): string {
  try {
    return new URL(url, location.origin).pathname;
  } catch {
    return url.split('?')[0];
  }
}
