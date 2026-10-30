import type { MarketingPlacement } from './models';

export const FALLBACK_CORPORATE: MarketingPlacement[] = [
  {
    id: 'workplace',
    audience: 'corporate',
    slot: 'feature',
    name: 'Workplace leagues',
    tagline: 'Run the office cup, the factory ladder, the regional KPI table.',
    body: 'Branded competitions for staff, partners and customers — your scoring, your feed, your results.',
    cta_label: 'Talk to partnerships',
    cta_url: '',
    logo_url: '',
    display_order: 0,
  },
  {
    id: 'broadcast',
    audience: 'corporate',
    slot: 'feature',
    name: 'Brand and broadcast',
    tagline: 'Kit, naming rights and live boards on public competitions.',
    body: 'Buy a commercial slot on the landing page, a league feed or a match day.',
    cta_label: 'Book a slot',
    cta_url: '',
    logo_url: '',
    display_order: 1,
  },
];

export const FALLBACK_GOVERNMENT: MarketingPlacement[] = [
  {
    id: 'schools',
    audience: 'government',
    slot: 'feature',
    name: 'Schools and municipalities',
    tagline: 'One platform for district sport, school cups and civic games.',
    body: 'Residents follow tables and fixtures without an account. Officials still run scoring.',
    cta_label: 'Plan a programme',
    cta_url: '',
    logo_url: '',
    display_order: 0,
  },
  {
    id: 'national',
    audience: 'government',
    slot: 'feature',
    name: 'National and provincial programmes',
    tagline: 'Talent pathways, school-to-club and public results.',
    body: 'A named programme on the landing page, plus a route for federations and departments.',
    cta_label: 'Contact public sector',
    cta_url: '',
    logo_url: '',
    display_order: 1,
  },
];

const SPONSOR_MEDIA = 'assets/landing';

export const FALLBACK_LOGOS: MarketingPlacement[] = [
  {
    id: 'pitchside',
    audience: 'general',
    slot: 'logo',
    name: 'Pitchside',
    tagline: 'Kit',
    body: 'Match kit, training wear and merchandise in your league’s colours.',
    cta_label: '',
    cta_url: '',
    logo_url: '',
    image_url: `${SPONSOR_MEDIA}/corp-merch.jpg`,
    display_order: 0,
  },
  {
    id: 'harbour',
    audience: 'general',
    slot: 'logo',
    name: 'Harbour Radio',
    tagline: 'Broadcast',
    body: 'Live commentary and results from community grounds every weekend.',
    cta_label: '',
    cta_url: '',
    logo_url: '',
    image_url: `${SPONSOR_MEDIA}/gov-programme.jpg`,
    display_order: 1,
  },
  {
    id: 'millwater',
    audience: 'general',
    slot: 'logo',
    name: 'Millwater',
    tagline: 'Hydration',
    body: 'Cold water on the touchline at every match day and fun run.',
    cta_label: '',
    cta_url: '',
    logo_url: '',
    image_url: `${SPONSOR_MEDIA}/hero.jpg`,
    display_order: 2,
  },
  {
    id: 'northstand',
    audience: 'general',
    slot: 'logo',
    name: 'Northstand',
    tagline: 'Community',
    body: 'Backing the clubs, schools and supporters who fill the stands.',
    cta_label: '',
    cta_url: '',
    logo_url: '',
    image_url: `${SPONSOR_MEDIA}/moment-fans.jpg`,
    display_order: 3,
  },
  {
    id: 'ledger',
    audience: 'general',
    slot: 'logo',
    name: 'Ledger & Co',
    tagline: 'Workplace',
    body: 'Sponsor of the after-work five-a-side and the quarterly KPI cup.',
    cta_label: '',
    cta_url: '',
    logo_url: '',
    image_url: `${SPONSOR_MEDIA}/moment-office.jpg`,
    display_order: 4,
  },
];

export const FALLBACK_CAMPAIGN: MarketingPlacement = {
  id: 'grow',
  audience: 'general',
  slot: 'banner',
  name: 'Put your league in front of the public',
  tagline: 'Current competitions, workplace cups and civic programmes share this page.',
  body: 'Create a public league or book a corporate / government slot — the same placements used on the landing page.',
  cta_label: 'Create a public league',
  cta_url: '',
  logo_url: '',
  display_order: 0,
};

const PHOTOS = {
  kpi: `${SPONSOR_MEDIA}/corp-kpi.jpg`,
  merch: `${SPONSOR_MEDIA}/corp-merch.jpg`,
  office: `${SPONSOR_MEDIA}/moment-office.jpg`,
  cleanup: `${SPONSOR_MEDIA}/gov-cleanup.jpg`,
  programme: `${SPONSOR_MEDIA}/gov-programme.jpg`,
  township: `${SPONSOR_MEDIA}/hero.jpg`,
  fans: `${SPONSOR_MEDIA}/moment-fans.jpg`,
  touchline: `${SPONSOR_MEDIA}/moment-touchline.jpg`,
  rugby: `${SPONSOR_MEDIA}/moment-rugby.jpg`,
};

/** A photo for a marketing card: the placement's own image, else one that fits its subject. */
export function placementImage(placement: MarketingPlacement, index = 0): string {
  if (placement.image_url) return placement.image_url;
  if (placement.slot === 'banner') return PHOTOS.township;
  // Match the name before the tagline, so "national programmes" beats a passing "school-to-club".
  for (const text of [placement.name.toLowerCase(), placement.tagline.toLowerCase()]) {
    if (/national|provinc|federation/.test(text)) return PHOTOS.programme;
    if (/kpi|workplace|office|staff/.test(text)) return PHOTOS.kpi;
    if (/kit|brand|broadcast|merch|naming/.test(text)) return PHOTOS.merch;
    if (/school|municipal|clean|civic/.test(text)) return PHOTOS.cleanup;
  }
  const pools: Record<string, string[]> = {
    corporate: [PHOTOS.kpi, PHOTOS.merch, PHOTOS.office],
    government: [PHOTOS.cleanup, PHOTOS.programme],
  };
  const pool = pools[placement.audience] ?? [PHOTOS.township, PHOTOS.fans, PHOTOS.rugby];
  return pool[index % pool.length];
}

/** A photo for a competition card: its own banner, else a match-day picture. */
export function competitionImage(competition: { banner_url?: string | null }, index = 0): string {
  if (competition.banner_url) return competition.banner_url;
  const pool = [PHOTOS.touchline, PHOTOS.rugby, PHOTOS.township, PHOTOS.fans];
  return pool[index % pool.length];
}
