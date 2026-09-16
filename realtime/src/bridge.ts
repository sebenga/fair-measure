import type { Redis } from 'ioredis';

import { config } from './config.js';
import { logger } from './logger.js';
import { isQueueName, queues } from './queues.js';
import { isJobEnvelope } from './types.js';

/**
 * Move jobs from Django's inbox list into the right BullMQ queue.
 *
 * Django LPUSHes onto a plain Redis list rather than writing BullMQ's internal
 * structures directly, because those are maintained by Lua scripts that would
 * have to be reimplemented (and kept in step) on the Python side. A list also
 * survives a worker restart, which a pub/sub message would not.
 */
export function startJobBridge(connection: Redis): { stop: () => void } {
  let running = true;

  async function pump(): Promise<void> {
    while (running) {
      try {
        // BRPOP blocks rather than polling, so an idle system costs nothing.
        const result = await connection.brpop(config.jobInboxKey, 5);
        if (!result) continue;

        const [, raw] = result;
        if (!raw) continue;

        let parsed: unknown;
        try {
          parsed = JSON.parse(raw);
        } catch {
          logger.warn({ raw: raw.slice(0, 200) }, 'Discarded a malformed job');
          continue;
        }

        if (!isJobEnvelope(parsed)) {
          logger.warn('Discarded a job with an unexpected shape');
          continue;
        }

        if (!isQueueName(parsed.queue)) {
          logger.warn({ queue: parsed.queue }, 'Discarded a job for an unknown queue');
          continue;
        }

        await queues[parsed.queue].add(parsed.name, parsed.data, {
          jobId: parsed.id,
          attempts: parsed.opts?.attempts ?? 3,
          ...(parsed.opts?.delay ? { delay: parsed.opts.delay } : {}),
        });

        logger.debug({ queue: parsed.queue, name: parsed.name }, 'Enqueued a job');
      } catch (error) {
        if (!running) break;
        logger.error({ err: error }, 'Job bridge error; retrying shortly');
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
    }
  }

  void pump();

  return {
    stop() {
      running = false;
    },
  };
}
