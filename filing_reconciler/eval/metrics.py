"""Evaluation metrics.

Design choices:
* **Precision is weighted over recall** (Fbeta with beta=0.5) — a false contradiction
  wastes analyst time and erodes trust, so it is the costly error.
* **Numeric-mismatch accuracy** is measured against labeled metric/period checks
  (true positives AND true negatives), validating the deterministic comparator.
* **Citation faithfulness** has two parts: an exact char-span match (the citation's
  quote must equal the source slice) and an LLM-judge score (semantic support).
* **Calibration** is summarized by Expected Calibration Error (ECE) plus a reliability
  table, so we can see whether the confidence scores mean anything.
"""

from collections import Counter
from dataclasses import dataclass, field

from ..llm import LLM
from ..models import Contradiction, Memo
from ..tools.numeric import extract_numbers
from .dataset import GoldContradiction, NumericCheck


def _pred_key(c: Contradiction) -> tuple[str, str, str | None]:
    # Period is part of the identity for numeric/guidance; narrative conflicts are
    # matched on type+topic only (the matter spans periods).
    period = None if c.ctype == "narrative_conflict" else c.period
    return (c.ctype, c.topic, period)


def _gold_key(g: GoldContradiction) -> tuple[str, str, str | None]:
    period = None if g.ctype == "narrative_conflict" else g.period
    return (g.ctype, g.topic, period)


@dataclass
class DetectionTally:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def __add__(self, other: "DetectionTally") -> "DetectionTally":
        return DetectionTally(self.tp + other.tp, self.fp + other.fp, self.fn + other.fn)

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 1.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 1.0

    def fbeta(self, beta: float = 0.5) -> float:
        p, r = self.precision, self.recall
        b2 = beta * beta
        denom = b2 * p + r
        return (1 + b2) * p * r / denom if denom else 0.0


def tally_detection(
    predicted: list[Contradiction], gold: list[GoldContradiction]
) -> DetectionTally:
    pred = Counter(_pred_key(c) for c in predicted)
    want = Counter(_gold_key(g) for g in gold)
    tp = sum((pred & want).values())
    fp = sum((pred - want).values())
    fn = sum((want - pred).values())
    return DetectionTally(tp=tp, fp=fp, fn=fn)


def numeric_accuracy(predicted: list[Contradiction], checks: list[NumericCheck]) -> tuple[int, int]:
    """Return (correct, total) over labeled numeric checks (mismatch true negatives included)."""
    mismatched = {
        (c.topic, c.period) for c in predicted if c.ctype == "numeric_mismatch"
    }
    correct = 0
    for chk in checks:
        predicted_mismatch = (chk.metric, chk.period) in mismatched
        correct += int(predicted_mismatch == chk.expected_mismatch)
    return correct, len(checks)


def citation_exact_span(
    predicted: list[Contradiction], doc_texts: dict[str, str]
) -> tuple[int, int]:
    """Fraction of citations whose quote exactly equals the cited source slice."""
    ok = 0
    total = 0
    for c in predicted:
        for cit in c.citations:
            total += 1
            text = doc_texts.get(cit.doc_id, "")
            if text[cit.start : cit.end] == cit.quote:
                ok += 1
    return ok, total


def citation_judge(predicted: list[Contradiction], llm: LLM) -> tuple[float, float]:
    """LLM-judge support: returns (fraction_supported, mean_score) over contradictions."""
    if not predicted:
        return 1.0, 1.0
    supported = 0
    score_sum = 0.0
    for c in predicted:
        cited_text = " ".join(cit.quote for cit in c.citations)
        judged = llm.judge_faithfulness(assertion=c.rationale, cited_text=cited_text).value
        supported += int(judged.supported)
        score_sum += judged.score
    return supported / len(predicted), score_sum / len(predicted)


def memo_citation_coverage(memo: Memo) -> tuple[int, int]:
    """Fraction of memo sections asserting a figure that carry at least one citation."""
    ok = 0
    total = 0
    for section in memo.sections:
        asserts_figure = bool(extract_numbers(section.body))
        if not asserts_figure:
            continue
        total += 1
        ok += int(bool(section.citations))
    return ok, total


@dataclass
class ReliabilityBin:
    lo: float
    hi: float
    count: int = 0
    correct: int = 0
    conf_sum: float = 0.0

    @property
    def accuracy(self) -> float:
        return self.correct / self.count if self.count else 0.0

    @property
    def avg_confidence(self) -> float:
        return self.conf_sum / self.count if self.count else 0.0


@dataclass
class Calibration:
    ece: float
    bins: list[ReliabilityBin] = field(default_factory=list)
    samples: int = 0


def calibration(samples: list[tuple[float, bool]], n_bins: int = 5) -> Calibration:
    """ECE + reliability bins from (confidence, was_correct) pairs."""
    bins = [ReliabilityBin(lo=i / n_bins, hi=(i + 1) / n_bins) for i in range(n_bins)]
    for conf, correct in samples:
        idx = min(int(conf * n_bins), n_bins - 1)
        b = bins[idx]
        b.count += 1
        b.correct += int(correct)
        b.conf_sum += conf
    total = len(samples)
    ece = 0.0
    if total:
        for b in bins:
            if b.count:
                ece += (b.count / total) * abs(b.accuracy - b.avg_confidence)
    return Calibration(ece=round(ece, 4), bins=bins, samples=total)
