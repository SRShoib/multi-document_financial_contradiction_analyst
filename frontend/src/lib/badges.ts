import type { DetectedBy, ReviewStatus, Severity } from "./types";

export interface BadgeStyle {
  label: string;
  className: string;
  dot?: string;
}

export const SEVERITY_STYLE: Record<Severity, BadgeStyle> = {
  low: {
    label: "Low",
    className: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/30",
    dot: "bg-emerald-400",
  },
  medium: {
    label: "Medium",
    className: "bg-amber-400/10 text-amber-300 ring-amber-400/30",
    dot: "bg-amber-400",
  },
  high: {
    label: "High",
    className: "bg-orange-400/10 text-orange-300 ring-orange-400/30",
    dot: "bg-orange-400",
  },
  critical: {
    label: "Critical",
    className: "bg-rose-500/15 text-rose-300 ring-rose-400/40",
    dot: "bg-rose-400",
  },
};

export const STATUS_STYLE: Record<ReviewStatus, BadgeStyle> = {
  pending: {
    label: "Pending review",
    className: "bg-slate-400/10 text-slate-300 ring-slate-400/30",
  },
  confirmed: {
    label: "Confirmed",
    className: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/30",
  },
  rejected: {
    label: "Rejected",
    className: "bg-rose-500/10 text-rose-300 ring-rose-400/30",
  },
  edited: {
    label: "Edited",
    className: "bg-amber-400/10 text-amber-300 ring-amber-400/30",
  },
  auto_accepted: {
    label: "Auto-accepted",
    className: "bg-cyan-400/10 text-cyan-300 ring-cyan-400/30",
  },
};

export const DETECTED_BY_STYLE: Record<DetectedBy, BadgeStyle> = {
  deterministic: {
    label: "Deterministic",
    className: "bg-cyan-400/10 text-cyan-300 ring-cyan-400/30",
  },
  llm: {
    label: "LLM judgment",
    className: "bg-violet-400/10 text-violet-300 ring-violet-400/30",
  },
};
