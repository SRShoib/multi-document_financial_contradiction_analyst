"""ingest — load each filing, classify type/period, build a section index.

Raw text is written to the content store; only refs + spans go into state.
The section index and classifier are intentionally light here and deepened in
step 4.
"""

from pathlib import Path

from ..deps import Deps
from ..models import SectionSpan, SourceDoc
from ..state import GraphState
from .common import Timer, metric

_TYPE_KEYWORDS: list[tuple[str, str]] = [
    ("10-K", "form 10-k"),
    ("10-Q", "form 10-q"),
    ("earnings_call", "earnings conference call"),
    ("earnings_call", "earnings call transcript"),
    ("press_release", "reports") ,
]


def classify_doc_type(text: str, hint: str | None) -> str:
    if hint:
        return hint
    head = text[:400].lower()
    for doc_type, kw in _TYPE_KEYWORDS:
        if kw in head:
            return doc_type
    return "unknown"


def _index_sections(text: str) -> list[SectionSpan]:
    """Single whole-document section for now (real header indexing lands in step 4)."""
    return [SectionSpan(name="body", start=0, end=len(text))]


def ingest(state: GraphState, deps: Deps) -> GraphState:
    with Timer() as timer:
        sources: list[SourceDoc] = []
        errors: list[str] = []
        company: str | None = state.get("company")

        for item in state.get("inputs", []):
            path = Path(item.path)
            if not path.exists():
                errors.append(f"ingest: missing file {item.path}")
                continue
            text = path.read_text(encoding="utf-8")
            doc_id = item.doc_id or path.stem
            text_ref = deps.store.put(doc_id, text)
            company = company or item.company
            sources.append(
                SourceDoc(
                    doc_id=doc_id,
                    doc_type=classify_doc_type(text, item.doc_type),
                    period=item.period,
                    company=item.company,
                    text_ref=text_ref,
                    char_len=len(text),
                    sections=_index_sections(text),
                )
            )

    update: GraphState = {
        "sources": sources,
        "company": company,
        "node_metrics": [metric("ingest", latency_ms=timer.latency_ms)],
    }
    if errors:
        update["errors"] = errors
    return update
