# filing-reconciler

A **multi-document financial contradiction analyst**. It ingests a company's filings
(10-K, 10-Q, earnings-call transcript, press release), extracts claims, reconciles them
**across documents** to surface contradictions, scores risk, and produces an analyst memo
with citations — gated by human-in-the-loop review and backed by an evaluation harness.

> Status: under active construction. This README is filled in milestone by milestone;
> the **Key Design Decisions** section (why these HITL gates, why deterministic numeric
> comparison, why the reflection cap, how the threshold is calibrated) is written in step 8.

## Quickstart

```bash
# 1. Install (creates a venv via uv). If you don't have uv: pip install uv
make install        # or: uv sync --extra dev

# 2. Run a full analysis over the bundled sample data (no API keys needed).
#    Pauses at the human contradiction-review gate.
make run            # or: uv run filing-reconciler run --sample set_a

# 3. Run the evaluation harness against the labeled sample set.
make eval           # or: uv run filing-reconciler eval
```

Everything runs **offline by default**: a deterministic stub LLM (`LLM_PROVIDER=stub`)
and an in-memory checkpointer (`CHECKPOINTER=memory`). No secrets are ever hardcoded —
configuration is read from the environment; copy `.env.example` to `.env` to change it.

### Durable execution (optional)

```bash
make up                     # start Postgres + pgvector via docker-compose
# set CHECKPOINTER=postgres in .env, then `make run` — HITL pauses now survive restarts
```

### Running on Windows (no `make`)

`make` isn't required. Use the console script or `uv run` directly:

```powershell
uv sync --extra dev
uv run filing-reconciler run --sample set_a
uv run filing-reconciler eval
uv run pytest
uv run ruff check .
uv run mypy filing_reconciler app
```

## Architecture

`START → ingest → (Send fan-out) extract_claims → reconcile → risk_scoring →`
`{needs_human → hitl_contradictions} → draft_memo → critique →`
`{reflect → draft_memo | hitl_final} → finalize → END`, compiled with a checkpointer.

See [the spec](#) and module docstrings; details land as each node is implemented.

## Repository layout

```
filing_reconciler/   state.py, models.py, llm.py, graph.py, cli.py, config.py
  nodes/             ingest, extract_claims, reconcile, risk_scoring, hitl, draft_memo, critique, finalize
  tools/             deterministic numeric comparison; pgvector retrieval
  eval/              datasets, evaluators, metrics
app/                 FastAPI: start run / list pending reviews / submit decision
data/samples/        sample document sets with injected contradictions + ground-truth labels
tests/               reconcile, reducers, routing, reflection circuit breaker
```

## License

MIT.
