import type { Job } from 'bullmq';

import { callDjango, DjangoError } from './djangoClient.js';
import { logger } from './logger.js';
import type { QueueName } from './queues.js';

type Handler = (job: Job) => Promise<unknown>;

/**
 * Each handler forwards to the Django endpoint that owns the logic. Errors from
 * a malformed job are swallowed so BullMQ does not retry something that can
 * never succeed; transient failures are rethrown so it does.
 */
async function forward(path: string, body: Record<string, unknown>, job: Job): Promise<unknown> {
  try {
    return await callDjango(path, body);
  } catch (error) {
    if (error instanceof DjangoError && !error.retryable) {
      logger.error(
        { jobId: job.id, name: job.name, status: error.status, err: error.message },
        'Dropping a job Django rejected as invalid',
      );
      return { dropped: true, reason: error.message };
    }
    throw error;
  }
}

export const handlers: Record<QueueName, Handler> = {
  standings: (job) =>
    forward('/internal/standings/recompute', { ...job.data }, job),

  notifications: (job) =>
    forward('/internal/notifications/dispatch', { job: job.name, data: job.data }, job),

  search: (job) => forward('/internal/search/index', { job: job.name, data: job.data }, job),

  media: (job) => forward('/internal/media/finalize', { job: job.name, data: job.data }, job),
};
