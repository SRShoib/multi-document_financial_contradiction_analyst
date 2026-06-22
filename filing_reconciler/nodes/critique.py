"""critique — faithfulness check over the draft memo.

Every assertion must map to a citation and no figures may be invented. The result
populates ``critique_issues``, which the post-critique router reads (via
``should_reflect``) to decide whether to loop back to drafting. Deepened in step 6.
"""

from ..deps import Deps
from ..state import GraphState
from .common import Timer, metric


def critique(state: GraphState, deps: Deps) -> GraphState:
    draft = state.get("draft_memo")
    with Timer() as timer:
        if draft is None:
            return {"critique_issues": []}
        generated = deps.llm.critique_memo(
            memo=draft,
            claims=state.get("claims", []) or [],
            contradictions=state.get("contradictions", []) or [],
        )
        issues = generated.value.issues

    return {
        "critique_issues": issues,
        "cost_usd": generated.usage.cost_usd,
        "node_metrics": [
            metric("critique", cost_usd=generated.usage.cost_usd, latency_ms=timer.latency_ms)
        ],
    }
