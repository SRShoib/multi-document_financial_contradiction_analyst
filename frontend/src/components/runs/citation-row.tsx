"use client";

import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { FileText, Quote } from "lucide-react";

import { cn } from "@/lib/utils";
import type { Citation } from "@/lib/types";

export function CitationRow({ citations, className }: { citations: Citation[]; className?: string }) {
  const [activeIdx, setActiveIdx] = React.useState<number | null>(null);

  if (citations.length === 0) return null;

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="flex flex-wrap items-center gap-1.5">
        {citations.map((c, i) => {
          const isActive = activeIdx === i;
          return (
            <button
              key={`${c.doc_id}-${c.start}-${c.end}`}
              type="button"
              onClick={() => setActiveIdx(isActive ? null : i)}
              className={cn(
                "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-[11px] transition-colors",
                isActive
                  ? "border-iris-3/50 bg-iris-3/10 text-iris-3"
                  : "border-border-subtle bg-white/[0.03] text-foreground/60 hover:border-white/25 hover:text-foreground/90",
              )}
              aria-expanded={isActive}
            >
              <FileText className="h-3 w-3" aria-hidden />
              {c.doc_id}
              <span className="text-foreground/35">:{c.start}-{c.end}</span>
            </button>
          );
        })}
      </div>
      <AnimatePresence initial={false} mode="wait">
        {activeIdx !== null && citations[activeIdx] && (
          <motion.div
            key={activeIdx}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div className="flex gap-2.5 rounded-lg border border-border-subtle bg-black/20 p-3">
              <Quote className="mt-0.5 h-3.5 w-3.5 shrink-0 text-iris-3/70" aria-hidden />
              <div className="flex flex-col gap-1">
                <p className="font-serif text-[13px] italic leading-relaxed text-foreground/85">
                  &ldquo;{citations[activeIdx].quote}&rdquo;
                </p>
                {citations[activeIdx].section && (
                  <p className="text-[11px] uppercase tracking-wide text-foreground/40">
                    {citations[activeIdx].section}
                  </p>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
