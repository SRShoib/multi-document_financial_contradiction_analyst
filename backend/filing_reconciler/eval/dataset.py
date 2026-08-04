"""Offline evaluation dataset: sample document sets + ground-truth labels.

Each ``data/samples/<set_id>/`` ships a ``manifest.json`` (documents) and a
``labels.json`` (gold contradictions + numeric checks). The repo therefore runs the
full evaluation with no external data or API keys.
"""

from pydantic import BaseModel, Field

from ..models import ContradictionType, DocInput
from ..samples import list_sample_sets, load_sample, sample_dir


class GoldContradiction(BaseModel):
    ctype: ContradictionType
    topic: str
    period: str | None = None
    doc_ids: list[str] = Field(default_factory=list)
    note: str = ""


class NumericCheck(BaseModel):
    metric: str
    period: str | None = None
    expected_mismatch: bool


class EvalLabels(BaseModel):
    set_id: str
    gold_contradictions: list[GoldContradiction] = Field(default_factory=list)
    numeric_checks: list[NumericCheck] = Field(default_factory=list)


class EvalCase(BaseModel):
    set_id: str
    company: str
    inputs: list[DocInput]
    labels: EvalLabels


def load_labels(set_id: str) -> EvalLabels:
    path = sample_dir(set_id) / "labels.json"
    return EvalLabels.model_validate_json(path.read_text(encoding="utf-8"))


def has_labels(set_id: str) -> bool:
    return (sample_dir(set_id) / "labels.json").exists()


def load_eval_cases() -> list[EvalCase]:
    """All labeled sample sets as evaluation cases."""
    cases: list[EvalCase] = []
    for set_id in list_sample_sets():
        if not has_labels(set_id):
            continue
        company, inputs = load_sample(set_id)
        cases.append(
            EvalCase(set_id=set_id, company=company, inputs=inputs, labels=load_labels(set_id))
        )
    return cases
