"use client";

import * as React from "react";
import { motion } from "framer-motion";

import { api, isNetworkError } from "@/lib/api";
import { cn } from "@/lib/utils";

type Status = "checking" | "online" | "offline";

export function EngineStatus() {
  const [status, setStatus] = React.useState<Status>("checking");

  React.useEffect(() => {
    let cancelled = false;

    async function ping() {
      try {
        await api.health();
        if (!cancelled) setStatus("online");
      } catch (err) {
        if (!cancelled) setStatus(isNetworkError(err) ? "offline" : "offline");
      }
    }

    ping();
    const id = setInterval(ping, 20_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const label =
    status === "checking" ? "Checking engine…" : status === "online" ? "Engine online" : "Engine offline";
  const dotClass =
    status === "online"
      ? "bg-emerald-400 text-emerald-400"
      : status === "offline"
        ? "bg-rose-400 text-rose-400"
        : "bg-amber-400 text-amber-400";

  return (
    <motion.div
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      className="inline-flex items-center gap-2 rounded-full border border-border-subtle bg-white/[0.03] px-3 py-1.5 text-xs text-foreground/70"
      title={label}
    >
      <span className={cn("relative flex h-2 w-2")}>
        <span className={cn("absolute inline-flex h-full w-full rounded-full opacity-75", status !== "checking" && "animate-pulse-ring", dotClass)} />
        <span className={cn("relative inline-flex h-2 w-2 rounded-full", dotClass)} />
      </span>
      <span className="hidden sm:inline">{label}</span>
    </motion.div>
  );
}
