"use client";

import Link from "next/link";
import { GitCompareArrows } from "lucide-react";

import { EngineStatus } from "@/components/chrome/engine-status";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-border-subtle bg-background/70 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link href="/" className="group flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-[linear-gradient(135deg,var(--iris-1),var(--iris-2)_60%,var(--iris-3))] shadow-[0_4px_16px_-4px_rgba(99,102,241,0.6)] transition-transform duration-300 group-hover:scale-105 group-hover:rotate-3">
            <GitCompareArrows className="h-4.5 w-4.5 text-white" strokeWidth={2.25} aria-hidden />
          </span>
          <span className="flex flex-col leading-none">
            <span className="text-[15px] font-semibold tracking-tight text-foreground">
              Filing Reconciler
            </span>
            <span className="text-[11px] text-foreground/45">
              Cross-document contradiction analyst
            </span>
          </span>
        </Link>
        <EngineStatus />
      </div>
    </header>
  );
}
