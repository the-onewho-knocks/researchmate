export type Tier = "A" | "B" | "C";
export type Status = "pass" | "fail" | "needs_review" | "could_not_assess";
export type Source = "rule" | "ml" | "llm";
export type Level = "low" | "medium" | "high";

export interface Verdict {
  id: string;
  component: string;
  name: string;
  tier: Tier;
  status: Status;
  evidence: string | null;
  confidence: number;
  source: Source;
  provider: string | null;
  note: string | null;
  section: string | null;
  block: number | null;
  suggestion: string | null;
}

export interface ComponentResult {
  key: string;
  name: string;
  acronym: string;
  score: number | null;
  coverage: number;
  verdicts: Verdict[];
}

export interface Usage {
  calls: number;
  input_tokens: number;
  output_tokens: number;
  model: string;
  by_provider?: Record<string, { calls: number; input_tokens: number; output_tokens: number }>;
}

export interface Paragraph {
  i: number;
  text: string;
  kind: string;
  sections: string[];
}

export interface TodoItem {
  id: string;
  name: string;
  component: string;
  component_name: string;
  status: Status;
  effort: Level;
  impact: Level;
  priority: number;
  suggestion: string;
  block: number | null;
  section: string | null;
}

export interface EvaluationReport {
  document_id: string;
  file_type: string;
  framework_version: string;
  overall_score: number | null;
  coverage: number;
  components: ComponentResult[];
  limitations: string[];
  sections_detected: string[];
  source_counts: Record<string, number>;
  usage: Usage;
  coach_feedback: string | null;
  paragraphs: Paragraph[];
  todo: TodoItem[];
  cached: boolean;
}

export interface CriterionChange {
  id: string;
  name: string;
  component: string;
  component_name: string;
  before: Status;
  after: Status;
  direction: "improved" | "regressed" | "changed";
  evidence_after: string | null;
  note_after: string | null;
}

export interface ComponentDelta {
  key: string;
  name: string;
  acronym: string;
  before: number | null;
  after: number | null;
  delta: number | null;
}

export interface Comparison {
  before_id: string;
  after_id: string;
  overall_before: number | null;
  overall_after: number | null;
  overall_delta: number | null;
  coverage_before: number;
  coverage_after: number;
  improved: number;
  regressed: number;
  changed: number;
  unchanged: number;
  still_failing: number;
  resolved_ids: string[];
  components: ComponentDelta[];
  changes: CriterionChange[];
}

export interface UploadResponse {
  document_id: string;
  filename: string;
  file_type: string;
  size_bytes: number;
}

export interface Health {
  status: string;
  llm_available: boolean;
  gemini_available: boolean;
  local_available: boolean;
  local_model: string;
  gemini_cooling_down: boolean;
  gemini_calls_left_today: number;
  ml_available: boolean;
  ml_calibrated: boolean;
  framework_version: string;
}

/** Where the "Show in text" buttons send the reading view. */
export interface Jump {
  block: number;
  id?: string;
  nonce: number;
}
