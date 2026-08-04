"""Step-2 coverage: settings defaults, structured models, and the stub LLM."""

from filing_reconciler.config import Settings
from filing_reconciler.llm import StubLLM, get_llm
from filing_reconciler.models import (
    Citation,
    Contradiction,
    MemoContext,
    RiskItem,
    RiskRegister,
)


def test_settings_offline_defaults() -> None:
    s = Settings(_env_file=None)
    assert s.llm_provider == "stub"
    assert s.checkpointer == "memory"
    assert s.max_reflections == 2
    assert s.hitl_confidence_threshold == 0.75
    assert get_llm(s).name  # stub is selected and usable


def _sample_context() -> MemoContext:
    cite_a = Citation(doc_id="10K_FY23", start=10, end=40, quote="revenue of $1,000M")
    cite_b = Citation(doc_id="PR_FY23", start=5, end=30, quote="revenue of $1,200M")
    contradiction = Contradiction(
        contradiction_id="c1",
        ctype="numeric_mismatch",
        topic="revenue",
        period="FY2023",
        severity="high",
        confidence=0.92,
        rationale="10-K reports $1,000M revenue while the press release states $1,200M.",
        citations=[cite_a, cite_b],
        claim_ids=["k1", "k2"],
        detected_by="deterministic",
    )
    risk = RiskRegister(
        items=[
            RiskItem(
                risk_id="r1",
                title="Revenue figure inconsistency",
                category="financial_reporting",
                severity="high",
                score=0.8,
                rationale="Conflicting revenue figures across filings.",
                citations=[cite_a, cite_b],
                contradiction_ids=["c1"],
            )
        ],
        overall_score=0.8,
        summary="One high-severity reporting inconsistency.",
    )
    return MemoContext(
        company="ACME",
        period_coverage="FY2023",
        contradictions=[contradiction],
        risk_register=risk,
    )


def test_stub_compose_memo_has_citations_and_cost() -> None:
    llm = StubLLM()
    out = llm.compose_memo(context=_sample_context())
    memo = out.value

    assert memo.executive_summary
    assert memo.sections, "memo should contain sections"
    assert memo.citations, "memo should aggregate citations"
    # Inline markers are rendered into section bodies for traceability.
    assert "[10K_FY23:10-40]" in memo.sections[0].body
    # Synthetic cost is tracked so the cost cap / logging are exercisable offline.
    assert out.usage.cost_usd > 0


def test_stub_critique_flags_uncited_section() -> None:
    llm = StubLLM()
    memo = llm.compose_memo(context=_sample_context()).value
    # Inject an uncited section to trip the faithfulness check.
    memo.sections[0].citations = []
    result = llm.critique_memo(memo=memo, claims=[], contradictions=[]).value
    assert not result.faithful
    assert any(i.problem == "missing_citation" for i in result.issues)
