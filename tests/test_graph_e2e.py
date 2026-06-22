"""End-to-end skeleton run + reducer behaviour over the sample data (stub LLM)."""

import uuid
from pathlib import Path

from filing_reconciler.config import Settings
from filing_reconciler.deps import make_deps
from filing_reconciler.graph import build_graph
from filing_reconciler.samples import load_sample
from langgraph.checkpoint.memory import InMemorySaver


def _runtime_graph(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        content_store_dir=str(tmp_path / "content"),
        output_dir=str(tmp_path / "out"),
    )
    deps = make_deps(settings)
    return build_graph(deps, checkpointer=InMemorySaver())


def test_e2e_detects_contradictions_then_pauses(tmp_path: Path) -> None:
    graph = _runtime_graph(tmp_path)
    company, inputs = load_sample("set_a")
    tid = uuid.uuid4().hex

    result = graph.invoke(
        {"inputs": inputs, "run_id": tid, "company": company},
        {"configurable": {"thread_id": tid}},
    )

    # Detection (ingest → Send fan-out → reconcile → risk) runs, then the graph
    # pauses at the HITL contradiction gate (resume/completion is covered in test_hitl).
    assert "__interrupt__" in result
    assert len(result["sources"]) == 4
    # operator.add reducer concatenated the parallel Send branches.
    assert len(result["claims"]) > 4
    # cost_usd add-reducer accumulated synthetic stub cost across nodes.
    assert result["cost_usd"] > 0

    # The three injected contradictions are detected, one of each type, no false positives.
    ctypes = {c.ctype for c in result["contradictions"]}
    assert ctypes == {"numeric_mismatch", "guidance_revision", "narrative_conflict"}
    assert len(result["contradictions"]) == 3
