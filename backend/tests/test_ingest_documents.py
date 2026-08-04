"""ingest node with real-document conversion integrated: per-document failures
degrade gracefully, oversized documents are truncated with a visible warning,
and colliding doc_ids don't silently overwrite each other's stored text.
"""

from pathlib import Path

from filing_reconciler.config import Settings
from filing_reconciler.deps import Deps
from filing_reconciler.llm import StubLLM
from filing_reconciler.models import DocInput
from filing_reconciler.nodes.ingest import ingest
from filing_reconciler.store import FileContentStore

from .pdf_fixtures import CORRUPT_PDF


def _deps(tmp_path: Path, **settings_kwargs: object) -> Deps:
    settings = Settings(
        _env_file=None,
        content_store_dir=str(tmp_path / "content"),
        **settings_kwargs,  # type: ignore[arg-type]
    )
    store = FileContentStore(settings.content_store_dir)
    return Deps(settings=settings, llm=StubLLM(), store=store)


def test_corrupt_pdf_does_not_crash_the_run(tmp_path: Path) -> None:
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(CORRUPT_PDF)
    good = tmp_path / "good.txt"
    good.write_text(
        "Total revenue was $1,000.0 million in fiscal year 2023.", encoding="utf-8"
    )

    deps = _deps(tmp_path)
    inputs = [
        DocInput(path=str(bad), doc_id="BAD"),
        DocInput(path=str(good), doc_id="GOOD"),
    ]

    result = ingest({"inputs": inputs, "company": "ACME"}, deps)

    assert len(result["sources"]) == 1
    assert result["sources"][0].doc_id == "GOOD"
    assert any("bad.pdf" in e for e in result["errors"])


def test_truncation_warning_recorded(tmp_path: Path) -> None:
    text = "Sentence one is here. " * 100  # well over the 1,000-char cap
    path = tmp_path / "long.txt"
    path.write_text(text, encoding="utf-8")

    # Settings.max_document_chars has a hard floor of 1,000 (config.py `ge=1_000`).
    deps = _deps(tmp_path, max_document_chars=1_000)
    inputs = [DocInput(path=str(path), doc_id="LONG")]

    result = ingest({"inputs": inputs, "company": "ACME"}, deps)

    assert len(result["sources"]) == 1
    assert result["sources"][0].char_len <= 1_000
    assert any("truncated" in e for e in result["errors"])


def test_duplicate_stems_get_unique_doc_ids(tmp_path: Path) -> None:
    dir_a, dir_b = tmp_path / "a", tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    path_a, path_b = dir_a / "10-K.txt", dir_b / "10-K.txt"
    path_a.write_text("Total revenue was $1,000.0 million.", encoding="utf-8")
    path_b.write_text("Total revenue was $2,000.0 million.", encoding="utf-8")

    deps = _deps(tmp_path)
    # No explicit doc_id -> both default to the "10-K" stem.
    inputs = [DocInput(path=str(path_a)), DocInput(path=str(path_b))]

    result = ingest({"inputs": inputs, "company": "ACME"}, deps)

    doc_ids = [s.doc_id for s in result["sources"]]
    assert len(doc_ids) == 2
    assert len(set(doc_ids)) == 2  # de-duplicated, not overwritten

    texts = [deps.store.get(s.text_ref) for s in result["sources"]]
    assert any("1,000.0" in t for t in texts)
    assert any("2,000.0" in t for t in texts)


def test_all_documents_failing_records_an_error(tmp_path: Path) -> None:
    bad1, bad2 = tmp_path / "bad1.pdf", tmp_path / "bad2.pdf"
    bad1.write_bytes(CORRUPT_PDF)
    bad2.write_bytes(CORRUPT_PDF)

    deps = _deps(tmp_path)
    inputs = [DocInput(path=str(bad1)), DocInput(path=str(bad2))]

    result = ingest({"inputs": inputs, "company": "ACME"}, deps)

    assert result["sources"] == []
    assert any("no documents could be read" in e for e in result["errors"])
