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
