import type { Memo } from "./types";

export function memoToMarkdown(memo: Memo): string {
  const lines: string[] = [];
  lines.push(`# ${memo.title}`, "");
  const meta = [memo.company, memo.period_coverage].filter(Boolean).join(" — ");
  if (meta) lines.push(`_${meta}_`, "");
  lines.push(memo.executive_summary, "");

  for (const section of memo.sections) {
    lines.push(`## ${section.heading}`, "", section.body, "");
    for (const c of section.citations) {
      lines.push(`> [${c.doc_id}:${c.start}-${c.end}] "${c.quote}"`);
    }
    if (section.citations.length) lines.push("");
  }

  lines.push("---", `${memo.citations.length} source citation(s). Generated ${memo.created_at}.`);
  return lines.join("\n");
}
