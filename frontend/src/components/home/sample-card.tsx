"use client";

import { motion } from "framer-motion";
import { Check, FileStack, ShieldCheck } from "lucide-react";

import { cn } from "@/lib/utils";
import type { SampleMeta } from "@/lib/sample-meta";

export function SampleCard({
  meta,
  selected,
  onSelect,
  index,
}: {
  meta: SampleMeta;
  selected: boolean;
  onSelect: () => void;
  index: number;
}) {
  return (
    <motion.button
      type="button"
      onClick={onSelect}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: index * 0.08, ease: [0.16, 1, 0.3, 1] }}
      className={cn(
        "group relative flex flex-col gap-4 rounded-2xl p-5 text-left transition-all duration-200",
        "glass-panel",
        selected
          ? "border-iris-2/50 shadow-[0_0_0_1px_rgba(168,85,247,0.35),0_20px_60px_-25px_rgba(168,85,247,0.45)]"
          : "hover:border-white/20 hover:-translate-y-0.5",
      )}
    >
      {selected && (
        <span className="absolute right-4 top-4 flex h-6 w-6 items-center justify-center rounded-full bg-[linear-gradient(135deg,var(--iris-1),var(--iris-2))]">
          <Check className="h-3.5 w-3.5 text-white" aria-hidden />
        </span>
      )}
      <div className="flex items-center gap-2.5">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/[0.04] ring-1 ring-white/10">
          <FileStack className="h-4 w-4 text-iris-3" aria-hidden />
        </span>
        <div className="flex flex-col leading-tight">
          <span className="font-semibold text-foreground">{meta.company}</span>
          <span className="font-mono text-[11px] text-foreground/40">{meta.ticker}</span>
        </div>
      </div>

      <span className="text-xs uppercase tracking-wide text-foreground/40">{meta.scenario}</span>
      <p className="text-sm leading-relaxed text-foreground/65">{meta.description}</p>

      <div className="mt-auto flex items-center justify-between pt-1 text-xs text-foreground/40">
        <span>{meta.docCount || "—"} documents</span>
        {!meta.hasContradictions && (
          <span className="inline-flex items-center gap-1 text-emerald-300/80">
            <ShieldCheck className="h-3 w-3" /> clean control
          </span>
        )}
      </div>
    </motion.button>
  );
}
