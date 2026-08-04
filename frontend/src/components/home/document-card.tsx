"use client";

import { AlertCircle, FileText, Loader2, X } from "lucide-react";

import { cn } from "@/lib/utils";
import { DOC_TYPE_OPTIONS, type StagedDoc } from "./upload-types";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function DocumentCard({
  doc,
  onChange,
  onRemove,
}: {
  doc: StagedDoc;
  onChange: (patch: Partial<StagedDoc>) => void;
  onRemove: () => void;
}) {
  const untagged = doc.status === "ready" && (!doc.docType || !doc.period.trim());

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border-subtle bg-black/15 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <FileText className="h-4 w-4 shrink-0 text-foreground/40" aria-hidden />
          <div className="flex min-w-0 flex-col">
            <span className="truncate text-sm text-foreground/85">{doc.file.name}</span>
            <span className="text-[11px] text-foreground/40">{formatBytes(doc.file.size)}</span>
          </div>
        </div>
        <button
          type="button"
          onClick={onRemove}
          className="shrink-0 rounded-md p-1 text-foreground/40 transition-colors hover:bg-white/5 hover:text-foreground/80"
          aria-label={`Remove ${doc.file.name}`}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {doc.status === "uploading" && (
        <div className="flex items-center gap-2 text-xs text-foreground/50">
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> Uploading…
        </div>
      )}

      {doc.status === "error" && (
        <div className="flex items-start gap-2 text-xs text-rose-300">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          {doc.error ?? "Upload failed."}
        </div>
      )}

      {doc.truncated && (
        <div className="flex items-start gap-2 text-xs text-amber-300">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          Only the first {doc.charLen?.toLocaleString()} characters will be analyzed — this
          document was truncated.
        </div>
      )}

      {doc.status === "ready" && (
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-xs text-foreground/50">
            Document type
            <select
              value={doc.docType}
              onChange={(e) => onChange({ docType: e.target.value })}
              className={cn(
                "rounded-md border bg-surface px-2.5 py-1.5 text-sm text-foreground outline-none focus:border-iris-2/60",
                doc.docType ? "border-border-subtle" : "border-amber-400/40",
              )}
            >
              <option value="" disabled>
                Select…
              </option>
              {DOC_TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-foreground/50">
            Period
            <input
              value={doc.period}
              onChange={(e) => onChange({ period: e.target.value })}
              placeholder="FY2024 or Q2-FY2024"
              className={cn(
                "rounded-md border bg-black/15 px-2.5 py-1.5 text-sm text-foreground placeholder:text-foreground/25 outline-none focus:border-iris-2/60",
                doc.period.trim() ? "border-border-subtle" : "border-amber-400/40",
              )}
            />
          </label>
        </div>
      )}

      {untagged && (
        <p className="text-[11px] text-amber-300">
          Tag this document&rsquo;s type and period before starting the analysis.
        </p>
      )}
    </div>
  );
}
