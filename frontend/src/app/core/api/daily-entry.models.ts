export interface ActualParticipantWrite {
  dog_id: string;
  assigned_role: 'lead' | 'team' | 'wheel' | null;
  actual_team_sequence: number | null;
  pair_index: number | null;
  side: 'left' | 'right' | null;
  position_order: number | null;
}

export interface ActualSessionWrite {
  distance_km: 5 | 10;
  start_time: string | null;
  label: string | null;
  note: string | null;
  participants: ActualParticipantWrite[];
}

export interface ActualSessionUpdate extends ActualSessionWrite {
  expected_revision: number;
}

export interface ActualParticipant {
  dog_id: string;
  dog_name: string;
  housing_code: string | null;
  dog_class: string | null;
  availability: string | null;
  assigned_role: 'lead' | 'team' | 'wheel' | null;
  actual_team_sequence: number | null;
  pair_index: number | null;
  pair_label: string | null;
  side: 'left' | 'right' | null;
  position_order: number | null;
}

export interface ActualSession {
  id: string;
  revision: number;
  work_date: string;
  start_time: string | null;
  distance_km: 5 | 10;
  label: string | null;
  note: string | null;
  source: 'planned' | 'manual' | 'seeded' | 'unlinked';
  planned_activity_id: string | null;
  planned_activity_title: string | null;
  plan_status: 'matches_plan' | 'modified' | null;
  deviations: string[];
  team_count: number;
  participants: ActualParticipant[];
}

export interface PlannedActivityActual {
  id: string;
  activity_type: 'training' | 'open_space_walk' | 'individual_exercise' | 'rest';
  title: string;
  start_time: string | null;
  distance_km: number | null;
  participant_count: number;
  recording_participant_names: string[];
  team_count: number;
  arranged_dog_count: number;
  actual_status: 'not_recorded' | 'matches_plan' | 'modified' | 'not_run' | 'context_only';
  actual_session_id: string | null;
  deviations: string[];
}

export interface DailyEntrySummary {
  actual_sessions: number;
  dogs_worked: number;
  dog_starts: number;
  total_dog_km: number;
}

export interface DailyDog {
  id: string;
  name: string;
  housing_code: string | null;
  dog_class: string | null;
  availability: string | null;
  starts: number;
  actual_km: number;
}

export interface DailyHousingGroup {
  code: string;
  display_name: string;
  zone: string;
  row: string;
  position: number;
  dogs: DailyDog[];
}

export interface DailyEntry {
  selected_date: string;
  season_start: string;
  season_end: string;
  reference_date: string;
  plan_exists: boolean;
  planned_activities: PlannedActivityActual[];
  sessions: ActualSession[];
  summary: DailyEntrySummary;
  housing_groups: DailyHousingGroup[];
}

export interface ActualEligibleDog {
  id: string;
  name: string;
  housing_code: string | null;
  dog_class: string | null;
  availability: string | null;
  capabilities: string[];
  actual_km_today: number;
  eligible: boolean;
  reasons: string[];
}

export interface ActualEligibility {
  selected_date: string;
  distance_km: 5 | 10;
  max_daily_km: number;
  dogs: ActualEligibleDog[];
}
