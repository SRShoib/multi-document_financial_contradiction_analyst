# filing-reconciler — frontend

A Next.js (App Router, TypeScript) frontend for the `filing-reconciler` FastAPI backend
(`../backend/app/main.py`). It drives the full run lifecycle: pick a sample filing set (or
point at custom documents), watch the pipeline progress, resolve the two human-in-the-loop
gates (contradiction review, final memo sign-off), and read the finished, cited memo.

## Running it

The backend must be running first, from `../backend`:

```bash
cd ../backend
uv run uvicorn app.main:app --reload --port 8000
```

Then, in this directory (`frontend/`):

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). By default the app calls the API at
`http://localhost:8000`; override with `NEXT_PUBLIC_API_URL` (copy `.env.example` to
`.env.local`) if the backend runs elsewhere. The backend's `CORS_ORIGINS` setting already
allows `http://localhost:3000` by default (see `../backend/.env.example`).

If `LLM_PROVIDER=openai` is set on the backend without a real `OPENAI_API_KEY`, requests
will fail — set `LLM_PROVIDER=stub` for the deterministic offline path used by the app's own
tests and eval harness.

## What's here

- `src/app/page.tsx` — home: sample picker + an "advanced" custom-documents mode, calls
  `POST /runs`, then routes to `/runs/[runId]`.
- `src/app/runs/[runId]/page.tsx` — the run workspace: a pipeline stepper, the contradiction
  review gate, the final sign-off gate, and the completed memo view. It re-fetches
  `GET /runs/{id}` on load so a refreshed/shared URL rehydrates correctly.
- `src/lib/types.ts` / `src/lib/api.ts` — a hand-mirrored TypeScript copy of the Pydantic
  contract in `../backend/filing_reconciler/models.py` + `../backend/app/main.py`. Keep both
  in sync if the backend contract changes.
- `src/components/pipeline/` — maps `{status, gate}` from `RunStatus`, plus which decision
  request is currently in flight, onto a 6-stage visual (no server-sent progress events exist;
  each backend call is a single synchronous graph `invoke`, so the "current" stage reflects
  the real in-flight request, not a simulated timer).
- `src/components/runs/` — contradiction cards (confirm/reject/edit with severity/confidence
  overrides), the memo renderer, citation chips (click to expand the cited quote), and the
  numeric-mismatch comparison (a labeled stat-pair + severity-colored delta, not a chart —
  there are only ever two competing figures to show).
- `src/components/home/` — the sample picker, plus the "advanced" panel with two ways to
  supply custom documents:
  - **Upload** (`upload-panel.tsx`, `upload-dropzone.tsx`, `document-card.tsx`,
    `upload-types.ts`) — drag-and-drop PDF/.txt/.md, which calls `POST /documents` (real
    upload — no filesystem access needed) and requires the user to tag each file's document
    type + period before a run can start. Tagging is enforced, not just offered: the
    reconciliation engine groups claims by an *exact* period-string match, so an untagged or
    mistagged document is a silent missed contradiction rather than a visible error.
  - **JSON paths** (behind a "paste server paths instead" toggle) — the original ops/CLI-
    adjacent mode: a `path` readable by the *API server* itself, still useful for filings
    already on the machine the server runs on.

## Design notes

Dark-only, glass-panel surfaces over an animated aurora background (`globals.css` /
`components/chrome/background-fx.tsx`, pure CSS keyframes — no client JS cost). Severity,
status, and detection-method badges are centralized in `lib/badges.ts` so color meaning stays
consistent everywhere a `Contradiction` is rendered.
