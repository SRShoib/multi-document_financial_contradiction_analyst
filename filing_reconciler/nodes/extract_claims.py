"""extract_claims — fan out one branch per document with the Send API.

Each branch pulls structured claims (with char-span provenance) from a single
document and returns them; the ``claims`` channel uses an ``operator.add`` reducer
so the parallel branches concatenate. Numeric *values* are parsed deterministically
in step 4 — this milestone emits a placeholder claim per document so the fan-out
and the reducer are observable end-to-end.
"""

from typing import TypedDict

from langgraph.types import Send

from ..deps import Deps
from ..models import Citation, Claim, SourceDoc
from ..state import GraphState
from .common import Timer, metric, new_id


class ExtractTask(TypedDict):
    doc: SourceDoc


def fan_out_to_extract(state: GraphState) -> list[Send]:
    """Map step: one Send per ingested document → parallel ``extract_claims`` branches."""
    return [Send("extract_claims", ExtractTask(doc=doc)) for doc in state.get("sources", [])]


def extract_claims(task: ExtractTask, deps: Deps) -> GraphState:
    doc = task["doc"]
    with Timer() as timer:
        text = deps.store.get(doc.text_ref)
        generated = deps.llm.extract_claims(doc=doc, text=text)

        # Step-3 placeholder so the reducer concatenation is observable; replaced by
        # deterministic numeric + LLM-candidate extraction in step 4.
        span_end = min(60, doc.char_len)
        placeholder = Claim(
            claim_id=new_id(doc.doc_id, "placeholder"),
            doc_id=doc.doc_id,
            doc_type=doc.doc_type,
            period=doc.period,
            topic="placeholder",
            kind="narrative",
            raw_text=text[:span_end],
            citation=Citation(
                doc_id=doc.doc_id, start=0, end=span_end, quote=text[:span_end], section="body"
            ),
        )
        # In step 4, `generated.value.claims` (LLM candidates) + deterministic numeric
        # parsing replace this placeholder.
        claims = [placeholder]

    return {
        "claims": claims,
        "cost_usd": generated.usage.cost_usd,
        "node_metrics": [
            metric("extract_claims", cost_usd=generated.usage.cost_usd, latency_ms=timer.latency_ms)
        ],
    }
