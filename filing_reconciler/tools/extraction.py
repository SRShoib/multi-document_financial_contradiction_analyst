"""Deterministic claim-candidate proposal.

This is the logic the *stub* LLM uses to stand in for a model's extraction step:
it proposes claim spans/topics (numeric actuals, forward-looking guidance, and
narrative claims). It deliberately does NOT assign numeric values — the extract
node parses those deterministically from the cited span (see ``tools/numeric.py``),
preserving the "no free-form figures" guarantee.

A real LLM provider implements the same contract: propose spans/topics, never the
authoritative number.
"""

from ..models import ClaimCandidate
from .numeric import extract_numbers
from .text import detect_period, split_sentences

# metric keyword -> canonical metric key (numeric actuals)
_METRIC_KEYWORDS: dict[str, str] = {
    "research and development": "rnd_expense",
    "operating expenses": "operating_expenses",
    "total revenue": "revenue",
    "revenue": "revenue",
    "net income": "net_income",
    "gross margin": "gross_margin",
    "earnings per share": "eps",
    "diluted earnings per share": "eps",
}
_GUIDANCE_TRIGGERS = ("expect", "guidance", "outlook", "anticipate")
_LEGAL_KEYWORDS = ("legal proceeding", "litigation", "lawsuit")

# Narrative polarity: does the claim DENY (-1) or ASSERT (+1) the matter exists?
# Deny phrases are checked first because they contain affirmative substrings.
_DENY_PHRASES = (
    "not currently a party",
    "not a party",
    "do not anticipate",
    "not anticipate",
    "no pending material",
    "no material",
)
_ASSERT_PHRASES = (
    "are a party",
    "is a party",
    "party to a material",
    "material lawsuit",
    "currently a party",
)


def narrative_polarity(text: str) -> int:
    """-1 denies the matter, +1 asserts it exists, 0 unknown."""
    low = text.lower()
    if any(p in low for p in _DENY_PHRASES):
        return -1
    if any(p in low for p in _ASSERT_PHRASES):
        return 1
    return 0


def _earliest_metric(lower: str) -> str | None:
    """Pick the metric whose keyword appears earliest in the sentence."""
    best: tuple[int, str] | None = None
    for kw, metric in _METRIC_KEYWORDS.items():
        idx = lower.find(kw)
        if idx >= 0 and (best is None or idx < best[0]):
            best = (idx, metric)
    return best[1] if best else None


def _has_number(text: str) -> bool:
    return bool(extract_numbers(text))


def propose_candidates(
    text: str, doc_type: str, default_period: str | None
) -> list[ClaimCandidate]:
    candidates: list[ClaimCandidate] = []
    for sentence, start, end in split_sentences(text):
        lower = sentence.lower()
        period = detect_period(sentence, default_period)

        # Forward-looking guidance about revenue (must carry a figure to be useful).
        if (
            any(t in lower for t in _GUIDANCE_TRIGGERS)
            and "revenue" in lower
            and _has_number(sentence)
        ):
            candidates.append(
                ClaimCandidate(
                    topic="guidance.revenue",
                    kind="guidance",
                    metric="revenue",
                    period=period,
                    raw_text=sentence,
                    char_start=start,
                    char_end=end,
                )
            )
        else:
            # Numeric actual: a known metric reported with a figure.
            metric = _earliest_metric(lower)
            if metric and _has_number(sentence):
                candidates.append(
                    ClaimCandidate(
                        topic=metric,
                        kind="numeric",
                        metric=metric,
                        period=period,
                        raw_text=sentence,
                        char_start=start,
                        char_end=end,
                    )
                )

        # Narrative legal/litigation claim (qualitative; reconciled by the LLM path).
        # Require a substantive sentence so bare headings ("LEGAL PROCEEDINGS") are skipped.
        if any(k in lower for k in _LEGAL_KEYWORDS) and len(sentence.split()) >= 5:
            candidates.append(
                ClaimCandidate(
                    topic="litigation",
                    kind="narrative",
                    metric=None,
                    period=period,
                    raw_text=sentence,
                    char_start=start,
                    char_end=end,
                )
            )

    return candidates
