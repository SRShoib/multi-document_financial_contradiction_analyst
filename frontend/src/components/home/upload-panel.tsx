"use client";

import { AlertTriangle } from "lucide-react";

import { api, ApiError, isNetworkError } from "@/lib/api";
import { DocumentCard } from "./document-card";
import { UploadDropzone } from "./upload-dropzone";
import { applyUploadResult, stagedFromFile, type StagedDoc } from "./upload-types";

const MAX_FILES = 8; // mirrors the backend's default MAX_UPLOAD_FILES; the server is authoritative

function messageFor(err: unknown): string {
  if (err instanceof ApiError) return err.detail;
  if (isNetworkError(err)) return err.message;
  if (err instanceof Error) return err.message;
  return "Upload failed.";
}

export function UploadPanel({
  docs,
  onDocsChange,
}: {
  docs: StagedDoc[];
  onDocsChange: (docs: StagedDoc[]) => void;
}) {
  const remainingSlots = Math.max(0, MAX_FILES - docs.length);

  const handleFilesSelected = async (files: File[]) => {
    const newDocs = files.map(stagedFromFile).map((d) => ({ ...d, status: "uploading" as const }));
    const withStaged = [...docs, ...newDocs];
    onDocsChange(withStaged);

    try {
      const result = await api.uploadDocuments(files);
      const next = withStaged.map((d) => {
        const localIndex = newDocs.findIndex((nd) => nd.key === d.key);
        if (localIndex === -1) return d; // not part of this batch — leave untouched
        const uploaded = result.documents.find((u) => u.index === localIndex);
        if (uploaded) return applyUploadResult(d, uploaded);
        const rejected = result.rejected.find((r) => r.index === localIndex);
        return rejected ? { ...d, status: "error" as const, error: rejected.reason } : d;
      });
      onDocsChange(next);
    } catch (err) {
      const message = messageFor(err);
      const next = withStaged.map((d) =>
        newDocs.some((nd) => nd.key === d.key)
          ? { ...d, status: "error" as const, error: message }
          : d,
      );
      onDocsChange(next);
    }
  };

  const removeDoc = (key: string) => onDocsChange(docs.filter((d) => d.key !== key));

  const patchDoc = (key: string, patch: Partial<StagedDoc>) =>
    onDocsChange(docs.map((d) => (d.key === key ? { ...d, ...patch } : d)));

  const readyDocs = docs.filter((d) => d.status === "ready");
  const distinctPeriods = new Set(readyDocs.map((d) => d.period.trim()).filter(Boolean));
  // Cross-document numeric reconciliation groups claims by an EXACT period-string
  // match (reconcile_numeric groups on (topic, period, unit)) — if every ready
  // document has a different period label, nothing will ever be compared, and
  // that failure mode is otherwise completely invisible until the memo comes
  // back with zero contradictions.
  const showPeriodNudge = readyDocs.length >= 2 && distinctPeriods.size === readyDocs.length;

  return (
    <div className="flex flex-col gap-4">
      <UploadDropzone
        disabled={remainingSlots <= 0}
        remainingSlots={remainingSlots}
        onFilesSelected={handleFilesSelected}
      />

      {docs.length > 0 && (
        <div className="flex flex-col gap-3">
          {docs.map((doc) => (
            <DocumentCard
              key={doc.key}
              doc={doc}
              onChange={(patch) => patchDoc(doc.key, patch)}
              onRemove={() => removeDoc(doc.key)}
            />
          ))}
        </div>
      )}

      {showPeriodNudge && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-400/25 bg-amber-400/[0.05] p-3 text-xs text-amber-200">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          No two documents share a period. Cross-document numeric reconciliation only
          compares claims with identical period labels — contradictions between these
          files will not be detected unless at least two share the same period tag.
        </div>
      )}
    </div>
  );
}
