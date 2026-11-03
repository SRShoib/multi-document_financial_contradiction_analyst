"use client";

import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Loader2 } from "lucide-react";

import { API_BASE_URL } from "@/lib/api";

type Phase = "checking" | "waking" | "ready" | "hidden";

export interface ServerWakeBannerProps {
  /** API base URL; `/health` is appended. Defaults to the app-wide API base URL. */
  baseUrl?: string;
  healthPath?: string;
  /** How long to wait for a response before showing the "waking up" banner. */
  showAfterMs?: number;
  /** Interval between retries (also the per-attempt timeout). */
  retryMs?: number;
  /** How long the green "ready" message stays visible. */
  readyMs?: number;
  /** Expected worst-case cold start; only scales the progress bar. */
  expectedWakeSeconds?: number;
}

/**
 * Pings the backend on load. Free-tier hosts (e.g. Render) sleep when idle, so
 * the first request can take ~1 min. If the server doesn't answer quickly, a
 * banner explains the wait; once it answers, a short "ready" message is shown.
 */
export function ServerWakeBanner({
  baseUrl = API_BASE_URL,
  healthPath = "/health",
  showAfterMs = 1500,
  retryMs = 3000,
  readyMs = 2000,
  expectedWakeSeconds = 60,
}: ServerWakeBannerProps) {
  const [phase, setPhase] = React.useState<Phase>("checking");
  const [elapsed, setElapsed] = React.useState(0);

  React.useEffect(() => {
    const url = `${baseUrl.replace(/\/+$/, "")}${healthPath}`;
    const startedAt = Date.now();
    let cancelled = false;
    let bannerShown = false;
    let controller: AbortController | null = null;
    let tickId: ReturnType<typeof setInterval> | undefined;
    let hideId: ReturnType<typeof setTimeout> | undefined;
    let retryId: ReturnType<typeof setTimeout> | undefined;

    const readElapsed = () => Math.floor((Date.now() - startedAt) / 1000);

    const showId = setTimeout(() => {
      bannerShown = true;
      setElapsed(readElapsed());
      setPhase("waking");
      tickId = setInterval(() => setElapsed(readElapsed()), 1000);
    }, showAfterMs);

    function onReady() {
      clearTimeout(showId);
      clearInterval(tickId);
      if (!bannerShown) {
        // Answered before the banner was due: never show anything.
        setPhase("hidden");
        return;
      }
      setPhase("ready");
      hideId = setTimeout(() => setPhase("hidden"), readyMs);
    }

    async function attempt() {
      if (cancelled) return;
      controller = new AbortController();
      const abortId = setTimeout(() => controller?.abort(), retryMs);
      try {
        const res = await fetch(url, { signal: controller.signal, cache: "no-store" });
        if (cancelled) return;
        // A sleeping host's proxy may answer 5xx; only a 2xx means the app is up.
        if (res.ok) return onReady();
      } catch {
        // network error or per-attempt timeout: fall through to retry
      } finally {
        clearTimeout(abortId);
      }
      if (!cancelled) retryId = setTimeout(attempt, retryMs);
    }

    attempt();

    return () => {
      cancelled = true;
      controller?.abort();
      clearTimeout(showId);
      clearTimeout(hideId);
      clearTimeout(retryId);
      clearInterval(tickId);
    };
  }, [baseUrl, healthPath, showAfterMs, retryMs, readyMs]);

  const progress = Math.min(95, (elapsed / expectedWakeSeconds) * 100);

  return (
    <div className="pointer-events-none fixed inset-x-0 top-[4.5rem] z-50 flex justify-center px-4">
      <AnimatePresence mode="wait">
        {phase === "waking" && (
          <motion.div
            key="waking"
            role="status"
            aria-live="polite"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="glass-panel pointer-events-auto w-full max-w-md rounded-2xl px-4 py-3"
          >
            <div className="flex items-center gap-3 text-sm text-foreground">
              <Loader2 className="h-4 w-4 shrink-0 animate-spin text-iris-3" aria-hidden />
              <span className="flex-1">Server is waking up, please wait</span>
              <span className="tabular-figures text-xs text-foreground/60">{elapsed}s</span>
            </div>
            <div
              role="progressbar"
              aria-label="Server wake-up progress"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(progress)}
              className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-white/[0.06]"
            >
              <div
                className="h-full rounded-full bg-[linear-gradient(90deg,var(--iris-1),var(--iris-2),var(--iris-3))] transition-[width] duration-1000 ease-linear"
                style={{ width: `${progress}%` }}
              />
            </div>
          </motion.div>
        )}
        {phase === "ready" && (
          <motion.div
            key="ready"
            role="status"
            aria-live="polite"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="pointer-events-auto flex items-center gap-2.5 rounded-2xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300 backdrop-blur-xl"
          >
            <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden />
            Server is ready
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
