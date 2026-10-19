/**
 * The BullMQ worker process.
 *
 * Runs the Django -> BullMQ bridge and one Worker per queue. Keep this separate
 * from the Socket.io gateway so a slow job cannot delay live score delivery, and
 * so the two can be scaled independently.
 */

import { Worker } from 'bullmq';

import { startJobBridge } from './bridge.js';
import { handlers } from './handlers.js';
import { logger } from './logger.js';
import { closeQueues, QUEUE_NAMES, queues, type QueueName } from './queues.js';
import { createRedis } from './redis.js';

const bridgeConnection = createRedis('job-bridge');
const workerConnection = createRedis('workers', { forBullMq: true });

const bridge = startJobBridge(bridgeConnection);

const workers = QUEUE_NAMES.map((name: QueueName) => {
  const worker = new Worker(
    name,
    async (job) => {
      const started = Date.now();
      const result = await handlers[name](job);
      logger.info(
        { queue: name, job: job.name, id: job.id, ms: Date.now() - started },
        'Job completed',
      );
      return result;
    },
    {
      connection: workerConnection,
      // Notifications and search fan out over the network, so a little
      // concurrency helps; standings and player-stats recomputes are heavier and
      // serialised per competition by Django anyway.
      concurrency: name === 'standings' || name === 'stats' ? 2 : 5,
    },
  );

  worker.on('failed', (job, error) => {
    logger.error(
      { queue: name, job: job?.name, id: job?.id, attempts: job?.attemptsMade, err: error.message },
      'Job failed',
    );
  });

  worker.on('error', (error) => {
    logger.error({ queue: name, err: error }, 'Worker error');
  });

  return worker;
});

logger.info({ queues: QUEUE_NAMES }, 'Workers started');

/** Saved-search alerts run on a schedule; the fixed job id keeps one schedule per deployment. */
const SAVED_SEARCH_EVERY_MS = Number(process.env.SAVED_SEARCH_EVERY_MS ?? 15 * 60 * 1000);
void queues.scouting
  .add('saved-search-alerts', {}, { repeat: { every: SAVED_SEARCH_EVERY_MS }, jobId: 'saved-search-alerts' })
  .then(() => logger.info({ everyMs: SAVED_SEARCH_EVERY_MS }, 'Saved-search alerts scheduled'))
  .catch((error: unknown) => logger.error({ err: error }, 'Could not schedule saved-search alerts'));

async function shutdown(signal: string): Promise<void> {
  logger.info({ signal }, 'Shutting down workers');
  bridge.stop();

  // Let in-flight jobs finish rather than leaving them stalled for the next boot.
  await Promise.all(workers.map((worker) => worker.close()));
  await closeQueues();
  bridgeConnection.disconnect();
  workerConnection.disconnect();

  process.exit(0);
}

process.on('SIGTERM', () => void shutdown('SIGTERM'));
process.on('SIGINT', () => void shutdown('SIGINT'));
