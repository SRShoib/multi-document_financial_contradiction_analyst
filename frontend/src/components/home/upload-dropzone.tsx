"use client";

import * as React from "react";
import { UploadCloud } from "lucide-react";

import { cn } from "@/lib/utils";

const ACCEPTED_EXTENSIONS = [".pdf", ".txt", ".md"];

function hasAcceptedExtension(name: string): boolean {
  const lower = name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export function UploadDropzone({
  disabled,
  remainingSlots,
  onFilesSelected,
}: {
  disabled: boolean;
  remainingSlots: number;
  onFilesSelected: (files: File[]) => void;
}) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [dragDepth, setDragDepth] = React.useState(0);

  const handleFiles = (fileList: FileList | null) => {
    if (!fileList || remainingSlots <= 0) return;
    const files = Array.from(fileList);
    // Client-side pre-filter is a UX nicety only — the server re-validates
    // extension, size, and file count on every request regardless.
    const accepted = files.filter((f) => hasAcceptedExtension(f.name)).slice(0, remainingSlots);
    if (accepted.length > 0) onFilesSelected(accepted);
  };

  const open = () => {
    if (!disabled) inputRef.current?.click();
  };

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      onClick={open}
      onKeyDown={(e) => {
        if (!disabled && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          open();
        }
      }}
      onDragOver={(e) => e.preventDefault()}
      onDragEnter={(e) => {
        e.preventDefault();
        if (!disabled) setDragDepth((d) => d + 1);
      }}
      onDragLeave={(e) => {
        e.preventDefault();
        setDragDepth((d) => Math.max(0, d - 1));
      }}
      onDrop={(e) => {
        e.preventDefault();
        setDragDepth(0);
        if (!disabled) handleFiles(e.dataTransfer.files);
      }}
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-border-subtle bg-white/[0.02] p-8 text-center transition-colors",
        dragDepth > 0 && !disabled && "border-iris-2/60 bg-iris-2/[0.04]",
        disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer hover:border-white/25",
      )}
    >
      <UploadCloud className="h-6 w-6 text-foreground/40" aria-hidden />
      <p className="text-sm text-foreground/70">
        Drop filings here, or <span className="text-iris-3 underline">browse</span>
      </p>
      <p className="text-xs text-foreground/40">
        PDF, .txt, or .md — up to {remainingSlots} more file{remainingSlots === 1 ? "" : "s"}
      </p>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.txt,.md"
        className="hidden"
        disabled={disabled}
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = ""; // allow re-selecting the same file
        }}
      />
    </div>
  );
}
