export type ReviewProvider = 'groq' | 'openrouter';
export type ReviewStatus = 'pass' | 'violation' | 'attention' | 'unverified';

export interface OperationsCapabilities {
  enabled: boolean;
  external_processing: boolean;
  providers: ReviewProvider[];
  selected_scenario: 'review_operations';
  season_start: string;
  season_end: string;
}

export interface ReviewEntity {
  kind: 'day' | 'dog' | 'activity' | 'actual' | 'location';
  id: string;
}

export interface ReviewCheck {
  rule: string;
  status: ReviewStatus;
  explanation: string;
  selected_date: string;
  entities: ReviewEntity[];
  evidence_ids: string[];
}

export interface ReviewEvidence {
  id: string;
  selected_date: string;
  entities: ReviewEntity[];
  values: {
    name: string;
    value: number | string | boolean | null;
    unit: 'km' | 'count' | 'days' | 'state' | 'date';
  }[];
}

export interface ReviewLink {
  entity: ReviewEntity;
  label: string;
  path: string;
}

export interface ReviewPresentation {
  status: 'ready' | 'unresolved';
  segments: { text: string; entity: ReviewEntity | null; path: string | null }[];
  message: string | null;
}

export interface ReviewSummary {
  plan_exists: boolean;
  activity_count: number;
  selected_unique_dogs: number;
  selected_participations: number;
  activities: {
    entity: ReviewEntity;
    kind: string;
    distance_km: number | null;
    selected_pool_count: number;
    selected_dogs: ReviewLink[];
    omitted_selected_dogs: number;
    saved_teams: number | null;
    actual_status: string;
  }[];
  omitted_activities: number;
  actual: { sessions: number; dogs_worked: number; dog_starts: number; dog_km: number };
}

export interface ReviewFindingGroup {
  scope: 'plan' | 'other_dogs';
  findings: ReviewCheck[];
  status_counts: { passed: number; violations: number; attention: number; unverified: number };
  omitted_findings: number;
  links: ReviewLink[];
}

export interface OperationsReview {
  snapshot_id: string;
  selected_date: string;
  captured_at: string;
  explanation: string;
  presentation: ReviewPresentation;
  summary: ReviewSummary;
  finding_groups: ReviewFindingGroup[];
  facts: ReviewCheck[];
  findings: ReviewCheck[];
  evidence: ReviewEvidence[];
  links: ReviewLink[];
  checked_rules: string[];
  status_counts: { passed: number; violations: number; attention: number; unverified: number };
  omitted_findings: number;
  provider: ReviewProvider;
  model: string;
  fallback: boolean;
  http_calls: number;
  tool_calls: number;
  trace: { tool_name: string; provider: ReviewProvider; outcome: string; elapsed_ms: number }[];
  usage: {
    known_prompt_tokens: number | null;
    known_completion_tokens: number | null;
    incomplete: boolean;
  };
}
