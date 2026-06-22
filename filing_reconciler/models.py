"""Pydantic v2 models — the typed contract shared by state, nodes, and the LLM.

Design notes
------------
* ``Literal`` types are used for every field that drives routing or scoring so
  conditional edges and comparisons stay statically type-checked.
* Structured LLM outputs (``ClaimExtraction``, ``ConflictJudgment``,
  ``CritiqueResult`` ...) set ``extra="forbid"`` so a hallucinated/extra field
  fails validation and triggers the retry-on-parse-failure guard.
* IDs are assigned deterministically by nodes (not random) so eval and tests are
  reproducible.
* Numeric *values* never originate from free-form LLM text — they are parsed
  deterministically (see ``tools/numeric.py``); the LLM only proposes spans/topics.
"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------------------------------- #
# Literal vocabularies (these drive routing/scoring — keep them closed sets)
# --------------------------------------------------------------------------- #
# doc_type is kept as an open ``str`` (filings in the wild are messy); the known
# set is enumerated for the classifier and validation hints.
DOC_TYPES = ("10-K", "10-Q", "earnings_call", "press_release", "unknown")

ClaimKind = Literal["numeric", "guidance", "narrative"]
ContradictionType = Literal[
    "numeric_mismatch",
    "guidance_revision",
    "narrative_conflict",
    "omission",
]
Severity = Literal["low", "medium", "high", "critical"]
SEVERITY_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}

ReviewStatus = Literal["pending", "confirmed", "rejected", "edited", "auto_accepted"]
DetectedBy = Literal["deterministic", "llm"]
DecisionAction = Literal["confirm", "reject", "edit", "approve", "request_changes"]
CritiqueProblem = Literal[
    "missing_citation",
    "invented_figure",
    "unsupported_assertion",
    "number_mismatch",
]


class _Base(BaseModel):
    """Shared config: forbid unknown fields, re-validate on mutation (HITL edits)."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


def _utcnow() -> datetime:
    return datetime.now(UTC)


# --------------------------------------------------------------------------- #
# Documents & provenance
# --------------------------------------------------------------------------- #
class SectionSpan(_Base):
    name: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class DocInput(_Base):
    """A document to ingest. Raw text stays out of state — only the path/ref."""

    path: str
    doc_id: str | None = None
    doc_type: str | None = None
    period: str | None = None
    company: str | None = None


class SourceDoc(_Base):
    """An ingested filing. ``text_ref`` points at the content store, not the text."""

    doc_id: str
    doc_type: str = "unknown"
    period: str | None = None
    company: str | None = None
    text_ref: str
    char_len: int = Field(ge=0)
    sections: list[SectionSpan] = Field(default_factory=list)


class Citation(_Base):
    """Char-span provenance. ``quote`` is the exact span text for faithfulness checks."""

    doc_id: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    quote: str = ""
    section: str | None = None

    def marker(self) -> str:
        """Inline citation marker rendered into memo prose."""
        return f"[{self.doc_id}:{self.start}-{self.end}]"


# --------------------------------------------------------------------------- #
# Claims
# --------------------------------------------------------------------------- #
class Claim(_Base):
    claim_id: str
    doc_id: str
    doc_type: str = "unknown"
    period: str | None = None
    topic: str  # normalized metric/topic key, e.g. "revenue", "guidance.revenue"
    metric: str | None = None
    kind: ClaimKind
    value: float | None = None  # normalized base units; only for kind="numeric"
    unit: str | None = None
    raw_text: str
    citation: Citation
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


# --------------------------------------------------------------------------- #
# Contradictions
# --------------------------------------------------------------------------- #
class NumericDelta(_Base):
    value_a: float
    value_b: float
    abs_diff: float
    pct_diff: float
    within_tolerance: bool


class Contradiction(_Base):
    contradiction_id: str
    ctype: ContradictionType
    topic: str
    period: str | None = None
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    citations: list[Citation] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    detected_by: DetectedBy
    status: ReviewStatus = "pending"
    numeric_delta: NumericDelta | None = None
    human_note: str | None = None


# --------------------------------------------------------------------------- #
# Risk
# --------------------------------------------------------------------------- #
class RiskItem(_Base):
    risk_id: str
    title: str
    category: str
    severity: Severity
    score: float = Field(ge=0.0, le=1.0)
    rationale: str
    citations: list[Citation] = Field(default_factory=list)
    contradiction_ids: list[str] = Field(default_factory=list)


class RiskRegister(_Base):
    items: list[RiskItem] = Field(default_factory=list)
    overall_score: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""


# --------------------------------------------------------------------------- #
# Memo
# --------------------------------------------------------------------------- #
class MemoSection(_Base):
    heading: str
    body: str
    citations: list[Citation] = Field(default_factory=list)


class Memo(_Base):
    title: str
    company: str | None = None
    period_coverage: str | None = None
    executive_summary: str
    sections: list[MemoSection] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    reflection_count: int = 0
    created_at: datetime = Field(default_factory=_utcnow)


# --------------------------------------------------------------------------- #
# Human-in-the-loop
# --------------------------------------------------------------------------- #
class HumanDecision(_Base):
    target_id: str  # contradiction_id, or "final_memo" for the sign-off gate
    action: DecisionAction
    note: str | None = None
    edited_severity: Severity | None = None
    edited_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    reviewer: str | None = None
    decided_at: datetime = Field(default_factory=_utcnow)


class ReviewRequest(_Base):
    """Payload surfaced by ``interrupt()`` for a human reviewer."""

    kind: Literal["contradictions", "final_memo"]
    run_id: str | None = None
    instructions: str = ""
    contradictions: list[Contradiction] = Field(default_factory=list)
    memo: Memo | None = None


# --------------------------------------------------------------------------- #
# Structured LLM outputs (extra=forbid catches hallucinated fields)
# --------------------------------------------------------------------------- #
class ClaimCandidate(_Base):
    topic: str
    kind: ClaimKind
    metric: str | None = None
    raw_text: str
    char_start: int = Field(ge=0)
    char_end: int = Field(ge=0)


class ClaimExtraction(_Base):
    claims: list[ClaimCandidate] = Field(default_factory=list)


class ConflictJudgment(_Base):
    is_conflict: bool
    ctype: Literal["guidance_revision", "narrative_conflict"] = "narrative_conflict"
    severity: Severity = "medium"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    rationale: str = ""


class CritiqueIssue(_Base):
    assertion: str
    problem: CritiqueProblem
    detail: str = ""
    section: str | None = None


class CritiqueResult(_Base):
    faithful: bool
    issues: list[CritiqueIssue] = Field(default_factory=list)


class FaithfulnessJudgment(_Base):
    supported: bool
    score: float = Field(ge=0.0, le=1.0)
    reason: str = ""


class MemoContext(_Base):
    """Everything ``compose_memo`` needs, assembled by the draft node."""

    company: str | None = None
    period_coverage: str | None = None
    contradictions: list[Contradiction] = Field(default_factory=list)
    risk_register: RiskRegister = Field(default_factory=RiskRegister)
    claims: list[Claim] = Field(default_factory=list)
    revision_notes: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Per-node telemetry (cost/latency); accumulated via an add-reducer in state
# --------------------------------------------------------------------------- #
class NodeMetric(_Base):
    node: str
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    model: str | None = None
