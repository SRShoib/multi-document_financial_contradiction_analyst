import { Calculator, Sparkles } from "lucide-react";

import { StyledBadge } from "@/components/ui/badge";
import { DETECTED_BY_STYLE, SEVERITY_STYLE, STATUS_STYLE } from "@/lib/badges";
import type { DetectedBy, ReviewStatus, Severity } from "@/lib/types";
import { cn } from "@/lib/utils";

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  return <StyledBadge style={SEVERITY_STYLE[severity]} showDot className={className} />;
}

export function StatusBadge({ status, className }: { status: ReviewStatus; className?: string }) {
  return <StyledBadge style={STATUS_STYLE[status]} className={className} />;
}

export function DetectedByBadge({ detectedBy, className }: { detectedBy: DetectedBy; className?: string }) {
  const style = DETECTED_BY_STYLE[detectedBy];
  const Icon = detectedBy === "deterministic" ? Calculator : Sparkles;
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset whitespace-nowrap", style.className, className)}>
      <Icon className="h-3 w-3" aria-hidden />
      {style.label}
    </span>
  );
}

export function ConfidenceMeter({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const tone =
    confidence >= 0.85 ? "bg-emerald-400" : confidence >= 0.75 ? "bg-cyan-400" : "bg-amber-400";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-white/10">
        <div
          className={cn("h-full rounded-full transition-[width] duration-700 ease-out", tone)}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs tabular-figures text-foreground/60">{pct}%</span>
    </div>
  );
}
