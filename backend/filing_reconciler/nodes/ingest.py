"""ingest — load each filing, classify type/period, build a section index.

Raw text is written to the content store; only refs + spans go into state.
The section index and classifier are intentionally light here and deepened in
step 4.
"""

from pathlib import Path

from ..deps import Deps
from ..models import SectionSpan, SourceDoc
from ..state import GraphState
from ..tools.convert import ConversionError, load_document_text
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


def _is_header(line: str) -> bool:
    """Heuristic header detector: ``ITEM N.`` lines or short ALL-CAPS headings."""
    if not line:
        return False
    if line.upper().startswith("ITEM "):
        return True
    return any(ch.isalpha() for ch in line) and line == line.upper() and len(line) <= 80


def _index_sections(text: str) -> list[SectionSpan]:
    """Build a section index from header lines; spans run header→next header."""
    headers: list[tuple[str, int]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if _is_header(stripped):
            headers.append((stripped[:80], offset))
        offset += len(line)

    if not headers:
        return [SectionSpan(name="body", start=0, end=len(text))]

    spans: list[SectionSpan] = []
    if headers[0][1] > 0:
        spans.append(SectionSpan(name="preamble", start=0, end=headers[0][1]))
    for i, (name, start) in enumerate(headers):
        end = headers[i + 1][1] if i + 1 < len(headers) else len(text)
        spans.append(SectionSpan(name=name, start=start, end=end))
    return spans


def _unique_doc_id(base: str, seen: set[str]) -> str:
    """De-duplicate ``doc_id`` within a run.

    Content-store keys and claim IDs derive from ``doc_id`` (``store.py``,
    ``common.new_id``); two uploaded files defaulting to the same stem (e.g.
    two ``10-K.pdf``) would otherwise silently overwrite each other's stored
    text rather than erroring or merging cleanly.
    """
    candidate = base
    n = 1
    while candidate in seen:
        candidate = f"{base}-{n}"
        n += 1
    seen.add(candidate)
    return candidate


def ingest(state: GraphState, deps: Deps) -> GraphState:
    with Timer() as timer:
        sources: list[SourceDoc] = []
        errors: list[str] = []
        company: str | None = state.get("company")
        seen_ids: set[str] = set()
        inputs = state.get("inputs", [])

        for item in inputs:
            path = Path(item.path)
            if not path.exists():
                errors.append(f"ingest: missing file {item.path}")
                continue

            try:
                conv = load_document_text(path, max_chars=deps.settings.max_document_chars)
            except ConversionError as exc:
                # Per-document failure — the rest of the run still proceeds,
                # exactly like the missing-file case above.
                errors.append(f"ingest: cannot read {path.name}: {exc}")
                continue

            text = conv.text
            if conv.truncated:
                # Naming the consequence (not just the fact) matters: a truncation
                # here is a false-negative risk for contradiction detection, not a
                # cosmetic one.
                errors.append(
                    f"ingest: {path.name} was truncated to {len(text):,} of "
                    f"{conv.original_char_len:,} characters (MAX_DOCUMENT_CHARS) — "
                    f"content after the cutoff was not analyzed and may contain "
                    f"contradictions this run will not report."
                )

            doc_id = _unique_doc_id(item.doc_id or path.stem, seen_ids)
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

        if not sources and inputs:
            errors.append(
                "ingest: no documents could be read — the run will produce an empty analysis"
            )

    update: GraphState = {
        "sources": sources,
        "company": company,
        "node_metrics": [metric("ingest", latency_ms=timer.latency_ms)],
    }
    if errors:
        update["errors"] = errors
    return update
