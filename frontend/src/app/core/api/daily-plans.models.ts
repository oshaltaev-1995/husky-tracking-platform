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
  team_count: number;
  arranged_dog_count: number;
}

export interface DailyPlan {
  selected_date: string;
  season_start: string;
  season_end: string;
  reference_date: string;
  minimum_team_size: number;
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
  clear_saved_teams?: boolean;
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

/** One opt-in example; its pool is not a saved team lineup or actual work. */
export interface TrainingDayProposal {
  date: string;
  preset_version: string;
  available: boolean;
  unavailable_reason: string | null;
  activities: {
    sequence: number;
    start_time: string;
    suggested_end_time: string;
    title: string;
    distance_km: number;
  }[];
  participants: (PlanParticipant & { capabilities: string[] })[];
  unique_dogs: number;
  planned_participations: number;
  planned_dog_km: number;
  planned_km_per_dog: number;
  /** Opaque, context-bound authorization for exactly this reviewed proposal. */
  precondition: string | null;
}

export interface TrainingDayApply {
  date: string;
  preset_version: string;
  participant_ids: string[];
  precondition: string;
}
