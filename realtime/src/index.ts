/**
 * The Socket.io gateway.
 *
 * Django publishes every realtime event to a Redis pub/sub channel. This
 * process subscribes once and fans each message out to the rooms named in the
 * envelope. Clients never write to the socket to change data; they call the
 * REST API, and the resulting event comes back through here. That keeps one
 * authorisation path instead of two.
 */

import express from 'express';
import { createServer } from 'node:http';
import { Server as SocketServer } from 'socket.io';

import { extractToken, verifyAccessToken } from './auth.js';
import { config } from './config.js';
import { logger } from './logger.js';
import { createRedis } from './redis.js';
import { authorizeRooms, isWellFormedRoom, ownRoom } from './rooms.js';
import { isRealtimeEnvelope, type AuthenticatedUser } from './types.js';

declare module 'socket.io' {
  interface Socket {
    user?: AuthenticatedUser;
  }
}

const app = express();
const httpServer = createServer(app);

const io = new SocketServer(httpServer, {
  cors: { origin: config.corsOrigins, credentials: true },
  // Mobile clients drop in and out of coverage; a short grace period lets them
  // resume the same session rather than refetching the whole screen.
  connectionStateRecovery: {
    maxDisconnectionDuration: 2 * 60 * 1000,
    skipMiddlewares: false,
  },
  pingTimeout: 25_000,
});

app.get('/healthz', (_req, res) => {
  res.json({
    status: 'ok',
    sockets: io.engine.clientsCount,
    subscriber: subscriber.status,
  });
});

// --- Authentication ---------------------------------------------------------

io.use((socket, next) => {
  const token = extractToken(socket.handshake);
  if (!token) {
    next(new Error('An access token is required to connect.'));
    return;
  }

  try {
    socket.user = verifyAccessToken(token);
    next();
  } catch (error) {
    logger.debug({ err: error }, 'Rejected a socket handshake');
    next(new Error('Invalid or expired access token.'));
  }
});

// --- Connection handling ----------------------------------------------------

io.on('connection', (socket) => {
  const user = socket.user;
  if (!user) {
    socket.disconnect(true);
    return;
  }

  // Every socket joins its own room so the server can reach one user directly,
  // for example when their video finishes encoding.
  void socket.join(ownRoom(user.id));
  logger.info({ userId: user.id, socketId: socket.id }, 'Socket connected');

  socket.on('subscribe', async (rooms: unknown, ack?: (result: unknown) => void) => {
    const requested = (Array.isArray(rooms) ? rooms : [rooms]).filter(
      (room): room is string => typeof room === 'string',
    );

    const malformed = requested.filter((room) => !isWellFormedRoom(room));
    const allowed = await authorizeRooms(user.id, requested);

    if (allowed.size > 0) {
      await socket.join([...allowed]);
    }

    const denied = requested.filter((room) => !allowed.has(room));
    if (denied.length > 0) {
      logger.debug({ userId: user.id, denied }, 'Denied room subscriptions');
    }

    ack?.({ joined: [...allowed], denied, malformed });
  });

  socket.on('unsubscribe', async (rooms: unknown, ack?: (result: unknown) => void) => {
    const requested = (Array.isArray(rooms) ? rooms : [rooms]).filter(
      (room): room is string => typeof room === 'string' && room !== ownRoom(user.id),
    );
    await Promise.all(requested.map((room) => socket.leave(room)));
    ack?.({ left: requested });
  });

  socket.on('disconnect', (reason) => {
    logger.info({ userId: user.id, socketId: socket.id, reason }, 'Socket disconnected');
  });
});

// --- Django -> Socket.io bridge ---------------------------------------------

const subscriber = createRedis('event-subscriber');

subscriber.subscribe(config.eventChannel, (error, count) => {
  if (error) {
    logger.error({ err: error }, 'Could not subscribe to the event channel');
    return;
  }
  logger.info({ channel: config.eventChannel, count }, 'Subscribed to Django events');
});

subscriber.on('message', (_channel, raw) => {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    logger.warn({ raw: raw.slice(0, 200) }, 'Discarded a malformed event');
    return;
  }

  if (!isRealtimeEnvelope(parsed)) {
    logger.warn('Discarded an event with an unexpected shape');
    return;
  }

  const { event, rooms, payload, ts } = parsed;
  if (rooms.length === 0) return;

  io.to(rooms).emit(event, { event, payload, ts });
  logger.debug({ event, rooms }, 'Relayed an event');
});

// --- Lifecycle --------------------------------------------------------------

httpServer.on('error', (error: NodeJS.ErrnoException) => {
  if (error.code === 'EADDRINUSE') {
    logger.error(
      `Port ${config.port} is already in use. Stop the other process or set REALTIME_PORT.`,
    );
    process.exit(1);
  }
  throw error;
});

httpServer.listen(config.port, () => {
  logger.info({ port: config.port }, 'Realtime gateway listening');
});

async function shutdown(signal: string): Promise<void> {
  logger.info({ signal }, 'Shutting down the realtime gateway');
  io.close();
  subscriber.disconnect();
  httpServer.close(() => process.exit(0));
  // Do not let a stuck connection hold the process open forever.
  setTimeout(() => process.exit(1), 10_000).unref();
}

process.on('SIGTERM', () => void shutdown('SIGTERM'));
process.on('SIGINT', () => void shutdown('SIGINT'));
