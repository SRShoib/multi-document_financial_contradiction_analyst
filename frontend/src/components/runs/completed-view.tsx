"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { Clipboard, ClipboardCheck, DollarSign, FileWarning, PartyPopper, Printer } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { MemoView } from "@/components/runs/memo-view";
import { StatTile } from "@/components/runs/stat-tile";
import { memoToMarkdown } from "@/lib/memo-export";
import type { Memo } from "@/lib/types";
import { formatUsd } from "@/lib/utils";

export function CompletedView({
  memo,
  contradictions,
  costUsd,
}: {
  memo: Memo | null;
  contradictions: number;
  costUsd: number;
}) {
  const [copied, setCopied] = React.useState<"json" | "md" | null>(null);

  const copy = async (kind: "json" | "md") => {
    if (!memo) return;
    const text = kind === "json" ? JSON.stringify(memo, null, 2) : memoToMarkdown(memo);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(kind);
      toast.success(kind === "json" ? "Memo JSON copied" : "Memo Markdown copied");
      setTimeout(() => setCopied(null), 1800);
    } catch {
      toast.error("Clipboard access was blocked by the browser");
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <motion.div
        initial={{ opacity: 0, scale: 0.97 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        className="flex flex-col items-start gap-2 rounded-2xl border border-emerald-400/25 bg-emerald-400/[0.06] p-5 sm:flex-row sm:items-center sm:justify-between"
      >
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-400/15">
            <PartyPopper className="h-5 w-5 text-emerald-300" aria-hidden />
          </span>
          <div className="flex flex-col">
            <span className="font-medium text-emerald-200">Analysis complete</span>
            <span className="text-xs text-foreground/55">
              The memo was approved and exported with full citations.
            </span>
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <StatTile label="Contradictions surfaced" value={contradictions} icon={FileWarning} tone={contradictions > 0 ? "warn" : "good"} />
        <StatTile label="Run cost" value={costUsd} format={formatUsd} icon={DollarSign} />
      </div>

      {memo && (
        <div className="glass-panel rounded-2xl p-6 sm:p-8">
          <MemoView memo={memo} />
        </div>
      )}

      {memo && (
        <div className="flex flex-wrap justify-end gap-2.5">
          <Button variant="outline" size="sm" onClick={() => copy("md")}>
            {copied === "md" ? <ClipboardCheck className="h-3.5 w-3.5" /> : <Clipboard className="h-3.5 w-3.5" />}
            Copy Markdown
          </Button>
          <Button variant="outline" size="sm" onClick={() => copy("json")}>
            {copied === "json" ? <ClipboardCheck className="h-3.5 w-3.5" /> : <Clipboard className="h-3.5 w-3.5" />}
            Copy JSON
          </Button>
          <Button variant="subtle" size="sm" onClick={() => window.print()}>
            <Printer className="h-3.5 w-3.5" /> Print
          </Button>
        </div>
      )}
    </div>
  );
}
