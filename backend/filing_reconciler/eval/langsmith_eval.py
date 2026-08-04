"""Optional LangSmith integration for the evaluation harness.

The offline harness in ``runner.py`` is the source of truth and runs with no network
or keys. This module *additionally* mirrors the eval set into a LangSmith dataset and
runs the same metrics as LangSmith evaluators, so results show up in the LangSmith UI
and can be tracked over time. It is a no-op (with a clear message) when LangSmith is
not installed or ``LANGSMITH_API_KEY`` is unset.

Run via ``filing-reconciler eval --langsmith`` (or ``make eval`` with tracing env set).
"""

from typing import Any

from ..config import get_settings
from ..deps import make_deps
from .dataset import load_eval_cases
from .metrics import _pred_key, tally_detection
from .runner import run_pipeline

_DATASET_NAME = "filing-reconciler-contradictions"


def _langsmith_available() -> tuple[bool, str]:
    settings = get_settings()
    if not settings.langsmith_api_key:
        return False, "LANGSMITH_API_KEY is not set"
    try:
        import langsmith  # noqa: F401
    except ImportError:
        return False, "langsmith package not installed"
    return True, ""


def push_to_langsmith() -> bool:
    """Create/refresh the dataset and run evaluators. Returns True if it ran."""
    ok, reason = _langsmith_available()
    if not ok:
        print(f"[langsmith] skipped: {reason}")
        return False

    from langsmith import Client  # imported lazily

    client = Client()
    deps = make_deps()
    cases = load_eval_cases()

    if not client.has_dataset(dataset_name=_DATASET_NAME):
        client.create_dataset(dataset_name=_DATASET_NAME)
    dataset = client.read_dataset(dataset_name=_DATASET_NAME)

    # One example per labeled set; inputs identify the set, outputs hold the gold labels.
    existing = {
        (ex.metadata or {}).get("set_id") for ex in client.list_examples(dataset_id=dataset.id)
    }
    for case in cases:
        if case.set_id in existing:
            continue
        client.create_example(
            dataset_id=dataset.id,
            inputs={"set_id": case.set_id},
            outputs={"gold": [g.model_dump() for g in case.labels.gold_contradictions]},
            metadata={"set_id": case.set_id},
        )

    case_by_id = {c.set_id: c for c in cases}

    def target(inputs: dict[str, Any]) -> dict[str, Any]:
        case = case_by_id[inputs["set_id"]]
        out = run_pipeline(case, deps)
        return {"predicted": [_pred_key(c) for c in out.contradictions]}

    def precision_evaluator(run: Any, example: Any) -> dict[str, Any]:
        case = case_by_id[example.inputs["set_id"]]
        out = run_pipeline(case, deps)
        t = tally_detection(out.contradictions, case.labels.gold_contradictions)
        return {"key": "precision", "score": t.precision}

    from langsmith import evaluate as ls_evaluate

    ls_evaluate(
        target,
        data=_DATASET_NAME,
        evaluators=[precision_evaluator],
        experiment_prefix="filing-reconciler",
    )
    print(f"[langsmith] uploaded dataset '{_DATASET_NAME}' and ran evaluators.")
    return True
