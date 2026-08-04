"""risk_scoring — turn contradictions into a scored risk register with citations.

Each contradiction becomes a risk item scored as ``severity_weight * confidence``
(severity drives magnitude; confidence discounts uncertain LLM-detected items). The
register's overall score is the worst-case item score, reflecting that a single
high-severity reporting inconsistency dominates analyst risk.
"""

from ..deps import Deps
from ..models import ContradictionType, RiskItem, RiskRegister, Severity
from ..state import GraphState
from .common import Timer, metric, new_id

_SEVERITY_WEIGHT: dict[Severity, float] = {
    "low": 0.25,
    "medium": 0.5,
    "high": 0.75,
    "critical": 1.0,
}
_CATEGORY: dict[ContradictionType, str] = {
    "numeric_mismatch": "financial_reporting",
    "guidance_revision": "guidance",
    "narrative_conflict": "disclosure",
    "omission": "disclosure",
}


def risk_scoring(state: GraphState, deps: Deps) -> GraphState:
    with Timer() as timer:
        contradictions = state.get("contradictions", []) or []
        items: list[RiskItem] = []
        for c in contradictions:
            score = round(_SEVERITY_WEIGHT[c.severity] * c.confidence, 3)
            items.append(
                RiskItem(
                    risk_id=new_id("risk", c.contradiction_id),
                    title=f"{c.topic}: {c.ctype}",
                    category=_CATEGORY.get(c.ctype, "other"),
                    severity=c.severity,
                    score=score,
                    rationale=c.rationale,
                    citations=list(c.citations),
                    contradiction_ids=[c.contradiction_id],
                )
            )
        overall = max((i.score for i in items), default=0.0)
        summary = (
            f"{len(items)} scored risk(s); peak score {overall:.2f}."
            if items
            else "No risks scored."
        )
        register = RiskRegister(items=items, overall_score=overall, summary=summary)

    return {
        "risk_register": register,
        "node_metrics": [metric("risk_scoring", latency_ms=timer.latency_ms)],
    }
