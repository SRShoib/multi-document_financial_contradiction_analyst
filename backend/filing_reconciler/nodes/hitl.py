"""Human-in-the-loop gates implemented with LangGraph ``interrupt()``.

* ``hitl_contradictions`` — a *conditional* gate (the router only sends flagged
  contradictions here). It surfaces every pending high-severity/low-confidence
  contradiction in a single ``interrupt()`` payload (one interrupt per node — robust
  against the index-based matching LangGraph uses for multiple interrupts), then
  applies the human's confirm/reject/edit decisions on resume.
* ``hitl_final`` — lightweight sign-off on the finished memo.

Resume contract: the caller continues the run with ``Command(resume=<payload>)``;
that payload becomes the return value of ``interrupt()``. For the contradiction gate
the payload is a list of decision dicts; for the final gate it is a single decision.

These nodes re-execute from the top on resume, so everything before ``interrupt()``
is kept pure/idempotent (no side effects).
"""

from typing import Any

from langgraph.types import interrupt

from ..deps import Deps
from ..models import Contradiction, HumanDecision, ReviewRequest, RiskRegister
from ..state import GraphState
from .common import metric, pending_reviews


def _parse_decisions(raw: Any) -> list[HumanDecision]:
    if raw is None:
        return []
    items = raw.get("decisions", []) if isinstance(raw, dict) else raw
    out: list[HumanDecision] = []
    for it in items:
        out.append(it if isinstance(it, HumanDecision) else HumanDecision(**it))
    return out


def _parse_final(raw: Any) -> HumanDecision:
    if isinstance(raw, HumanDecision):
        return raw
    if isinstance(raw, list) and raw:
        raw = raw[0]
    if isinstance(raw, dict):
        data = {"target_id": "final_memo", **raw}
        data.setdefault("action", "approve")
        return HumanDecision(**data)
    return HumanDecision(target_id="final_memo", action="approve")


def hitl_contradictions(state: GraphState, deps: Deps) -> GraphState:
    contradictions = state.get("contradictions", []) or []
    pending = pending_reviews(contradictions, deps.settings)
    if not pending:
        return {}

    request = ReviewRequest(
        kind="contradictions",
        run_id=state.get("run_id"),
        instructions=(
            "Confirm, reject, or edit each flagged contradiction. "
            "Send a list of decisions: {target_id, action: confirm|reject|edit, "
            "note?, edited_severity?, edited_confidence?}."
        ),
        contradictions=pending,
    )
    # PAUSE here; resumes with Command(resume=<list of decisions>).
    decisions = _parse_decisions(interrupt(request.model_dump(mode="json")))

    by_id = {d.target_id: d for d in decisions}
    pending_ids = {c.contradiction_id for c in pending}
    rejected_ids: set[str] = set()
    kept: list[Contradiction] = []

    for c in contradictions:
        decision = by_id.get(c.contradiction_id)
        if decision is None:
            # Not under review (auto-accepted) — or left undecided; mark accordingly.
            if c.contradiction_id not in pending_ids:
                c.status = "auto_accepted"
            kept.append(c)
            continue
        if decision.action == "reject":
            c.status = "rejected"
            c.human_note = decision.note
            rejected_ids.add(c.contradiction_id)
            continue  # drop rejected from the downstream set
        if decision.action == "edit":
            c.status = "edited"
            if decision.edited_severity is not None:
                c.severity = decision.edited_severity
            if decision.edited_confidence is not None:
                c.confidence = decision.edited_confidence
        else:  # confirm
            c.status = "confirmed"
        c.human_note = decision.note
        kept.append(c)

    update: GraphState = {
        "contradictions": kept,
        "human_decisions": decisions,
        "node_metrics": [metric("hitl_contradictions")],
    }

    # Keep the risk register consistent with rejected contradictions.
    register = state.get("risk_register")
    if register is not None and rejected_ids:
        items = [i for i in register.items if not (set(i.contradiction_ids) & rejected_ids)]
        update["risk_register"] = RiskRegister(
            items=items,
            overall_score=max((i.score for i in items), default=0.0),
            summary=register.summary,
        )
    return update


def hitl_final(state: GraphState, deps: Deps) -> GraphState:
    memo = state.get("draft_memo")
    request = ReviewRequest(
        kind="final_memo",
        run_id=state.get("run_id"),
        instructions=(
            "Approve the memo or request changes: "
            "{action: approve|request_changes, note?}."
        ),
        memo=memo,
    )
    decision = _parse_final(interrupt(request.model_dump(mode="json")))
    update: GraphState = {
        "human_decisions": [decision],
        "node_metrics": [metric("hitl_final")],
    }
    if decision.action == "request_changes":
        update["errors"] = [f"hitl_final: changes requested — {decision.note or 'no note'}"]
    return update
