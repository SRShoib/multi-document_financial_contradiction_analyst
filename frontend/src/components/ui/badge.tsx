import * as React from "react";

import { badgeVariants } from "@/lib/variants";
import { cn } from "@/lib/utils";
import type { BadgeStyle } from "@/lib/badges";

export function Badge({
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn(badgeVariants(), "bg-white/5 text-foreground/80 ring-white/10", className)} {...props} />;
}

export function StyledBadge({
  style,
  className,
  showDot = false,
}: {
  style: BadgeStyle;
  className?: string;
  showDot?: boolean;
}) {
  return (
    <span className={cn(badgeVariants(), style.className, className)}>
      {showDot && style.dot && (
        <span className={cn("h-1.5 w-1.5 rounded-full", style.dot)} aria-hidden />
      )}
      {style.label}
    </span>
  );
}
