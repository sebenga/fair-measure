/**
 * What running a competition costs and earns on Fair Measure, for organisers.
 *
 * These are the proposed commercial terms. The rand amounts are starting points
 * that have not been tested, so the page presents them as proposed and nothing
 * here drives billing. Change the figures in this file only.
 */

export const COMMERCIAL = {
  lastUpdated: '18 November 2026',
  /** The share of a sponsorship Fair Measure keeps, live from the first day. */
  sponsorshipCommission: 15,
  /**
   * Paystack test amounts for visibility upgrades (ZAR cents).
   * Server settings can override; keep these in sync as the SPA fallback copy.
   */
  payments: {
    gateway: 'paystack' as const,
    currency: 'ZAR',
    privateCents: 9900,
    landingCents: 14900,
  },
};

export function randAmount(cents: number): string {
  return `R${(cents / 100).toFixed(cents % 100 === 0 ? 0 : 2)}`;
}

export interface CommercialPoint {
  title: string;
  text: string;
}

/** The three things an organiser should know before creating a competition. */
export const COMMERCIAL_KEY_POINTS: CommercialPoint[] = [
  {
    title: 'Free until you earn',
    text: 'A competition stays free to create and run until it starts making revenue.',
  },
  {
    title: 'Sponsorship carries a commission now',
    text: 'The marketing marketplace is live, and Fair Measure keeps 15% of every sponsorship arranged through it.',
  },
  {
    title: 'Notice before paid plans',
    text: 'You get 2–3 months’ notice before platform plans change, and a season already running finishes on its old terms.',
  },
];

export interface CommercialPlan {
  name: string;
  price: string;
}

export const COMMERCIAL_FREE_TIER = {
  name: 'Free',
  price: 'R0',
  detail: 'One small competition for everyone: up to 8 teams and 40 players. Profiles stay free forever.',
};

export const COMMERCIAL_PLANS: CommercialPlan[] = [
  { name: 'Tournament pass', price: 'R199, R349 or R499' },
  { name: 'Community', price: 'R79 a month' },
  { name: 'Club', price: 'R249 a month' },
  { name: 'School', price: 'R3,500 a year, or R875 a term' },
  { name: 'Province', price: 'From R25,000 a year' },
];

export interface CommercialSplit {
  source: string;
  organiser: string;
  fairMeasure: string;
}

export const COMMERCIAL_SPLITS: CommercialSplit[] = [
  { source: 'Sponsorships', organiser: '85%', fairMeasure: '15%' },
  { source: 'Entry fees and tickets', organiser: 'The rest', fairMeasure: '5% + R3' },
  { source: 'Ad income on paid organisers’ pages', organiser: '50%', fairMeasure: '50%' },
  { source: 'Paid streams', organiser: '80%', fairMeasure: '20%' },
];

export interface CommercialLine {
  label: string;
  amount: string;
  total?: boolean;
}

/** A school whose sponsors cover its plan: R11,500 less 15% commission, less the yearly plan. */
export const COMMERCIAL_EXAMPLE: CommercialLine[] = [
  { label: 'Sponsors pay', amount: 'R11,500' },
  { label: 'Fair Measure commission (15%)', amount: '− R1,725' },
  { label: 'School plan for the year', amount: '− R3,500' },
  { label: 'The school keeps', amount: 'R6,275', total: true },
];

export const COMMERCIAL_MOVING: CommercialPoint[] = [
  { title: 'Notice', text: '2–3 months before paid plans begin.' },
  { title: 'Running seasons', text: 'A season already under way stays on the old terms until it ends.' },
  { title: 'Founding members', text: '50% off for the first 12 paid months.' },
];

export const COMMERCIAL_PAYOUTS: CommercialPoint[] = [
  { title: 'How often', text: 'Every 14 days.' },
  { title: 'Minimum payout', text: 'R250.' },
  { title: 'Before the first payout', text: 'A FICA identity check on the organiser.' },
];
