"""Deterministic numeric extraction and comparison.

Figures are NEVER taken from free-form LLM output — they are parsed here with
regexes and normalized to base units, then compared with a configurable tolerance.
This is the auditability + false-positive-control backbone of the reconciler: a
"numeric mismatch" is a deterministic, reproducible fact, not a model opinion.
"""

import re
from dataclasses import dataclass

from ..models import NumericDelta

_SCALE: dict[str, float] = {
    "thousand": 1e3,
    "thousands": 1e3,
    "k": 1e3,
    "million": 1e6,
    "millions": 1e6,
    "mm": 1e6,
    "billion": 1e9,
    "billions": 1e9,
    "bn": 1e9,
}

# "$1,000.0 million", "$1,200 million", "$310.0 million", "$120 million"
_MONEY_RE = re.compile(
    r"\$\s?([\d,]+(?:\.\d+)?)\s*(thousand|thousands|million|millions|billion|billions|bn|mm|k)?",
    re.IGNORECASE,
)
# scaled amount without a currency symbol, e.g. "1,300 million"
_SCALED_RE = re.compile(
    r"(?<![\w$.])([\d,]+(?:\.\d+)?)\s*(thousand|thousands|million|millions|billion|billions|bn|mm)\b",
    re.IGNORECASE,
)
_PCT_RE = re.compile(r"([\d]+(?:\.\d+)?)\s*%")


@dataclass(frozen=True)
class NumberMatch:
    value: float  # normalized to base units (USD for money; the % value for percent)
    unit: str  # "USD" | "percent" | "number"
    raw: str
    start: int
    end: int


def _to_float(num: str) -> float:
    return float(num.replace(",", ""))


def _spans_overlap(a: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    return any(not (a[1] <= s or a[0] >= e) for s, e in spans)


def extract_numbers(text: str) -> list[NumberMatch]:
    """All numeric figures in ``text`` with char spans, normalized to base units."""
    matches: list[NumberMatch] = []
    claimed: list[tuple[int, int]] = []

    for m in _MONEY_RE.finditer(text):
        scale = (m.group(2) or "").lower()
        mult = _SCALE.get(scale, 1.0)
        matches.append(
            NumberMatch(_to_float(m.group(1)) * mult, "USD", m.group(0), m.start(), m.end())
        )
        claimed.append((m.start(), m.end()))

    for m in _PCT_RE.finditer(text):
        if _spans_overlap((m.start(), m.end()), claimed):
            continue
        matches.append(
            NumberMatch(_to_float(m.group(1)), "percent", m.group(0), m.start(), m.end())
        )
        claimed.append((m.start(), m.end()))

    for m in _SCALED_RE.finditer(text):
        if _spans_overlap((m.start(), m.end()), claimed):
            continue
        mult = _SCALE.get(m.group(2).lower(), 1.0)
        matches.append(
            NumberMatch(_to_float(m.group(1)) * mult, "USD", m.group(0), m.start(), m.end())
        )
        claimed.append((m.start(), m.end()))

    matches.sort(key=lambda nm: nm.start)
    return matches


def first_number(text: str) -> NumberMatch | None:
    nums = extract_numbers(text)
    return nums[0] if nums else None


def compare(value_a: float, value_b: float, tolerance_pct: float) -> NumericDelta:
    """Symmetric relative comparison. ``within_tolerance`` ⇒ not a mismatch."""
    abs_diff = abs(value_a - value_b)
    denom = max(abs(value_a), abs(value_b))
    pct_diff = (abs_diff / denom * 100.0) if denom else 0.0
    return NumericDelta(
        value_a=value_a,
        value_b=value_b,
        abs_diff=abs_diff,
        pct_diff=round(pct_diff, 4),
        within_tolerance=pct_diff <= tolerance_pct,
    )
