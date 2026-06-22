"""risk_scoring — turn contradictions + risk factors into a scored register with
citations. Full scoring lands in step 4; this milestone produces an empty register.
"""

from ..deps import Deps
from ..models import RiskRegister
from ..state import GraphState
from .common import Timer, metric


def risk_scoring(state: GraphState, deps: Deps) -> GraphState:
    with Timer() as timer:
        register = RiskRegister(items=[], overall_score=0.0, summary="No risks scored yet.")
    return {
        "risk_register": register,
        "node_metrics": [metric("risk_scoring", latency_ms=timer.latency_ms)],
    }
