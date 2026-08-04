/**
 * TypeScript mirror of the filing-reconciler Pydantic contract
 * (`filing_reconciler/models.py`, `app/main.py`). Keep in sync with the backend.
 */

export type ClaimKind = "numeric" | "guidance" | "narrative";

export type ContradictionType =
  | "numeric_mismatch"
  | "guidance_revision"
  | "narrative_conflict"
  | "omission";

export type Severity = "low" | "medium" | "high" | "critical";

export type ReviewStatus =
  | "pending"
  | "confirmed"
  | "rejected"
  | "edited"
  | "auto_accepted";

export type DetectedBy = "deterministic" | "llm";

export type ContradictionDecisionAction = "confirm" | "reject" | "edit";
export type FinalGateAction = "approve" | "request_changes";
export type DecisionAction = ContradictionDecisionAction | FinalGateAction;

export interface Citation {
  doc_id: string;
  start: number;
  end: number;
  quote: string;
  section: string | null;
}

export interface NumericDelta {
  value_a: number;
  value_b: number;
  abs_diff: number;
  pct_diff: number;
  within_tolerance: boolean;
}

export interface Contradiction {
  contradiction_id: string;
  ctype: ContradictionType;
  topic: string;
  period: string | null;
  severity: Severity;
  confidence: number;
  rationale: string;
  citations: Citation[];
  claim_ids: string[];
  detected_by: DetectedBy;
  status: ReviewStatus;
  numeric_delta: NumericDelta | null;
  human_note: string | null;
}

export interface MemoSection {
  heading: string;
  body: string;
  citations: Citation[];
}

export interface Memo {
  title: string;
  company: string | null;
  period_coverage: string | null;
  executive_summary: string;
  sections: MemoSection[];
  citations: Citation[];
  reflection_count: number;
  created_at: string;
}

export type GateKind = "contradictions" | "final_memo";

export interface ReviewRequest {
  kind: GateKind;
  run_id: string | null;
  instructions: string;
  contradictions: Contradiction[];
  memo: Memo | null;
}

export type RunLifecycleStatus = "paused" | "completed";

export interface RunStatus {
  run_id: string;
  status: RunLifecycleStatus;
  gate: GateKind | null;
  pending: ReviewRequest[] | null;
  contradictions: number;
  cost_usd: number;
  memo: Memo | null;
  /** Non-fatal per-document notices: truncation, conversion failures, dropped
   * citations. Populated from the graph's `errors` state channel. */
  errors: string[];
}

export interface DocInput {
  path: string;
  doc_id?: string | null;
  doc_type?: string | null;
  period?: string | null;
  company?: string | null;
}

export interface StartRequest {
  sample?: string | null;
  inputs?: DocInput[] | null;
  company?: string | null;
}

export interface ContradictionDecisionInput {
  target_id: string;
  action: ContradictionDecisionAction;
  note?: string | null;
  edited_severity?: Severity | null;
  edited_confidence?: number | null;
}

export interface DecisionRequest {
  decisions?: ContradictionDecisionInput[] | null;
  action?: FinalGateAction | null;
  note?: string | null;
}

// --- POST /documents (upload) ------------------------------------------------

export interface UploadedDoc {
  /** Position in the request — match responses back to staged files by this,
   * not filename (filenames can collide within a batch). */
  index: number;
  path: string;
  doc_id: string;
  filename: string;
  size_bytes: number;
  char_len: number;
  truncated: boolean;
  doc_type_guess: string | null;
  period_guess: string | null;
}

export interface RejectedDoc {
  index: number;
  filename: string;
  reason: string;
}

export interface UploadResponse {
  batch_id: string;
  documents: UploadedDoc[];
  rejected: RejectedDoc[];
}
