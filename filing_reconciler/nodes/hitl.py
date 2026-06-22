"""Human-in-the-loop gates.

* ``hitl_contradictions`` — pause for a human to confirm/reject/edit contradictions
  that are high-severity OR low-confidence.
* ``hitl_final`` — lightweight human sign-off on the finished memo.

Both become real ``interrupt()`` gates in step 5. At this milestone they are
pass-through no-ops so the end-to-end skeleton runs without pausing.
"""

from ..deps import Deps
from ..state import GraphState
from .common import Timer, metric


def hitl_contradictions(state: GraphState, deps: Deps) -> GraphState:
    with Timer() as timer:
        pass  # step 5: interrupt() with the pending contradictions
    return {"node_metrics": [metric("hitl_contradictions", latency_ms=timer.latency_ms)]}


def hitl_final(state: GraphState, deps: Deps) -> GraphState:
    with Timer() as timer:
        pass  # step 5: interrupt() for memo sign-off
    return {"node_metrics": [metric("hitl_final", latency_ms=timer.latency_ms)]}
