"use client";

import { AnimatePresence, motion } from "framer-motion";
import { AlertCircle, ChevronDown, FlaskConical } from "lucide-react";

import { cn } from "@/lib/utils";
import { UploadPanel } from "./upload-panel";
import type { StagedDoc } from "./upload-types";

// Paths must resolve inside the API server's DOCUMENTS_ROOT (default: ./data), so
// the example points at the bundled corpus rather than an arbitrary local drive.
const PLACEHOLDER = `[
  { "path": "data/samples/set_a/10k_fy2023.txt", "doc_id": "ACME_10K_FY2023", "doc_type": "10-K", "period": "FY2023" },
  { "path": "data/samples/set_a/press_release_fy2023.txt", "doc_id": "ACME_PR_FY2023", "doc_type": "press_release", "period": "FY2023" }
]`;

export function AdvancedInputs({
  open,
  onToggle,
  company,
  onCompanyChange,
  docs,
  onDocsChange,
  useJsonMode,
  onToggleJsonMode,
  inputsJson,
  onInputsJsonChange,
  jsonError,
}: {
  open: boolean;
  onToggle: () => void;
  company: string;
  onCompanyChange: (v: string) => void;
  docs: StagedDoc[];
  onDocsChange: (docs: StagedDoc[]) => void;
  useJsonMode: boolean;
  onToggleJsonMode: () => void;
  inputsJson: string;
  onInputsJsonChange: (v: string) => void;
  jsonError: string | null;
}) {
  return (
    <div className="glass-panel rounded-2xl">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between gap-3 p-5 text-left"
      >
        <span className="flex items-center gap-2.5 text-sm font-medium text-foreground/85">
          <FlaskConical className="h-4 w-4 text-iris-3" />
          Advanced: analyze your own documents
        </span>
        <ChevronDown
          className={cn("h-4 w-4 text-foreground/40 transition-transform duration-300", open && "rotate-180")}
        />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div className="flex flex-col gap-4 border-t border-border-subtle p-5 pt-4">
              <p className="text-xs leading-relaxed text-foreground/45">
                Upload PDF, .txt, or .md filings, then tag each one&rsquo;s document type and
                period — cross-document reconciliation only compares claims that share an
                identical period label.
              </p>

              <label className="flex flex-col gap-1.5 text-xs text-foreground/50">
                Company (optional)
                <input
                  value={company}
                  onChange={(e) => onCompanyChange(e.target.value)}
                  placeholder="e.g. Acme Corporation"
                  className="rounded-md border border-border-subtle bg-black/15 px-3 py-2 text-sm text-foreground placeholder:text-foreground/25 outline-none focus:border-iris-2/60"
                />
              </label>

              {!useJsonMode && <UploadPanel docs={docs} onDocsChange={onDocsChange} />}

              <button
                type="button"
                onClick={onToggleJsonMode}
                className="self-start text-[11px] text-foreground/40 underline underline-offset-2 hover:text-foreground/70"
              >
                {useJsonMode ? "Use the upload panel instead" : "Paste server paths instead"}
              </button>

              {useJsonMode && (
                <>
                  <p className="text-xs leading-relaxed text-foreground/45">
                    Each document needs a file{" "}
                    <code className="rounded bg-white/10 px-1 py-0.5">path</code> readable by the
                    API server itself (not your browser) — this is the ops/CLI-adjacent path, for
                    filings already sitting on the machine the server runs on. For safety the
                    server only accepts paths inside its{" "}
                    <code className="rounded bg-white/10 px-1 py-0.5">DOCUMENTS_ROOT</code>{" "}
                    directory (<code className="rounded bg-white/10 px-1 py-0.5">./data</code> by
                    default); anything outside is rejected.
                  </p>
                  <label className="flex flex-col gap-1.5 text-xs text-foreground/50">
                    Documents (JSON array)
                    <textarea
                      value={inputsJson}
                      onChange={(e) => onInputsJsonChange(e.target.value)}
                      placeholder={PLACEHOLDER}
                      rows={7}
                      spellCheck={false}
                      className="resize-y rounded-md border border-border-subtle bg-black/25 px-3 py-2 font-mono text-[12.5px] leading-relaxed text-foreground/85 placeholder:text-foreground/25 outline-none focus:border-iris-2/60"
                    />
                  </label>
                  {jsonError && (
                    <div className="flex items-center gap-2 text-xs text-rose-300">
                      <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                      {jsonError}
                    </div>
                  )}
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
