import { AttentionDog, WeeklyAnalytics } from './analytics.models';

export interface DashboardContext {
  selected_date: string;
  season_start: string;
  season_end: string;
  reference_date: string;
  season_label: string;
}

export interface DashboardPopulation {
  active_dogs: number;
  class_counts: Record<string, number>;
  available_dogs: number;
  unavailable_dogs: number;
  availability_counts: Record<string, number>;
  resident_dogs: number;
  occupied_locations: number;
  housing_areas: Record<string, number>;
}

export interface DashboardUnavailableDog {
  id: string;
  name: string;
  availability: string;
  housing_code: string;
}

export interface DashboardTraining {
  id: string;
  title: string;
  distance_km: number;
  participant_count: number;
  team_count: number;
  arranged_dog_count: number;
  actual_status: string;
}

export interface DashboardPlan {
  exists: boolean;
  activities_count: number;
  activity_counts: Record<string, number>;
  planned_dogs: number;
  planned_dog_km: number;
  training_with_saved_teams: number;
  training_without_saved_teams: number;
  notes_preview: string | null;
  status_counts: Record<string, number>;
  training: DashboardTraining[];
}

export interface DashboardActual {
  sessions: number;
  dogs_worked: number;
  dog_starts: number;
  dog_km: number;
}

export interface DashboardAttention {
  date_from: string;
  date_to: string;
  label: string;
  underused_count: number;
  higher_workload_count: number;
  underused: AttentionDog[];
  higher_workload: AttentionDog[];
}

export interface DashboardResponse {
  context: DashboardContext;
  population: DashboardPopulation;
  unavailable_dogs: DashboardUnavailableDog[];
  plan: DashboardPlan;
  actual: DashboardActual;
  attention: DashboardAttention;
  recent_weekly: WeeklyAnalytics[];
}
