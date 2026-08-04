"use client";

import { motion } from "framer-motion";
import {
  Check,
  FileSearch,
  GitCompareArrows,
  Loader2,
  PenLine,
  ShieldCheck,
  UserCheck,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { STAGES, computeStageStatuses, type RunningPhase, type StageKey } from "./stages";
import type { GateKind, RunLifecycleStatus } from "@/lib/types";

const ICONS: Record<StageKey, typeof FileSearch> = {
  ingest: FileSearch,
  reconcile: GitCompareArrows,
  contra_gate: UserCheck,
  draft: PenLine,
  final_gate: ShieldCheck,
  finalize: Check,
};

export function PipelineStepper({
  status,
  gate,
  runningPhase,
}: {
  status: RunLifecycleStatus | null;
  gate: GateKind | null;
  runningPhase: RunningPhase;
}) {
  const statuses = computeStageStatuses({ status, gate, runningPhase });
  const doneCount = STAGES.filter((s) => statuses[s.key] === "done").length;
  const fillPct = (doneCount / (STAGES.length - 1)) * 100;

  return (
    <div className="w-full overflow-x-auto pb-1">
      <div className="relative flex min-w-[720px] items-start justify-between px-2">
        <div className="absolute left-8 right-8 top-5 h-px bg-white/10" />
        <motion.div
          className="absolute left-8 top-5 h-px bg-[linear-gradient(90deg,var(--iris-1),var(--iris-2),var(--iris-3))]"
          initial={false}
          animate={{ width: `calc(${Math.min(fillPct, 100)}% * (100% - 4rem) / 100%)` }}
          style={{ maxWidth: "calc(100% - 4rem)" }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        />

        {STAGES.map((stage) => {
          const st = statuses[stage.key];
          const Icon = ICONS[stage.key];
          const isCurrent = st === "current";
          const isDone = st === "done";

          return (
            <div key={stage.key} className="relative z-10 flex w-32 flex-col items-center gap-2.5 text-center">
              <motion.div
                animate={isCurrent ? { scale: [1, 1.08, 1] } : { scale: 1 }}
                transition={isCurrent ? { duration: 1.6, repeat: Infinity, ease: "easeInOut" } : undefined}
                className={cn(
                  "flex h-10 w-10 items-center justify-center rounded-full ring-1 transition-colors duration-300",
                  isDone &&
                    "bg-[linear-gradient(135deg,var(--iris-1),var(--iris-2))] text-white ring-transparent shadow-[0_4px_16px_-4px_rgba(99,102,241,0.6)]",
                  isCurrent && "bg-surface-raised text-iris-3 ring-iris-3/50",
                  st === "upcoming" && "bg-white/[0.03] text-foreground/30 ring-white/10",
                )}
              >
                {isCurrent ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                ) : (
                  <Icon className="h-4 w-4" aria-hidden />
                )}
              </motion.div>
              <div className="flex flex-col gap-0.5">
                <span
                  className={cn(
                    "text-[12.5px] font-medium leading-tight",
                    isCurrent ? "text-foreground" : isDone ? "text-foreground/80" : "text-foreground/35",
                  )}
                >
                  {stage.title}
                </span>
                <span className="text-[10.5px] leading-tight text-foreground/35">{stage.detail}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
