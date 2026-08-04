# filing-reconciler

A **multi-document financial contradiction analyst**: ingest a company's filings (10-K,
10-Q, earnings-call transcript, press release), reconcile claims **across documents** to
surface contradictions, score risk, and produce a cited analyst memo — gated by
human-in-the-loop review.

This is a two-part repo:

| | |
|---|---|
| [`backend/`](backend/README.md) | The engine: LangGraph pipeline, FastAPI HITL API, evaluation harness. Runs fully offline by default (deterministic stub LLM, no API keys). **Start here** — it has the full design writeup. |
| [`frontend/`](frontend/README.md) | A Next.js UI over the API: sample picker, pipeline view, both HITL gates, and the final memo view. |

## Quickstart

```bash
# Terminal 1 — backend (see backend/README.md for the non-make Windows path)
cd backend
make install
make serve            # http://localhost:8000

# Terminal 2 — frontend
cd frontend
npm install
npm run dev            # http://localhost:3000
```

Open `http://localhost:3000`, pick a bundled sample set, and work through the pipeline.

For the pipeline design, HITL gate semantics, evaluation metrics, and configuration, see
[`backend/README.md`](backend/README.md). For the UI's structure and design notes, see
[`frontend/README.md`](frontend/README.md).

## License

MIT.
