"""Reflection loop end-to-end: convergence and the circuit breaker.

Uses small StubLLM subclasses whose composer injects an uncited (thus unfaithful)
figure, so the critique→draft loop is actually exercised through the graph.
"""

import uuid
from pathlib import Path
from typing import Any

from filing_reconciler.config import Settings
from filing_reconciler.deps import Deps
from filing_reconciler.graph import build_graph
from filing_reconciler.llm import StubLLM
from filing_reconciler.models import MemoSection
from filing_reconciler.runtime import auto_confirm_decider
from filing_reconciler.samples import load_sample
from filing_reconciler.store import FileContentStore
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

_BOGUS = MemoSection(heading="Bogus", body="Revenue was $9,999 million.", citations=[])


class _ConvergingLLM(StubLLM):
    """Adds an uncited figure on the first draft; clean once revision notes arrive."""

    def compose_memo(self, *, context: Any) -> Any:
        gen = super().compose_memo(context=context)
        if not context.revision_notes:
            gen.value.sections.append(_BOGUS.model_copy())
        return gen


class _AlwaysBadLLM(StubLLM):
    """Never fixes the unfaithful figure → the loop must hit the breaker."""

    def compose_memo(self, *, context: Any) -> Any:
        gen = super().compose_memo(context=context)
        gen.value.sections.append(_BOGUS.model_copy())
        return gen


def _deps(tmp_path: Path, llm: StubLLM) -> Deps:
    settings = Settings(
        _env_file=None,
        content_store_dir=str(tmp_path / "c"),
        output_dir=str(tmp_path / "o"),
    )
    return Deps(settings=settings, llm=llm, store=FileContentStore(settings.content_store_dir))


def _drive(graph: Any, inputs: Any, company: str) -> dict[str, Any]:
    tid = uuid.uuid4().hex
    cfg = {"configurable": {"thread_id": tid}}
    result = graph.invoke({"inputs": inputs, "run_id": tid, "company": company}, cfg)
    for _ in range(12):
        pending = [getattr(i, "value", i) for i in (result.get("__interrupt__") or [])]
        if not pending:
            break
        result = graph.invoke(Command(resume=auto_confirm_decider(pending[0])), cfg)
    return result


def test_reflection_loop_converges(tmp_path: Path) -> None:
    deps = _deps(tmp_path, _ConvergingLLM())
    graph = build_graph(deps, checkpointer=InMemorySaver())
    company, inputs = load_sample("set_a")

    result = _drive(graph, inputs, company)

    assert "__interrupt__" not in result
    assert result["reflection_count"] == 1  # a single redraft fixed the issue
    assert result["critique_issues"] == []  # converged
    assert result["final_memo"] is not None


def test_reflection_circuit_breaker_trips(tmp_path: Path) -> None:
    deps = _deps(tmp_path, _AlwaysBadLLM())
    graph = build_graph(deps, checkpointer=InMemorySaver())
    company, inputs = load_sample("set_a")

    result = _drive(graph, inputs, company)

    assert "__interrupt__" not in result
    # Breaker caps redrafts at max_reflections and proceeds despite unresolved issues.
    assert result["reflection_count"] == deps.settings.max_reflections
    assert result["critique_issues"]
    assert result["final_memo"] is not None
    assert any("unresolved" in e for e in result.get("errors", []))
