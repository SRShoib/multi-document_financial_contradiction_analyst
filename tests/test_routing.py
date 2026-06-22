"""Routing + reflection circuit breaker (pure predicates over state)."""

from filing_reconciler.config import Settings
from filing_reconciler.graph import route_after_critique, route_after_risk
from filing_reconciler.models import Contradiction, CritiqueIssue
from filing_reconciler.nodes.common import should_reflect


def _contra(
    *, severity: str = "high", confidence: float = 0.9, status: str = "pending"
) -> Contradiction:
    return Contradiction(
        contradiction_id="c1",
        ctype="numeric_mismatch",
        topic="revenue",
        severity=severity,  # type: ignore[arg-type]
        confidence=confidence,
        rationale="x",
        detected_by="deterministic",
        status=status,  # type: ignore[arg-type]
    )


def test_high_severity_routes_to_human() -> None:
    s = Settings(_env_file=None)
    state = {"contradictions": [_contra(severity="high", confidence=0.99)]}
    assert route_after_risk(state, s) == "hitl_contradictions"


def test_low_confidence_routes_to_human() -> None:
    s = Settings(_env_file=None)
    state = {"contradictions": [_contra(severity="low", confidence=0.5)]}
    assert route_after_risk(state, s) == "hitl_contradictions"


def test_clean_contradictions_bypass_human() -> None:
    s = Settings(_env_file=None)
    # low severity + high confidence → auto-accepted, straight to drafting
    state = {"contradictions": [_contra(severity="low", confidence=0.95)]}
    assert route_after_risk(state, s) == "draft_memo"
    assert route_after_risk({"contradictions": []}, s) == "draft_memo"


def test_reflection_circuit_breaker() -> None:
    s = Settings(_env_file=None, max_reflections=2)
    issues = [CritiqueIssue(assertion="a", problem="missing_citation")]
    # under both caps → reflect
    assert should_reflect(critique_issues=issues, reflection_count=0, cost_usd=0.0, settings=s)
    assert should_reflect(critique_issues=issues, reflection_count=1, cost_usd=0.0, settings=s)
    # max-iteration breaker trips
    assert not should_reflect(
        critique_issues=issues, reflection_count=2, cost_usd=0.0, settings=s
    )
    # cost-cap breaker trips
    assert not should_reflect(
        critique_issues=issues, reflection_count=0, cost_usd=999.0, settings=s
    )
    # nothing to fix → no reflection
    assert not should_reflect(critique_issues=[], reflection_count=0, cost_usd=0.0, settings=s)


def test_route_after_critique_uses_breaker() -> None:
    s = Settings(_env_file=None, max_reflections=2)
    issues = [CritiqueIssue(assertion="a", problem="missing_citation")]
    assert (
        route_after_critique(
            {"critique_issues": issues, "reflection_count": 0, "cost_usd": 0.0}, s
        )
        == "draft_memo"
    )
    assert (
        route_after_critique(
            {"critique_issues": issues, "reflection_count": 2, "cost_usd": 0.0}, s
        )
        == "hitl_final"
    )
    assert (
        route_after_critique({"critique_issues": [], "reflection_count": 0, "cost_usd": 0.0}, s)
        == "hitl_final"
    )
