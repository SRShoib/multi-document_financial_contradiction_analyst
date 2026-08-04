"""Evaluation regression gate (CI fails if metrics drop below threshold).

Marked ``eval`` so it can be run as a dedicated CI job (`pytest -m eval`).
"""

from pathlib import Path

import pytest
from filing_reconciler.config import Settings
from filing_reconciler.deps import make_deps
from filing_reconciler.eval.runner import evaluate

pytestmark = pytest.mark.eval


def test_offline_eval_meets_thresholds(tmp_path: Path) -> None:
    deps = make_deps(
        Settings(
            _env_file=None,
            content_store_dir=str(tmp_path / "c"),
            output_dir=str(tmp_path / "o"),
        )
    )
    report = evaluate(deps)

    # Precision is weighted: zero false positives across all sets (incl. the clean one).
    assert report.precision == 1.0
    assert report.recall >= 0.95
    assert report.f0_5 >= 0.95
    assert report.numeric_acc == 1.0
    assert report.citation_exact == 1.0
    assert report.memo_cite_coverage == 1.0
    # Calibration should not be wildly off (catches gross confidence regressions).
    assert report.cal.ece <= 0.35

    by_set = {c.set_id: c for c in report.cases}
    assert by_set["set_c"].predicted == 0  # clean control → no false positives
    assert by_set["set_a"].tally.tp == 3
    assert by_set["set_b"].tally.tp == 3
