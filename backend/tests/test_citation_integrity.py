"""Citation-offset recovery: locate_quote must never fabricate a wrong span,
and extract_claims must drop any candidate it can't verify.

The bug this guards against: providers/openai_llm.py used to fall back to
``start, end = 0, min(len(text), len(quote))`` whenever a model's "verbatim"
quote wasn't found — producing a Citation that looks valid but points at the
document's first N characters. PDF-extracted text (hyphenation, hard-wrapped
lines) is exactly what triggers a non-exact match, so this is a required
companion to real-document ingestion, not separate polish.
"""

from pathlib import Path
from typing import Any

from filing_reconciler.config import Settings
from filing_reconciler.deps import Deps
from filing_reconciler.llm import Generated, StubLLM, Usage
from filing_reconciler.models import ClaimCandidate, ClaimExtraction, SourceDoc
from filing_reconciler.nodes.extract_claims import ExtractTask, extract_claims
from filing_reconciler.nodes.ingest import ingest
from filing_reconciler.samples import list_sample_sets, load_sample
from filing_reconciler.store import FileContentStore
from filing_reconciler.tools.text import collapse_ws_with_map, locate_quote


def _norm(s: str) -> str:
    """Whitespace-collapse + de-hyphenate, for comparing across PDF-style reflow."""
    return " ".join(s.replace("-\n", "").split())


# --------------------------------------------------------------------------- #
# locate_quote — pure-function tests
# --------------------------------------------------------------------------- #
def test_locate_quote_exact() -> None:
    text = "Total revenue was $1,000.0 million in FY2023."
    quote = "Total revenue was $1,000.0 million"
    span = locate_quote(text, quote)
    assert span == (0, len(quote))
    assert text[span[0] : span[1]] == quote


def test_locate_quote_across_hard_wrap() -> None:
    text = "Total revenue was\n$1,000.0 million in FY2023."
    quote = "Total revenue was $1,000.0 million"
    span = locate_quote(text, quote)
    assert span is not None
    start, end = span
    assert _norm(text[start:end]) == _norm(quote)


def test_locate_quote_dehyphenated() -> None:
    text = "Full year reve-\nnue grew 8% year over year."
    quote = "Full year revenue grew 8% year over year."
    span = locate_quote(text, quote)
    assert span is not None
    start, end = span
    assert _norm(text[start:end]) == _norm(quote)


def test_locate_quote_returns_none_when_absent() -> None:
    """The direct anti-regression test for the old silent-wrong (0, len(quote)) fallback."""
    text = "Total revenue was $1,000.0 million in FY2023."
    quote = "Net income declined sharply due to litigation costs."
    assert locate_quote(text, quote) is None


def test_locate_quote_empty_quote_returns_none() -> None:
    assert locate_quote("some text", "") is None


def test_collapse_ws_with_map_offsets_are_exact() -> None:
    text = "a   b\n\nc"
    collapsed, offsets = collapse_ws_with_map(text)
    assert collapsed == "a b c"
    assert all(
        text[offsets[i]] == collapsed[i] or collapsed[i] == " " for i in range(len(collapsed))
    )


# --------------------------------------------------------------------------- #
# extract_claims node — provenance invariant + provider resilience
# --------------------------------------------------------------------------- #
class _FakeLLM:
    """Minimal fake exposing only what the extract_claims node calls."""

    def __init__(
        self, candidates: list[ClaimCandidate] | None = None, *, raise_error: bool = False
    ) -> None:
        self._candidates = candidates or []
        self._raise = raise_error

    def extract_claims(self, *, doc: SourceDoc, text: str) -> Generated[ClaimExtraction]:
        if self._raise:
            raise RuntimeError("simulated provider failure")
        return Generated(
            ClaimExtraction(claims=self._candidates),
            Usage(model="fake", input_tokens=1, output_tokens=1, cost_usd=0.0),
        )


def _make_doc_and_deps(
    tmp_path: Path, text: str, llm: Any, doc_id: str = "DOC1"
) -> tuple[SourceDoc, Deps]:
    settings = Settings(_env_file=None, content_store_dir=str(tmp_path / "content"))
    store = FileContentStore(settings.content_store_dir)
    text_ref = store.put(doc_id, text)
    doc = SourceDoc(
        doc_id=doc_id,
        doc_type="10-K",
        period="FY2023",
        company="ACME",
        text_ref=text_ref,
        char_len=len(text),
        sections=[],
    )
    return doc, Deps(settings=settings, llm=llm, store=store)


def test_node_drops_unverifiable_candidates(tmp_path: Path) -> None:
    text = "Total revenue was $1,000.0 million in FY2023."
    unlocatable = ClaimCandidate(
        topic="revenue",
        kind="numeric",
        metric="revenue",
        period="FY2023",
        raw_text="Revenue increased to $2,000 million",  # not present in text at all
        char_start=0,
        char_end=0,
        located=False,
    )
    doc, deps = _make_doc_and_deps(tmp_path, text, _FakeLLM([unlocatable]))

    result = extract_claims(ExtractTask(doc=doc), deps)

    assert result["claims"] == []
    assert any("dropped 1 claim" in e for e in result.get("errors", []))


def test_node_drops_candidate_whose_offsets_dont_match_raw_text(tmp_path: Path) -> None:
    """Even a ``located=True`` candidate is dropped if the span doesn't reproduce raw_text."""
    text = "Total revenue was $1,000.0 million in FY2023."
    mismatched = ClaimCandidate(
        topic="revenue",
        kind="numeric",
        metric="revenue",
        period="FY2023",
        raw_text="something else entirely",
        char_start=0,
        char_end=10,  # a real span, but text[0:10] != raw_text
        located=True,
    )
    doc, deps = _make_doc_and_deps(tmp_path, text, _FakeLLM([mismatched]))

    result = extract_claims(ExtractTask(doc=doc), deps)

    assert result["claims"] == []
    assert any("dropped 1 claim" in e for e in result.get("errors", []))


def test_node_survives_provider_exception(tmp_path: Path) -> None:
    text = "Total revenue was $1,000.0 million in FY2023."
    doc, deps = _make_doc_and_deps(tmp_path, text, _FakeLLM(raise_error=True))

    result = extract_claims(ExtractTask(doc=doc), deps)

    assert result["claims"] == []
    assert any("failed" in e for e in result.get("errors", []))


def test_stub_candidates_all_satisfy_the_invariant(tmp_path: Path) -> None:
    """Regression: the invariant enforcement must not break the offline stub path."""
    settings = Settings(_env_file=None, content_store_dir=str(tmp_path / "content"))
    store = FileContentStore(settings.content_store_dir)
    deps = Deps(settings=settings, llm=StubLLM(), store=store)

    for set_id in list_sample_sets():
        company, inputs = load_sample(set_id)
        ingest_result = ingest({"inputs": inputs, "company": company}, deps)
        for doc in ingest_result["sources"]:
            result = extract_claims(ExtractTask(doc=doc), deps)
            assert "errors" not in result, f"{set_id}/{doc.doc_id}: {result.get('errors')}"
            assert result["claims"], f"{set_id}/{doc.doc_id}: expected at least one claim"
