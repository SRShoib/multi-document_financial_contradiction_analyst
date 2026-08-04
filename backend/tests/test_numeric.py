"""Deterministic numeric extraction + comparison."""

import math

from filing_reconciler.tools.numeric import compare, extract_numbers, first_number


def test_money_with_scale_normalizes_to_base_units() -> None:
    (m,) = extract_numbers("$1,000.0 million")
    assert m.unit == "USD"
    assert math.isclose(m.value, 1_000_000_000.0)


def test_decimal_inside_money_is_not_split_or_dropped() -> None:
    # Regression: the decimal point must not be treated as a sentence/token break.
    n = first_number("Net income was $120.0 million, up from before.")
    assert n is not None
    assert math.isclose(n.value, 120_000_000.0)


def test_percent_and_plain_money() -> None:
    nums = extract_numbers("Gross margin was 62% and revenue was $1,200 million.")
    by_unit = {n.unit: n.value for n in nums}
    assert by_unit["percent"] == 62.0
    assert math.isclose(by_unit["USD"], 1_200_000_000.0)


def test_compare_flags_mismatch_and_respects_tolerance() -> None:
    big = compare(1_000_000_000.0, 1_200_000_000.0, tolerance_pct=0.5)
    assert not big.within_tolerance
    assert math.isclose(big.pct_diff, 16.6667, abs_tol=1e-3)

    equal = compare(120.0, 120.0, tolerance_pct=0.5)
    assert equal.within_tolerance
    assert equal.pct_diff == 0.0
