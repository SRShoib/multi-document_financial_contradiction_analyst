"""draft_memo — compose the memo with inline citations as structured output.

On a reflection pass (the critique found issues) it increments ``reflection_count``
and feeds the issues back to the composer as revision notes. The increment lives
here (a node) rather than in the router, which must stay a pure predicate.
"""

from ..deps import Deps
from ..models import MemoContext, RiskRegister
from ..state import GraphState
from .common import Timer, metric


def _period_coverage(state: GraphState) -> str | None:
    periods = [s.period for s in state.get("sources", []) if s.period]
    seen = list(dict.fromkeys(periods))  # preserve order, dedupe
    return ", ".join(seen) if seen else None


def draft_memo(state: GraphState, deps: Deps) -> GraphState:
    with Timer() as timer:
        prior_issues = state.get("critique_issues", []) or []
        is_reflection = bool(prior_issues)
        reflection_count = state.get("reflection_count", 0)
        new_count = reflection_count + 1 if is_reflection else reflection_count

        context = MemoContext(
            company=state.get("company"),
            period_coverage=_period_coverage(state),
            contradictions=state.get("contradictions", []) or [],
            risk_register=state.get("risk_register") or RiskRegister(),
            claims=state.get("claims", []) or [],
            revision_notes=[f"{i.problem}: {i.detail}" for i in prior_issues],
        )
        generated = deps.llm.compose_memo(context=context)
        memo = generated.value
        memo.reflection_count = new_count

    return {
        "draft_memo": memo,
        "reflection_count": new_count,
        "cost_usd": generated.usage.cost_usd,
        "node_metrics": [
            metric("draft_memo", cost_usd=generated.usage.cost_usd, latency_ms=timer.latency_ms)
        ],
    }
