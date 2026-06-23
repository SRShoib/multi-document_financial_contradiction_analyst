"""LLM provider behind an interface, with a deterministic offline stub.

Why an interface
----------------
Nodes depend on the ``LLM`` Protocol, never on a concrete provider. The default
implementation (``StubLLM``) is fully deterministic and needs no API key, so the
whole graph — and the eval harness — runs offline and reproducibly. A real
provider (``anthropic``) is wired behind the same Protocol in a later step.

Cost accounting
---------------
Every call returns a ``Generated[T]`` carrying ``Usage`` (tokens + cost). Nodes
add ``usage.cost_usd`` into the ``cost_usd`` channel, which drives the hard
per-run cost cap. The stub assigns a small *synthetic* cost from a token estimate
so cost tracking and the cost-cap circuit breaker are exercisable offline.

Determinism boundary
---------------------
The stub never invents figures. Numeric *values* are parsed deterministically by
``tools/numeric.py``; the LLM/stub only proposes claim spans, topics, and prose.
"""

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar, runtime_checkable

from .config import Settings
from .models import (
    Citation,
    Claim,
    ClaimExtraction,
    ConflictJudgment,
    Contradiction,
    CritiqueIssue,
    CritiqueResult,
    FaithfulnessJudgment,
    Memo,
    MemoContext,
    MemoSection,
    Severity,
    SourceDoc,
)
from .tools.extraction import narrative_polarity, propose_candidates
from .tools.numeric import compare, extract_numbers

T = TypeVar("T")

# Synthetic stub pricing (USD/token). Not Anthropic's real prices — just enough
# that cost_usd is nonzero so the cost cap and per-run cost logging are testable.
_STUB_INPUT_PRICE = 1e-6
_STUB_OUTPUT_PRICE = 3e-6


@dataclass(frozen=True)
class Usage:
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass(frozen=True)
class Generated(Generic[T]):
    value: T
    usage: Usage


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token), min 1."""
    return max(1, len(text) // 4)


@runtime_checkable
class LLM(Protocol):
    """Provider interface. All methods are pure given their inputs."""

    @property
    def name(self) -> str: ...

    def extract_claims(self, *, doc: SourceDoc, text: str) -> Generated[ClaimExtraction]:
        """Propose claim candidates (spans/topics) from a single document."""

    def judge_conflict(self, *, claim_a: Claim, claim_b: Claim) -> Generated[ConflictJudgment]:
        """Decide whether two narrative/guidance claims conflict (LLM-only path)."""

    def compose_memo(self, *, context: MemoContext) -> Generated[Memo]:
        """Draft the analyst memo with inline citations."""

    def critique_memo(
        self,
        *,
        memo: Memo,
        claims: list[Claim],
        contradictions: list[Contradiction],
    ) -> Generated[CritiqueResult]:
        """Faithfulness check: every assertion maps to a citation; no invented figures."""

    def judge_faithfulness(
        self, *, assertion: str, cited_text: str
    ) -> Generated[FaithfulnessJudgment]:
        """Eval-time judge: is ``assertion`` supported by ``cited_text``?"""


# --------------------------------------------------------------------------- #
# Deterministic stub
# --------------------------------------------------------------------------- #
class StubLLM:
    """Deterministic, offline implementation of the ``LLM`` Protocol.

    The narrative/guidance/critique behaviours are intentionally simple at this
    milestone and are deepened in later build steps; ``compose_memo`` is already
    a real deterministic template so the end-to-end run produces a usable memo.
    """

    def __init__(self, model: str = "stub-v1") -> None:
        self._model = model

    @property
    def name(self) -> str:
        return self._model

    def _usage(self, *, prompt: str, output: str) -> Usage:
        in_tok = estimate_tokens(prompt)
        out_tok = estimate_tokens(output)
        cost = round(in_tok * _STUB_INPUT_PRICE + out_tok * _STUB_OUTPUT_PRICE, 6)
        return Usage(self._model, in_tok, out_tok, cost)

    # --- extraction: propose spans/topics (figures parsed later, not here) --
    def extract_claims(self, *, doc: SourceDoc, text: str) -> Generated[ClaimExtraction]:
        candidates = propose_candidates(text, doc.doc_type, doc.period)
        result = ClaimExtraction(claims=candidates)
        return Generated(result, self._usage(prompt=text, output=result.model_dump_json()))

    # --- narrative/guidance conflict (the LLM-only reconciliation path) -----
    def judge_conflict(self, *, claim_a: Claim, claim_b: Claim) -> Generated[ConflictJudgment]:
        result = self._judge_conflict(claim_a, claim_b)
        prompt = f"{claim_a.raw_text}\n{claim_b.raw_text}"
        return Generated(result, self._usage(prompt=prompt, output=result.model_dump_json()))

    @staticmethod
    def _judge_conflict(claim_a: Claim, claim_b: Claim) -> ConflictJudgment:
        # Guidance revision: same forward metric/period, materially different figure.
        if claim_a.kind == "guidance" and claim_b.kind == "guidance":
            if claim_a.value is not None and claim_b.value is not None:
                delta = compare(claim_a.value, claim_b.value, tolerance_pct=1.0)
                if not delta.within_tolerance:
                    severity: Severity = "high" if delta.pct_diff >= 15.0 else "medium"
                    return ConflictJudgment(
                        is_conflict=True,
                        ctype="guidance_revision",
                        severity=severity,
                        confidence=0.8,
                        rationale=(
                            f"Revenue guidance revised by {delta.pct_diff:.1f}% "
                            f"({claim_a.value:,.0f} vs {claim_b.value:,.0f})."
                        ),
                    )
            return ConflictJudgment(is_conflict=False, confidence=0.6)

        # Narrative conflict: opposing polarity on the same qualitative matter.
        if claim_a.kind == "narrative" and claim_b.kind == "narrative":
            pol_a = narrative_polarity(claim_a.raw_text)
            pol_b = narrative_polarity(claim_b.raw_text)
            if pol_a * pol_b < 0:
                return ConflictJudgment(
                    is_conflict=True,
                    ctype="narrative_conflict",
                    severity="high",
                    confidence=0.7,
                    rationale=(
                        "One document denies the matter while another asserts it "
                        f"(topic={claim_a.topic})."
                    ),
                )
            return ConflictJudgment(is_conflict=False, confidence=0.6)

        return ConflictJudgment(is_conflict=False, confidence=0.5)

    # --- memo drafting (real deterministic template) ------------------------
    def compose_memo(self, *, context: MemoContext) -> Generated[Memo]:
        memo = _template_memo(context)
        prompt = context.model_dump_json()
        return Generated(memo, self._usage(prompt=prompt, output=memo.model_dump_json()))

    # --- critique (deepened in step 6) --------------------------------------
    def critique_memo(
        self,
        *,
        memo: Memo,
        claims: list[Claim],
        contradictions: list[Contradiction],
    ) -> Generated[CritiqueResult]:
        # Monetary values the memo is allowed to assert: those backed by extracted
        # claims, plus any figure present verbatim in a cited span.
        backed: list[float] = [c.value for c in claims if c.value is not None and c.unit == "USD"]

        issues: list[CritiqueIssue] = []
        for section in memo.sections:
            asserts_figure = any(ch.isdigit() for ch in section.body)
            # 1. Any section asserting a figure must carry a citation. Sections with no
            #    figures (e.g. "no contradictions detected") are exempt.
            if asserts_figure and not section.citations:
                issues.append(
                    CritiqueIssue(
                        assertion=section.heading,
                        problem="missing_citation",
                        detail="Section asserts a figure without a supporting citation.",
                        section=section.heading,
                    )
                )
                continue
            # 2. No invented monetary figures: every $-figure in the prose must match
            #    (within tolerance) a claim value or a figure in the cited spans. Bare
            #    numbers / percentages (computed deltas) are intentionally not checked.
            cited_text = " ".join(c.quote for c in section.citations)
            supported = backed + [
                nm.value for nm in extract_numbers(cited_text) if nm.unit == "USD"
            ]
            for nm in extract_numbers(section.body):
                if nm.unit != "USD":
                    continue
                tol = max(1.0, 0.005 * abs(nm.value))
                if not any(abs(nm.value - v) <= tol for v in supported):
                    issues.append(
                        CritiqueIssue(
                            assertion=section.heading,
                            problem="invented_figure",
                            detail=f"Figure {nm.raw} is not supported by any citation.",
                            section=section.heading,
                        )
                    )

        result = CritiqueResult(faithful=not issues, issues=issues)
        return Generated(
            result,
            self._usage(prompt=memo.model_dump_json(), output=result.model_dump_json()),
        )

    # --- faithfulness judge (deterministic token overlap) -------------------
    def judge_faithfulness(
        self, *, assertion: str, cited_text: str
    ) -> Generated[FaithfulnessJudgment]:
        a = {t for t in assertion.lower().split() if len(t) > 3}
        c = {t for t in cited_text.lower().split() if len(t) > 3}
        overlap = len(a & c) / len(a) if a else 0.0
        result = FaithfulnessJudgment(
            supported=overlap >= 0.5,
            score=round(overlap, 3),
            reason=f"token overlap={overlap:.2f}",
        )
        prompt = f"{assertion}\n{cited_text}"
        return Generated(result, self._usage(prompt=prompt, output=result.model_dump_json()))


def _template_memo(context: MemoContext) -> Memo:
    """Build a deterministic memo from reconciled contradictions + risk register."""
    contradictions = context.contradictions
    risk = context.risk_register

    all_citations: list[Citation] = []
    sections: list[MemoSection] = []

    if contradictions:
        for c in contradictions:
            markers = " ".join(cit.marker() for cit in c.citations)
            body = f"{c.rationale} {markers}".strip()
            sections.append(
                MemoSection(
                    heading=f"{c.topic} — {c.ctype} (severity={c.severity}, "
                    f"confidence={c.confidence:.2f})",
                    body=body,
                    citations=list(c.citations),
                )
            )
            all_citations.extend(c.citations)
    else:
        sections.append(
            MemoSection(
                heading="No contradictions detected",
                body="Cross-document reconciliation surfaced no contradictions.",
                citations=[],
            )
        )

    if risk.items:
        risk_lines = [
            f"- {item.title} (severity={item.severity}, score={item.score:.2f}): {item.rationale}"
            for item in risk.items
        ]
        risk_section = MemoSection(
            heading=f"Risk register (overall={risk.overall_score:.2f})",
            body="\n".join(risk_lines),
            citations=[cit for item in risk.items for cit in item.citations],
        )
        sections.append(risk_section)
        all_citations.extend(risk_section.citations)

    summary = (
        f"{len(contradictions)} cross-document contradiction(s) identified; "
        f"overall risk score {risk.overall_score:.2f}."
    )
    return Memo(
        title="Cross-Document Contradiction Analysis",
        company=context.company,
        period_coverage=context.period_coverage,
        executive_summary=summary,
        sections=sections,
        citations=_dedupe_citations(all_citations),
    )


def _dedupe_citations(citations: list[Citation]) -> list[Citation]:
    seen: set[tuple[str, int, int]] = set()
    out: list[Citation] = []
    for c in citations:
        key = (c.doc_id, c.start, c.end)
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #
def get_llm(settings: Settings) -> LLM:
    """Return the configured LLM provider (defaults to the deterministic stub)."""
    if settings.llm_provider == "stub":
        return StubLLM()
    if settings.llm_provider == "anthropic":
        # Real provider behind the same interface (needs the `anthropic` extra + key).
        from .providers.anthropic_llm import AnthropicLLM

        return AnthropicLLM(settings)
    if settings.llm_provider == "openai":
        from .providers.openai_llm import OpenAILLM

        return OpenAILLM(settings)
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider!r}")
