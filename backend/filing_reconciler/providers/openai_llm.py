"""OpenAI (GPT) implementation of the ``LLM`` interface.

Selected with ``LLM_PROVIDER=openai`` (needs the ``openai`` extra + ``OPENAI_API_KEY``).
This is the project's real LLM provider; the deterministic ``StubLLM`` remains the
offline default that tests/eval/CI exercise. Uses the official ``openai`` SDK structured
outputs (``chat.completions.parse`` with a Pydantic ``response_format``), defaulting to
``gpt-4.1`` for analysis and ``gpt-4.1-mini`` for the eval judge.

Preserved guarantees:
* The LLM never emits figures — extraction returns verbatim quotes; the numeric value
  is parsed deterministically from the cited span, and offsets are located by string
  search (``tools/numeric.py``).
* Memo citations stay verifiable — ``compose_memo`` reuses the deterministic template;
  the model only rewrites the executive-summary prose.
* Schema validation + retry-on-parse-failure (``tenacity``).

OpenAI strict structured outputs reject numeric ``minimum``/``maximum`` keywords, so the
OpenAI-facing schemas use plain floats (no ``ge/le``); the values are clamped/validated
when mapped onto the canonical Pydantic models.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from ..config import Settings
from ..llm import Generated, Usage, _template_memo
from ..models import (
    Claim,
    ClaimCandidate,
    ClaimExtraction,
    ClaimKind,
    ConflictJudgment,
    Contradiction,
    CritiqueIssue,
    CritiqueProblem,
    CritiqueResult,
    FaithfulnessJudgment,
    Memo,
    MemoContext,
    Severity,
    SourceDoc,
)
from ..tools.text import locate_quote

# USD per token (input, output). See the OpenAI API pricing page.
_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4.1": (2e-6, 8e-6),
    "gpt-4.1-mini": (0.4e-6, 1.6e-6),
    "gpt-4.1-nano": (0.1e-6, 0.4e-6),
    "gpt-4o": (2.5e-6, 10e-6),
    "gpt-4o-mini": (0.15e-6, 0.6e-6),
}


def _price(model: str) -> tuple[float, float]:
    return _PRICES.get(model, (2e-6, 8e-6))


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


# OpenAI-facing schemas: Literals/enums are allowed (they constrain generation), but
# numeric range constraints are not — keep confidence/score as plain floats.
class _OAIClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str
    kind: ClaimKind
    metric: str | None = None
    period: str | None = None
    quote: str


class _OAIClaims(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claims: list[_OAIClaim] = Field(default_factory=list)


class _OAIConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_conflict: bool
    ctype: Literal["guidance_revision", "narrative_conflict"]
    severity: Severity
    confidence: float
    rationale: str


class _OAICritiqueIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assertion: str
    problem: CritiqueProblem
    detail: str = ""
    section: str | None = None


class _OAICritique(BaseModel):
    model_config = ConfigDict(extra="forbid")
    faithful: bool
    issues: list[_OAICritiqueIssue] = Field(default_factory=list)


class _OAIFaithful(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supported: bool
    score: float
    reason: str = ""


class _OAISummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    executive_summary: str


class OpenAILLM:
    def __init__(self, settings: Settings) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - exercised only with the extra
            raise RuntimeError(
                "The 'openai' extra is required for LLM_PROVIDER=openai: "
                "install with `uv sync --extra openai`."
            ) from exc
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for LLM_PROVIDER=openai.")
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model
        self._judge_model = settings.openai_judge_model

    @property
    def name(self) -> str:
        return self._model

    def _usage(self, completion: Any, model: str) -> Usage:
        u = getattr(completion, "usage", None)
        in_tok = int(getattr(u, "prompt_tokens", 0) or 0)
        out_tok = int(getattr(u, "completion_tokens", 0) or 0)
        p_in, p_out = _price(model)
        return Usage(model, in_tok, out_tok, round(in_tok * p_in + out_tok * p_out, 6))

    @retry(
        retry=retry_if_exception_type((ValidationError, ValueError)),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _parse(self, *, model: str, system: str, prompt: str, schema: type) -> Any:
        completion = self._client.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            response_format=schema,
        )
        message = completion.choices[0].message
        if getattr(message, "refusal", None):
            raise ValueError(f"openai refused: {message.refusal}")
        if message.parsed is None:
            raise ValueError("openai returned no parsed output")
        return completion

    # --- extraction --------------------------------------------------------
    def extract_claims(self, *, doc: SourceDoc, text: str) -> Generated[ClaimExtraction]:
        system = (
            "You extract financial claims from a single SEC filing or transcript. "
            "Return claim candidates as VERBATIM quotes copied exactly from the text. "
            "kind is one of: numeric (a reported actual figure), guidance (a forward-looking "
            "expectation), narrative (a qualitative statement, e.g. litigation). Provide the "
            "normalized metric/topic. Do NOT compute or restate numbers — quote the source."
        )
        completion = self._parse(model=self._model, system=system, prompt=text, schema=_OAIClaims)
        parsed: _OAIClaims = completion.choices[0].message.parsed
        candidates: list[ClaimCandidate] = []
        for c in parsed.claims:
            span = locate_quote(text, c.quote)
            if span is None:
                # The model's "verbatim" quote isn't in the source text, even after
                # whitespace/hyphenation-tolerant matching. Emit an explicitly
                # unlocatable candidate rather than fabricating a plausible-but-wrong
                # span — extract_claims (the node) drops these before they become
                # citations, instead of silently pointing at the document's start.
                start, end, located = 0, 0, False
            else:
                start, end = span
                located = True
            candidates.append(
                ClaimCandidate(
                    topic=c.topic,
                    kind=c.kind,
                    metric=c.metric,
                    period=c.period,
                    raw_text=c.quote,
                    char_start=start,
                    char_end=end,
                    located=located,
                )
            )
        return Generated(ClaimExtraction(claims=candidates), self._usage(completion, self._model))

    # --- conflict judging (guidance / narrative) ---------------------------
    def judge_conflict(self, *, claim_a: Claim, claim_b: Claim) -> Generated[ConflictJudgment]:
        system = (
            "You judge whether two claims from different documents conflict. For guidance, a "
            "materially different forward number is a guidance_revision; for narrative, opposing "
            "assertions are a narrative_conflict. Set is_conflict, ctype, severity, confidence."
        )
        prompt = (
            f"Claim A ({claim_a.doc_id}, kind={claim_a.kind}): {claim_a.raw_text}\n"
            f"Claim B ({claim_b.doc_id}, kind={claim_b.kind}): {claim_b.raw_text}"
        )
        completion = self._parse(
            model=self._model, system=system, prompt=prompt, schema=_OAIConflict
        )
        o: _OAIConflict = completion.choices[0].message.parsed
        judgment = ConflictJudgment(
            is_conflict=o.is_conflict,
            ctype=o.ctype,
            severity=o.severity,
            confidence=_clamp01(o.confidence),
            rationale=o.rationale,
        )
        return Generated(judgment, self._usage(completion, self._model))

    # --- memo drafting (citations stay deterministic) ----------------------
    def compose_memo(self, *, context: MemoContext) -> Generated[Memo]:
        memo = _template_memo(context)
        system = (
            "You are a financial analyst. Rewrite ONLY the executive summary for the memo, "
            "grounded strictly in the provided contradictions and risk register. Do not invent "
            "figures or facts beyond what is given."
        )
        completion = self._parse(
            model=self._model,
            system=system,
            prompt=context.model_dump_json(),
            schema=_OAISummary,
        )
        memo.executive_summary = completion.choices[0].message.parsed.executive_summary
        return Generated(memo, self._usage(completion, self._model))

    # --- critique ----------------------------------------------------------
    def critique_memo(
        self,
        *,
        memo: Memo,
        claims: list[Claim],
        contradictions: list[Contradiction],
    ) -> Generated[CritiqueResult]:
        system = (
            "You audit a financial memo for faithfulness. Flag any section that asserts a figure "
            "without a citation (missing_citation) or that states a figure not supported by the "
            "claims/citations (invented_figure). Return faithful + a list of issues."
        )
        completion = self._parse(
            model=self._model, system=system, prompt=memo.model_dump_json(), schema=_OAICritique
        )
        o: _OAICritique = completion.choices[0].message.parsed
        result = CritiqueResult(
            faithful=o.faithful,
            issues=[
                CritiqueIssue(
                    assertion=i.assertion, problem=i.problem, detail=i.detail, section=i.section
                )
                for i in o.issues
            ],
        )
        return Generated(result, self._usage(completion, self._model))

    # --- faithfulness judge (eval) -----------------------------------------
    def judge_faithfulness(
        self, *, assertion: str, cited_text: str
    ) -> Generated[FaithfulnessJudgment]:
        system = (
            "Decide whether the assertion is supported by the cited source text. "
            "Return supported (bool), score (0..1), and a brief reason."
        )
        prompt = f"ASSERTION:\n{assertion}\n\nCITED TEXT:\n{cited_text}"
        completion = self._parse(
            model=self._judge_model, system=system, prompt=prompt, schema=_OAIFaithful
        )
        o: _OAIFaithful = completion.choices[0].message.parsed
        judgment = FaithfulnessJudgment(
            supported=o.supported, score=_clamp01(o.score), reason=o.reason
        )
        return Generated(judgment, self._usage(completion, self._judge_model))
