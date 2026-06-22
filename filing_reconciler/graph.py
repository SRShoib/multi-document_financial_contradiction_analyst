"""Graph assembly and compilation.

START → ingest → (Send fan-out) extract_claims → reconcile → risk_scoring
      → {needs_human → hitl_contradictions | draft_memo}
      → draft_memo → critique
      → {reflect → draft_memo | hitl_final}
      → finalize → END

Nodes close over a ``Deps`` instance via ``functools.partial`` (see ``deps.py``).
Routers are pure predicates over state, bound to ``Settings`` the same way, and
return ``Literal`` node names so the conditional edges stay type-checked.
"""

from functools import partial
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from .config import Settings
from .deps import Deps, make_deps
from .nodes.common import needs_human, should_reflect
from .nodes.critique import critique
from .nodes.draft_memo import draft_memo
from .nodes.extract_claims import extract_claims, fan_out_to_extract
from .nodes.finalize import finalize
from .nodes.hitl import hitl_contradictions, hitl_final
from .nodes.ingest import ingest
from .nodes.reconcile import reconcile
from .nodes.risk_scoring import risk_scoring
from .state import GraphState

RiskRoute = Literal["hitl_contradictions", "draft_memo"]
CritiqueRoute = Literal["draft_memo", "hitl_final"]


def route_after_risk(state: GraphState, settings: Settings) -> RiskRoute:
    """Gate: send high-severity/low-confidence contradictions to a human; else draft."""
    if needs_human(state.get("contradictions", []) or [], settings):
        return "hitl_contradictions"
    return "draft_memo"


def route_after_critique(state: GraphState, settings: Settings) -> CritiqueRoute:
    """Reflection loop with circuit breakers (max iterations + cost cap)."""
    if should_reflect(
        critique_issues=state.get("critique_issues", []) or [],
        reflection_count=state.get("reflection_count", 0),
        cost_usd=state.get("cost_usd", 0.0),
        settings=settings,
    ):
        return "draft_memo"
    return "hitl_final"


def build_graph(deps: Deps | None = None, checkpointer: Any | None = None) -> Any:
    """Build and compile the state graph. Defaults to offline deps (stub LLM)."""
    deps = deps or make_deps()
    settings = deps.settings

    builder = StateGraph(GraphState)

    builder.add_node("ingest", partial(ingest, deps=deps))
    builder.add_node("extract_claims", partial(extract_claims, deps=deps))
    builder.add_node("reconcile", partial(reconcile, deps=deps))
    builder.add_node("risk_scoring", partial(risk_scoring, deps=deps))
    builder.add_node("hitl_contradictions", partial(hitl_contradictions, deps=deps))
    builder.add_node("draft_memo", partial(draft_memo, deps=deps))
    builder.add_node("critique", partial(critique, deps=deps))
    builder.add_node("hitl_final", partial(hitl_final, deps=deps))
    builder.add_node("finalize", partial(finalize, deps=deps))

    builder.add_edge(START, "ingest")
    # Map step: one parallel extract branch per document (Send API).
    builder.add_conditional_edges("ingest", fan_out_to_extract, ["extract_claims"])
    builder.add_edge("extract_claims", "reconcile")
    builder.add_edge("reconcile", "risk_scoring")
    builder.add_conditional_edges(
        "risk_scoring",
        partial(route_after_risk, settings=settings),
        ["hitl_contradictions", "draft_memo"],
    )
    builder.add_edge("hitl_contradictions", "draft_memo")
    builder.add_edge("draft_memo", "critique")
    builder.add_conditional_edges(
        "critique",
        partial(route_after_critique, settings=settings),
        ["draft_memo", "hitl_final"],
    )
    builder.add_edge("hitl_final", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer)
