/** Performance results: one event, many entrants, ranked from preset data. */

export type ResultType =
  | 'finishing_order'
  | 'faults_then_time'
  | 'penalty_total_lowest'
  | 'judged_percentage'
  | 'timed_with_vet_gates'
  | 'points_per_run';

export interface ResultStatus {
  code: string;
  label: string;
}

export interface PenaltyItem {
  key: string;
  label: string;
  faults?: number | string;
  eliminate_at?: number;
  per_obstacle?: boolean;
  scale?: Array<number | string>;
}

export interface ResultConfig {
  statuses?: ResultStatus[];
  record_fields?: string[];
  rounds?: Array<{ key: string; label?: string; decides?: string }>;
  penalties?: PenaltyItem[];
  time_allowed?: Record<string, number | string>;
  time_limit?: Record<string, number | string>;
  phases?: Array<{
    key: string;
    label: string;
    input?: 'percentage' | 'sheet';
    penalties?: PenaltyItem[];
  }>;
  inspections?: Array<{ key: string; label: string }>;
  sheet?: Array<{ key: string; label: string; coefficient?: number; collective?: boolean }>;
  judges?: string[];
  max_mark?: number;
  mark_step?: number | string;
  errors?: { deduct_points?: number[]; eliminate_at?: number };
  loops?: Array<{ key: string; label: string; distance_km?: number | string }>;
  heart_rate_max?: number;
  outcomes?: Array<{ key: string; label: string; points: number | string }>;
  time_limit_seconds?: number | string;
  runs?: number;
  [key: string]: unknown;
}

export type EntryData = Record<string, any>;

export interface ResultEntry {
  side_id: string;
  participant_id: string;
  name: string;
  combination: { horse_id: string; horse: string; rider: string; trainer: string } | null;
  data: EntryData;
  status: string;
  status_reason: string;
  computed_status: string;
  effective_status: string;
  welfare_locked: boolean;
  rank: number | null;
  primary: string | null;
  breakdown: Record<string, any>;
}

export interface ResultAmendment {
  id: string;
  action: string;
  action_label: string;
  reason: string;
  actor: string;
  entrant: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  created_at: string;
}

export interface ResultSheet {
  fixture: {
    id: string;
    competition_id: string;
    label: string;
    status: string;
    scheduled_at: string | null;
  };
  result_type: ResultType;
  config: ResultConfig;
  statuses: ResultStatus[];
  placing_points: Array<number | string>;
  final: boolean;
  finalised_at: string | null;
  finalised_by: string;
  permissions: { can_record: boolean; can_decide: boolean; officials_required: boolean };
  entries: ResultEntry[];
  amendments: ResultAmendment[];
}

export interface CompetitionOfficial {
  id: string;
  user_id: string;
  name: string;
  title: string;
  title_label: string;
}

export interface OfficialsResponse {
  officials: CompetitionOfficial[];
  required: boolean;
  titles: Array<{ key: string; label: string }>;
  can_manage: boolean;
  i_am_official: boolean;
}

export interface Horse {
  id: string;
  name: string;
  registration_number: string;
  fei_id: string;
  breed: string;
  sex: '' | 'mare' | 'gelding' | 'stallion' | 'filly' | 'colt';
  colour: string;
  foaled_on: string | null;
  owner_ids: string[];
  owner_names: string;
  trainer: string | null;
  trainer_name: string;
  trainer_label: string;
  photo_url: string;
  status: 'active' | 'retired';
  can_edit: boolean;
  created_at: string;
  record?: { starts: number; wins: number; seconds: number; thirds: number; competitions: string[] };
}

export interface CombinationRow {
  participant_id: string;
  name: string;
  horse_id: string;
  horse: string;
  rider: string;
  trainer: string;
}

export interface CombinationStatRow {
  key: string;
  name: string;
  starts: number;
  wins: number;
  seconds: number;
  thirds: number;
  points: string;
  statuses: number;
}
