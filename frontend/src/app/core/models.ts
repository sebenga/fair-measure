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
  email_verified: boolean;
  date_joined: string;
}

export interface UserSummary {
  id: string;
  display_name: string;
  avatar_url: string;
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

export interface RosterMember {
  id: string;
  name: string;
  number: number | null;
  position: string;
  user: string | null;
  is_active: boolean;
}

export interface Participant {
  id: string;
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
  player: string | null;
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
  location: string;
  status: FixtureStatus;
  sides: FixtureSide[];
  started_at: string | null;
  completed_at: string | null;
}

export interface FixtureDetail extends Fixture {
  notes: string;
  events: ScoreEvent[];
  created_at: string;
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
  sport: string;
  kind?: PresetKind;
  format: CompetitionFormat;
  table_mode?: TableMode;
  scoring_locked?: boolean;
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
  settings_json?: Record<string, unknown>;
}): boolean {
  return competition.settings_json?.['scoring_locked'] === true;
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
