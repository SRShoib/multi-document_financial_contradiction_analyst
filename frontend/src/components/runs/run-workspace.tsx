"use client";

import * as React from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { AlertTriangle, ArrowLeft, Check, Copy, DollarSign, FileWarning, RotateCw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ContradictionsGate } from "@/components/runs/contradictions-gate";
import { FinalGatePanel } from "@/components/runs/final-gate-panel";
import { CompletedView } from "@/components/runs/completed-view";
import { StatTile } from "@/components/runs/stat-tile";
import { PipelineStepper } from "@/components/pipeline/pipeline-stepper";
import type { RunningPhase } from "@/components/pipeline/stages";
import { api, ApiError, isNetworkError } from "@/lib/api";
import { formatUsd } from "@/lib/utils";
import type { ContradictionDecisionInput, FinalGateAction, RunStatus } from "@/lib/types";

function messageFor(err: unknown): string {
  if (err instanceof ApiError) return err.detail;
  if (isNetworkError(err)) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong.";
}

export function RunWorkspace({ runId }: { runId: string }) {
  const [runStatus, setRunStatus] = React.useState<RunStatus | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [runningPhase, setRunningPhase] = React.useState<RunningPhase>("start");
  const [actionSubmitting, setActionSubmitting] = React.useState(false);
  const [copied, setCopied] = React.useState(false);

  const fetchStatus = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const status = await api.getRun(runId);
      setRunStatus(status);
    } catch (err) {
      setError(messageFor(err));
    } finally {
      setLoading(false);
      setRunningPhase(null);
    }
  }, [runId]);

  React.useEffect(() => {
    // Standard fetch-on-mount/on-runId-change: fetchStatus sets state once its
    // request resolves, not synchronously during this effect's execution.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchStatus();
  }, [fetchStatus]);

  const submitContradictionDecisions = async (decisions: ContradictionDecisionInput[]) => {
    setActionSubmitting(true);
    setRunningPhase("contradiction-decision");
    try {
      const status = await api.decide(runId, { decisions });
      setRunStatus(status);
      toast.success("Decisions recorded — memo drafting in progress");
    } catch (err) {
      toast.error(messageFor(err));
    } finally {
      setActionSubmitting(false);
      setRunningPhase(null);
    }
  };

  const submitFinalDecision = async (action: FinalGateAction, note?: string) => {
    setActionSubmitting(true);
    setRunningPhase("final-decision");
    try {
      const status = await api.decide(runId, { action, note });
      setRunStatus(status);
      toast.success(action === "approve" ? "Memo approved" : "Sent back for another draft pass");
    } catch (err) {
      toast.error(messageFor(err));
    } finally {
      setActionSubmitting(false);
      setRunningPhase(null);
    }
  };

  const copyRunId = async () => {
    try {
      await navigator.clipboard.writeText(runId);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard may be blocked; not critical
    }
  };

  const gateItem = runStatus?.pending?.[0] ?? null;

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-8 px-6 py-10">
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between gap-3">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-sm text-foreground/50 transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" /> New analysis
          </Link>
          <button
            onClick={copyRunId}
            className="inline-flex items-center gap-1.5 rounded-full border border-border-subtle bg-white/[0.02] px-3 py-1 font-mono text-[11px] text-foreground/45 transition-colors hover:border-white/25 hover:text-foreground/80"
            title="Copy run ID"
          >
            {copied ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
            {runId}
          </button>
        </div>

        <div className="glass-panel rounded-2xl p-5 sm:p-6">
          <PipelineStepper
            status={runStatus?.status ?? null}
            gate={runStatus?.gate ?? null}
            runningPhase={runningPhase}
          />
        </div>
      </div>

      {error && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="flex items-center justify-between gap-3 rounded-2xl border border-rose-400/25 bg-rose-500/[0.06] p-4"
        >
          <div className="flex items-center gap-2.5 text-sm text-rose-200">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {error}
          </div>
          <Button variant="outline" size="sm" onClick={fetchStatus}>
            <RotateCw className="h-3.5 w-3.5" /> Retry
          </Button>
        </motion.div>
      )}

      {loading && !runStatus && (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Skeleton className="h-20 rounded-2xl" />
            <Skeleton className="h-20 rounded-2xl" />
          </div>
          <Skeleton className="h-64 rounded-2xl" />
        </div>
      )}

      {runStatus && (
        <>
          {runStatus.errors.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex flex-col gap-2 rounded-2xl border border-amber-400/20 bg-amber-400/[0.04] p-4"
            >
              <div className="flex items-center gap-2 text-sm font-medium text-amber-200">
                <FileWarning className="h-4 w-4 shrink-0" />
                Run notices
              </div>
              <ul className="flex flex-col gap-1 text-xs leading-relaxed text-foreground/60">
                {runStatus.errors.map((notice, i) => (
                  <li key={i}>{notice}</li>
                ))}
              </ul>
            </motion.div>
          )}

          {runStatus.status !== "completed" && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <StatTile
                label="Contradictions so far"
                value={runStatus.contradictions}
                icon={FileWarning}
                tone={runStatus.contradictions > 0 ? "warn" : "good"}
              />
              <StatTile label="Cost so far" value={runStatus.cost_usd} format={formatUsd} icon={DollarSign} />
            </div>
          )}

          {runStatus.status === "completed" && (
            <CompletedView memo={runStatus.memo} contradictions={runStatus.contradictions} costUsd={runStatus.cost_usd} />
          )}

          {runStatus.status === "paused" && runStatus.gate === "contradictions" && gateItem && (
            <ContradictionsGate
              contradictions={gateItem.contradictions}
              instructions={gateItem.instructions}
              onSubmit={submitContradictionDecisions}
              submitting={actionSubmitting}
            />
          )}

          {runStatus.status === "paused" && runStatus.gate === "final_memo" && gateItem?.memo && (
            <FinalGatePanel
              memo={gateItem.memo}
              instructions={gateItem.instructions}
              onSubmit={submitFinalDecision}
              submitting={actionSubmitting}
            />
          )}
        </>
      )}
    </div>
  );
}
