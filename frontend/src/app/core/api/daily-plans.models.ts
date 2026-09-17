export type PlannedActivityType =
  | 'training'
  | 'open_space_walk'
  | 'individual_exercise'
  | 'rest';

export interface PlanParticipant {
  id: string;
  name: string;
  housing_code: string | null;
  dog_class: string | null;
  availability: string | null;
}

export interface PlannedActivity {
  id: string;
  activity_type: PlannedActivityType;
  sequence: number;
  start_time: string | null;
  title: string;
  distance_km: number | null;
  notes: string | null;
  participants: PlanParticipant[];
}

export interface DailyPlan {
  selected_date: string;
  season_start: string;
  season_end: string;
  reference_date: string;
  exists: boolean;
  id: string | null;
  revision: number | null;
  notes: string | null;
  activities: PlannedActivity[];
}

export interface ActivityWrite {
  activity_type: PlannedActivityType;
  start_time: string | null;
  title: string;
  distance_km: number | null;
  notes: string | null;
  participant_ids: string[];
  expected_revision: number | null;
}

export interface EligibleDog {
  id: string;
  name: string;
  housing_code: string | null;
  dog_class: string | null;
  availability: string | null;
  eligible: boolean;
  reasons: string[];
  planned_training_km: number;
}

export interface Eligibility {
  selected_date: string;
  activity_type: PlannedActivityType;
  distance_km: number | null;
  max_daily_training_km: number;
  dogs: EligibleDog[];
}
