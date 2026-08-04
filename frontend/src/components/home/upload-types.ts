/**
 * Client-only types for the upload flow. Kept separate from `lib/types.ts`,
 * which the frontend README documents as a pure hand-mirror of the backend
 * Pydantic contract — none of this shape crosses the wire as-is.
 */

import type { UploadedDoc } from "@/lib/types";

export type StageStatus = "staged" | "uploading" | "ready" | "error";

export interface StagedDoc {
  /** Stable React key; never sent to the server. */
  key: string;
  file: File;
  status: StageStatus;
  path?: string;
  doc_id?: string;
  charLen?: number;
  truncated?: boolean;
  error?: string;
  /** User-controlled tags — required (non-empty) before a run can start. */
  docType: string;
  period: string;
}

// Values must exactly match the strings `classify_doc_type` accepts
// (filing_reconciler/models.py `DOC_TYPES`) — any hint is passed straight
// through to the reconciliation engine, so a typo here silently becomes the
// document's type.
export const DOC_TYPE_OPTIONS = [
  { value: "10-K", label: "10-K (annual report)" },
  { value: "10-Q", label: "10-Q (quarterly report)" },
  { value: "press_release", label: "Press release" },
  { value: "earnings_call", label: "Earnings call transcript" },
] as const;

export function stagedFromFile(file: File): StagedDoc {
  return {
    key: crypto.randomUUID(),
    file,
    status: "staged",
    docType: "",
    period: "",
  };
}

/** Merge an upload response entry onto its staged file. Guesses only ever
 * fill an EMPTY tag — they default the form, they never override the user. */
export function applyUploadResult(doc: StagedDoc, uploaded: UploadedDoc): StagedDoc {
  return {
    ...doc,
    status: "ready",
    path: uploaded.path,
    doc_id: uploaded.doc_id,
    charLen: uploaded.char_len,
    truncated: uploaded.truncated,
    docType: doc.docType || uploaded.doc_type_guess || "",
    period: doc.period || uploaded.period_guess || "",
  };
}
