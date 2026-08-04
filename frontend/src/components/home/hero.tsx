"use client";

import { motion } from "framer-motion";
import { Calculator, ShieldCheck, Sparkles } from "lucide-react";

const FEATURES = [
  {
    icon: Calculator,
    title: "Deterministic figures",
    detail: "Numbers are parsed and compared with a tolerance — never invented by a model.",
  },
  {
    icon: Sparkles,
    title: "LLM narrative judgment",
    detail: "Guidance revisions and narrative conflicts get real qualitative reasoning.",
  },
  {
    icon: ShieldCheck,
    title: "Human sign-off gates",
    detail: "High-severity or low-confidence findings pause for a reviewer, every time.",
  },
];

export function Hero() {
  return (
    <div className="flex flex-col items-center gap-7 px-6 pb-4 pt-14 text-center sm:pt-20">
      <motion.span
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="inline-flex items-center gap-2 rounded-full border border-border-subtle bg-white/[0.03] px-4 py-1.5 text-xs text-foreground/60"
      >
        10-Ks · 10-Qs · earnings calls · press releases
      </motion.span>

      <motion.h1
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="max-w-3xl font-serif text-[38px] italic leading-[1.1] sm:text-[52px]"
      >
        Find where the filing{" "}
        <span className="iris-gradient-text">disagrees with itself.</span>
      </motion.h1>

      <motion.p
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.12, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="max-w-xl text-[15px] leading-relaxed text-foreground/55"
      >
        Ingest a company&rsquo;s filings, reconcile every claim across documents, and get a
        cited, risk-scored memo — with a human in the loop at every consequential decision.
      </motion.p>

      <motion.div
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2, duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
        className="mt-2 grid w-full max-w-3xl grid-cols-1 gap-3 sm:grid-cols-3"
      >
        {FEATURES.map(({ icon: Icon, title, detail }) => (
          <div key={title} className="glass-panel flex flex-col items-center gap-2 rounded-xl p-4 text-center">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/[0.04] ring-1 ring-white/10">
              <Icon className="h-4 w-4 text-iris-3" aria-hidden />
            </span>
            <span className="text-[13px] font-medium text-foreground/85">{title}</span>
            <span className="text-[11.5px] leading-snug text-foreground/45">{detail}</span>
          </div>
        ))}
      </motion.div>
    </div>
  );
}
