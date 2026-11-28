/**
 * Pre-roll shown when someone opens a public competition.
 *
 * The break is a placeholder for a real advertiser. To swap the creative,
 * edit `HOUSE_COMPETITION_AD` below:
 * - `durationSeconds` is how long the break stays up (it is not skippable).
 * - `media` turns the house layout into an image or a bundled video.
 *   Put the file in `frontend/src/assets/` and point `src` at `assets/...`.
 * - `href` is the click-through. It opens in a new tab and does not dismiss
 *   the break.
 *
 * To drive this from the API later, return the same `AdCreative` shape and
 * pass it in: `<fm-ad-break [creative]="ad" />`. The component already renders
 * image and video creatives; this function is the only source the page reads.
 */

export const AD_BREAK_SECONDS = 30;

export interface AdImageMedia {
  type: 'image';
  src: string;
  alt: string;
}

export interface AdVideoMedia {
  type: 'video';
  src: string;
  poster?: string;
}

export interface AdCreative {
  id: string;
  /** Seconds the break stays on screen. Not skippable. */
  durationSeconds: number;
  /** Small label, usually "Advertisement". */
  label: string;
  sponsor: string;
  title: string;
  message: string;
  highlights?: readonly string[];
  /** Click-through. Opens in a new tab and does not end the break. */
  href?: string;
  ctaLabel?: string;
  media?: AdImageMedia | AdVideoMedia;
}

/** Branded Fair Measure house ad. Replace this object to run a real creative. */
export const HOUSE_COMPETITION_AD: AdCreative = {
  id: 'fair-measure-house',
  durationSeconds: AD_BREAK_SECONDS,
  label: 'Advertisement',
  sponsor: 'Fair Measure',
  title: 'Every point, counted in the open.',
  message:
    'Custom scoring, live results, league tables and a feed. Build any competition you can describe — then run it.',
  highlights: ['Live results', 'League tables', 'Your own rules'],
  href: 'https://fair-measure.com/',
  ctaLabel: 'fair-measure.com',
};

/** The creative played on public competition pages. */
export function competitionAdCreative(): AdCreative {
  return HOUSE_COMPETITION_AD;
}

/** Usable duration. A missing or invalid value falls back to the house length. */
export function adDurationSeconds(creative: AdCreative): number {
  const value = Number(creative.durationSeconds);
  if (!Number.isFinite(value) || value < 1) return AD_BREAK_SECONDS;
  return Math.round(value);
}

/** `90` → `1:30`. The clock never goes negative. */
export function formatAdCountdown(seconds: number): string {
  const safe = Math.max(0, Math.ceil(seconds));
  const minutes = Math.floor(safe / 60);
  const rest = safe % 60;
  return `${minutes}:${rest.toString().padStart(2, '0')}`;
}

/**
 * One pre-roll per opening of a competition page.
 *
 * `start` marks the opening created with the route (ngOnInit). The first
 * `enter` (Ionic's ionViewWillEnter) is that same opening. Each later `enter`
 * is a new opening, so coming back plays the ad again. Refreshes call
 * `consider` again and do not restart a break that already started or finished.
 * Private competitions skip the break for that opening.
 */
export class AdBreakGate {
  private visit = 0;
  private decidedFor = -1;
  private ionicEntries = 0;
  private phase: 'waiting' | 'playing' | 'clear' = 'waiting';

  /** Id of the current opening. Changes when the visitor opens the page again. */
  get opening(): number {
    return this.visit;
  }

  get show(): boolean {
    return this.phase === 'playing';
  }

  start(): void {
    this.activate(1);
  }

  enter(): void {
    this.ionicEntries += 1;
    if (this.ionicEntries === 1) {
      if (this.visit === 0) this.activate(1);
      return;
    }
    this.activate(this.visit + 1);
  }

  leave(): void {
    if (this.phase === 'playing') this.phase = 'waiting';
  }

  /** `isPublic` is false for a private competition, which never plays the ad. */
  consider(isPublic: boolean): void {
    if (this.visit === 0 || this.decidedFor === this.visit) return;
    this.decidedFor = this.visit;
    this.phase = isPublic ? 'playing' : 'clear';
  }

  complete(): void {
    if (this.phase === 'playing') this.phase = 'clear';
  }

  private activate(visit: number): void {
    this.visit = visit;
    this.phase = 'waiting';
  }
}
