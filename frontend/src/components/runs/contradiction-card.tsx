"use client";

import { motion } from "framer-motion";
import { Check, PencilLine, X } from "lucide-react";

import { CitationRow } from "@/components/runs/citation-row";
import { ConfidenceMeter, DetectedByBadge, SeverityBadge } from "@/components/runs/domain-badges";
import { NumericDeltaCompare } from "@/components/runs/numeric-delta-compare";
import { cn, ctypeLabel, titleCase } from "@/lib/utils";
import type { Contradiction } from "@/lib/types";
import { SEVERITY_OPTIONS, type DecisionDraft } from "./decision-types";

const ACTIONS: { key: DecisionDraft["action"]; label: string; icon: typeof Check }[] = [
  { key: "confirm", label: "Confirm", icon: Check },
  { key: "reject", label: "Reject", icon: X },
  { key: "edit", label: "Edit", icon: PencilLine },
];

export function ContradictionCard({
  contradiction,
  draft,
  onChange,
  index,
}: {
  contradiction: Contradiction;
  draft: DecisionDraft;
  onChange: (patch: Partial<DecisionDraft>) => void;
  index: number;
}) {
  const c = contradiction;

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.06, ease: [0.16, 1, 0.3, 1] }}
      className="glass-panel glass-panel-hover flex flex-col gap-4 rounded-2xl p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold text-foreground">{titleCase(c.topic)}</h3>
            {c.period && (
              <span className="rounded-md bg-white/5 px-1.5 py-0.5 font-mono text-[11px] text-foreground/50">
                {c.period}
              </span>
            )}
          </div>
          <span className="text-xs text-foreground/50">{ctypeLabel(c.ctype)}</span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SeverityBadge severity={c.severity} />
          <DetectedByBadge detectedBy={c.detected_by} />
        </div>
      </div>

      <div className="flex items-center justify-between gap-3 text-xs text-foreground/50">
        <span>Model confidence</span>
        <ConfidenceMeter confidence={c.confidence} />
      </div>

      <p className="text-sm leading-relaxed text-foreground/75">{c.rationale}</p>

      {c.numeric_delta && c.citations.length >= 2 && (
        <NumericDeltaCompare
          delta={c.numeric_delta}
          docA={c.citations[0].doc_id}
          docB={c.citations[1].doc_id}
          severity={c.severity}
        />
      )}

      <CitationRow citations={c.citations} />

      <div className="mt-1 flex flex-col gap-3 border-t border-border-subtle pt-4">
        <div className="inline-flex self-start rounded-full bg-white/[0.03] p-1 ring-1 ring-inset ring-white/10">
          {ACTIONS.map(({ key, label, icon: Icon }) => {
            const active = draft.action === key;
            return (
              <button
                key={key}
                type="button"
                onClick={() => onChange({ action: key })}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors",
                  active
                    ? key === "confirm"
                      ? "bg-emerald-400/15 text-emerald-300"
                      : key === "reject"
                        ? "bg-rose-500/15 text-rose-300"
                        : "bg-amber-400/15 text-amber-300"
                    : "text-foreground/50 hover:text-foreground/80",
                )}
              >
                <Icon className="h-3.5 w-3.5" aria-hidden />
                {label}
              </button>
            );
          })}
        </div>

        {draft.action === "edit" && (
          <div className="grid grid-cols-1 gap-3 rounded-lg border border-border-subtle bg-black/15 p-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1.5 text-xs text-foreground/50">
              Corrected severity
              <select
                value={draft.editedSeverity}
                onChange={(e) => onChange({ editedSeverity: e.target.value as DecisionDraft["editedSeverity"] })}
                className="rounded-md border border-border-subtle bg-surface px-2.5 py-1.5 text-sm text-foreground outline-none focus:border-iris-2/60"
              >
                {SEVERITY_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {titleCase(s)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1.5 text-xs text-foreground/50">
              Corrected confidence — {Math.round(draft.editedConfidence * 100)}%
              <input
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={draft.editedConfidence}
                onChange={(e) => onChange({ editedConfidence: Number(e.target.value) })}
                className="accent-iris-2 mt-2"
              />
            </label>
          </div>
        )}

        {(draft.action === "reject" || draft.action === "edit") && (
          <textarea
            value={draft.note}
            onChange={(e) => onChange({ note: e.target.value })}
            placeholder={
              draft.action === "reject"
                ? "Optional: why is this not a real contradiction?"
                : "Optional: why did you adjust this?"
            }
            rows={2}
            className="w-full resize-none rounded-lg border border-border-subtle bg-black/15 px-3 py-2 text-sm text-foreground placeholder:text-foreground/30 outline-none focus:border-iris-2/60"
          />
        )}
      </div>
    </motion.div>
  );
}
