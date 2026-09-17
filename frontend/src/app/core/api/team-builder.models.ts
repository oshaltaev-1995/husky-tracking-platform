export interface TeamBuilderActivity {
  id: string;
  date: string;
  title: string;
  distance_km: number;
  participant_count: number;
  plan_revision: number;
}

export interface WorkloadMetrics {
  km_7d: number;
  km_14d: number;
  season_km: number;
  starts_14d: number;
  days_since_last_work: number | null;
  planned_km_today: number;
}

export interface TeamBuilderCandidate {
  id: string;
  name: string;
  housing_code: string | null;
  dog_class: string | null;
  availability: string | null;
  capabilities: string[];
  eligible: boolean;
  reasons: string[];
  workload: WorkloadMetrics;
}

export interface TeamRelationship {
  dog_a_id: string;
  dog_b_id: string;
  kind: 'preferred_pair' | 'hard_conflict';
}

export interface TeamSlot {
  dog_id: string;
  dog_name: string;
  pair_index: number;
  pair_label: string;
  side: 'left' | 'right';
  harness_role: 'lead' | 'team' | 'wheel';
  position_order: number;
  explanations: string[];
}

export interface PlannedTeam {
  id: string | null;
  sequence: number;
  display_label: string;
  team_size: number;
  slots: TeamSlot[];
}

export interface UnassignedDog {
  dog_id: string;
  dog_name: string;
  reason: string;
}

export interface TeamBuilderContext {
  activity: TeamBuilderActivity;
  recommended_team_count: number;
  recommended_team_size: number;
  supported_team_sizes: number[];
  capability_summary: { lead: number; team: number; wheel: number };
  candidates: TeamBuilderCandidate[];
  relationships: TeamRelationship[];
  saved_teams: PlannedTeam[];
}

export interface GeneratedTeams {
  activity: TeamBuilderActivity;
  persisted: boolean;
  teams: PlannedTeam[];
  unassigned: UnassignedDog[];
}

export interface TeamSlotWrite {
  dog_id: string;
  pair_index: number;
  side: string;
  harness_role: string;
  position_order: number;
}

export interface SaveTeamsRequest {
  expected_revision: number;
  replace_existing: boolean;
  teams: {
    sequence: number;
    display_label: string;
    team_size: number;
    slots: TeamSlotWrite[];
  }[];
}
