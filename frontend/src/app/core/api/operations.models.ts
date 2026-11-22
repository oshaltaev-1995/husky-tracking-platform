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

export interface OperationsReview {
  snapshot_id: string;
  selected_date: string;
  captured_at: string;
  explanation: string;
  facts: ReviewCheck[];
  findings: ReviewCheck[];
  evidence: ReviewEvidence[];
  links: { entity: ReviewEntity; label: string; path: string }[];
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
