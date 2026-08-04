import { ArrowRight } from "lucide-react";

import { SEVERITY_STYLE } from "@/lib/badges";
import type { NumericDelta, Severity } from "@/lib/types";
import { formatNumber, formatPercent } from "@/lib/utils";
import { cn } from "@/lib/utils";

/**
 * Two competing figures from two documents, side by side, with the gap called
 * out as a single status-colored delta badge. Deliberately not a bar/diverging
 * chart: with exactly two labeled values, a stat-pair + delta badge reads
 * faster than a chart would and avoids inventing a comparison axis.
 */
export function NumericDeltaCompare({
  delta,
  docA,
  docB,
  severity,
}: {
  delta: NumericDelta;
  docA: string;
  docB: string;
  severity: Severity;
}) {
  const style = SEVERITY_STYLE[severity];

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border-subtle bg-black/15 p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex flex-1 items-center gap-3">
        <ValueStat label={docA} value={delta.value_a} />
        <ArrowRight className="h-4 w-4 shrink-0 text-foreground/25" aria-hidden />
        <ValueStat label={docB} value={delta.value_b} />
      </div>
      <div
        className={cn(
          "flex shrink-0 items-center gap-2 self-start rounded-lg px-3 py-2 ring-1 ring-inset sm:self-center",
          style.className,
        )}
      >
        <span className="text-lg font-semibold tabular-figures">
          {formatPercent(delta.pct_diff)}
        </span>
        <span className="text-[11px] leading-tight opacity-80">
          gap
          <br />
          Δ {formatNumber(delta.abs_diff)}
        </span>
      </div>
    </div>
  );
}

function ValueStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex min-w-0 flex-col">
      <span className="truncate font-mono text-[11px] text-foreground/45">{label}</span>
      <span className="text-base font-semibold tabular-figures text-foreground/90">
        {formatNumber(value)}
      </span>
    </div>
  );
}
