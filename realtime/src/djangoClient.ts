import { config } from './config.js';
import { logger } from './logger.js';

export class DjangoError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly retryable: boolean,
  ) {
    super(message);
    this.name = 'DjangoError';
  }
}

/**
 * Call one of Django's internal endpoints.
 *
 * The workers deliberately hold no database credentials and no business logic.
 * Django owns both, so a rule such as "who receives this notification" has a
 * single definition rather than one per language.
 */
export async function callDjango<T = unknown>(
  path: string,
  body: Record<string, unknown>,
  { timeoutMs = 20_000 }: { timeoutMs?: number } = {},
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${config.djangoBaseUrl}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${config.internalApiToken}`,
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    });

    if (!response.ok) {
      const detail = await response.text();
      // 4xx means the job is malformed and will fail identically on every
      // retry; only 5xx and network faults are worth attempting again.
      const retryable = response.status >= 500;
      throw new DjangoError(
        `${path} returned ${response.status}: ${detail.slice(0, 300)}`,
        response.status,
        retryable,
      );
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DjangoError) throw error;
    if (error instanceof Error && error.name === 'AbortError') {
      throw new DjangoError(`${path} timed out after ${timeoutMs}ms`, 504, true);
    }
    logger.error({ err: error, path }, 'Call to Django failed');
    throw new DjangoError(String(error), 0, true);
  } finally {
    clearTimeout(timer);
  }
}
