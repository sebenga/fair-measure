import { config as loadEnv } from 'dotenv';
import { resolve } from 'node:path';

// Prefer realtime/.env, then fall back to the repo-root .env so a single file
// can configure Django and this service with the same values.
loadEnv({ path: resolve(process.cwd(), '.env') });
loadEnv({ path: resolve(process.cwd(), '..', '.env') });

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(
      `${name} is not set. The realtime service shares this value with Django; ` +
        'copy .env.example to .env and fill it in.',
    );
  }
  return value;
}

function optional(name: string, fallback: string): string {
  return process.env[name] ?? fallback;
}

function list(name: string, fallback: string): string[] {
  return optional(name, fallback)
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

export const config = {
  port: Number(optional('REALTIME_PORT', '4000')),
  logLevel: optional('LOG_LEVEL', 'info').toLowerCase(),

  redisUrl: optional('REDIS_URL', 'redis://localhost:6379/0'),

  // Must match Django's SIMPLE_JWT SIGNING_KEY and ALGORITHM.
  jwtSecret: required('JWT_SIGNING_KEY'),
  jwtAlgorithm: 'HS256' as const,

  corsOrigins: list('REALTIME_CORS_ORIGINS', 'http://localhost:8100,http://localhost:4200'),

  // Django side of the bridge. These names are mirrored in apps/core/bus.py.
  eventChannel: optional('REALTIME_EVENT_CHANNEL', 'fm:events'),
  jobInboxKey: optional('JOB_INBOX_KEY', 'fm:jobs:inbox'),

  internalApiToken: required('INTERNAL_API_TOKEN'),
  djangoBaseUrl: optional('DJANGO_INTERNAL_BASE_URL', 'http://localhost:8000').replace(/\/$/, ''),
};

export type Config = typeof config;
