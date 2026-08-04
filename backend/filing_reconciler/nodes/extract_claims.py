"""extract_claims — fan out one branch per document with the Send API.

Each branch pulls structured claims (with char-span provenance) from a single
document and returns them; the ``claims`` channel uses an ``operator.add`` reducer
so the parallel branches concatenate.

The LLM (here, the deterministic stub) proposes claim *spans/topics*; the numeric
*value* of each claim is parsed deterministically from the cited span via
``tools/numeric.py`` — never trusted from model output.
"""

from typing import TypedDict

from langgraph.types import Send

from ..deps import Deps
from ..models import Citation, Claim, SourceDoc
from ..state import GraphState
from ..tools.numeric import first_number
from ..tools.text import find_section
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
        try:
            generated = deps.llm.extract_claims(doc=doc, text=text)
        except Exception as exc:
            # A provider failure (context-length overflow, rate limit, refusal,
            # network error) must degrade this document to "contributed no claims",
            # not abort the whole run — the other documents' branches are unaffected.
            return {
                "claims": [],
                "errors": [f"extract_claims: {doc.doc_id} failed: {exc}"],
                "node_metrics": [metric("extract_claims", latency_ms=timer.latency_ms)],
            }

        claims: list[Claim] = []
        dropped = 0
        for i, cand in enumerate(generated.value.claims):
            quote = text[cand.char_start : cand.char_end]
            # Provenance invariant: the cited span must exactly reproduce the quote.
            # A candidate the provider couldn't locate (``located=False``) or whose
            # offsets don't actually match the raw text is dropped rather than
            # emitting a citation that looks verified but points at the wrong place.
            if not cand.located or quote != cand.raw_text:
                dropped += 1
                continue
            number = first_number(quote) if cand.kind in ("numeric", "guidance") else None
            claims.append(
                Claim(
                    claim_id=new_id(doc.doc_id, cand.topic, i),
                    doc_id=doc.doc_id,
                    doc_type=doc.doc_type,
                    period=cand.period or doc.period,
                    topic=cand.topic,
                    metric=cand.metric,
                    kind=cand.kind,
                    value=number.value if number else None,
                    unit=number.unit if number else None,
                    raw_text=cand.raw_text,
                    citation=Citation(
                        doc_id=doc.doc_id,
                        start=cand.char_start,
                        end=cand.char_end,
                        quote=quote,
                        section=find_section(doc.sections, cand.char_start),
                    ),
                )
            )

    update: GraphState = {
        "claims": claims,
        "cost_usd": generated.usage.cost_usd,
        "node_metrics": [
            metric("extract_claims", cost_usd=generated.usage.cost_usd, latency_ms=timer.latency_ms)
        ],
    }
    if dropped:
        update["errors"] = [
            f"extract_claims: dropped {dropped} claim(s) from {doc.doc_id} — the quoted "
            f"text could not be located in the source document"
        ]
    return update
