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


# --------------------------------------------------------------------------- #
# Quote location — recovers an exact char span for a model-returned "verbatim"
# quote, tolerating the artifacts real PDF/HTML extraction introduces (extra
# whitespace, line-wrap hyphenation) without ever fabricating a wrong span.
# --------------------------------------------------------------------------- #
def collapse_ws_with_map(text: str) -> tuple[str, list[int]]:
    """Collapse whitespace runs in ``text`` to single spaces, tracking offsets.

    Returns ``(collapsed, offsets)`` where ``collapsed[i]`` originates at
    ``text[offsets[i]]`` — the table lets a match found in the collapsed string
    be translated back into an exact span in the original text.
    """
    out: list[str] = []
    offsets: list[int] = []
    prev_ws = False
    for i, ch in enumerate(text):
        if ch.isspace():
            if not prev_ws:
                out.append(" ")
                offsets.append(i)
            prev_ws = True
        else:
            out.append(ch)
            offsets.append(i)
            prev_ws = False
    return "".join(out), offsets


_SOFT_HYPHEN_RE = re.compile(r"(?<=[a-z])-\n(?=[a-z])")


def _dehyphenate_with_map(text: str) -> tuple[str, list[int]]:
    """Join a lowercase word split by a hyphen at a PDF line-wrap, tracking offsets.

    Scoped to lowercase-lowercase (``reve-\\nnue`` -> ``revenue``) so hyphenated
    proper nouns and codes like "10-K" are left untouched. Same offset-map shape
    as ``collapse_ws_with_map`` so the two can be composed.
    """
    out: list[str] = []
    offsets: list[int] = []
    i = 0
    n = len(text)
    while i < n:
        if (
            text[i] == "-"
            and i + 2 < n
            and text[i + 1] == "\n"
            and out
            and out[-1].islower()
            and text[i + 2].islower()
        ):
            i += 2  # drop the '-' and '\n'; the join happens naturally on the next char
            continue
        out.append(text[i])
        offsets.append(i)
        i += 1
    return "".join(out), offsets


def locate_quote(text: str, quote: str) -> tuple[int, int] | None:
    """Best-effort, deterministic span locator for a model-returned "verbatim" quote.

    Tries progressively fuzzier matches against artifacts of PDF text extraction
    (extra whitespace, line-wrap hyphenation) but never fabricates a span: a
    plausible-looking wrong citation is worse than a claim with no citation at
    all, because it passes every downstream check and lands in the memo looking
    verified. Callers MUST treat ``None`` as "could not locate" and must not
    invent a fallback span.
    """
    if not quote:
        return None

    # Tier 1: exact match.
    start = text.find(quote)
    if start >= 0:
        return start, start + len(quote)

    collapsed_quote, _ = collapse_ws_with_map(quote)
    if not collapsed_quote:
        return None

    # Tier 2: whitespace-collapsed match (handles reflowed/extra-spaced text).
    collapsed_text, offsets = collapse_ws_with_map(text)
    idx = collapsed_text.find(collapsed_quote)
    if idx >= 0:
        return offsets[idx], offsets[idx + len(collapsed_quote) - 1] + 1

    # Tier 3: same, after undoing line-wrap hyphenation in the source text.
    dehyph_text, dehyph_offsets = _dehyphenate_with_map(text)
    collapsed_dehyph, collapse_offsets = collapse_ws_with_map(dehyph_text)
    idx = collapsed_dehyph.find(collapsed_quote)
    if idx >= 0:
        start = dehyph_offsets[collapse_offsets[idx]]
        end = dehyph_offsets[collapse_offsets[idx + len(collapsed_quote) - 1]] + 1
        return start, end

    return None
