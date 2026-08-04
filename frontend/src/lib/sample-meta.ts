/**
 * Presentation-only metadata for the bundled sample sets, mirrored from
 * `data/samples/<set>/manifest.json`. The backend only exposes sample IDs via
 * `GET /samples`; this enriches the picker UI. Unknown sample IDs (e.g. a new
 * set added to the backend) fall back to `genericSampleMeta`.
 */

export interface SampleMeta {
  id: string;
  company: string;
  ticker: string;
  scenario: string;
  description: string;
  docCount: number;
  hasContradictions: boolean;
}

export const SAMPLE_META: Record<string, SampleMeta> = {
  set_a: {
    id: "set_a",
    company: "ACME Corporation",
    ticker: "ACME",
    scenario: "FY2023 filing set",
    description:
      "A FY2023 revenue numeric mismatch (10-K vs. press release), a FY2024 revenue guidance revision (press release vs. earnings call), and a litigation narrative conflict (10-K vs. earnings call).",
    docCount: 4,
    hasContradictions: true,
  },
  set_b: {
    id: "set_b",
    company: "Globex Corporation",
    ticker: "GLBX",
    scenario: "Q2 FY2024 filing set",
    description:
      "A Q2 revenue numeric mismatch (10-Q vs. press release), a raised FY2024 revenue guidance (press release vs. earnings call), and a litigation narrative conflict (10-K vs. earnings call).",
    docCount: 4,
    hasContradictions: true,
  },
  set_c: {
    id: "set_c",
    company: "Initech Corporation",
    ticker: "INI",
    scenario: "FY2025 clean control set",
    description:
      "Consistent figures and disclosures across every document — no injected contradictions. Used to measure false positives.",
    docCount: 2,
    hasContradictions: false,
  },
};

export function genericSampleMeta(id: string): SampleMeta {
  return {
    id,
    company: id,
    ticker: id.toUpperCase(),
    scenario: "Sample filing set",
    description: "A bundled sample document set for cross-document reconciliation.",
    docCount: 0,
    hasContradictions: true,
  };
}

export function sampleMeta(id: string): SampleMeta {
  return SAMPLE_META[id] ?? genericSampleMeta(id);
}
