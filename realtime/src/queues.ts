import { Queue } from 'bullmq';

import { createRedis } from './redis.js';

/** Queue names, mirrored in backend/apps/core/bus.py (class Queues). */
export const QUEUE_NAMES = ['media', 'notifications', 'standings', 'search'] as const;

export type QueueName = (typeof QUEUE_NAMES)[number];

export function isQueueName(value: string): value is QueueName {
  return (QUEUE_NAMES as readonly string[]).includes(value);
}

const connection = createRedis('queues', { forBullMq: true });

export const queues: Record<QueueName, Queue> = Object.fromEntries(
  QUEUE_NAMES.map((name) => [
    name,
    new Queue(name, {
      connection,
      defaultJobOptions: {
        attempts: 3,
        // Retries space out so a struggling downstream service is not hammered.
        backoff: { type: 'exponential', delay: 2000 },
        removeOnComplete: { age: 3600, count: 1000 },
        removeOnFail: { age: 86400 },
      },
    }),
  ]),
) as Record<QueueName, Queue>;

export async function closeQueues(): Promise<void> {
  await Promise.all(Object.values(queues).map((queue) => queue.close()));
  connection.disconnect();
}
