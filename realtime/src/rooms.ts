import { callDjango } from './djangoClient.js';
import { logger } from './logger.js';

/**
 * Room-name grammar, mirrored in backend/apps/core/bus.py.
 *
 * `user:<id>` is authorised locally because the socket's own identity is proof
 * enough. Competition, fixture and Games rooms need Django to confirm access, so
 * a private competition's live scores never leak to a non-member who guessed
 * an id.
 */
const ROOM_PATTERN = /^(competition|fixture|games|user):[0-9a-fA-F-]{36}$/;

export function isWellFormedRoom(room: string): boolean {
  return ROOM_PATTERN.test(room);
}

export function ownRoom(userId: string): string {
  return `user:${userId}`;
}

interface AuthorizeResponse {
  allowed: string[];
}

/** Ask Django which of `rooms` this user may subscribe to. */
export async function authorizeRooms(userId: string, rooms: string[]): Promise<Set<string>> {
  const wellFormed = rooms.filter(isWellFormedRoom);
  if (wellFormed.length === 0) return new Set();

  const allowed = new Set<string>();
  const needsCheck: string[] = [];

  for (const room of wellFormed) {
    if (room === ownRoom(userId)) {
      allowed.add(room);
    } else {
      needsCheck.push(room);
    }
  }

  if (needsCheck.length === 0) return allowed;

  try {
    const result = await callDjango<AuthorizeResponse>('/internal/rooms/authorize', {
      user_id: userId,
      rooms: needsCheck,
    });
    for (const room of result.allowed ?? []) {
      allowed.add(room);
    }
  } catch (error) {
    // Fail closed: an outage must not turn into an authorisation bypass.
    logger.error({ err: error, userId }, 'Room authorisation failed; denying access');
  }

  return allowed;
}
