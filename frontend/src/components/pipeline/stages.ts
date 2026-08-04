import type { GateKind, RunLifecycleStatus } from "@/lib/types";

export type StageKey =
  | "ingest"
  | "reconcile"
  | "contra_gate"
  | "draft"
  | "final_gate"
  | "finalize";

export type StageStatus = "done" | "current" | "upcoming";

export interface Stage {
  key: StageKey;
  title: string;
  detail: string;
}

export const STAGES: Stage[] = [
  { key: "ingest", title: "Ingest & extract", detail: "Parse filings, extract per-document claims" },
  { key: "reconcile", title: "Reconcile & score", detail: "Cross-document diff + risk scoring" },
  { key: "contra_gate", title: "Contradiction review", detail: "Human confirms / rejects / edits" },
  { key: "draft", title: "Draft & critique", detail: "Memo composed, faithfulness-checked" },
  { key: "final_gate", title: "Final sign-off", detail: "Human approves the memo" },
  { key: "finalize", title: "Complete", detail: "Memo exported with citations" },
];

/**
 * A request currently in flight against the graph, when known — lets the
 * stepper show *which* real stage the synchronous backend call is executing,
 * rather than a generic spinner.
 */
export type RunningPhase = "start" | "contradiction-decision" | "final-decision" | null;

export function computeStageStatuses(args: {
  status: RunLifecycleStatus | null;
  gate: GateKind | null;
  runningPhase: RunningPhase;
}): Record<StageKey, StageStatus> {
  const { status, gate, runningPhase } = args;

  const order: StageKey[] = STAGES.map((s) => s.key);
  const result = {} as Record<StageKey, StageStatus>;
  for (const key of order) result[key] = "upcoming";

  const setUpTo = (key: StageKey, inclusive: boolean) => {
    const idx = order.indexOf(key);
    for (let i = 0; i < idx; i++) result[order[i]] = "done";
    if (inclusive) result[key] = "done";
  };

  if (runningPhase === "start") {
    result.ingest = "current";
    return result;
  }
  if (runningPhase === "contradiction-decision") {
    setUpTo("contra_gate", true);
    result.draft = "current";
    return result;
  }
  if (runningPhase === "final-decision") {
    setUpTo("final_gate", true);
    result.finalize = "current";
    return result;
  }

  if (status === "completed") {
    for (const key of order) result[key] = "done";
    return result;
  }

  if (status === "paused" && gate === "contradictions") {
    setUpTo("reconcile", true);
    result.contra_gate = "current";
    return result;
  }

  if (status === "paused" && gate === "final_memo") {
    setUpTo("draft", true);
    result.final_gate = "current";
    return result;
  }

  return result;
}
