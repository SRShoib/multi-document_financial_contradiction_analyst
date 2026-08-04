"""Offline evaluation runner.

Executes the analysis pipeline deterministically over each labeled sample set
(calling the nodes directly — no graph/HITL, for speed and reproducibility),
compares predictions to ground truth, and aggregates the metrics. ``make eval`` /
``filing-reconciler eval`` print the report; ``tests/test_eval.py`` asserts
thresholds so CI fails on a regression.
"""

from collections import Counter
from dataclasses import dataclass, field

from ..deps import Deps, make_deps
from ..models import Claim, Contradiction, Memo
from ..nodes.draft_memo import draft_memo
from ..nodes.extract_claims import extract_claims
from ..nodes.ingest import ingest
from ..nodes.reconcile import reconcile
from ..nodes.risk_scoring import risk_scoring
from .dataset import EvalCase, load_eval_cases
from .metrics import (
    Calibration,
    DetectionTally,
    _gold_key,
    _pred_key,
    calibration,
    citation_exact_span,
    citation_judge,
    memo_citation_coverage,
    numeric_accuracy,
    tally_detection,
)


@dataclass
class PipelineOutput:
    contradictions: list[Contradiction]
    memo: Memo
    doc_texts: dict[str, str]


def run_pipeline(case: EvalCase, deps: Deps) -> PipelineOutput:
    state = ingest({"inputs": case.inputs, "company": case.company}, deps)
    sources = state["sources"]
    doc_texts = {d.doc_id: deps.store.get(d.text_ref) for d in sources}

    claims: list[Claim] = []
    for doc in sources:
        claims += extract_claims({"doc": doc}, deps)["claims"]

    contradictions = reconcile({"claims": claims}, deps)["contradictions"]
    register = risk_scoring({"contradictions": contradictions}, deps)["risk_register"]
    memo = draft_memo(
        {
            "sources": sources,
            "claims": claims,
            "contradictions": contradictions,
            "risk_register": register,
            "company": case.company,
        },
        deps,
    )["draft_memo"]
    assert memo is not None  # draft_memo always composes a memo
    return PipelineOutput(contradictions=contradictions, memo=memo, doc_texts=doc_texts)


@dataclass
class CaseResult:
    set_id: str
    tally: DetectionTally
    predicted: int
    gold: int


@dataclass
class EvalReport:
    detection: DetectionTally
    numeric_correct: int
    numeric_total: int
    citation_ok: int
    citation_total: int
    judge_supported: float
    judge_score: float
    memo_cite_ok: int
    memo_cite_total: int
    cal: Calibration
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def precision(self) -> float:
        return self.detection.precision

    @property
    def recall(self) -> float:
        return self.detection.recall

    @property
    def f0_5(self) -> float:
        return self.detection.fbeta(0.5)

    @property
    def numeric_acc(self) -> float:
        return self.numeric_correct / self.numeric_total if self.numeric_total else 1.0

    @property
    def citation_exact(self) -> float:
        return self.citation_ok / self.citation_total if self.citation_total else 1.0

    @property
    def memo_cite_coverage(self) -> float:
        return self.memo_cite_ok / self.memo_cite_total if self.memo_cite_total else 1.0


def evaluate(deps: Deps | None = None) -> EvalReport:
    deps = deps or make_deps()
    cases = load_eval_cases()

    detection = DetectionTally()
    num_correct = num_total = 0
    cite_ok = cite_total = 0
    memo_ok = memo_total = 0
    all_pred: list[Contradiction] = []
    cal_samples: list[tuple[float, bool]] = []
    case_results: list[CaseResult] = []

    for case in cases:
        out = run_pipeline(case, deps)
        gold = case.labels.gold_contradictions

        t = tally_detection(out.contradictions, gold)
        detection = detection + t
        case_results.append(
            CaseResult(case.set_id, t, len(out.contradictions), len(gold))
        )

        c, n = numeric_accuracy(out.contradictions, case.labels.numeric_checks)
        num_correct += c
        num_total += n

        ok, tot = citation_exact_span(out.contradictions, out.doc_texts)
        cite_ok += ok
        cite_total += tot

        mok, mtot = memo_citation_coverage(out.memo)
        memo_ok += mok
        memo_total += mtot

        # Per-prediction correctness for calibration (matched within the case's gold).
        want = Counter(_gold_key(g) for g in gold)
        for pred in out.contradictions:
            key = _pred_key(pred)
            correct = want[key] > 0
            if correct:
                want[key] -= 1
            cal_samples.append((pred.confidence, correct))

        all_pred.extend(out.contradictions)

    judge_supported, judge_score = citation_judge(all_pred, deps.llm)

    return EvalReport(
        detection=detection,
        numeric_correct=num_correct,
        numeric_total=num_total,
        citation_ok=cite_ok,
        citation_total=cite_total,
        judge_supported=round(judge_supported, 4),
        judge_score=round(judge_score, 4),
        memo_cite_ok=memo_ok,
        memo_cite_total=memo_total,
        cal=calibration(cal_samples),
        cases=case_results,
    )


def format_report(report: EvalReport) -> str:
    lines = [
        "=" * 64,
        "filing-reconciler — offline evaluation",
        "=" * 64,
        "Contradiction detection (precision-weighted):",
        f"  precision : {report.precision:.3f}   "
        f"(tp={report.detection.tp} fp={report.detection.fp} fn={report.detection.fn})",
        f"  recall    : {report.recall:.3f}",
        f"  F0.5      : {report.f0_5:.3f}   (beta=0.5 — false positives penalized)",
        "",
        f"Numeric-mismatch accuracy : {report.numeric_acc:.3f} "
        f"({report.numeric_correct}/{report.numeric_total})",
        f"Citation exact-span match : {report.citation_exact:.3f} "
        f"({report.citation_ok}/{report.citation_total})",
        f"Citation LLM-judge        : supported={report.judge_supported:.3f} "
        f"mean_score={report.judge_score:.3f}",
        f"Memo citation coverage    : {report.memo_cite_coverage:.3f} "
        f"({report.memo_cite_ok}/{report.memo_cite_total})",
        "",
        f"Confidence calibration (ECE) : {report.cal.ece:.3f} over {report.cal.samples} preds",
        "  reliability (bin: acc vs conf):",
    ]
    for b in report.cal.bins:
        if b.count:
            lines.append(
                f"    [{b.lo:.1f}-{b.hi:.1f}] n={b.count} "
                f"acc={b.accuracy:.2f} conf={b.avg_confidence:.2f}"
            )
    lines.append("")
    lines.append("Per-set:")
    for cr in report.cases:
        lines.append(
            f"  {cr.set_id}: predicted={cr.predicted} gold={cr.gold} "
            f"(tp={cr.tally.tp} fp={cr.tally.fp} fn={cr.tally.fn})"
        )
    lines.append("=" * 64)
    return "\n".join(lines)
