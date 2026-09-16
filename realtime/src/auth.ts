import jwt from 'jsonwebtoken';

import { config } from './config.js';
import type { AuthenticatedUser } from './types.js';

interface DjangoAccessToken extends jwt.JwtPayload {
  token_type?: string;
  user_id?: string;
  email?: string;
  display_name?: string;
}

/**
 * Verify an access token minted by Django's SimpleJWT.
 *
 * Both services share `JWT_SIGNING_KEY`, so no network call is needed and a
 * socket handshake stays fast. Refresh tokens are rejected explicitly: they
 * live much longer than access tokens and must never authorise a connection.
 */
export function verifyAccessToken(token: string): AuthenticatedUser {
  const claims = jwt.verify(token, config.jwtSecret, {
    algorithms: [config.jwtAlgorithm],
  }) as DjangoAccessToken;

  if (claims.token_type && claims.token_type !== 'access') {
    throw new Error(`Expected an access token, received a ${claims.token_type} token.`);
  }
  if (!claims.user_id) {
    throw new Error('Token is missing the user_id claim.');
  }

  return {
    id: String(claims.user_id),
    email: claims.email,
    displayName: claims.display_name,
  };
}

/** Pull the token from Socket.io's auth payload, a query param, or a header. */
export function extractToken(handshake: {
  auth?: Record<string, unknown>;
  query?: Record<string, unknown>;
  headers?: Record<string, unknown>;
}): string | null {
  const fromAuth = handshake.auth?.['token'];
  if (typeof fromAuth === 'string' && fromAuth) return fromAuth;

  const fromQuery = handshake.query?.['token'];
  if (typeof fromQuery === 'string' && fromQuery) return fromQuery;

  const header = handshake.headers?.['authorization'];
  if (typeof header === 'string' && header.startsWith('Bearer ')) {
    return header.slice('Bearer '.length);
  }

  return null;
}
