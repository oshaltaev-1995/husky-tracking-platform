export type AnalyticsDogSort =
  | 'highest_km'
  | 'lowest_km'
  | 'most_starts'
  | 'fewest_starts'
  | 'name';

export interface AnalyticsSummary {
  sessions: number;
  dogs_worked: number;
  dog_starts: number;
  dog_km: number;
  average_km_per_worked_dog: number;
  average_km_per_start: number;
  starts_5km: number;
  starts_10km: number;
  max_daily_dog_km: number;
}

export interface WeeklyAnalytics extends AnalyticsSummary {
  week_start: string;
  week_end: string;
  period_start: string;
  period_end: string;
  iso_week: number;
}

export interface DistanceBreakdown {
  distance_km: number;
  dog_starts: number;
  dog_km: number;
}

export interface RoleBreakdown {
  role: 'lead' | 'team' | 'wheel' | 'unpositioned';
  dog_starts: number;
  dog_km: number;
}

export interface AttentionDog {
  id: string;
  name: string;
  dog_class: string;
  availability: string | null;
  dog_km: number;
  dog_starts: number;
  eligible_days: number;
  worked_days: number;
  recent_7d_km: number;
  recent_14d_km: number;
  longest_work_streak: number;
  eligible_rest_streak: number;
  workload_rate: number;
  peer_median_rate: number;
  reason: string;
}

export interface AnalyticsOverview {
  date_from: string;
  date_to: string;
  season_start: string;
  season_end: string;
  context_date: string;
  summary: AnalyticsSummary;
  weekly: WeeklyAnalytics[];
  distance_breakdown: DistanceBreakdown[];
  role_breakdown: RoleBreakdown[];
  attention_population: number;
  underused: AttentionDog[];
  higher_workload: AttentionDog[];
}

export interface AnalyticsDog {
  id: string;
  name: string;
  sex: string;
  dog_class: string | null;
  lifecycle: string | null;
  availability: string | null;
  housing_code: string | null;
  housing_zone: string | null;
  capabilities: string[];
  dog_starts: number;
  dog_km: number;
  starts_5km: number;
  starts_10km: number;
  last_work_date: string | null;
  worked_days: number;
  eligible_days: number;
  longest_work_streak: number;
  eligible_rest_streak: number;
  recent_7d_km: number;
  recent_14d_km: number;
  workload_status: 'underused' | 'balanced' | 'higher' | 'not_applicable';
  attention_reason: string | null;
}

export interface AnalyticsDogsResponse {
  date_from: string;
  date_to: string;
  context_date: string;
  result_count: number;
  items: AnalyticsDog[];
}

export interface AnalyticsQuery {
  from: string;
  to: string;
  search?: string;
  dogClass?: string;
  sort?: AnalyticsDogSort;
}

export interface PopulationBucket {
  key: string;
  label: string;
  count: number;
}

export interface PopulationCohort {
  birth_year: number;
  total: number;
  active: number;
  archived: number;
  litter_codes: string[];
}

export interface PopulationAnalytics {
  snapshot_date: string;
  season_start: string;
  season_end: string;
  distribution_basis: string;
  headline: {
    total_represented: number;
    active_dogs: number;
    archived_dogs: number;
    average_age_years: number;
    median_age_years: number;
  };
  sex: PopulationBucket[];
  age_bands: PopulationBucket[];
  birth_cohorts: PopulationCohort[];
  classes: PopulationBucket[];
  neuter_status: PopulationBucket[];
  availability: PopulationBucket[];
  capabilities: PopulationBucket[];
  housing_areas: PopulationBucket[];
}
