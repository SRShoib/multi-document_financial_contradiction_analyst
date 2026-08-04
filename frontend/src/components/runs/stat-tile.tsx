import type { LucideIcon } from "lucide-react";

import { CountUp } from "@/components/ui/count-up";
import { cn } from "@/lib/utils";

export function StatTile({
  label,
  value,
  format,
  icon: Icon,
  tone = "default",
  className,
}: {
  label: string;
  value: number;
  format?: (n: number) => string;
  icon: LucideIcon;
  tone?: "default" | "warn" | "good";
  className?: string;
}) {
  const toneClass =
    tone === "warn" ? "text-amber-300" : tone === "good" ? "text-emerald-300" : "text-foreground";

  return (
    <div className={cn("glass-panel glass-panel-hover flex items-center gap-4 rounded-2xl p-5", className)}>
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/[0.04] ring-1 ring-white/10">
        <Icon className="h-5 w-5 text-iris-3" aria-hidden />
      </div>
      <div className="flex flex-col">
        <span className="text-xs uppercase tracking-wide text-foreground/45">{label}</span>
        <CountUp value={value} format={format} className={cn("text-2xl font-semibold tabular-figures", toneClass)} />
      </div>
    </div>
  );
}
