"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { CheckCircle2, MessageSquareWarning } from "lucide-react";

import { Button } from "@/components/ui/button";
import { MemoView } from "@/components/runs/memo-view";
import type { FinalGateAction, Memo } from "@/lib/types";

export function FinalGatePanel({
  memo,
  instructions,
  onSubmit,
  submitting,
}: {
  memo: Memo;
  instructions?: string;
  onSubmit: (action: FinalGateAction, note?: string) => void;
  submitting: boolean;
}) {
  const [note, setNote] = React.useState("");
  const [pendingAction, setPendingAction] = React.useState<FinalGateAction | null>(null);

  const requestChanges = () => {
    if (!note.trim()) return;
    setPendingAction("request_changes");
    onSubmit("request_changes", note.trim());
  };

  const approve = () => {
    setPendingAction("approve");
    onSubmit("approve", note.trim() || undefined);
  };

  return (
    <div className="flex flex-col gap-5">
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col gap-1 rounded-2xl border border-iris-2/25 bg-iris-2/[0.05] p-4"
      >
        <span className="text-sm font-medium text-foreground/90">Final sign-off</span>
        <span className="text-xs text-foreground/55">
          {instructions || "Review the drafted memo below, then approve it or send it back for another pass."}
        </span>
      </motion.div>

      <div className="glass-panel rounded-2xl p-6 sm:p-8">
        <MemoView memo={memo} />
      </div>

      <div className="flex flex-col gap-3 border-t border-border-subtle pt-5">
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Optional note for approval, or required feedback if requesting changes…"
          rows={2}
          className="w-full resize-none rounded-lg border border-border-subtle bg-black/15 px-3 py-2 text-sm text-foreground placeholder:text-foreground/30 outline-none focus:border-iris-2/60"
        />
        <div className="flex flex-col-reverse gap-2.5 sm:flex-row sm:justify-end">
          <Button
            variant="outline"
            onClick={requestChanges}
            disabled={!note.trim()}
            loading={submitting && pendingAction === "request_changes"}
          >
            <MessageSquareWarning className="h-4 w-4" /> Request changes
          </Button>
          <Button variant="success" onClick={approve} loading={submitting && pendingAction === "approve"}>
            <CheckCircle2 className="h-4 w-4" /> Approve memo
          </Button>
        </div>
      </div>
    </div>
  );
}
