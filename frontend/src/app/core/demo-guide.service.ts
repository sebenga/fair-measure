import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';

import { DemoVoiceService } from './demo-voice.service';
import type { CompetitionDetail } from './models';
import { FeatureKey, ReleasesService } from './releases.service';

export type CoachPose = 'wave' | 'point' | 'cheer' | 'think';

export interface GuideContext {
  competitionId: string;
  competitionName: string;
  liveFixture: string | null;
  liveCupFixture: string | null;
  penaltyFixture: string | null;
}

/** One click (or typed text) the coach performs on the real page while the user watches. */
export interface GuideAction {
  /** What the coach says while doing it. */
  say: string;
  /** CSS selector of the element to use. */
  target: string;
  /** Only elements whose text starts with this (case-insensitive). */
  text?: string;
  /** Which match to use when several qualify; negative counts from the end. */
  nth?: number;
  /** Type this into the field instead of tapping it. */
  type?: string;
  /** Point at the element without tapping it. */
  point?: boolean;
  /** Carry on with the next action when the element never shows up. */
  optional?: boolean;
}

export interface GuideCursor {
  x: number;
  y: number;
  pressing: boolean;
  say: string;
}

interface GuideStep {
  key: string;
  title: string;
  body: string;
  pose: CoachPose;
  /** Where the coach takes you for this step. */
  route: (ctx: GuideContext) => { path: string[]; query?: Record<string, string> };
  /** What to spotlight once the page is there. */
  target?: string;
  /** The clicks the coach demonstrates on this page. */
  actions?: GuideAction[];
  feature?: FeatureKey;
  needs?: 'liveFixture' | 'liveCupFixture' | 'penaltyFixture';
}

const competition = (ctx: GuideContext, tab?: string) => ({
  path: ['/tabs/competitions', ctx.competitionId],
  query: tab ? { tab } : undefined,
});

const fixture = (id: string | null, ctx: GuideContext, tab: string) => ({
  path: ['/tabs/competitions', ctx.competitionId, 'fixtures', id ?? ''],
  query: { tab },
});

const SHIRT = 'fm-match-day .pitch button.shirt.tappable:not(.off)';
const SHEET_BUTTON = 'ion-action-sheet button.action-sheet-button';
const ALERT_BUTTON = 'ion-alert button.alert-button';
const KICKER = '.shootout button.kicker:not([disabled])';

/** The platform manual, in the order a new organiser meets each feature. */
const STEPS: GuideStep[] = [
  {
    key: 'welcome',
    title: 'Welcome to your demo',
    body:
      "I'm Coach Kaya. This demo has 16 teams, a league and a cup, officials, line-ups, ratings and a fantasy " +
      'game, all filled in for you. It deletes itself after an hour. On each page I will do the clicks myself ' +
      'while you watch the hand. Tap Next to start.',
    pose: 'wave',
    route: (ctx) => competition(ctx, 'feed'),
    target: '.pick-banner',
  },
  {
    key: 'feed',
    title: 'Posting on the feed',
    body:
      'Every result, goal and rating lands here as a post. Watch: I write an update, post it, like it and leave a comment.',
    pose: 'point',
    route: (ctx) => competition(ctx, 'feed'),
    target: 'fm-post-composer',
    actions: [
      { say: 'The Feed tab is the league’s social wall.', target: 'ion-segment-button[value="feed"]', point: true },
      {
        say: 'Tap the box and write your update.',
        target: 'fm-post-composer ion-textarea',
        type: 'Matchday is here! Who lifts the demo cup?',
      },
      { say: 'Tap Post to share it with every member.', target: 'fm-post-composer ion-button', text: 'Post' },
      { say: 'Tap the heart to react to a post.', target: 'fm-post-card footer button.action', nth: 0 },
      { say: 'Tap the speech bubble to open the comments.', target: 'fm-post-card footer button.action', nth: 1 },
      { say: 'Write a comment…', target: 'fm-post-card .comments ion-input', type: 'Good luck to all 16 teams!' },
      { say: '…and send it.', target: 'fm-post-card .comments ion-button[type="submit"]' },
    ],
  },
  {
    key: 'fixtures',
    title: 'Fixtures',
    body:
      'The schedule the platform generated: match days, kick-off times, the venue and the referee. Live games wear a red badge. Tap any game to open it.',
    pose: 'point',
    route: (ctx) => competition(ctx, 'fixtures'),
    target: 'fm-competition-fixtures',
    actions: [
      { say: 'Live games show a red Live badge and the score as it happens.', target: 'fm-competition-fixtures .fixture.is-live', point: true, optional: true },
      { say: 'Upcoming games show the kick-off time and round.', target: 'fm-competition-fixtures .fixture:not(.is-live) .when', point: true, optional: true },
    ],
  },
  {
    key: 'standings',
    title: 'The table',
    body:
      'Standings update the moment a game ends: points, goal difference and the tie-breakers you chose when you set the league up.',
    pose: 'point',
    route: (ctx) => competition(ctx, 'standings'),
    target: 'fm-competition-standings',
    actions: [
      { say: 'The leader sits on top. Tap Next when you are ready.', target: 'fm-competition-standings tbody tr', point: true, optional: true },
    ],
  },
  {
    key: 'cup',
    title: 'The cup bracket',
    body:
      'All 16 teams are in the cup and every round is already scheduled, from the round of 16 to the final. Ties still waiting for their teams show TBD; Advance fills them once the round before is decided.',
    pose: 'point',
    route: (ctx) => competition(ctx, 'cup'),
    target: 'fm-competition-cup',
    actions: [
      { say: 'How far the cup has got, and when the next round is.', target: 'fm-competition-cup .meta', point: true, optional: true },
    ],
  },
  {
    key: 'fantasy',
    title: 'Picking a fantasy team',
    body:
      'Fans pick a 15-player squad and a captain from the real teams. Watch me pick a player, let Auto Pick fill the squad, name a captain and save.',
    pose: 'cheer',
    route: (ctx) => competition(ctx, 'fantasy'),
    target: 'fm-competition-fantasy',
    feature: 'fantasy',
    actions: [
      { say: 'Start from an empty squad.', target: 'fm-competition-fantasy .actions ion-button', text: 'Reset', optional: true },
      { say: 'Tap an empty shirt to fill that position.', target: 'fm-competition-fantasy .pitch button.empty' },
      { say: 'Pick a player from the market. Price and points are shown.', target: 'fm-competition-fantasy .sheet .market ion-button', text: 'Select' },
      { say: 'Auto Pick fills the rest of the squad inside the R100m budget.', target: 'fm-competition-fantasy .actions ion-button', text: 'Auto Pick' },
      { say: 'Tap a player on your pitch…', target: 'fm-competition-fantasy .pitch button.shirt', nth: -1 },
      { say: '…and make them captain. The captain scores double.', target: ALERT_BUTTON, text: 'Captain' },
      { say: 'Save the team. Points arrive as games are played.', target: 'fm-competition-fantasy .actions ion-button', text: 'Save team' },
    ],
  },
  {
    key: 'live',
    title: 'Running the match clock',
    body:
      'This league game is in play. The referee runs the clock: End half only works in the first half, then Start second half, and End game only in the second half. Watch me take it to the second half.',
    pose: 'point',
    route: (ctx) => fixture(ctx.liveFixture, ctx, 'live'),
    target: '.match-clock',
    needs: 'liveFixture',
    actions: [
      { say: 'The clock and the period come from the server.', target: '.match-clock .readout', point: true },
      { say: 'In the first half, tap End half.', target: '.match-clock button', text: 'End half', optional: true },
      { say: 'After the break, tap Start second half.', target: '.match-clock button', text: 'Start second half', optional: true },
      { say: 'End game only appears now, in the second half.', target: '.match-clock button', text: 'End game', point: true, optional: true },
    ],
  },
  {
    key: 'lineups',
    title: 'Recording a goal, a card and a sub',
    body:
      'Each team submits a team sheet before kick-off. During the game you record everything from the line-up: tap a player, choose what happened, then confirm. The clock stamps the minute.',
    pose: 'think',
    route: (ctx) => fixture(ctx.liveFixture, ctx, 'lineups'),
    target: 'fm-match-day',
    needs: 'liveFixture',
    actions: [
      { say: 'Tap the player who scored.', target: SHIRT, nth: 0 },
      { say: 'Choose Goal.', target: SHEET_BUTTON, text: 'Goal' },
      { say: 'Check the player and minute, then tap Record. The score and the feed update straight away.', target: ALERT_BUTTON, text: 'Record' },
      { say: 'For a booking, tap the player…', target: SHIRT, nth: 3 },
      { say: '…and choose Yellow card.', target: SHEET_BUTTON, text: 'Yellow card' },
      { say: 'Confirm the booking with Record.', target: ALERT_BUTTON, text: 'Record' },
      { say: 'For a substitution, tap the player coming on from the bench.', target: 'fm-match-day button.bench-shirt.tappable' },
      { say: 'Pick who comes off.', target: 'ion-alert button.alert-radio-button', nth: 0 },
      { say: 'Confirm with Substitute.', target: ALERT_BUTTON, text: 'Substitute' },
    ],
  },
  {
    key: 'raters',
    title: 'Rating players and logging stats',
    body:
      'Appointed raters score every player out of 10 and log stats such as shots, tackles and saves. The average becomes the match rating that feeds fantasy points and scouting.',
    pose: 'point',
    route: (ctx) => fixture(ctx.liveFixture, ctx, 'raters'),
    target: 'fm-match-raters',
    needs: 'liveFixture',
    actions: [
      { say: 'Tap a player to open their stats and rating.', target: 'fm-match-day .pitch button.shirt', nth: 0 },
      { say: 'Organisers can appoint themselves as a rater.', target: '.player-sheet .appoint-me', optional: true },
      { say: 'Tap + to log a stat for this player.', target: '.player-sheet button[aria-label^="Add one"]', optional: true },
      { say: 'Then give a rating out of 10.', target: '.player-sheet .marks button', text: '8', optional: true },
      { say: 'Tap Done. A tick marks who you have rated.', target: '.player-sheet button.close', text: 'Done' },
    ],
  },
  {
    key: 'cup-live',
    title: 'Ending a live cup tie',
    body:
      'This quarter-final is in the second half. In a knockout a draw cannot stand: if it is level at full time, extra time is played in two halves, and if it is still level, a penalty shootout decides it.',
    pose: 'think',
    route: (ctx) => fixture(ctx.liveCupFixture, ctx, 'live'),
    target: '.match-clock',
    needs: 'liveCupFixture',
    actions: [
      { say: 'One side leads, so this tie is decided in normal time.', target: '.scoreboard .line', point: true, optional: true },
      { say: 'Tap End game. The winner goes through to the semi-final.', target: '.match-clock button', text: 'End game', optional: true },
    ],
  },
  {
    key: 'penalties',
    title: 'Scoring a penalty shootout',
    body:
      'This tie is on penalties. Pick the kicker from the players still on the pitch, tap Scored or Missed, then confirm. Teams alternate, five each then sudden death, and the winner goes through automatically.',
    pose: 'cheer',
    route: (ctx) => fixture(ctx.penaltyFixture, ctx, 'live'),
    target: '.shootout',
    needs: 'penaltyFixture',
    actions: [
      { say: 'Pick the next kicker from the line-up.', target: KICKER, optional: true },
      { say: 'Tap Scored…', target: '.shootout button.scored', optional: true },
      { say: '…and confirm with Record.', target: ALERT_BUTTON, text: 'Record', optional: true },
      { say: 'Now the other team. Pick their kicker…', target: KICKER, optional: true },
      { say: '…saved! Tap Missed.', target: '.shootout button.missed', optional: true },
      { say: 'Confirm the miss.', target: ALERT_BUTTON, text: 'Record', optional: true },
      { say: 'One more kick can settle it.', target: KICKER, optional: true },
      { say: 'Scored…', target: '.shootout button.scored', optional: true },
      { say: '…confirm, and the shootout is decided.', target: ALERT_BUTTON, text: 'Record', optional: true },
      { say: 'The winner goes through.', target: '.shootout .verdict', point: true, optional: true },
    ],
  },
  {
    key: 'advance',
    title: 'Advancing the cup',
    body:
      'With every quarter-final decided, one tap draws the winners into the semi-finals that were already scheduled.',
    pose: 'cheer',
    route: (ctx) => competition(ctx, 'cup'),
    target: 'fm-competition-cup',
    needs: 'penaltyFixture',
    actions: [
      { say: 'Tap Advance to the next round.', target: 'fm-competition-cup ion-button', text: 'Advance', optional: true },
      { say: 'Confirm, and the waiting semi-final gets its teams.', target: ALERT_BUTTON, text: 'Advance', optional: true },
    ],
  },
  {
    key: 'setup',
    title: 'Setting up and inviting',
    body:
      'As the organiser you manage everything here: entrants and squads, officials and raters, game time, invites and who can see the competition.',
    pose: 'think',
    route: (ctx) => ({ path: ['/tabs/competitions', ctx.competitionId, 'setup'] }),
  },
  {
    key: 'scouting',
    title: 'Scouting',
    body:
      'Ratings, stats and test results build each player a scouting profile. Scouts search, compare and shortlist players, and leagues can name a squad of their best.',
    pose: 'point',
    route: () => ({ path: ['/tabs/scouting'] }),
    feature: 'scouting',
  },
  {
    key: 'discover',
    title: 'Discover',
    body:
      'Public competitions, partners and live games from across Fair Measure. Mark a competition "Show on the landing page" and visitors see it before they sign in.',
    pose: 'point',
    route: () => ({ path: ['/tabs/discover'] }),
    feature: 'discover',
  },
  {
    key: 'finish',
    title: "You're ready",
    body:
      'That is the whole platform. Create your own competition from My leagues with the + button: pick a sport, name it, set the format and dates, and invite your teams. You can replay this tour from the demo banner.',
    pose: 'cheer',
    route: (ctx) => competition(ctx, 'feed'),
    target: '.pick-banner',
  },
];

const STATE_KEY = 'fm.guide';
const SEEN_KEY = 'fm.guide.seen.';
const SPOT = 'fm-guide-target';

interface SavedState {
  context: GuideContext;
  index: number;
  open: boolean;
}

@Injectable({ providedIn: 'root' })
export class DemoGuideService {
  private readonly router = inject(Router);
  private readonly releases = inject(ReleasesService);
  readonly voice = inject(DemoVoiceService);

  readonly context = signal<GuideContext | null>(null);
  readonly index = signal(0);
  readonly open = signal(false);
  readonly minimized = signal(false);

  readonly steps = computed(() => {
    const ctx = this.context();
    if (!ctx) return [];
    return STEPS.filter(
      (step) =>
        (!step.feature || this.releases.isOpen(step.feature)) && (!step.needs || !!ctx[step.needs]),
    );
  });
  readonly step = computed(() => this.steps()[this.index()] ?? null);
  readonly isFirst = computed(() => this.index() === 0);
  readonly isLast = computed(() => this.index() >= this.steps().length - 1);

  /** True while the coach is clicking through the current step. */
  readonly driving = signal(false);
  readonly cursor = signal<GuideCursor | null>(null);
  /** Which of the current step's clicks the coach is on, e.g. 2 of 7. */
  readonly progress = signal<{ done: number; total: number } | null>(null);

  private spotTimer: ReturnType<typeof setTimeout> | null = null;
  private run = 0;
  private readonly calm =
    typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;

  constructor() {
    this.restore();
  }

  /** The tour runs on demo competitions only. */
  contextFor(competition: CompetitionDetail): GuideContext | null {
    const demo = competition.settings_json?.['demo_league'] as
      | { active?: boolean; live_fixture?: string; live_cup_fixture?: string; penalty_fixture?: string }
      | undefined;
    if (!demo?.active) return null;
    return {
      competitionId: competition.id,
      competitionName: competition.name,
      liveFixture: demo.live_fixture ?? null,
      liveCupFixture: demo.live_cup_fixture ?? null,
      penaltyFixture: demo.penalty_fixture ?? null,
    };
  }

  /** Opens the tour the first time someone lands on a demo competition. */
  offerFor(competition: CompetitionDetail): void {
    const ctx = this.contextFor(competition);
    if (!ctx) return;
    if (this.open()) {
      if (this.context()?.competitionId === ctx.competitionId) return;
      // A tour left open for another (possibly deleted) demo points at the wrong games.
      this.close();
    }
    if (localStorage.getItem(SEEN_KEY + ctx.competitionId)) return;
    localStorage.setItem(SEEN_KEY + ctx.competitionId, '1');
    this.start(ctx, false);
  }

  start(ctx: GuideContext, navigate = true): void {
    this.context.set(ctx);
    this.index.set(0);
    this.open.set(true);
    this.minimized.set(false);
    this.save();
    if (navigate) this.show();
    else {
      this.spotlight();
      void this.voice.say(this.step()?.body ?? '');
    }
  }

  next(): void {
    if (this.isLast()) {
      this.close();
      return;
    }
    this.index.update((value) => value + 1);
    this.save();
    this.show();
  }

  back(): void {
    if (this.isFirst()) return;
    this.index.update((value) => value - 1);
    this.save();
    this.show();
  }

  goTo(index: number): void {
    this.index.set(Math.max(0, Math.min(index, this.steps().length - 1)));
    this.save();
    this.show();
  }

  close(): void {
    this.halt();
    this.open.set(false);
    this.clearSpot();
    this.save();
  }

  toggleMinimized(): void {
    this.minimized.update((value) => !value);
  }

  /** Stops the coach mid-demonstration; whatever was clicked stays done. */
  halt(): void {
    this.run++;
    this.voice.hush();
    this.driving.set(false);
    this.cursor.set(null);
    this.progress.set(null);
  }

  /** Replays the current step's clicks on the page. */
  async demonstrate(): Promise<void> {
    const actions = this.step()?.actions;
    if (!actions?.length) return;
    this.halt();
    const run = this.run;
    const live = () => run === this.run && this.open();
    this.driving.set(true);
    this.progress.set({ done: 0, total: actions.length });
    this.cursor.set({ x: 72, y: window.innerHeight - 140, pressing: false, say: 'Watch the hand.' });
    try {
      for (const [index, action] of actions.entries()) {
        if (!live()) return;
        this.progress.set({ done: index + 1, total: actions.length });
        const element = await this.find(action, live);
        if (!live()) return;
        if (!element) {
          if (action.optional) continue;
          this.cursor.update((cursor) => cursor && { ...cursor, say: 'That part is already done in this demo.' });
          await pause(1800);
          break;
        }
        element.scrollIntoView({ behavior: this.calm ? 'auto' : 'smooth', block: 'center' });
        await pause(450);
        if (!live()) return;
        const box = element.getBoundingClientRect();
        this.cursor.set({
          x: box.left + Math.min(box.width / 2, 60),
          y: box.top + box.height / 2,
          pressing: false,
          say: action.say,
        });
        await Promise.all([
          pause(this.voice.on() ? 750 : Math.min(2600, 900 + action.say.length * 22)),
          this.voice.say(action.say),
        ]);
        if (!live()) return;
        if (action.type !== undefined) {
          await this.typeInto(element, action.type, live);
        } else if (!action.point) {
          this.cursor.update((cursor) => cursor && { ...cursor, pressing: true });
          await pause(180);
          if (!live()) return;
          element.click();
          await pause(260);
          this.cursor.update((cursor) => cursor && { ...cursor, pressing: false });
        }
        await pause(action.point ? 700 : 1100);
      }
    } finally {
      if (run === this.run) {
        this.driving.set(false);
        this.cursor.set(null);
        this.progress.set(null);
      }
    }
  }

  /** Waits for a usable element: on screen, enabled and with the right text. */
  private async find(action: GuideAction, live: () => boolean): Promise<HTMLElement | null> {
    const started = Date.now();
    const wanted = action.text?.toLowerCase();
    while (live() && Date.now() - started < 6000) {
      const matches = Array.from(document.querySelectorAll<HTMLElement>(action.target)).filter(
        (node) =>
          !node.closest('fm-demo-guide') &&
          node.getClientRects().length > 0 &&
          !isDisabled(node) &&
          (!wanted || (node.textContent ?? '').trim().toLowerCase().startsWith(wanted)),
      );
      const nth = action.nth ?? 0;
      const found = matches.at(nth < 0 ? nth : Math.min(nth, matches.length - 1));
      if (found) return found;
      await pause(200);
    }
    return null;
  }

  /** Types into an input or textarea (including Ionic's wrappers) one letter at a time. */
  private async typeInto(element: HTMLElement, text: string, live: () => boolean): Promise<void> {
    const field =
      element instanceof HTMLInputElement || element instanceof HTMLTextAreaElement
        ? element
        : element.querySelector<HTMLInputElement | HTMLTextAreaElement>('textarea, input');
    if (!field) return;
    field.focus();
    const step = this.calm ? text.length : 1;
    for (let shown = step; shown <= text.length; shown += step) {
      if (!live()) return;
      field.value = text.slice(0, shown);
      field.dispatchEvent(new Event('input', { bubbles: true }));
      await pause(45);
    }
    field.dispatchEvent(new Event('change', { bubbles: true }));
    field.blur();
  }

  private show(): void {
    const ctx = this.context();
    const step = this.step();
    if (!ctx || !step) return;
    const { path, query } = step.route(ctx);
    this.halt();
    this.clearSpot();
    const run = this.run;
    void this.router.navigate(path, { queryParams: query ?? {} }).then(async () => {
      this.spotlight();
      const told = this.voice.say(step.body);
      if (!step.actions?.length) return;
      // Let the coach finish explaining before the hand starts moving.
      await Promise.all([pause(2200), told]);
      if (run === this.run && this.step() === step) void this.demonstrate();
    });
  }

  /** Waits for the page to draw the feature, then rings it and scrolls it into view. */
  private spotlight(): void {
    const selector = this.step()?.target;
    this.clearSpot();
    if (!selector) return;
    const started = Date.now();
    const look = () => {
      const found = Array.from(document.querySelectorAll<HTMLElement>(selector)).find(
        (node) => node.offsetParent !== null,
      );
      if (found) {
        found.classList.add(SPOT);
        found.scrollIntoView({ behavior: 'smooth', block: 'center' });
        return;
      }
      if (Date.now() - started < 6000) this.spotTimer = setTimeout(look, 250);
    };
    this.spotTimer = setTimeout(look, 350);
  }

  private clearSpot(): void {
    if (this.spotTimer !== null) clearTimeout(this.spotTimer);
    this.spotTimer = null;
    document.querySelectorAll(`.${SPOT}`).forEach((node) => node.classList.remove(SPOT));
  }

  private save(): void {
    const ctx = this.context();
    if (!ctx) return;
    const state: SavedState = { context: ctx, index: this.index(), open: this.open() };
    sessionStorage.setItem(STATE_KEY, JSON.stringify(state));
  }

  private restore(): void {
    try {
      const raw = sessionStorage.getItem(STATE_KEY);
      if (!raw) return;
      const state = JSON.parse(raw) as SavedState;
      if (!state?.context?.competitionId) return;
      this.context.set(state.context);
      this.index.set(state.index || 0);
      this.open.set(state.open === true);
      if (state.open) this.spotlight();
    } catch {
      sessionStorage.removeItem(STATE_KEY);
    }
  }
}

function pause(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isDisabled(node: HTMLElement): boolean {
  return (
    (node as HTMLElement & { disabled?: boolean }).disabled === true ||
    node.getAttribute('aria-disabled') === 'true'
  );
}
