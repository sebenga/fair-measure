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

export const FALLBACK_LOGOS: MarketingPlacement[] = [
  { id: 'pitchside', audience: 'general', slot: 'logo', name: 'Pitchside', tagline: 'Kit', body: '', cta_label: '', cta_url: '', logo_url: '', display_order: 0 },
  { id: 'harbour', audience: 'general', slot: 'logo', name: 'Harbour Radio', tagline: 'Broadcast', body: '', cta_label: '', cta_url: '', logo_url: '', display_order: 1 },
  { id: 'millwater', audience: 'general', slot: 'logo', name: 'Millwater', tagline: 'Hydration', body: '', cta_label: '', cta_url: '', logo_url: '', display_order: 2 },
  { id: 'northstand', audience: 'general', slot: 'logo', name: 'Northstand', tagline: 'Community', body: '', cta_label: '', cta_url: '', logo_url: '', display_order: 3 },
  { id: 'ledger', audience: 'general', slot: 'logo', name: 'Ledger & Co', tagline: 'Workplace', body: '', cta_label: '', cta_url: '', logo_url: '', display_order: 4 },
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
