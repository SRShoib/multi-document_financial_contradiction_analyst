"""Cross-document reconciliation: numeric (deterministic) + guidance/narrative (LLM)."""

from filing_reconciler.config import Settings
from filing_reconciler.deps import make_deps
from filing_reconciler.models import Citation, Claim
from filing_reconciler.nodes.reconcile import (
    reconcile_guidance,
    reconcile_narrative,
    reconcile_numeric,
)


def _claim(
    doc: str,
    topic: str,
    kind: str,
    *,
    value: float | None = None,
    unit: str | None = None,
    period: str = "FY2023",
    raw: str = "",
) -> Claim:
    return Claim(
        claim_id=f"{doc}:{topic}",
        doc_id=doc,
        doc_type="10-K",
        period=period,
        topic=topic,
        metric=topic,
        kind=kind,  # type: ignore[arg-type]
        value=value,
        unit=unit,
        raw_text=raw or topic,
        citation=Citation(doc_id=doc, start=0, end=5, quote="x"),
    )


def test_numeric_mismatch_detected_across_docs() -> None:
    s = Settings(_env_file=None)
    claims = [
        _claim("10K", "revenue", "numeric", value=1_000_000_000.0, unit="USD"),
        _claim("PR", "revenue", "numeric", value=1_200_000_000.0, unit="USD"),
    ]
    out = reconcile_numeric(claims, s)
    assert len(out) == 1
    c = out[0]
    assert c.ctype == "numeric_mismatch"
    assert c.detected_by == "deterministic"
    assert c.severity == "high"
    assert len(c.citations) == 2


def test_numeric_within_tolerance_is_not_flagged() -> None:
    s = Settings(_env_file=None)
    claims = [
        _claim("10K", "net_income", "numeric", value=120_000_000.0, unit="USD"),
        _claim("PR", "net_income", "numeric", value=120_000_000.0, unit="USD"),
    ]
    assert reconcile_numeric(claims, s) == []


def test_numeric_same_document_is_not_cross_doc() -> None:
    s = Settings(_env_file=None)
    claims = [
        _claim("10K", "revenue", "numeric", value=1_000_000_000.0, unit="USD"),
        _claim("10K", "revenue", "numeric", value=1_500_000_000.0, unit="USD"),
    ]
    assert reconcile_numeric(claims, s) == []


def test_guidance_revision_detected() -> None:
    deps = make_deps(Settings(_env_file=None))
    claims = [
        _claim("PR", "guidance.revenue", "guidance", value=1_400_000_000.0, period="FY2024"),
        _claim("CALL", "guidance.revenue", "guidance", value=1_300_000_000.0, period="FY2024"),
    ]
    out, cost = reconcile_guidance(claims, deps)
    assert len(out) == 1
    assert out[0].ctype == "guidance_revision"
    assert out[0].detected_by == "llm"
    assert cost > 0


def test_narrative_conflict_detected_on_opposing_polarity() -> None:
    deps = make_deps(Settings(_env_file=None))
    claims = [
        _claim(
            "10K",
            "litigation",
            "narrative",
            raw="We are not currently a party to any pending material legal proceedings.",
        ),
        _claim(
            "CALL",
            "litigation",
            "narrative",
            raw="We are currently a party to a material lawsuit relating to a commercial dispute.",
            period="Q4-FY2023",
        ),
    ]
    out, _cost = reconcile_narrative(claims, deps)
    assert len(out) == 1
    assert out[0].ctype == "narrative_conflict"


def test_narrative_agreement_is_not_flagged() -> None:
    deps = make_deps(Settings(_env_file=None))
    claims = [
        _claim("CALL", "litigation", "narrative", raw="We are a party to a material lawsuit."),
        _claim(
            "10Q",
            "litigation",
            "narrative",
            raw="We are a party to a material lawsuit, ongoing.",
        ),
    ]
    out, _cost = reconcile_narrative(claims, deps)
    assert out == []
