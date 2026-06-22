"""Lightweight, deterministic text utilities: sentence spans, period detection,
and section lookup. No LLM — these feed the claim extractor and citation builder.
"""

import re
from collections.abc import Callable

from ..models import SectionSpan

# Sentence boundary: punctuation followed by whitespace, OR newline(s). The
# punctuation+whitespace lookbehind means a decimal point inside a number
# ("$1,000.0 million") is NOT a boundary — critical for correct figure parsing.
_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+|\n+")

_ORDINAL = {"first": 1, "second": 2, "third": 3, "fourth": 4}
# quarter-end month -> fiscal quarter (calendar-year fiscal assumption for samples)
_MONTH_QUARTER = {"march": 1, "june": 2, "september": 3, "december": 4}

_QUARTER_OF_FY_RE = re.compile(
    r"(first|second|third|fourth)\s+quarter\s+of\s+fiscal\s+year\s+(\d{4})", re.IGNORECASE
)
_QUARTER_ENDED_RE = re.compile(
    r"quarter\s+ended\s+(january|february|march|april|may|june|july|august|september|"
    r"october|november|december)\s+\d{1,2},\s*(\d{4})",
    re.IGNORECASE,
)
_FY_ENDED_RE = re.compile(
    r"fiscal\s+year\s+ended\s+[A-Za-z]+\s+\d{1,2},\s*(\d{4})", re.IGNORECASE
)
_FULL_YEAR_RE = re.compile(r"full(?:\s+fiscal)?\s+year\s+(\d{4})", re.IGNORECASE)
_FISCAL_YEAR_RE = re.compile(r"fiscal\s+year\s+(\d{4})", re.IGNORECASE)
_FISCAL_BARE_RE = re.compile(r"fiscal\s+(\d{4})", re.IGNORECASE)


def _norm_quarter_of_fy(m: re.Match[str]) -> str:
    return f"Q{_ORDINAL[m.group(1).lower()]}-FY{m.group(2)}"


def _norm_quarter_ended(m: re.Match[str]) -> str:
    return f"Q{_MONTH_QUARTER[m.group(1).lower()]}-FY{m.group(2)}"


def _norm_fy(m: re.Match[str]) -> str:
    return f"FY{m.group(1)}"


# (regex, normalizer, rank). Lower rank breaks ties at equal positions
# (a quarter reference is more specific than a bare fiscal year).
_PERIOD_PATTERNS: list[tuple[re.Pattern[str], Callable[[re.Match[str]], str], int]] = [
    (_QUARTER_OF_FY_RE, _norm_quarter_of_fy, 0),
    (_QUARTER_ENDED_RE, _norm_quarter_ended, 0),
    (_FY_ENDED_RE, _norm_fy, 1),
    (_FULL_YEAR_RE, _norm_fy, 1),
    (_FISCAL_YEAR_RE, _norm_fy, 1),
    (_FISCAL_BARE_RE, _norm_fy, 2),
]


def split_sentences(text: str) -> list[tuple[str, int, int]]:
    """Return ``(sentence, start, end)`` tuples with exact (stripped) char offsets."""
    bounds: list[tuple[int, int]] = []
    last = 0
    for m in _BOUNDARY_RE.finditer(text):
        bounds.append((last, m.start()))
        last = m.end()
    bounds.append((last, len(text)))

    out: list[tuple[str, int, int]] = []
    for s, e in bounds:
        seg = text[s:e]
        stripped = seg.strip()
        if not stripped:
            continue
        lead = len(seg) - len(seg.lstrip())
        start = s + lead
        out.append((stripped, start, start + len(stripped)))
    return out


def detect_period(text: str, fallback: str | None = None) -> str | None:
    """Normalize the *primary* period reference to ``FY<year>`` or ``Q<n>-FY<year>``.

    Picks the earliest-mentioned period (the subject of the sentence) so comparative
    references like "...compared to fiscal 2022" don't override the primary period.
    """
    best: tuple[int, int, str] | None = None
    for rx, norm, rank in _PERIOD_PATTERNS:
        m = rx.search(text)
        if m is None:
            continue
        cand = (m.start(), rank, norm(m))
        if best is None or (cand[0], cand[1]) < (best[0], best[1]):
            best = cand
    return best[2] if best else fallback


def find_section(sections: list[SectionSpan], offset: int) -> str | None:
    for s in sections:
        if s.start <= offset < s.end:
            return s.name
    return None
