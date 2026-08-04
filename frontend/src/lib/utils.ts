import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPercent(value: number, digits = 1): string {
  return `${value.toFixed(digits)}%`;
}

export function formatConfidence(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatUsd(value: number): string {
  if (value < 0.01 && value > 0) {
    return `$${value.toFixed(4)}`;
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(value);
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}

export function formatDateTime(iso: string): string {
  try {
    return new Intl.DateTimeFormat("en-US", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function titleCase(input: string): string {
  return input
    .replace(/[_.]/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(" ");
}

export function ctypeLabel(ctype: string): string {
  const map: Record<string, string> = {
    numeric_mismatch: "Numeric mismatch",
    guidance_revision: "Guidance revision",
    narrative_conflict: "Narrative conflict",
    omission: "Omission",
  };
  return map[ctype] ?? titleCase(ctype);
}

export function statusLabel(status: string): string {
  const map: Record<string, string> = {
    pending: "Pending review",
    confirmed: "Confirmed",
    rejected: "Rejected",
    edited: "Edited",
    auto_accepted: "Auto-accepted",
  };
  return map[status] ?? titleCase(status);
}
