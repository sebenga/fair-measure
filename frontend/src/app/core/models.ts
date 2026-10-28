/** Mirrors the DRF serializers. Regenerate from /api/schema/ if they change. */

export type Role = 'owner' | 'admin' | 'scorer' | 'member';

export type CompetitionFormat =
  | 'league'
  | 'knockout'
  | 'league_knockout'
  | 'group_knockout'
  | 'ladder'
  | 'freeform';

export type CompetitionStatus = 'draft' | 'active' | 'completed' | 'archived';

export type FixtureStatus =
  | 'scheduled'
  | 'live'
  | 'completed'
  | 'postponed'
  | 'cancelled'
  | 'forfeit';

export type Outcome = 'pending' | 'win' | 'draw' | 'loss';

export type ReactionKind = 'like' | 'love' | 'laugh' | 'wow' | 'clap';

export interface AppNotification {
  id: string;
  competition: string | null;
  kind: string;
  title: string;
  body: string;
  data: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface CursorPaginated<T> {
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  avatar_url: string;
  bio: string;
  given_name: string;
  family_name: string;
  date_of_birth: string | null;
  id_number: string;
  phone: string;
  city: string;
  country: string;
  headline: string;
  website: string;
  experience: string;
  education: string;
  skills: string;
  languages: string;
  email_verified: boolean;
  date_joined: string;
}

export interface UserSummary {
  id: string;
  display_name: string;
  avatar_url: string;
  headline?: string;
  city?: string;
  bio?: string;
}

export interface ProfileSummary {
  id: string;
  display_name: string;
  email: string;
  avatar_url: string;
  bio: string;
  headline: string;
}

export interface Membership {
  id: string;
  user: UserSummary;
  member_email: string;
  role: Role;
  created_at: string;
}

export interface AuthResponse {
  access: string;
  refresh: string;
  user: User;
}

export interface ScoringCategory {
  id: string;
  name: string;
  code: string;
  description: string;
  points: string;
  affects_score: boolean;
  display_order: number;
  icon: string;
}

export interface Rule {
  id: string;
  name: string;
  description: string;
  display_order: number;
}

export interface PointsPolicy {
  id: string;
  win_points: string;
  draw_points: string;
  loss_points: string;
  bonus_win_margin: number | null;
  bonus_win_points: string;
  bonus_loss_margin: number | null;
  bonus_loss_points: string;
  forfeit_points: string;
  tiebreakers: string[];
  allow_draws: boolean;
}

/** Extra table points on a VS competition, stored in settings_json.table_bonus. */
export interface TableBonus {
  enabled: boolean;
  scoring_threshold?: number | null;
  scoring_points?: number;
  scoring_code?: string;
  scoring_codes?: string[];
  win_margin?: number | null;
  win_points?: number;
  loss_margin?: number | null;
  loss_points?: number;
}

export interface Stage {
  id: string;
  name: string;
  kind: 'league' | 'group' | 'knockout';
  display_order: number;
  starts_on: string | null;
  ends_on: string | null;
  advances_count: number;
}

export type ParticipantKind = 'individual' | 'team';

export interface RosterMember {
  id: string;
  name: string;
  number: number | null;
  position: string;
  handicap?: string | null;
  user: string | null;
  user_display_name?: string;
  is_active: boolean;
}

export interface TeamPick {
  id: string;
  participant: string;
  team_name: string;
  competition: string;
  competition_name: string;
  user: string;
  user_display_name: string;
  user_email: string;
  status: 'pending' | 'accepted' | 'declined';
  created_at: string;
  responded_at: string | null;
}

export interface DraftBoard {
  squad_size: number;
  on_the_clock: { id: string; name: string } | null;
  teams: Array<{ id: string; name: string; accepted: number; pending: number; total: number }>;
  picks?: Array<{
    user: string;
    user_display_name: string;
    participant: string;
    team_name: string;
  }>;
  complete: boolean;
  pick?: TeamPick;
  undrafted?: boolean;
}

export interface Participant {
  id: string;
  kind: ParticipantKind;
  name: string;
  short_name: string;
  description: string;
  logo_url: string;
  managed_by: string | null;
  seed: number | null;
  is_active: boolean;
  metadata: Record<string, unknown>;
  stage_ids?: string[];
  roster: RosterMember[];
  pending_count?: number;
  pending_user_ids?: string[];
}

export interface ParticipantRef {
  id: string;
  name: string;
  short_name: string;
  logo_url: string;
}

export interface Competition {
  id: string;
  name: string;
  slug: string;
  description: string;
  sport: string;
  logo_url: string;
  banner_url: string;
  format: CompetitionFormat;
  status: CompetitionStatus;
  is_private: boolean;
  /** When set, visitors see this public competition on the marketing landing page. */
  show_on_landing?: boolean;
  /** Sport competitions only: scouts can follow it and it can name its own squad. */
  open_to_scouts?: boolean;
  starts_on: string | null;
  ends_on: string | null;
  owner: UserSummary;
  participant_count: number;
  my_role: Role | null;
  scoring_basis?: 'results' | 'criteria';
  settings_json?: Record<string, unknown>;
  created_at: string;
}

export interface CompetitionDetail extends Competition {
  /** Members, rostered players and team managers may post, comment and react. */
  can_post?: boolean;
  /** Whether the sport is one scouting covers, so it may be opened to scouts. */
  scouting_eligible?: boolean;
  timezone: string;
  match_weekdays: number[];
  settings_json: Record<string, unknown>;
  scoring_categories: ScoringCategory[];
  rules: Rule[];
  points_policy: PointsPolicy;
  stages: Stage[];
  participants: Participant[];
  updated_at: string;
  /** Every remaining fixture is finished, so a new season or knockout can be scheduled. */
  season_finished?: boolean;
}

export interface FixtureSide {
  id: string;
  participant: ParticipantRef;
  position: number;
  is_home: boolean;
  score: string;
  /** Goals on the board before play (handicap start), where the preset uses one. */
  head_start?: string | null;
  outcome: Outcome;
  forfeited: boolean;
}

export interface FixtureAward {
  key: string;
  label: string;
  kind: 'player' | 'horse';
  description: string;
  winner: {
    player_id: string | null;
    player_name: string;
    team: string;
    horse_id: string | null;
    name: string;
  } | null;
}

export interface FixtureAwards {
  awards: FixtureAward[];
  can_award: boolean;
}

export interface MatchRaters {
  minimum: number;
  raters: Array<{ id: string; user_id: string; name: string; email: string; rated: number }>;
  enough: boolean;
  can_manage: boolean;
  is_rater: boolean;
  can_rate: boolean;
  can_record_stats: boolean;
  status: string;
  teams: Array<{
    side_id: string;
    team: string;
    players: Array<{
      player_id: string;
      user_id: string | null;
      name: string;
      number: number | null;
      role: string;
      position: string;
      captain: boolean;
      sent_off?: boolean;
      rating_locked?: boolean;
      average: string | null;
      count: number;
      mine: string | null;
      stats: Array<{
        code: string;
        label: string;
        count: string;
        kind?: string;
        recorded?: boolean;
        editable?: boolean;
      }>;
    }>;
  }>;
  candidates: Array<{ id: string; name: string; email: string }>;
}

export interface FormationSlot {
  index: number;
  row: number;
  column: number;
  columns: number;
  label: string;
}

export interface MatchPlayer {
  player_id: string;
  user_id: string | null;
  name: string;
  number: number | null;
}

export interface LineupPlayer extends MatchPlayer {
  slot: number | null;
  position: string;
  on_field: boolean;
  subbed_off: boolean;
  sent_off?: boolean;
  minutes?: number | null;
  rating?: string | null;
  stats?: Array<{ code: string; label: string; count: string }>;
}

export interface TeamSheetSide {
  side_id: string;
  participant_id: string;
  name: string;
  can_edit: boolean;
  squad: Array<MatchPlayer & { position: string }>;
  lineup: {
    formation: string;
    slots: FormationSlot[];
    captain_id: string | null;
    starters: LineupPlayer[];
    bench: LineupPlayer[];
    updated_at: string;
  } | null;
  on_field: string[];
  available_subs: string[];
  substitutions_used: number;
  substitutions_left: number | null;
}

export interface SubstitutionRecord {
  id: string;
  side_id: string;
  team: string;
  player_off: MatchPlayer;
  player_on: MatchPlayer;
  minute: number | null;
  reason: string;
  note: string;
  created_at: string;
}

export interface MatchDay {
  enabled: boolean;
  config?: {
    starters: number | null;
    min_personnel?: number;
    bench_max: number | null;
    max_substitutions: number | null;
    rolling_substitutions: boolean;
    keeper: string;
    lines: string[];
    formations: string[];
  };
  formations?: Array<{ key: string; slots: FormationSlot[] }>;
  status?: string;
  sides?: TeamSheetSide[];
  substitutions?: SubstitutionRecord[];
  can_substitute?: boolean;
  reasons?: Array<{ key: string; label: string }>;
}

export interface MatchReportEvent {
  minute: number | null;
  team: string;
  player: string;
  label: string;
  quantity: string;
  points: string;
  kind?: string;
}

export interface MatchReportData {
  fixture: {
    id: string;
    label: string;
    competition: string;
    status: string;
    scheduled_at: string | null;
    started_at: string | null;
    completed_at: string | null;
    location: string;
    duration_minutes: number | null;
  };
  sides: Array<{
    side_id: string;
    name: string;
    score: string;
    outcome: string;
    forfeited: boolean;
    lineup: TeamSheetSide['lineup'];
  }>;
  goals: MatchReportEvent[];
  cards: MatchReportEvent[];
  other_events: MatchReportEvent[];
  substitutions: SubstitutionRecord[];
  awards: Array<{ label: string; winner: { name: string; team: string } }>;
  referees: string[];
  report: {
    summary: string;
    attendance: number | null;
    conditions: string;
    incidents: string;
    injuries: string;
    written_by: string;
    submitted_at: string | null;
  } | null;
  finished: boolean;
  can_edit: boolean;
}

export interface PlayerStatsTable {
  columns: Array<{ key: string; label: string }>;
  rows: Array<{
    player_id: string;
    user_id: string | null;
    name: string;
    team: string;
    values: Record<string, string>;
  }>;
}

export interface ScoreEvent {
  id: string;
  side: string;
  participant_id: string;
  scoring_category: string;
  scoring_category_name: string;
  quantity: string;
  points: string;
  minute: number | null;
  period: string;
  unit_index?: number | null;
  player: string | null;
  player_user_id: string | null;
  player_name: string;
  note: string;
  occurred_at: string | null;
  created_at: string;
}

export interface Fixture {
  id: string;
  competition: string;
  stage: string | null;
  round_number: number | null;
  label: string;
  scheduled_at: string | null;
  duration_minutes: number | null;
  overtime_minutes: number | null;
  location: string;
  status: FixtureStatus;
  sides: FixtureSide[];
  highlights?: FixtureHighlight[];
  ratings?: MatchRating[];
  started_at: string | null;
  completed_at: string | null;
}

export interface FixtureHighlight {
  id: string;
  side: string;
  minute: number | null;
  /** goal-like scores are "score"; cards are their colour. */
  kind: 'score' | 'own_goal' | 'yellow' | 'red' | 'green' | string;
  label: string;
  player_name: string;
  created_at: string;
}

export interface MatchRating {
  id: string;
  player: string;
  player_name: string;
  player_user_id: string | null;
  rating: string;
}

export interface FixtureDetail extends Fixture {
  notes: string;
  events: ScoreEvent[];
  ratings: MatchRating[];
  referees: Array<{ id: string; display_name: string; email: string }>;
  raters_count?: number;
  kickoff_problems: string[];
  created_at: string;
}

export interface ScrabbleTile {
  letter: string;
  blank: boolean;
  letter_mult: number;
  new: boolean;
  id?: string;
}

export interface ScrabbleWord {
  text: string;
  tiles: ScrabbleTile[];
  word_mult: number;
  breakdown?: string;
  total?: number;
}

export interface ScrabbleMove {
  id: string;
  side: string;
  player: string;
  turn_no: number;
  type: 'play' | 'pass' | 'exchange' | 'challenge_lost';
  words: ScrabbleWord[];
  total: number;
  bingo: boolean;
  breakdown: string[];
  created_at: string;
}

export interface ScrabbleBoard {
  tile_set: { key: string; label: string; blanks: number; values: Record<string, number> };
  can_score: boolean;
  moves: ScrabbleMove[];
  endgame: { racks: Array<{ side: string; letters: string; value: number }>; went_out: string | null } | null;
}

export interface PlayerLeagueProfile {
  profile: {
    id: string;
    display_name: string;
    avatar_url: string;
    bio: string;
    headline: string;
    city: string;
    country: string;
    experience: string;
    education: string;
    skills: string;
    languages: string;
  };
  team: { id: string; name: string } | null;
  totals: Array<{ category: string; code?: string; count: string; points: string; affects_score?: boolean }>;
  timeline: Array<{
    id: string;
    fixture_id: string;
    fixture_label: string;
    minute: number | null;
    period: string;
    category: string;
    quantity: string;
    points: string;
    team: string;
    occurred_at: string | null;
    created_at: string;
  }>;
  ratings: Array<{
    fixture_id: string;
    fixture_label: string;
    rating: string;
    scheduled_at: string | null;
  }>;
}

export interface StandingRow {
  position: number;
  participant: ParticipantRef;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  score_for: string;
  score_against: string;
  score_difference: string;
  points: string;
  bonus_points: string;
  form: Array<'W' | 'D' | 'L'>;
  /** Series tables: second and third places, and results with a status. */
  detail?: { seconds?: number; thirds?: number; statuses?: number };
  computed_at: string;
}

export interface StandingsResponse {
  competition_id: string;
  stage_id: string | null;
  scoring_basis?: 'results' | 'criteria';
  breakdown?: Record<string, CriterionBreakdown[]>;
  rows: StandingRow[];
}

export interface CriterionBreakdown {
  id: string;
  name: string;
  description: string;
  points_each: string;
  total: string;
  entries: Array<{
    id: string;
    fixture_id: string;
    quantity: string;
    awarded: string;
    note: string;
    created_at: string;
  }>;
}

export interface ScoreAssistEntry {
  id: string;
  fixture_id: string;
  participant_id: string;
  participant_name: string;
  criterion: string;
  description: string;
  quantity: string;
  awarded: string;
  note: string;
  created_at: string;
}

export interface MediaAsset {
  id: string;
  kind: 'image' | 'video';
  status: 'pending' | 'processing' | 'ready' | 'failed';
  caption: string;
  url: string;
  playback_url: string;
  thumbnail_url: string;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  content_type: string;
  size_bytes: number | null;
  created_at: string;
  ready_at: string | null;
}

export interface UploadTarget {
  media_asset: MediaAsset;
  upload_url: string;
  method: string;
  headers?: Record<string, string>;
  storage_key?: string;
  expires_in?: number;
}

export interface PostMedia {
  id: string;
  media_asset: MediaAsset;
  display_order: number;
}

export type PostKind = 'profile' | 'competition' | 'live';

export interface Post {
  id: string;
  kind?: PostKind;
  competition: string;
  competition_name?: string;
  competition_logo_url?: string;
  competition_sport?: string;
  author: UserSummary;
  body: string;
  fixture: string | null;
  fixture_label?: string | null;
  scoreline?: string | null;
  participant: string | null;
  is_pinned: boolean;
  is_announcement: boolean;
  media: PostMedia[];
  comment_count: number;
  reaction_count: number;
  my_reaction: ReactionKind | null;
  created_at: string;
  updated_at: string;
}

export interface Comment {
  id: string;
  author: UserSummary;
  parent: string | null;
  body: string;
  media: PostMedia[];
  reply_count: number;
  reaction_count: number;
  my_reaction: ReactionKind | null;
  created_at: string;
  updated_at: string;
}

export interface ReactionResult {
  my_reaction: ReactionKind | null;
  reaction_count: number;
}

export type PresetKind = 'sport' | 'work' | 'home' | 'custom';

export type TableMode = 'points' | 'head_to_head';

export interface Preset {
  key: string;
  label: string;
  icon?: string;
  description?: string;
  sport: string;
  kind?: PresetKind;
  /** Create-page section, for example ball or olympic. Empty for Custom, KPIs and cleaning. */
  group?: string;
  group_label?: string;
  format: CompetitionFormat;
  formats_allowed?: string[];
  contest_type?: 'head_to_head' | 'accumulation';
  accumulation_ranking?: 'highest_first' | 'lowest_first' | null;
  participant_type?: 'team' | 'individual' | 'pair';
  table_mode?: TableMode;
  scoring_locked?: boolean;
  locked?: boolean;
  scoring_categories: Array<{
    name: string;
    code: string;
    points: string;
    affects_score: boolean;
    description?: string;
  }>;
  rules: Array<{ name: string; description: string }>;
  result_type?: string | null;
  /** Presets that let the owner pick how many periods a match has. */
  unit_count_options?: { unit: string; options: number[]; default?: number };
  team_sheet?: TeamSheet;
  /** Separate category of the same sport, for example women. */
  category?: string;
  /** Setup groups variants of one sport under a single card. */
  family?: string;
  variant?: string;
  family_label?: string;
  variant_label?: string;
  league_points?: Record<string, number>;
  table_bonus?: TableBonus;
  tile_set?: string;
}

export interface TeamSheet {
  starters?: number;
  min_on_field?: number;
  min_squad?: number;
  bench_max?: number;
  max_substitutions?: number;
  rolling_substitutions?: boolean;
}

export function teamSheetOf(competition: {
  settings_json?: Record<string, unknown>;
}): TeamSheet | null {
  const raw = competition.settings_json?.['team_sheet'];
  if (!raw || typeof raw !== 'object') return null;
  return raw as TeamSheet;
}

/** Fewest players a team needs for this competition. Picked players must accept; drafted players count at once. */
export function squadSizeOf(competition: {
  settings_json?: Record<string, unknown>;
}): number {
  const sheet = teamSheetOf(competition);
  const minimum = Number(sheet?.min_squad);
  if (minimum > 0) return minimum;
  const starters = Number(sheet?.starters);
  if (starters >= 11) return 14;
  if (starters > 0) return starters;
  return 14;
}

/** Ranked by accumulated score, not head-to-head match results. */
export function isPointsTable(competition: {
  settings_json?: Record<string, unknown>;
  points_policy?: Pick<PointsPolicy, 'win_points' | 'draw_points' | 'loss_points'>;
}): boolean {
  const basis = competition.settings_json?.['scoring_basis'];
  if (basis === 'criteria') return true;
  if (basis === 'results') return false;
  const mode = competition.settings_json?.['table_mode'];
  if (mode === 'points') return true;
  if (mode === 'head_to_head') return false;
  const policy = competition.points_policy;
  if (!policy) return false;
  return (
    Number(policy.win_points) === 0 &&
    Number(policy.draw_points) === 0 &&
    Number(policy.loss_points) === 0
  );
}

/** Fantasy picks a squad from club rosters. Only team-sport leagues have those. */
export function showsFantasy(competition: {
  settings_json?: Record<string, unknown>;
  scoring_basis?: 'results' | 'criteria';
  points_policy?: Pick<PointsPolicy, 'win_points' | 'draw_points' | 'loss_points'>;
}): boolean {
  const type = String(competition.settings_json?.['participant_type'] ?? 'team');
  if (type !== 'team') return false;
  if (competition.scoring_basis === 'criteria') return false;
  return !isPointsTable(competition);
}

export function tableBonusOf(competition: {
  settings_json?: Record<string, unknown>;
}): TableBonus | null {
  const raw = competition.settings_json?.['table_bonus'];
  if (!raw || typeof raw !== 'object') return null;
  return raw as TableBonus;
}

/** VS table awards extra points from scoring or from the winning/losing margin. */
export function tableBonusEnabled(competition: {
  settings_json?: Record<string, unknown>;
  points_policy?: Pick<PointsPolicy, 'bonus_win_margin' | 'bonus_loss_margin'>;
}): boolean {
  const bonus = tableBonusOf(competition);
  if (bonus && 'enabled' in bonus) return !!bonus.enabled;
  const policy = competition.points_policy;
  return policy?.bonus_win_margin != null || policy?.bonus_loss_margin != null;
}

export function isScoringLocked(competition: {
  status?: string;
  settings_json?: Record<string, unknown>;
}): boolean {
  const settings = competition.settings_json ?? {};
  if (settings['lock_when_started'] === true) {
    return !!competition.status && competition.status !== 'draft';
  }
  return settings['scoring_locked'] === true;
}

export function isPointsPreset(preset: Pick<Preset, 'kind' | 'table_mode' | 'key'> | null): boolean {
  if (!preset) return true; // blank custom path
  if (preset.table_mode === 'points') return true;
  if (preset.table_mode === 'head_to_head') return false;
  const kind = preset.kind ?? (preset.key === 'kpi' ? 'work' : preset.key === 'cleaning' ? 'home' : preset.key === 'custom' ? 'custom' : 'sport');
  return kind === 'work' || kind === 'home' || kind === 'custom';
}

export type FantasySlot = 'GKP' | 'DEF' | 'MID' | 'FWD';

export interface FantasyRules {
  budget: string;
  squad_size: number;
  starters: number;
  max_per_club: number;
  slots: Array<{ key: FantasySlot; label: string; count: number }>;
  formations: string[];
  scoring: Array<{ label: string; points: string }>;
}

export interface FantasyPlayer {
  id: string;
  name: string;
  number: number | null;
  position: string;
  slot: FantasySlot;
  slots?: FantasySlot[];
  team_id: string;
  team_name: string;
  team_short: string;
  user_id: string | null;
  price: string;
  points: string;
  event_points: string;
  pick_id?: string;
  is_starter?: boolean;
  is_captain?: boolean;
  is_vice?: boolean;
  bench_order?: number;
}

export interface FantasyTeam {
  id: string;
  name: string;
  manager: UserSummary;
  complete: boolean;
  budget_used: string;
  budget_remaining: string;
  points: string;
  event_points: string;
  formation: string;
  picks: FantasyPlayer[];
  rank?: number;
  managers?: number;
}

export interface FantasyStandingRow {
  rank: number;
  team_id: string;
  name: string;
  manager: UserSummary;
  complete: boolean;
  points: string;
  event_points: string;
}

export interface FantasyOverview {
  rules: FantasyRules;
  player_count: number;
  team: FantasyTeam | null;
  standings: FantasyStandingRow[];
  valid_formations: string[];
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    detail?: unknown;
  };
}

export interface NextSeasonRequest {
  kind: 'season' | 'knockout';
  starts_on: string;
  kickoff?: string;
  weekdays?: number[];
  minutes_between_fixtures?: number;
  double_round?: boolean;
  location?: string;
  advance?: number;
}

export interface NextSeasonResponse {
  stage: Stage;
  fixtures: Fixture[];
  competition: CompetitionDetail;
}

export type MarketingAudience = 'corporate' | 'government' | 'general';
export type MarketingSlot = 'feature' | 'banner' | 'logo';

export interface MarketingPlacement {
  id: string;
  audience: MarketingAudience;
  slot: MarketingSlot;
  name: string;
  tagline: string;
  body: string;
  cta_label: string;
  cta_url: string;
  logo_url: string;
  display_order: number;
}

export interface MarketingEnquiry {
  audience: 'corporate' | 'government';
  organisation: string;
  contact_name: string;
  email: string;
  phone: string;
  message: string;
}

export interface GenerateFixturesRequest {
  method: 'round_robin' | 'knockout' | 'league_knockout';
  participant_ids?: string[];
  stage_id?: string | null;
  starts_on: string;
  weekdays?: number[];
  kickoff?: string;
  minutes_between_fixtures?: number;
  double_round?: boolean;
  location?: string;
  replace_existing?: boolean;
  cup_every_league_rounds?: number;
  cups?: string[];
}
