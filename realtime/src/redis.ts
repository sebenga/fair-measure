import { Redis } from 'ioredis';

import { config } from './config.js';
import { logger } from './logger.js';

/**
 * A Redis connection in subscribe mode cannot issue other commands, and BullMQ
 * requires `maxRetriesPerRequest: null` on the connections it owns. Each caller
 * therefore gets a purpose-built connection rather than sharing one.
 */
export function createRedis(purpose: string, options: { forBullMq?: boolean } = {}): Redis {
  const client = new Redis(config.redisUrl, {
    // BullMQ blocks on commands indefinitely and manages its own retries.
    maxRetriesPerRequest: options.forBullMq ? null : 3,
    enableReadyCheck: !options.forBullMq,
    lazyConnect: false,
    retryStrategy(attempt) {
      return Math.min(attempt * 200, 5000);
    },
  });

  client.on('error', (error) => logger.error({ purpose, err: error }, 'Redis error'));
  client.on('connect', () => logger.info({ purpose }, 'Redis connected'));
  client.on('close', () => logger.warn({ purpose }, 'Redis connection closed'));

  return client;
}
