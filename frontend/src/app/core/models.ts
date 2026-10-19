/** Mirrors the DRF serializers. Regenerate from /api/schema/ if they change. */

export type Role = 'owner' | 'admin' | 'scorer' | 'member';

export type CompetitionFormat = 'league' | 'knockout' | 'group_knockout' | 'ladder' | 'freeform';

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
  user: string | null;
  user_display_name?: string;
  is_active: boolean;
}

export interface TeamPick {
  id: string;
  participant: string;
  team_name: string;
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
  complete: boolean;
  pick?: TeamPick;
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
  timezone: string;
  match_weekdays: number[];
  settings_json: Record<string, unknown>;
  scoring_categories: ScoringCategory[];
  rules: Rule[];
  points_policy: PointsPolicy;
  stages: Stage[];
  participants: Participant[];
  updated_at: string;
}

export interface FixtureSide {
  id: string;
  participant: ParticipantRef;
  position: number;
  is_home: boolean;
  score: string;
  outcome: Outcome;
  forfeited: boolean;
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
  kickoff_problems: string[];
  created_at: string;
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
    quantity: string;
    awarded: string;
    note: string;
    created_at: string;
  }>;
}

export interface ScoreAssistEntry {
  id: string;
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

export interface Post {
  id: string;
  competition: string;
  author: UserSummary;
  body: string;
  fixture: string | null;
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

export interface ApiError {
  error: {
    code: string;
    message: string;
    detail?: unknown;
  };
}

export interface GenerateFixturesRequest {
  method: 'round_robin' | 'knockout';
  participant_ids?: string[];
  stage_id?: string | null;
  starts_on: string;
  weekdays?: number[];
  kickoff?: string;
  minutes_between_fixtures?: number;
  double_round?: boolean;
  location?: string;
  replace_existing?: boolean;
}
