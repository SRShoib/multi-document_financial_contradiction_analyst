"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { AlertTriangle, ArrowRight, RotateCw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Hero } from "@/components/home/hero";
import { SampleCard } from "@/components/home/sample-card";
import { AdvancedInputs } from "@/components/home/advanced-inputs";
import type { StagedDoc } from "@/components/home/upload-types";
import { api, ApiError, isNetworkError } from "@/lib/api";
import { sampleMeta } from "@/lib/sample-meta";
import type { DocInput } from "@/lib/types";

function messageFor(err: unknown): string {
  if (err instanceof ApiError) return err.detail;
  if (isNetworkError(err)) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong.";
}

function parseCustomInputs(json: string): { inputs: DocInput[] } | { error: string } {
  if (!json.trim()) return { error: "Paste a JSON array of documents, or pick a sample above instead." };
  let parsed: unknown;
  try {
    parsed = JSON.parse(json);
  } catch {
    return { error: "That isn't valid JSON." };
  }
  if (!Array.isArray(parsed) || parsed.length === 0) {
    return { error: "Expected a non-empty JSON array of documents." };
  }
  for (const [i, doc] of parsed.entries()) {
    if (typeof doc !== "object" || doc === null || typeof (doc as { path?: unknown }).path !== "string") {
      return { error: `Document at index ${i} is missing a string "path".` };
    }
  }
  return { inputs: parsed as DocInput[] };
}

export function HomeView() {
  const router = useRouter();
  const [samples, setSamples] = React.useState<string[] | null>(null);
  const [loadingSamples, setLoadingSamples] = React.useState(true);
  const [samplesError, setSamplesError] = React.useState<string | null>(null);

  const [selected, setSelected] = React.useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = React.useState(false);
  const [company, setCompany] = React.useState("");
  const [docs, setDocs] = React.useState<StagedDoc[]>([]);
  const [useJsonMode, setUseJsonMode] = React.useState(false);
  const [inputsJson, setInputsJson] = React.useState("");
  const [starting, setStarting] = React.useState(false);

  const loadSamples = React.useCallback(async () => {
    setLoadingSamples(true);
    setSamplesError(null);
    try {
      const res = await api.samples();
      setSamples(res.samples);
      if (res.samples.length > 0) setSelected((prev) => prev ?? res.samples[0]);
    } catch (err) {
      setSamplesError(messageFor(err));
    } finally {
      setLoadingSamples(false);
    }
  }, []);

  React.useEffect(() => {
    // Standard fetch-on-mount: loadSamples sets state once its request resolves,
    // not synchronously during this effect's execution.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadSamples();
  }, [loadSamples]);

  const readyDocs = docs.filter((d) => d.status === "ready");
  const anyUploading = docs.some((d) => d.status === "uploading");
  const allReadyTagged = readyDocs.every((d) => d.docType && d.period.trim());

  const usingUpload = advancedOpen && !useJsonMode && docs.length > 0;
  const usingJson = advancedOpen && useJsonMode && inputsJson.trim().length > 0;
  const usingAdvanced = usingUpload || usingJson;

  const customParse = usingJson ? parseCustomInputs(inputsJson) : null;
  const customError = customParse && "error" in customParse ? customParse.error : null;

  const canStart = usingJson
    ? !!customParse && !("error" in customParse)
    : usingUpload
      ? readyDocs.length > 0 && allReadyTagged && !anyUploading
      : !!selected;

  const startRun = async () => {
    setStarting(true);
    try {
      let status;
      if (usingJson && customParse && "inputs" in customParse) {
        status = await api.startRun({
          inputs: customParse.inputs,
          company: company.trim() || undefined,
        });
      } else if (usingUpload) {
        // Built explicitly field-by-field, never by spreading a StagedDoc: DocInput
        // is `extra="forbid"` server-side, so a stray client-only key (file,
        // status, key, charLen...) would 422 with an opaque validation error.
        const inputs: DocInput[] = readyDocs.map((d) => ({
          path: d.path!,
          doc_id: d.doc_id,
          doc_type: d.docType,
          period: d.period,
        }));
        status = await api.startRun({ inputs, company: company.trim() || undefined });
      } else {
        status = await api.startRun({ sample: selected! });
      }
      toast.success("Run started — paused where a human is needed");
      router.push(`/runs/${status.run_id}`);
    } catch (err) {
      toast.error(messageFor(err));
      setStarting(false);
    }
  };

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-10 px-6 pb-20">
      <Hero />

      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium uppercase tracking-wide text-foreground/45">
            Pick a bundled sample set
          </h2>
          {samples && (
            <span className="text-xs text-foreground/35">{samples.length} available, no API key needed</span>
          )}
        </div>

        {samplesError && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center justify-between gap-3 rounded-2xl border border-rose-400/25 bg-rose-500/[0.06] p-4"
          >
            <div className="flex items-center gap-2.5 text-sm text-rose-200">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              {samplesError}
            </div>
            <Button variant="outline" size="sm" onClick={loadSamples}>
              <RotateCw className="h-3.5 w-3.5" /> Retry
            </Button>
          </motion.div>
        )}

        {loadingSamples && !samples && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Skeleton className="h-48 rounded-2xl" />
            <Skeleton className="h-48 rounded-2xl" />
            <Skeleton className="h-48 rounded-2xl" />
          </div>
        )}

        {samples && samples.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {samples.map((id, i) => (
              <SampleCard
                key={id}
                meta={sampleMeta(id)}
                selected={!usingAdvanced && selected === id}
                onSelect={() => {
                  setSelected(id);
                  setAdvancedOpen(false);
                }}
                index={i}
              />
            ))}
          </div>
        )}

        {samples && samples.length === 0 && !samplesError && (
          <p className="text-sm text-foreground/45">
            No bundled sample sets were found on the server — use the advanced option below.
          </p>
        )}
      </div>

      <AdvancedInputs
        open={advancedOpen}
        onToggle={() => setAdvancedOpen((v) => !v)}
        company={company}
        onCompanyChange={setCompany}
        docs={docs}
        onDocsChange={setDocs}
        useJsonMode={useJsonMode}
        onToggleJsonMode={() => setUseJsonMode((v) => !v)}
        inputsJson={inputsJson}
        onInputsJsonChange={setInputsJson}
        jsonError={advancedOpen && useJsonMode ? customError : null}
      />

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="sticky bottom-6 flex justify-center"
      >
        <Button size="lg" onClick={startRun} disabled={!canStart} loading={starting} className="shadow-2xl">
          Start analysis <ArrowRight className="h-4 w-4" />
        </Button>
      </motion.div>
    </div>
  );
}
