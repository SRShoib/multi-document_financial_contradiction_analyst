"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Check, Send, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ContradictionCard } from "@/components/runs/contradiction-card";
import type { Contradiction, ContradictionDecisionInput } from "@/lib/types";
import type { DecisionDraft } from "./decision-types";

function initialDraft(c: Contradiction): DecisionDraft {
  return {
    action: "confirm",
    note: "",
    editedSeverity: c.severity,
    editedConfidence: c.confidence,
  };
}

export function ContradictionsGate({
  contradictions,
  instructions,
  onSubmit,
  submitting,
}: {
  contradictions: Contradiction[];
  instructions?: string;
  onSubmit: (decisions: ContradictionDecisionInput[]) => void;
  submitting: boolean;
}) {
  const [drafts, setDrafts] = React.useState<Record<string, DecisionDraft>>(() =>
    Object.fromEntries(contradictions.map((c) => [c.contradiction_id, initialDraft(c)])),
  );

  const setAll = (action: DecisionDraft["action"]) => {
    setDrafts((prev) => {
      const next = { ...prev };
      for (const c of contradictions) {
        next[c.contradiction_id] = { ...next[c.contradiction_id], action };
      }
      return next;
    });
  };

  const handleSubmit = () => {
    const decisions: ContradictionDecisionInput[] = contradictions.map((c) => {
      const d = drafts[c.contradiction_id];
      return {
        target_id: c.contradiction_id,
        action: d.action,
        note: d.note.trim() ? d.note.trim() : undefined,
        edited_severity: d.action === "edit" ? d.editedSeverity : undefined,
        edited_confidence: d.action === "edit" ? d.editedConfidence : undefined,
      };
    });
    onSubmit(decisions);
  };

  const counts = contradictions.reduce(
    (acc, c) => {
      acc[drafts[c.contradiction_id]?.action ?? "confirm"]++;
      return acc;
    },
    { confirm: 0, reject: 0, edit: 0 } as Record<DecisionDraft["action"], number>,
  );

  return (
    <div className="flex flex-col gap-5">
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col gap-3 rounded-2xl border border-amber-400/20 bg-amber-400/[0.04] p-4 sm:flex-row sm:items-center sm:justify-between"
      >
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-medium text-amber-200">Human review required</span>
          <span className="text-xs text-foreground/55">
            {instructions ||
              `${contradictions.length} contradiction(s) need a decision before the memo can be drafted.`}
          </span>
        </div>
        <div className="flex gap-2">
          <Button variant="subtle" size="sm" onClick={() => setAll("confirm")}>
            <Check className="h-3.5 w-3.5" /> Confirm all
          </Button>
          <Button variant="subtle" size="sm" onClick={() => setAll("reject")}>
            <X className="h-3.5 w-3.5" /> Reject all
          </Button>
        </div>
      </motion.div>

      <div className="flex flex-col gap-4">
        {contradictions.map((c, i) => (
          <ContradictionCard
            key={c.contradiction_id}
            contradiction={c}
            index={i}
            draft={drafts[c.contradiction_id]}
            onChange={(patch) =>
              setDrafts((prev) => ({
                ...prev,
                [c.contradiction_id]: { ...prev[c.contradiction_id], ...patch },
              }))
            }
          />
        ))}
      </div>

      <div className="flex flex-col-reverse items-center justify-between gap-3 border-t border-border-subtle pt-5 sm:flex-row">
        <span className="text-xs text-foreground/45">
          {counts.confirm} confirm · {counts.reject} reject · {counts.edit} edit
        </span>
        <Button size="lg" onClick={handleSubmit} loading={submitting}>
          Submit decisions <Send className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
