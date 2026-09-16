/**
 * End-to-end check of the Django -> Redis -> Socket.io path.
 *
 * Signs in over REST, opens a socket, joins the competition and fixture rooms,
 * then records a score event through the API and waits for the broadcast to
 * come back. Exits non-zero if nothing arrives.
 *
 *   node scripts/smoke.mjs
 */

import { io } from 'socket.io-client';

const API = process.env.API_BASE_URL ?? 'http://localhost:8000/api/v1';
const REALTIME = process.env.REALTIME_URL ?? 'http://localhost:4000';
const EMAIL = process.env.SMOKE_EMAIL ?? 'owner@example.com';
const PASSWORD = process.env.SMOKE_PASSWORD ?? 'fairmeasure';

const log = (...args) => console.log('•', ...args);

async function api(path, { token, method = 'GET', body } = {}) {
  const response = await fetch(`${API}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });

  if (!response.ok) {
    throw new Error(`${method} ${path} -> ${response.status} ${await response.text()}`);
  }
  return response.status === 204 ? null : response.json();
}

async function main() {
  const { access } = await api('/auth/login', {
    method: 'POST',
    body: { email: EMAIL, password: PASSWORD },
  });
  log('signed in');

  const competitions = await api('/competitions?mine=true', { token: access });
  const competition = competitions.results[0];
  if (!competition) throw new Error('No competitions. Run: manage.py seed_demo');
  log(`competition: ${competition.name}`);

  const detail = await api(`/competitions/${competition.id}`, { token: access });
  const category = detail.scoring_categories.find((entry) => entry.affects_score);
  if (!category) throw new Error('Competition has no scoring category that affects the score.');

  const fixtures = await api(`/competitions/${competition.id}/fixtures?status=live`, {
    token: access,
  });
  const fixture = fixtures.results[0];
  if (!fixture) throw new Error('No live fixture to score.');
  log(`fixture: ${fixture.sides.map((side) => side.participant.short_name).join(' v ')}`);

  const socket = io(REALTIME, { transports: ['websocket'], auth: { token: access } });

  const received = new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Timed out waiting for score.recorded')), 12_000);
    socket.on('score.recorded', (message) => {
      clearTimeout(timer);
      resolve(message);
    });
    socket.on('connect_error', (error) => {
      clearTimeout(timer);
      reject(new Error(`Socket rejected: ${error.message}`));
    });
  });

  await new Promise((resolve, reject) => {
    socket.on('connect', resolve);
    socket.on('connect_error', reject);
  });
  log(`socket connected: ${socket.id}`);

  const joined = await new Promise((resolve) =>
    socket.emit('subscribe', [`competition:${competition.id}`, `fixture:${fixture.id}`], resolve),
  );
  log(`rooms granted: ${JSON.stringify(joined)}`);

  const side = fixture.sides[0];
  await api(`/fixtures/${fixture.id}/events`, {
    token: access,
    method: 'POST',
    body: { side: side.id, scoring_category: category.id, quantity: '1', minute: 44 },
  });
  log(`recorded a ${category.name} for ${side.participant.short_name} over REST`);

  const message = await received;
  log(`broadcast received: ${message.event}`);
  console.log(JSON.stringify(message, null, 2));

  socket.close();
  console.log('\nPASS — REST write reached the socket.');
}

main().catch((error) => {
  console.error(`\nFAIL — ${error.message}`);
  process.exit(1);
});
