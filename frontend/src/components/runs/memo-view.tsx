import { CalendarClock, Quote, RefreshCw } from "lucide-react";

import { CitationRow } from "@/components/runs/citation-row";
import type { Memo } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

export function MemoView({ memo }: { memo: Memo }) {
  return (
    <article className="flex flex-col gap-8">
      <header className="flex flex-col gap-3 border-b border-border-subtle pb-6">
        <h2 className="font-serif text-[28px] italic leading-tight text-foreground sm:text-[32px]">
          {memo.title}
        </h2>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-foreground/50">
          {memo.company && <span className="font-medium text-foreground/70">{memo.company}</span>}
          {memo.period_coverage && <span>{memo.period_coverage}</span>}
          <span className="inline-flex items-center gap-1.5 text-xs">
            <CalendarClock className="h-3.5 w-3.5" aria-hidden />
            {formatDateTime(memo.created_at)}
          </span>
          {memo.reflection_count > 0 && (
            <span className="inline-flex items-center gap-1.5 text-xs">
              <RefreshCw className="h-3.5 w-3.5" aria-hidden />
              {memo.reflection_count} reflection pass{memo.reflection_count === 1 ? "" : "es"}
            </span>
          )}
        </div>
      </header>

      <div className="flex gap-3 rounded-xl border border-iris-2/20 bg-iris-2/[0.05] p-4">
        <Quote className="mt-0.5 h-4 w-4 shrink-0 text-iris-3" aria-hidden />
        <p className="text-[15px] leading-relaxed text-foreground/90">{memo.executive_summary}</p>
      </div>

      <div className="flex flex-col gap-6">
        {memo.sections.map((section, i) => (
          <section key={`${section.heading}-${i}`} className="flex flex-col gap-2.5">
            <h3 className="text-[15px] font-semibold text-foreground/95">{section.heading}</h3>
            <p className="whitespace-pre-line text-sm leading-relaxed text-foreground/70">
              {section.body}
            </p>
            <CitationRow citations={section.citations} />
          </section>
        ))}
      </div>

      {memo.citations.length > 0 && (
        <footer className="border-t border-border-subtle pt-4 text-xs text-foreground/40">
          {memo.citations.length} source citation{memo.citations.length === 1 ? "" : "s"} across{" "}
          {new Set(memo.citations.map((c) => c.doc_id)).size} document
          {new Set(memo.citations.map((c) => c.doc_id)).size === 1 ? "" : "s"}.
        </footer>
      )}
    </article>
  );
}
