"""Graph state.

A ``TypedDict`` whose channels carry the analysis as it flows through the graph.
Reducers matter here:

* ``claims`` uses ``operator.add`` so the **parallel** ``extract_claims`` branches
  (fanned out with the Send API) concatenate instead of clobbering each other.
* ``cost_usd`` uses ``operator.add`` so per-node spend accumulates into a per-run
  total (drives the hard cost cap).
* ``errors``, ``human_decisions``, and ``node_metrics`` likewise accumulate.

Single-writer channels (``sources``, ``contradictions``, ``risk_register``,
``draft_memo`` ...) use the default last-value behaviour. Raw document text is
**never** stored in state — only ``text_ref`` pointers (see ``store.py``).

``total=False`` lets callers build a partial initial state (e.g. just ``inputs``);
nodes read optional channels with ``state.get(...)``.
"""

import operator
from typing import Annotated, TypedDict

from .models import (
    Claim,
    Contradiction,
    CritiqueIssue,
    HumanDecision,
    Memo,
    NodeMetric,
    RiskRegister,
    SourceDoc,
)
from .models import (
    DocInput as DocInput,  # re-export for convenience
)


class GraphState(TypedDict, total=False):
    # --- inputs / run metadata ---------------------------------------------
    inputs: list[DocInput]
    run_id: str
    company: str | None

    # --- pipeline artifacts ------------------------------------------------
    sources: list[SourceDoc]
    claims: Annotated[list[Claim], operator.add]  # parallel extraction → concat
    contradictions: list[Contradiction]
    risk_register: RiskRegister | None
    draft_memo: Memo | None
    final_memo: Memo | None

    # --- control / guardrails ----------------------------------------------
    reflection_count: int
    human_decisions: Annotated[list[HumanDecision], operator.add]
    critique_issues: list[CritiqueIssue]
    cost_usd: Annotated[float, operator.add]  # accumulates → hard cost cap
    node_metrics: Annotated[list[NodeMetric], operator.add]
    errors: Annotated[list[str], operator.add]
