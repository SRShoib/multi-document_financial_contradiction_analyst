"""reconcile — group claims by metric/topic/period across documents and emit scored
Contradiction candidates.

Two detection paths, by design:

* **Deterministic numeric** (``numeric_mismatch``): same metric + period reported as
  materially different figures across documents. Pure arithmetic with a tolerance —
  reproducible, high-confidence, and the cheap/safe default. The LLM is never asked
  to decide whether numbers differ.
* **LLM-only narrative/guidance**: forward-looking guidance revisions and qualitative
  conflicts (e.g. litigation) are judged by ``llm.judge_conflict``. These carry lower
  confidence and are the ones most likely to be routed to a human.

One contradiction is emitted per (metric, period) numeric group and per guidance
group, and per narrative topic, to avoid double-counting the same underlying issue.
"""

from collections import defaultdict
from itertools import combinations

from ..config import Settings
from ..deps import Deps
from ..models import Claim, Contradiction, Severity
from ..state import GraphState
from ..tools.numeric import compare
from .common import Timer, metric, new_id


def _severity_from_pct(pct: float) -> Severity:
    if pct >= 50.0:
        return "critical"
    if pct >= 15.0:
        return "high"
    if pct >= 5.0:
        return "medium"
    return "low"


def _one_per_doc(group: list[Claim]) -> list[Claim]:
    """First claim per document (cross-document comparison, not intra-document)."""
    seen: dict[str, Claim] = {}
    for c in group:
        seen.setdefault(c.doc_id, c)
    return list(seen.values())


def reconcile_numeric(claims: list[Claim], settings: Settings) -> list[Contradiction]:
    groups: dict[tuple[str, str | None, str | None], list[Claim]] = defaultdict(list)
    for c in claims:
        if c.kind == "numeric" and c.value is not None:
            groups[(c.topic, c.period, c.unit)].append(c)

    out: list[Contradiction] = []
    for (topic, period, _unit), group in groups.items():
        reps = [(c.value, c) for c in _one_per_doc(group) if c.value is not None]
        if len(reps) < 2:
            continue
        reps.sort(key=lambda t: t[0])
        lo_v, lo = reps[0]
        hi_v, hi = reps[-1]
        delta = compare(lo_v, hi_v, settings.numeric_tolerance_pct)
        if delta.within_tolerance:
            continue
        out.append(
            Contradiction(
                contradiction_id=new_id("num", topic, period or "na"),
                ctype="numeric_mismatch",
                topic=topic,
                period=period,
                severity=_severity_from_pct(delta.pct_diff),
                confidence=0.97,  # deterministic arithmetic → high confidence
                rationale=(
                    f"{topic} for {period} differs across documents: "
                    f"{lo_v:,.0f} ({lo.doc_id}) vs {hi_v:,.0f} ({hi.doc_id}) — "
                    f"{delta.pct_diff:.1f}% gap (tolerance {settings.numeric_tolerance_pct}%)."
                ),
                citations=[lo.citation, hi.citation],
                claim_ids=[lo.claim_id, hi.claim_id],
                detected_by="deterministic",
                numeric_delta=delta,
            )
        )
    return out


def reconcile_guidance(claims: list[Claim], deps: Deps) -> tuple[list[Contradiction], float]:
    groups: dict[tuple[str, str | None], list[Claim]] = defaultdict(list)
    for c in claims:
        if c.kind == "guidance":
            groups[(c.topic, c.period)].append(c)

    out: list[Contradiction] = []
    cost = 0.0
    for (topic, period), group in groups.items():
        reps = _one_per_doc(group)
        if len(reps) < 2:
            continue
        a, b = reps[0], reps[1]
        gen = deps.llm.judge_conflict(claim_a=a, claim_b=b)
        cost += gen.usage.cost_usd
        if gen.value.is_conflict:
            out.append(
                Contradiction(
                    contradiction_id=new_id("guid", topic, period or "na"),
                    ctype=gen.value.ctype,
                    topic=topic,
                    period=period,
                    severity=gen.value.severity,
                    confidence=gen.value.confidence,
                    rationale=gen.value.rationale,
                    citations=[a.citation, b.citation],
                    claim_ids=[a.claim_id, b.claim_id],
                    detected_by="llm",
                )
            )
    return out, cost


def reconcile_narrative(claims: list[Claim], deps: Deps) -> tuple[list[Contradiction], float]:
    groups: dict[str, list[Claim]] = defaultdict(list)
    for c in claims:
        if c.kind == "narrative":
            groups[c.topic].append(c)

    out: list[Contradiction] = []
    cost = 0.0
    for topic, group in groups.items():
        reps = _one_per_doc(group)
        # First conflicting cross-document pair → one contradiction for the topic.
        for a, b in combinations(reps, 2):
            gen = deps.llm.judge_conflict(claim_a=a, claim_b=b)
            cost += gen.usage.cost_usd
            if gen.value.is_conflict:
                out.append(
                    Contradiction(
                        contradiction_id=new_id("narr", topic),
                        ctype=gen.value.ctype,
                        topic=topic,
                        period=a.period,
                        severity=gen.value.severity,
                        confidence=gen.value.confidence,
                        rationale=gen.value.rationale,
                        citations=[a.citation, b.citation],
                        claim_ids=[a.claim_id, b.claim_id],
                        detected_by="llm",
                    )
                )
                break
    return out, cost


def reconcile(state: GraphState, deps: Deps) -> GraphState:
    with Timer() as timer:
        claims = state.get("claims", []) or []
        contradictions = reconcile_numeric(claims, deps.settings)
        guidance, cost_g = reconcile_guidance(claims, deps)
        narrative, cost_n = reconcile_narrative(claims, deps)
        contradictions += guidance + narrative
        cost = cost_g + cost_n

    return {
        "contradictions": contradictions,
        "cost_usd": cost,
        "node_metrics": [metric("reconcile", cost_usd=cost, latency_ms=timer.latency_ms)],
    }
