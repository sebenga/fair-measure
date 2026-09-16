/** The message Django publishes on the realtime pub/sub channel. */
export interface RealtimeEnvelope {
  id: string;
  event: string;
  rooms: string[];
  payload: Record<string, unknown>;
  ts: number;
}

/** The message Django pushes onto the job inbox list. */
export interface JobEnvelope {
  id: string;
  queue: string;
  name: string;
  data: Record<string, unknown>;
  opts?: {
    attempts?: number;
    delay?: number;
  };
}

export interface AuthenticatedUser {
  id: string;
  email?: string;
  displayName?: string;
}

export function isRealtimeEnvelope(value: unknown): value is RealtimeEnvelope {
  if (typeof value !== 'object' || value === null) return false;
  const candidate = value as Partial<RealtimeEnvelope>;
  return (
    typeof candidate.event === 'string' &&
    Array.isArray(candidate.rooms) &&
    candidate.rooms.every((room) => typeof room === 'string')
  );
}

export function isJobEnvelope(value: unknown): value is JobEnvelope {
  if (typeof value !== 'object' || value === null) return false;
  const candidate = value as Partial<JobEnvelope>;
  return typeof candidate.queue === 'string' && typeof candidate.name === 'string';
}
