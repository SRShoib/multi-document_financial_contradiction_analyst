"""reconcile — group claims by metric/topic/period across docs and emit scored
Contradiction candidates.

Deterministic numeric comparison (with tolerance) handles figure mismatches; the
LLM is used only for narrative/guidance conflicts. Implemented in step 4 — this
milestone returns an empty candidate set so the pipeline flows end-to-end.
"""

from ..deps import Deps
from ..state import GraphState
from .common import Timer, metric


def reconcile(state: GraphState, deps: Deps) -> GraphState:
    with Timer() as timer:
        contradictions: list = []  # step 4: deterministic numeric + LLM narrative
    return {
        "contradictions": contradictions,
        "node_metrics": [metric("reconcile", latency_ms=timer.latency_ms)],
    }
