"""Shared node helpers: ID generation, HITL gating, the reflection breaker, timing.

These predicates are the single source of truth for routing so the conditional
edges and the nodes agree (and so they can be unit-tested directly).
"""

import time
from collections.abc import Iterable

from ..config import Settings
from ..models import SEVERITY_ORDER, Contradiction, NodeMetric


def new_id(*parts: str | int) -> str:
    """Deterministic ID from parts (no randomness → reproducible eval/tests)."""
    return ":".join(str(p) for p in parts)


def needs_review(contradiction: Contradiction, settings: Settings) -> bool:
    """Gate: a contradiction needs a human if it is high-severity OR low-confidence.

    Everything else is auto-accepted and bypasses the HITL gate straight to drafting.
    """
    if contradiction.status != "pending":
        return False
    severe = SEVERITY_ORDER[contradiction.severity] >= SEVERITY_ORDER[
        settings.hitl_severity_threshold
    ]
    low_conf = contradiction.confidence < settings.hitl_confidence_threshold
    return severe or low_conf


def pending_reviews(
    contradictions: Iterable[Contradiction], settings: Settings
) -> list[Contradiction]:
    return [c for c in contradictions if needs_review(c, settings)]


def needs_human(contradictions: Iterable[Contradiction], settings: Settings) -> bool:
    return bool(pending_reviews(contradictions, settings))


def cost_exceeded(cost_usd: float, settings: Settings) -> bool:
    """Hard per-run cost cap circuit breaker."""
    return cost_usd >= settings.cost_cap_usd


def should_reflect(
    *, critique_issues: list, reflection_count: int, cost_usd: float, settings: Settings
) -> bool:
    """Reflection loop predicate with circuit breakers.

    Loop back to drafting only if the critique found faithfulness issues AND we are
    under both the max-iteration cap and the cost cap. Otherwise the breaker trips
    and we proceed (the unresolved issues are recorded for the human sign-off gate).
    """
    if not critique_issues:
        return False
    if reflection_count >= settings.max_reflections:
        return False
    return not cost_exceeded(cost_usd, settings)


class Timer:
    """Context manager measuring wall-clock latency in milliseconds."""

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        self.latency_ms = 0.0
        return self

    def __exit__(self, *exc: object) -> None:
        self.latency_ms = (time.perf_counter() - self._start) * 1000.0


def metric(
    node: str,
    *,
    cost_usd: float = 0.0,
    latency_ms: float = 0.0,
    model: str | None = None,
) -> NodeMetric:
    return NodeMetric(node=node, cost_usd=cost_usd, latency_ms=latency_ms, model=model)
