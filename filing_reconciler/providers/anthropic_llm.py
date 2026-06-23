"""Anthropic (Claude) implementation of the ``LLM`` interface.

This is the non-default, key-required path (``LLM_PROVIDER=anthropic``). The
deterministic ``StubLLM`` remains the default and is what the tests/eval exercise;
this provider is wired behind the same Protocol so swapping providers is a config
change. It uses the official ``anthropic`` SDK with structured outputs
(``messages.parse``) and adaptive thinking, defaulting to ``claude-opus-4-8`` for
analysis and ``claude-haiku-4-5`` for the eval judge.

Design guarantees preserved across providers:
* **Figures are never invented by the LLM.** Extraction asks the model only for
  verbatim quotes + topic/kind; the numeric value is parsed deterministically from
  the cited span downstream (see ``tools/numeric.py``), and char offsets are located
  by string search — not trusted from model output.
* **Citations stay verifiable.** ``compose_memo`` reuses the deterministic memo
  template (citations come from reconciled contradictions); the model only rewrites
  the executive-summary prose.
* **Schema validation + retry.** Structured outputs are validated against the Pydantic
  models; a validation failure retries the call (retry-on-parse-failure guard).
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from ..config import Settings
from ..llm import Generated, Usage, _template_memo
from ..models import (
    Claim,
    ClaimCandidate,
    ClaimExtraction,
    ConflictJudgment,
    Contradiction,
    CritiqueResult,
    FaithfulnessJudgment,
    Memo,
    MemoContext,
    SourceDoc,
)

# USD per token (input, output). See the Claude API model/pricing table.
_PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-4-8": (5e-6, 25e-6),
    "claude-opus-4-7": (5e-6, 25e-6),
    "claude-sonnet-4-6": (3e-6, 15e-6),
    "claude-haiku-4-5": (1e-6, 5e-6),
}


def _price(model: str) -> tuple[float, float]:
    return _PRICES.get(model, (5e-6, 25e-6))


class _LLMClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str
    kind: str  # numeric | guidance | narrative (validated when mapped to ClaimCandidate)
    metric: str | None = None
    period: str | None = None
    quote: str  # verbatim text copied from the document


class _LLMClaims(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claims: list[_LLMClaim] = Field(default_factory=list)


class _Summary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    executive_summary: str


class AnthropicLLM:
    def __init__(self, settings: Settings) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - exercised only with the extra
            raise RuntimeError(
                "The 'anthropic' extra is required for LLM_PROVIDER=anthropic: "
                "install with `uv sync --extra anthropic`."
            ) from exc
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for LLM_PROVIDER=anthropic.")
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.llm_model
        self._judge_model = settings.llm_judge_model

    @property
    def name(self) -> str:
        return self._model

    def _usage(self, response: Any, model: str) -> Usage:
        u = response.usage
        in_tok = int(getattr(u, "input_tokens", 0) or 0)
        out_tok = int(getattr(u, "output_tokens", 0) or 0)
        p_in, p_out = _price(model)
        return Usage(model, in_tok, out_tok, round(in_tok * p_in + out_tok * p_out, 6))

    @retry(
        retry=retry_if_exception_type((ValidationError, ValueError)),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _parse(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        schema: type,
        max_tokens: int = 4096,
    ) -> Any:
        response = self._client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
        if getattr(response, "parsed_output", None) is None:
            raise ValueError("model returned no parsed output (possible refusal)")
        return response

    # --- extraction --------------------------------------------------------
    def extract_claims(self, *, doc: SourceDoc, text: str) -> Generated[ClaimExtraction]:
        system = (
            "You extract financial claims from a single SEC filing or transcript. "
            "Return claim candidates as VERBATIM quotes copied exactly from the text. "
            "kind is one of: numeric (a reported actual figure), guidance (a forward-looking "
            "expectation), narrative (a qualitative statement, e.g. litigation). Provide the "
            "normalized metric/topic. Do NOT compute or restate numbers — quote the source."
        )
        response = self._parse(
            model=self._model, system=system, prompt=text, schema=_LLMClaims
        )
        candidates: list[ClaimCandidate] = []
        for c in response.parsed_output.claims:
            start = text.find(c.quote)
            if start < 0:
                start, end = 0, min(len(text), len(c.quote))
            else:
                end = start + len(c.quote)
            candidates.append(
                ClaimCandidate(
                    topic=c.topic,
                    kind=c.kind,  # validated against ClaimKind by ClaimCandidate
                    metric=c.metric,
                    period=c.period,
                    raw_text=c.quote,
                    char_start=start,
                    char_end=end,
                )
            )
        return Generated(ClaimExtraction(claims=candidates), self._usage(response, self._model))

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
        response = self._parse(
            model=self._model,
            system=system,
            prompt=prompt,
            schema=ConflictJudgment,
            max_tokens=1024,
        )
        return Generated(response.parsed_output, self._usage(response, self._model))

    # --- memo drafting (citations stay deterministic) ----------------------
    def compose_memo(self, *, context: MemoContext) -> Generated[Memo]:
        memo = _template_memo(context)
        system = (
            "You are a financial analyst. Rewrite ONLY the executive summary for the memo, "
            "grounded strictly in the provided contradictions and risk register. Do not invent "
            "figures or facts beyond what is given."
        )
        response = self._parse(
            model=self._model,
            system=system,
            prompt=context.model_dump_json(),
            schema=_Summary,
            max_tokens=1024,
        )
        memo.executive_summary = response.parsed_output.executive_summary
        return Generated(memo, self._usage(response, self._model))

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
        response = self._parse(
            model=self._model,
            system=system,
            prompt=memo.model_dump_json(),
            schema=CritiqueResult,
        )
        return Generated(response.parsed_output, self._usage(response, self._model))

    # --- faithfulness judge (eval) -----------------------------------------
    def judge_faithfulness(
        self, *, assertion: str, cited_text: str
    ) -> Generated[FaithfulnessJudgment]:
        system = (
            "Decide whether the assertion is supported by the cited source text. "
            "Return supported (bool), score (0..1), and a brief reason."
        )
        prompt = f"ASSERTION:\n{assertion}\n\nCITED TEXT:\n{cited_text}"
        response = self._parse(
            model=self._judge_model,
            system=system,
            prompt=prompt,
            schema=FaithfulnessJudgment,
            max_tokens=512,
        )
        return Generated(response.parsed_output, self._usage(response, self._judge_model))
