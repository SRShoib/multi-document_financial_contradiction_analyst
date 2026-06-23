# filing-reconciler

A **multi-document financial contradiction analyst**. It ingests a company's filings
(10-K, 10-Q, earnings-call transcript, press release), extracts claims, reconciles them
**across documents** to surface contradictions, scores risk, and produces an analyst memo
with inline citations — gated by human-in-the-loop review and backed by a first-class
evaluation harness.

Built on **LangGraph 1.x** (durable execution + interrupt/resume), **Pydantic v2**,
**FastAPI**, and **Postgres/pgvector**. It runs **fully offline by default** — a
deterministic stub LLM and an in-memory checkpointer — so the whole pipeline, the HITL
gates, and `make eval` work with **no API keys and no external data**.

---

## Contents

- [Quickstart](#quickstart)
- [What it does (the graph)](#what-it-does-the-graph)
- [Human-in-the-loop via the API](#human-in-the-loop-via-the-api)
- [Evaluation harness](#evaluation-harness)
- [Key design decisions](#key-design-decisions) ← *reviewers start here*
- [Configuration](#configuration)
- [Durable execution & Docker](#durable-execution--docker)
- [LLM providers](#llm-providers)
- [Project layout](#project-layout)
- [Testing, lint, types](#testing-lint-types)
- [Known limitations & next steps](#known-limitations--next-steps)

---

## Quickstart

```bash
# 1. Install (uv-managed venv). If you don't have uv:  pip install uv
make install                 # or: uv sync --extra dev

# 2. Run a full analysis over the bundled sample data (no keys needed).
#    Detects contradictions, then PAUSES at the human contradiction-review gate.
make run                     # or: uv run filing-reconciler run --sample set_a

# 2b. Drive straight through both HITL gates to a final memo (non-interactive):
uv run filing-reconciler run --sample set_a --auto-approve

# 3. Run the offline evaluation harness and print the metrics.
make eval                    # or: uv run filing-reconciler eval

# 4. Serve the HITL API.
make serve                   # or: uv run uvicorn app.main:app --reload --port 8000
```

`make run` output (abridged):

```
documents ingested : 4
claims extracted   : 16
contradictions     : 3
** Paused for human review (HITL gate). **
gate: contradictions
  - [numeric_mismatch] revenue FY2023 severity=high confidence=0.97
  - [narrative_conflict] litigation FY2023 severity=high confidence=0.7
```

### Running on Windows (no `make`)

`make` isn't required — every target maps to a console command:

```powershell
uv sync --extra dev
uv run filing-reconciler run --sample set_a            # pauses at the gate
uv run filing-reconciler run --sample set_a --auto-approve
uv run filing-reconciler eval
uv run pytest
uv run ruff check .
uv run mypy filing_reconciler app
```

---

## What it does (the graph)

```
START
  └─ ingest            load filings, classify type/period, build a section index;
  │                    raw text goes to the content store, only refs into state
  └─ extract_claims    Send API fan-out: one parallel branch per document
  │                    (claims concatenate via an operator.add reducer)
  └─ reconcile         group claims by metric/topic/period ACROSS docs:
  │                      • deterministic numeric comparison (tolerance) → numeric_mismatch
  │                      • LLM judge → guidance_revision / narrative_conflict
  └─ risk_scoring      scored risk register (severity × confidence) with citations
  └─ {needs_human?}    high-severity OR confidence < 0.75  ──► hitl_contradictions  (interrupt)
  │                    everything else                      ──► draft_memo
  └─ draft_memo        structured memo with inline citations [doc_id:start-end]
  └─ critique          faithfulness check (every figure cited; no invented figures)
  └─ {reflect?}        issues AND under caps  ──► draft_memo  (loop)
  │                    else                    ──► hitl_final (interrupt)
  └─ finalize          export memo (md + json), log per-run cost & latency
END
```

State is a `TypedDict` with reducers (`filing_reconciler/state.py`). The two HITL gates are
real LangGraph `interrupt()`s; the graph is compiled with a checkpointer so a run can pause
for a human and resume later (durably, with Postgres).

---

## Human-in-the-loop via the API

A single `GraphRuntime` is held for the app's lifetime so the checkpointer persists across
requests. Full flow:

```bash
# 1. Start a run → pauses at the contradiction gate
curl -s localhost:8000/runs -H 'content-type: application/json' \
     -d '{"sample":"set_a"}'
# → {"run_id":"...", "status":"paused", "gate":"contradictions", "pending":[...]}

# 2. See what's awaiting review
curl -s localhost:8000/runs/$RUN_ID/pending

# 3. Submit decisions (confirm / reject / edit) → resumes to the final sign-off gate
curl -s localhost:8000/runs/$RUN_ID/decision -H 'content-type: application/json' \
     -d '{"decisions":[{"target_id":"num:revenue:FY2023","action":"confirm"},
                       {"target_id":"narr:litigation","action":"reject","note":"duplicate"}]}'
# → {"status":"paused", "gate":"final_memo", ...}

# 4. Approve the memo → run completes with inline citations
curl -s localhost:8000/runs/$RUN_ID/decision -H 'content-type: application/json' \
     -d '{"action":"approve"}'
# → {"status":"completed", "memo":{...}, "contradictions":3}
```

Endpoints: `POST /runs`, `GET /runs/{id}`, `GET /runs/{id}/pending`,
`POST /runs/{id}/decision`, `GET /samples`, `GET /health`. Decisions are recorded into the
run's `human_decisions` and exported by `finalize` (the online→offline feedback hook, below).

---

## Evaluation harness

The harness is a first-class deliverable, not an afterthought. It ships **3 labeled sample
sets** (`data/samples/`) with deliberately injected contradictions and ground-truth labels,
so the repo evaluates end-to-end with no external data:

| Set | Scenario | Gold contradictions |
|---|---|---|
| `set_a` | ACME FY2023 | numeric_mismatch (revenue), guidance_revision (FY2024), narrative_conflict (litigation) |
| `set_b` | Globex Q2 FY2024 | numeric_mismatch (Q2 revenue), guidance_revision (raised), narrative_conflict (litigation) |
| `set_c` | Initech FY2025 — **clean control** | none (measures false positives → precision) |

`make eval` runs the pipeline over every set and prints:

```
Contradiction detection (precision-weighted):
  precision : 1.000   (tp=6 fp=0 fn=0)
  recall    : 1.000
  F0.5      : 1.000   (beta=0.5 — false positives penalized)
Numeric-mismatch accuracy : 1.000 (8/8)
Citation exact-span match : 1.000 (12/12)
Citation LLM-judge        : supported=0.000 mean_score=0.083   (stub judge — see note)
Memo citation coverage    : 1.000 (6/6)
Confidence calibration (ECE) : 0.177 over 6 preds
```

**Metrics** (`filing_reconciler/eval/metrics.py`):
- **Precision + recall, weighted to precision** via Fβ (β=0.5) — false positives are the
  costly error for an analyst tool.
- **Numeric-mismatch accuracy** over labeled metric/period checks (true positives *and* true
  negatives — e.g. equal net-income must *not* be flagged).
- **Citation faithfulness**: exact char-span match (the citation's `quote` must equal the
  cited source slice) **and** an LLM-judge score.
- **Confidence calibration**: ECE + a reliability table.

> **Note on the LLM-judge metric.** With the offline stub, the judge is a crude token-overlap
> heuristic, so its score is low and is **reported, not gated**. The reliable faithfulness
> signal is the deterministic **exact-span match (1.000)**. Swap in `LLM_PROVIDER=anthropic`
> to get a real semantic judge.
>
> **ECE = 0.177** is a genuine calibration signal: the detector is *under-confident* on this
> set (accuracy 1.0 vs mean confidence ~0.82). That's the kind of drift the metric exists to
> surface.

**CI gate.** `tests/test_eval.py` (marked `eval`) asserts thresholds (precision == 1.0,
recall ≥ 0.95, numeric == 1.0, exact-span == 1.0, ECE ≤ 0.35); CI runs it as a dedicated step
so a detection/citation regression fails the build.

**Online → offline loop.** `finalize` writes a run record (`<run_id>.run.json`) with the
contradictions and their HITL status; `python scripts/append_overrides.py --set set_a
--run-json <path>` replays human-**confirmed** contradictions back into that set's gold
labels — so reviewer judgments become future regression tests.

**LangSmith (optional).** `filing_reconciler/eval/langsmith_eval.py` mirrors the eval set into
a LangSmith dataset and runs the metrics as evaluators when `LANGSMITH_API_KEY` is set
(`filing-reconciler eval --langsmith`); it is a no-op otherwise. Per-node tracing/cost is
emitted when `LANGSMITH_TRACING=true`.

---

## Key design decisions

These are the choices a reviewer should interrogate.

### Why deterministic numeric comparison (LLM never emits figures)

A "numeric mismatch" must be a **reproducible fact, not a model opinion**. All figures are
parsed by regex and normalized to base units in `tools/numeric.py`, then compared with a
tolerance — the LLM is *never* asked whether two numbers differ, and never asked to *produce*
a number. Extraction asks the model only for verbatim spans/topics; the value is parsed from
the cited span. This buys three things: (1) **auditability** — every numeric contradiction
traces to two char-spans and an arithmetic delta; (2) **false-positive control** — no
hallucinated figures, which is the costly error here; (3) **cost/latency** — the common case
needs no tokens. The LLM is reserved for what it's actually good at: *narrative* and
*guidance* conflicts, where judgment is required.

This split is visible in the data: on the sample sets the deterministic path nails revenue
mismatches and correctly leaves equal net-income/gross-margin alone (numeric accuracy 8/8,
zero false positives), while the LLM path handles the litigation and guidance conflicts.

### Why these HITL gates, and why *conditional*

Two gates, deliberately asymmetric:

- **`hitl_contradictions` is conditional.** Routing it on *every* contradiction would make the
  human a bottleneck and train them to rubber-stamp. Instead the gate fires only for
  contradictions that are **high-severity OR confidence < 0.75** — the ones where a false
  positive is expensive or the model is unsure. Everything else is auto-accepted and flows
  straight to drafting. On `set_a` that means the revenue mismatch (high) and the litigation
  conflict (low-confidence) go to a human, while the medium/0.8 guidance revision bypasses.
- **`hitl_final` is a lightweight sign-off** on the finished memo (approve / request changes).

Both are implemented as a **single `interrupt()` per node** carrying *all* pending items —
not one interrupt per contradiction. LangGraph matches multiple interrupts in a node by
*index*, which is brittle across re-execution; one interrupt with a list payload is robust and
gives the reviewer the whole picture at once. The gates are real durable pauses: with the
Postgres checkpointer a run can pause for a human and resume in a different process.

The human's confirm/reject/edit decisions are applied on resume (rejected contradictions are
dropped from both the memo and the risk register), recorded in state, and fed back into the
eval set via the overrides script.

### How the threshold is calibrated

The gate thresholds (`HITL_SEVERITY_THRESHOLD=high`, `HITL_CONFIDENCE_THRESHOLD=0.75`) and the
detector's confidence scores are **calibrated against the labeled eval set**, not guessed:

- Deterministic numeric mismatches are assigned **confidence 0.97** (arithmetic is reliable);
  severity scales with the %-gap (`≥15% → high`, `≥5% → medium`, …).
- LLM-detected guidance/narrative conflicts get **lower confidence** (0.8 / 0.7) because
  qualitative judgment is less certain — which is exactly what routes the litigation conflict
  (0.7 < 0.75) to a human.
- The eval harness reports **ECE + a reliability curve**, so the confidence numbers are
  measurable and tunable rather than vibes. The current set shows the detector is slightly
  under-confident (ECE 0.177) — the lever to fix that is the per-type confidence constants,
  validated by re-running `make eval`.

The numeric tolerance (`NUMERIC_TOLERANCE_PCT=0.5`) is the boundary between "rounding" and
"mismatch"; it's an env knob and is exercised by `test_reconcile.py` (the within-tolerance
case must *not* be flagged).

### Why the reflection cap (and a cost cap)

The critique→draft reflection loop is a cycle, so it needs **circuit breakers** or it can spin
forever / burn unbounded tokens:

- **Max-iteration breaker** (`MAX_REFLECTIONS=2`): after N redrafts the loop stops even if
  issues remain; the unresolved issues are recorded and surfaced at the final sign-off gate
  rather than blocking the run.
- **Hard per-run cost cap** (`COST_CAP_USD`): `cost_usd` accumulates via an `operator.add`
  reducer across every node; the reflection router refuses to loop once the cap is hit.

`should_reflect()` is a pure predicate (single source of truth for the router) and is unit-
tested directly; `test_reflection.py` drives the full loop through the graph and asserts both
that it **converges** when the issue is fixable and that the **breaker trips** (proceeding to
finalize with the issue logged) when it isn't.

### Other production guards

- **Schema validation on every structured output** (`extra="forbid"` on LLM-output models) with
  **retry-on-parse-failure** in the Anthropic provider (`tenacity`).
- **Raw text kept out of state** — only `text_ref` pointers — so the checkpointer stays small
  and long filings don't bloat every snapshot.
- **Citations stay verifiable across providers**: even the real LLM memo composer reuses the
  deterministic citation attachment; the model only rewrites prose.
- **Typed routing**: every field that drives a conditional edge is a `Literal`, and routers
  return `Literal` node names, so routing stays type-checked by mypy.

---

## Configuration

All config is read from the environment (never hardcoded). Copy `.env.example` to `.env`.
Defaults are offline-safe.

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `stub` | `stub` (offline, deterministic) or `anthropic` (real Claude) |
| `ANTHROPIC_API_KEY` | — | required when `LLM_PROVIDER=anthropic` |
| `LLM_MODEL` | `claude-opus-4-8` | analysis model (anthropic provider) |
| `LLM_JUDGE_MODEL` | `claude-haiku-4-5-20251001` | eval judge model |
| `CHECKPOINTER` | `memory` | `memory` (in-process) or `postgres` (durable) |
| `DATABASE_URL` | `postgresql://reconciler:reconciler@localhost:5432/reconciler` | used when `CHECKPOINTER=postgres` |
| `MAX_REFLECTIONS` | `2` | reflection-loop circuit breaker |
| `COST_CAP_USD` | `2.50` | hard per-run cost cap |
| `HITL_SEVERITY_THRESHOLD` | `high` | severity at/above which a contradiction needs review |
| `HITL_CONFIDENCE_THRESHOLD` | `0.75` | confidence below which a contradiction needs review |
| `NUMERIC_TOLERANCE_PCT` | `0.5` | %-gap below which figures are "equal" |
| `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` / `LANGSMITH_PROJECT` | off | optional tracing + eval upload |

---

## Durable execution & Docker

```bash
make up                      # start Postgres + pgvector (docker-compose)
# set CHECKPOINTER=postgres and DATABASE_URL in .env
make run                     # HITL pauses now survive process restarts
make down
```

`docker-compose.yml` runs `pgvector/pgvector:pg16` and enables the `vector` extension on init
(`docker/initdb/`). LangGraph's `PostgresSaver` creates its own checkpoint tables via
`.setup()` on first use (`filing_reconciler/checkpointer.py`). The `Dockerfile` builds the
FastAPI image. (Docker isn't required for the offline path — `memory` checkpointer makes
`make run` / `make eval` work without it.)

---

## LLM providers

The provider sits behind a small `LLM` Protocol (`filing_reconciler/llm.py`); nodes depend on
the interface, never a concrete client.

- **`StubLLM` (default)** — fully deterministic, no key. Numeric work is real (the tools);
  guidance/narrative judging, memo prose, and critique are deterministic heuristics. This is
  what the tests and eval exercise, so results are reproducible.
- **`AnthropicLLM`** (`providers/anthropic_llm.py`, `--extra anthropic`) — official `anthropic`
  SDK with structured outputs (`messages.parse`), `claude-opus-4-8` for analysis and
  `claude-haiku-4-5` for the judge, per-call cost from token usage, and retry-on-validation.
  It preserves the no-invented-figures and verifiable-citations guarantees.

Switching providers is a config change (`LLM_PROVIDER`), nothing else.

---

## Project layout

```
filing_reconciler/
  state.py          GraphState TypedDict + reducers (operator.add on claims/cost/errors)
  models.py         Pydantic contract (SourceDoc, Claim+Citation, Contradiction, Memo, ...)
  llm.py            LLM Protocol + deterministic StubLLM + factory
  graph.py          build_graph(): nodes, Send fan-out, conditional edges, compile
  runtime.py        GraphRuntime: checkpointer lifecycle, start/resume/drive
  checkpointer.py   memory | postgres (PostgresSaver.setup())
  config.py         env-driven Settings (pydantic-settings)
  deps.py / store.py  DI container; content store (refs, not raw text)
  nodes/            ingest, extract_claims, reconcile, risk_scoring, hitl, draft_memo,
                    critique, finalize, common (gating + reflection predicates)
  tools/            numeric (parse/compare), text (sentences/periods), extraction (candidates)
  providers/        anthropic_llm (official SDK, structured outputs)
  eval/             dataset, metrics, runner, langsmith_eval
app/main.py         FastAPI: start / pending / decision
data/samples/       set_a, set_b, set_c + labels.json
scripts/            append_overrides.py (online→offline feedback)
tests/              numeric, reconcile, reducers/e2e, routing, hitl, api, reflection, eval
```

---

## Testing, lint, types

```bash
make check          # ruff + mypy + pytest  (what CI runs)
uv run pytest -m eval     # the evaluation regression gate only
```

Tests cover the DoD surface: `reconcile` (numeric mismatch / tolerance / cross-doc /
guidance / narrative), the **reducers** (Send concatenation + cost accumulation), **routing**
(HITL gating + reflection breaker), the **reflection circuit breaker** end-to-end, the HITL
interrupt/resume cycle, and the full API flow. `ruff` + `mypy` (pydantic plugin) are clean.

---

## Known limitations & next steps

- **Extraction is heuristic, tuned to the sample corpus.** Real filings need a stronger
  extractor (the LLM provider helps, but the sentence/period heuristics in `tools/` are the
  ceiling for the stub). The deterministic numeric layer generalizes well; the candidate
  proposal does not yet.
- **pgvector retrieval is scaffolded, not yet wired into extraction.** The schema/extension are
  provisioned; semantic retrieval over very long filings is the natural next step (chunk →
  embed → retrieve relevant spans before extraction).
- **The stub LLM-judge is a placeholder** — use the Anthropic provider for a meaningful
  semantic faithfulness judge (the exact-span metric is the reliable offline signal).
- **API concurrency**: the in-memory checkpointer + single runtime is fine for a demo;
  multi-tenant production should use the Postgres checkpointer and a connection pool.
- **LangSmith online feedback** is wired for dataset + evaluators; submitting the HITL decision
  as run feedback (vs. the offline overrides loop) is a small extension.

## License

MIT.
