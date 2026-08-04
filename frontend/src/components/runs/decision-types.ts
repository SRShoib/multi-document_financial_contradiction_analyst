import type { ContradictionDecisionAction, Severity } from "@/lib/types";

export interface DecisionDraft {
  action: ContradictionDecisionAction;
  note: string;
  editedSeverity: Severity;
  editedConfidence: number;
}

export const SEVERITY_OPTIONS: Severity[] = ["low", "medium", "high", "critical"];
