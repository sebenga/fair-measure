/** Talent scouting types. Sport-specific values come from the catalogue, never from code. */

export type ScoutingRoleKey = 'player' | 'guardian' | 'scout' | 'scout_admin' | 'coach';
export type Visibility = 'private' | 'scouts' | 'public';
export type ProfileAccess = 'owner' | 'guardian' | 'scout' | 'public';

export interface CatalogItem {
  key: string;
  label: string;
}

export interface CatalogSport extends CatalogItem {
  positions: CatalogItem[];
  attribute_count?: number;
  physical_test_count?: number;
  match_stat_count?: number;
}

export type RatingAreaKey = 'physical' | 'technical' | 'tactical' | 'mental' | 'context';

export interface RatingArea {
  key: RatingAreaKey;
  label: string;
  description: string;
  /** What 2, 5, 8 and 10 look like on the 1 to 10 scale. */
  anchors: Record<'2' | '5' | '8' | '10', string>;
}

export interface CatalogAttribute {
  key: string;
  label: string;
  area: RatingAreaKey;
  description: string;
  scale: { min: number; max: number };
  applies_to_positions?: string[];
  universal?: boolean;
}

export interface PhysicalTest {
  key: string;
  label: string;
  unit: string;
  better: 'lower' | 'higher';
  description: string;
}

export interface MatchStat {
  key: string;
  label: string;
  per: 'match' | '90min' | 'game';
  source?: string;
  source_label?: string;
  formula?: string;
  unit?: string;
  better?: 'higher' | 'lower' | null;
}

export interface SportCatalogue {
  key: string;
  label: string;
  positions: CatalogItem[];
  scale: { min: number; max: number };
  areas: Array<RatingArea & { attributes: CatalogAttribute[] }>;
  physical_tests: PhysicalTest[];
  match_stats: MatchStat[];
  presets: string[];
}

export interface MeasurementSpec extends CatalogItem {
  kind: 'number' | 'choice';
  unit?: string;
  choices?: string[];
}

export interface ScoutingCatalog {
  sports: CatalogSport[];
  age_groups: Array<CatalogItem & { under: number | null }>;
  age_of_consent: number;
  gender_categories: CatalogItem[];
  regions: CatalogItem[];
  measurements: MeasurementSpec[];
  consent_sections: Array<CatalogItem & { required: boolean }>;
  /** Catalogue sport key → the competition sport names that count as it. */
  competition_sports?: Record<string, string[]>;
  areas?: RatingArea[];
  universal_attributes?: CatalogAttribute[];
  competition_levels?: Array<CatalogItem & { rank: number }>;
  shortlist_statuses?: CatalogItem[];
  rating_recommendations?: CatalogItem[];
}

export interface ScoutingRole {
  id: string;
  role: ScoutingRoleKey;
  organisation: string | null;
  organisation_name: string | null;
  team: string | null;
  team_name: string | null;
  user: string;
  user_name: string;
  created_at: string;
}

export interface Organisation {
  id: string;
  name: string;
  kind: 'club' | 'academy' | 'school' | 'agency';
  region: string;
  logo_url: string;
  my_role: 'scout' | 'scout_admin' | null;
  scout_count: number;
}

export interface ScoutingMe {
  roles: ScoutingRole[];
  role_keys: ScoutingRoleKey[];
  organisations: Organisation[];
  profile_id: string | null;
  guarding: number;
  pending_guardian_requests: number;
}

export interface PlayerSport {
  id: string;
  sport: string;
  sport_label: string;
  primary_position: string;
  primary_position_label: string;
  secondary_positions: string[];
  is_primary: boolean;
}

export interface Measurement {
  id: string;
  kind: string;
  label: string;
  value: string | null;
  text_value: string;
  unit: string;
  measured_on: string;
  source: 'self' | 'coach' | 'official';
  verified: boolean;
  verified_by_name: string;
  created_at: string;
}

export interface Injury {
  id: string;
  description: string;
  injured_on: string | null;
  recovered_on: string | null;
  shared_with_scouts: boolean;
}

export interface HighlightVideo {
  id: string;
  title: string;
  url: string;
  media_asset: string | null;
  playback_url: string;
  status: string;
  created_at: string;
}

export interface GuardianLink {
  id: string;
  profile_id: string;
  player_name: string;
  player_age_group: string | null;
  invited_email: string;
  relationship: string;
  status: 'pending' | 'active' | 'revoked';
  guardian_name: string;
  created_at: string;
}

export interface ConsentRecord {
  id: string;
  given_by_name: string;
  given_as: 'guardian' | 'player';
  action: 'granted' | 'revoked';
  visibility: string;
  sections: string[];
  note: string;
  created_at: string;
}

export interface ProfileTeam {
  id: string;
  name: string;
  competition_id: string;
  competition: string;
  sport: string;
  from_roster: boolean;
}

export interface ConsentStatus {
  needed: boolean;
  granted: boolean;
  visibility: Visibility | null;
  sections: string[];
  missing_date_of_birth?: boolean;
}

/** The owner's and guardian's full view. */
export interface PlayerProfile {
  id: string;
  first_name: string;
  last_name: string;
  photo_url: string;
  date_of_birth: string | null;
  age: number | null;
  age_group: CatalogItem | null;
  is_minor: boolean;
  gender_category: string;
  nationality: string;
  region: string;
  school_or_club: string;
  teams: ProfileTeam[];
  bio: string;
  availability: 'available' | 'limited' | 'unavailable' | 'injured';
  availability_note: string;
  visibility: Visibility;
  effective_visibility: Visibility;
  consent_status: ConsentStatus;
  sports: PlayerSport[];
  measurements: Measurement[];
  measurement_history: Measurement[];
  injuries: Injury[];
  videos: HighlightVideo[];
  guardians: GuardianLink[];
  access: ProfileAccess;
  updated_at: string;
}

/** What scouts and the public receive. No contact details, ever. */
export interface ScoutProfileView {
  id: string;
  first_name: string;
  last_name: string;
  photo_url: string;
  age?: number | null;
  age_group: CatalogItem | null;
  gender_category: string;
  nationality: string;
  region: string;
  school_or_club: string;
  teams: ProfileTeam[];
  bio: string;
  access: ProfileAccess;
  contact: string;
  sports: PlayerSport[];
  measurements: Measurement[];
  videos: HighlightVideo[];
  injuries: Injury[];
  availability: { status: string; note: string } | null;
  updated_at: string;
  /** Set when a player previews their own profile as a scout sees it. */
  preview?: boolean;
  effective_visibility?: Visibility;
}

export interface ReportRating {
  fixture: string;
  date: string;
  rating: string;
}

export interface ReportStat {
  key: string;
  label: string;
  count: string;
  points: string;
  first: string;
  last: string;
}

export interface ReportSelection {
  squad: string;
  status: 'draft' | 'published';
  group: string;
  position: string;
  score: string | null;
  summary: string[];
  published_at: string | null;
}

export interface ReportLeague {
  competition_id: string;
  competition: string;
  sport: string;
  team: string;
  position: string;
  number: number | null;
  games: number;
  record: { won: number; drawn: number; lost: number };
  avg_rating: string | null;
  ratings: ReportRating[];
  stats: ReportStat[];
  selection: ReportSelection | null;
}

export interface ScoutingReport {
  kind: 'player_scouting_report';
  generated_at: string;
  access: ProfileAccess;
  shaped_as: ProfileAccess;
  profile: ScoutProfileView;
  headline: string[];
  leagues: ReportLeague[];
  coverage: Array<{ key: string; label: string; available: boolean; note?: string }>;
}

export type EvidenceConfidence = 'strong' | 'some' | 'thin' | 'none';

export interface SquadPick {
  id: string;
  user_id: string;
  name: string;
  team: string;
  position: string;
  group_key: string;
  score: string | null;
  confidence: EvidenceConfidence;
  basis: string[];
  summary: string[];
  locked: boolean;
  profile_id: string | null;
  photo_url: string;
}

export interface SquadGroup {
  key: string;
  label: string;
  min: number;
  max: number | null;
  picks: SquadPick[];
}

export interface LeagueSquad {
  id: string;
  competition_id: string;
  competition: string;
  sport: string;
  name: string;
  size: number;
  status: 'draft' | 'published';
  notes: string;
  filled: number;
  generated_at: string | null;
  published_at: string | null;
  groups: SquadGroup[];
  warnings: string[];
  excluded: string[];
  can_edit: boolean;
}

export interface LeagueSquadResponse {
  squad: LeagueSquad | null;
  can_edit?: boolean;
  competition?: string;
}

export interface LeagueSummary {
  id: string;
  name: string;
  sport: string;
  sport_key: string | null;
  teams: number;
  open_to_scouts: boolean;
  scouts: number;
  i_scout_it: boolean;
  can_select: boolean;
  can_manage: boolean;
  squad_status: 'draft' | 'published' | null;
  squad_filled: number;
  squad_size: number;
}

export interface LeagueCandidate {
  user_id: string;
  name: string;
  team: string;
  position: string;
  group_key: string | null;
  score: string | null;
  available: boolean;
  availability: string;
  in_squad: boolean;
  excluded: boolean;
  profile_id: string | null;
  photo_url: string;
  basis: string[];
  components: Record<string, string>;
  ratings: number;
  avg_rating: string | null;
  points: string;
  games: number;
  record: { won: number; drawn: number; lost: number };
  confidence: EvidenceConfidence;
  summary: string[];
}

export interface LeagueCandidates {
  counts: { rostered: number; no_profile: number; private: number; eligible: number };
  groups: Array<{ key: string; label: string }>;
  weights: Record<string, number>;
  results: LeagueCandidate[];
}

export interface ProfileCard {
  id: string;
  name: string;
  photo_url: string;
  age_group: string | null;
  region: string;
  school_or_club: string;
  teams: ProfileTeam[];
  sport: PlayerSport | null;
}

export interface LeagueScout {
  id: string;
  user_id: string;
  name: string;
  organisation: string | null;
  added_at: string;
}

export interface LeagueScouts {
  scouts: LeagueScout[];
  can_manage: boolean;
}

export interface TeamMembership {
  id: string;
  name: string;
  competition_id: string;
  competition: string;
  sport: string;
  sport_key: string | null;
  sport_label: string;
  position: string;
  number: number | null;
  active: boolean;
  open_to_scouts: boolean;
  joined_at: string;
}

export interface TeamMemberships {
  teams: TeamMembership[];
  pending_invites: number;
}

export type IdentityDocumentKind = 'passport' | 'national_id';

export interface IdentityDocument {
  id: string;
  kind: IdentityDocumentKind;
  kind_label: string;
  original_name: string;
  content_type: string;
  size_bytes: number;
  uploaded_at: string;
}

// --- Phase 3: stats, tests and percentiles ----------------------------------------------

export interface PlayerStat {
  key: string;
  label: string;
  per: 'match' | '90min' | 'game';
  unit?: string;
  formula?: string;
  source?: string;
  better: 'higher' | 'lower' | null;
  value: number | null;
  per_match: number | null;
  percentile: number | null;
  sample: number;
}

export interface TestResultRow {
  id: string;
  value: number;
  unit: string;
  tested_on: string;
  venue: string;
  source: 'self' | 'coach' | 'official';
  verified: boolean;
  label: 'Verified' | 'Self-reported';
}

export interface TestSummary extends PhysicalTest {
  personal_best: TestResultRow;
  latest: TestResultRow;
  history: TestResultRow[];
  trend: 'improving' | 'declining' | 'steady' | null;
  percentile: number | null;
  sample: number;
}

export interface PlayerStats {
  profile_id: string;
  name: string;
  sports: CatalogItem[];
  sport: string;
  seasons: number[];
  season: number;
  competitions: Array<{ id: string; name: string }>;
  competition: string | null;
  line: { matches: number; minutes: number; computed_at: string | null };
  stats: PlayerStat[];
  history: Array<{ season: number; matches: number; values: Record<string, number | null> }>;
  tests: TestSummary[];
  percentile_minimum: number;
  cohort: number;
  can_record_tests: boolean;
}

export interface RecordablePlayers {
  players: Array<{ profile_id: string; name: string; team: string; sports: CatalogItem[] }>;
  self: { profile_id: string; sports: CatalogItem[] } | null;
}

// --- Phase 4: scout ratings ------------------------------------------------------------

export type RatingMode = 'quick' | 'full';
export type Confidence = 'low' | 'medium' | 'high';
export type Watched = 'live' | 'video';
export type Recommendation = 'monitor' | 'trial' | 'sign' | 'not_for_us';

export interface RatingClip {
  video?: string | null;
  title?: string;
  url?: string;
  at_seconds: number;
  note?: string;
}

/** What the app saves on the phone and sends when there is signal. */
export interface RatingDraft {
  client_id: string;
  profile: string;
  organisation?: string;
  sport: string;
  position?: string;
  fixture?: string;
  mode: RatingMode;
  watched: Watched;
  confidence: Confidence;
  area_scores: Partial<Record<RatingAreaKey, number>>;
  attribute_scores: Record<string, number>;
  current_ability?: number | null;
  potential?: number | null;
  recommendation?: Recommendation | '';
  notes?: string;
  clips?: RatingClip[];
  observed_at: string;
}

export interface QueuedRating {
  draft: RatingDraft;
  player_name: string;
  status: 'pending' | 'rejected';
  error?: string;
  queued_at: string;
}

export interface RatingContext {
  profile: { id: string; name: string; photo_url: string; code: string };
  sports: Array<{ key: string; label: string; position: string }>;
  fixtures: Array<{ id: string; label: string; competition: string; scheduled_at: string | null; status: string }>;
  videos: Array<{ id: string; title: string }>;
  organisations: Array<{ id: string; name: string }>;
  confidence: Array<{ key: Confidence; label: string; description: string; weight: number }>;
  watched: Array<{ key: Watched; label: string }>;
  recommendations: Array<{ key: Recommendation; label: string }>;
}

export interface ScoutRatingRow {
  id: string;
  client_id: string;
  scout: { id: string; name: string };
  sport: string;
  position: string;
  fixture: { id: string; label: string; competition: string } | null;
  mode: RatingMode;
  watched: Watched;
  confidence: Confidence;
  area_scores: Record<string, number>;
  attribute_scores: Record<string, number>;
  areas: Record<string, number>;
  current_ability: number | null;
  potential: number | null;
  recommendation: Recommendation | '';
  notes: string;
  clips: RatingClip[];
  observed_at: string;
  synced_at: string;
}

export interface RatingSummary {
  organisation: { id: string; name: string };
  scouts: number;
  ratings: number;
  areas: Array<{ key: RatingAreaKey; label: string; average: number | null; scouts: number }>;
  current_ability: number | null;
  potential: number | null;
  recommendations: Array<{ key: Recommendation; label: string; count: number }>;
  progress: Array<{ observed_at: string; scout: string; average: number | null; current_ability: number | null; potential: number | null }>;
}

export interface ProfileRatings {
  summary: RatingSummary;
  ratings: ScoutRatingRow[];
  organisations: Array<{ id: string; name: string }>;
}

// --- Phase 5: search, compare, shortlists and contact ------------------------------------

export type FilterOp = 'lt' | 'lte' | 'gt' | 'gte' | 'eq';

export interface SearchFilters {
  q?: string;
  sport?: string;
  position?: string;
  age_group?: string;
  gender?: string;
  region?: string;
  level?: string;
  has_video?: boolean;
  tests?: Array<{ key: string; op: FilterOp; value: number }>;
  stats?: Array<{ key: string; op: FilterOp; value: number }>;
  percentiles?: Array<{ key: string; min: number }>;
  areas?: Array<{ key: RatingAreaKey; min: number }>;
  potential_min?: number;
  current_min?: number;
  recommendation?: Recommendation;
}

export interface SearchResult extends ProfileCard {
  facts: {
    level?: string;
    has_video?: boolean;
    tests?: Record<string, number>;
    stats?: Record<string, number>;
    percentiles?: Record<string, number>;
    areas?: Record<string, number>;
    potential?: number | null;
    recommendation?: string | null;
  };
}

export interface SavedSearch {
  id: string;
  name: string;
  filters: SearchFilters;
  alerts: boolean;
  matches: number;
  last_run_at: string | null;
  created_at: string;
}

export interface ComparePlayer extends ProfileCard {
  areas: Partial<Record<RatingAreaKey, number | null>>;
  current_ability: number | null;
  potential: number | null;
  season: number | null;
  matches: number;
  stats: Record<string, { value: number | null; percentile: number | null }>;
  tests: Record<string, { best: number; verified: boolean; percentile: number | null }>;
}

export interface CompareResponse {
  sport: string;
  areas: Array<{ key: RatingAreaKey; label: string }>;
  stats: Array<{ key: string; label: string; unit: string; better: 'higher' | 'lower' | null }>;
  tests: Array<{ key: string; label: string; unit: string; better: 'higher' | 'lower' }>;
  players: ComparePlayer[];
}

export type ShortlistStatus = 'watching' | 'contacted' | 'trial_booked' | 'signed' | 'rejected';

export interface PersonRef {
  id: string;
  name: string;
}

export interface ShortlistEntry {
  id: string;
  profile: ProfileCard;
  status: ShortlistStatus;
  assigned_to: PersonRef | null;
  added_by: PersonRef | null;
  created_at: string;
  comments: Array<{ id: string; author: PersonRef | null; body: string; created_at: string }>;
  contact: { status: string; created_at: string } | null;
}

export interface Shortlist {
  id: string;
  name: string;
  description: string;
  organisation: { id: string; name: string };
  count: number;
  statuses: Record<ShortlistStatus, number>;
  created_at: string;
  has_profile?: boolean;
  entries?: ShortlistEntry[];
  scouts?: PersonRef[];
}

export interface ShortlistLogRow {
  id: string;
  action: string;
  action_label: string;
  player: string;
  actor: PersonRef | null;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  created_at: string;
}

export interface ContactRequestRow {
  id: string;
  player: { id: string; name: string };
  organisation: { id: string; name: string };
  requested_by: PersonRef | null;
  message: string;
  to_guardian: boolean;
  status: 'pending' | 'accepted' | 'declined' | 'withdrawn';
  status_label: string;
  response: string;
  responded_at: string | null;
  created_at: string;
  can_respond: boolean;
}
