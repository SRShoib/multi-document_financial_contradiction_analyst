"""POST /documents: upload validation, storage sandboxing, and the two-step
upload -> POST /runs flow real users will actually drive.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from .pdf_fixtures import make_image_only_pdf, make_text_pdf


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("CONTENT_STORE_DIR", str(tmp_path / "content"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("CHECKPOINTER", "memory")
    # Uploads must land in an isolated sandbox, never the repo's real data/ dir.
    documents_root = tmp_path / "documents"
    documents_root.mkdir()
    monkeypatch.setenv("DOCUMENTS_ROOT", str(documents_root))

    from filing_reconciler.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as c:  # triggers lifespan → builds the GraphRuntime
        yield c
    get_settings.cache_clear()


def test_rejects_disallowed_extension(client: TestClient) -> None:
    resp = client.post(
        "/documents",
        files=[("files", ("evil.docx", b"not a real docx", "application/octet-stream"))],
    )
    assert resp.status_code == 400
    assert "docx" in resp.json()["detail"]


def test_mixed_batch_partial_success(client: TestClient) -> None:
    resp = client.post(
        "/documents",
        files=[
            ("files", ("good.txt", b"Total revenue was $1,000.0 million.", "text/plain")),
            ("files", ("bad.docx", b"not a real docx", "application/octet-stream")),
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["documents"]) == 1
    assert len(body["rejected"]) == 1
    assert body["rejected"][0]["filename"] == "bad.docx"


def test_rejects_oversized_file_and_cleans_up_partial_write(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from filing_reconciler.config import get_settings

    # Settings.max_upload_bytes has a hard floor of 1,024 (config.py `ge=1024`).
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1024")
    get_settings.cache_clear()

    resp = client.post(
        "/documents", files=[("files", ("big.txt", b"x" * 4096, "text/plain"))]
    )

    assert resp.status_code == 400
    assert "exceeds" in resp.json()["detail"]
    uploads_root = tmp_path / "documents" / "uploads"
    leftover_files = (
        [p for p in uploads_root.rglob("*") if p.is_file()] if uploads_root.exists() else []
    )
    assert leftover_files == []


def test_rejects_too_many_files(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from filing_reconciler.config import get_settings

    monkeypatch.setenv("MAX_UPLOAD_FILES", "2")
    get_settings.cache_clear()

    resp = client.post(
        "/documents",
        files=[
            ("files", ("a.txt", b"a", "text/plain")),
            ("files", ("b.txt", b"b", "text/plain")),
            ("files", ("c.txt", b"c", "text/plain")),
        ],
    )
    assert resp.status_code == 400
    assert "too many files" in resp.json()["detail"]


def test_sanitizes_filenames(client: TestClient, tmp_path: Path) -> None:
    resp = client.post(
        "/documents",
        files=[
            (
                "files",
                (
                    "../../etc/passwd.txt",
                    b"Total revenue was $1,000.0 million.",
                    "text/plain",
                ),
            ),
            ("files", ("C:\\Windows\\evil.txt", b"Net income was $50 million.", "text/plain")),
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["documents"]) == 2

    documents_root = (tmp_path / "documents").resolve()
    for doc in body["documents"]:
        resolved = Path(doc["path"]).resolve()
        assert resolved.is_relative_to(documents_root)
        assert ".." not in Path(doc["path"]).parts


def test_returned_path_passes_check_input_paths(client: TestClient) -> None:
    """Contract test: the upload endpoint's output must satisfy the same
    DOCUMENTS_ROOT sandbox check POST /runs enforces on every input path."""
    from app.main import _check_input_paths
    from filing_reconciler.models import DocInput

    resp = client.post(
        "/documents",
        files=[("files", ("doc.txt", b"Total revenue was $1,000.0 million.", "text/plain"))],
    )
    doc = resp.json()["documents"][0]

    _check_input_paths([DocInput(path=doc["path"])])  # must not raise


def test_scanned_pdf_rejected_at_upload(client: TestClient) -> None:
    resp = client.post(
        "/documents",
        files=[("files", ("scan.pdf", make_image_only_pdf(), "application/pdf"))],
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "scan" in detail or "OCR" in detail


def test_upload_then_start_run_reaches_contradiction_gate(client: TestClient) -> None:
    """The key integration test: two uploaded .txt files with a genuine revenue
    mismatch flow all the way through ingest -> extract -> reconcile -> the gate."""
    doc_a = (
        "Total revenue for the fiscal year ended December 31, 2023 was $1,000.0 million, "
        "an increase of 8% compared to the prior fiscal year."
    )
    doc_b = (
        "Full year 2023 total revenue was $1,200 million, a record result for the company "
        "and an increase of 8% over fiscal 2022."
    )
    up = client.post(
        "/documents",
        files=[
            ("files", ("10k.txt", doc_a.encode(), "text/plain")),
            ("files", ("press_release.txt", doc_b.encode(), "text/plain")),
        ],
    )
    assert up.status_code == 200
    docs = up.json()["documents"]
    assert len(docs) == 2

    inputs = [
        {
            "path": docs[0]["path"],
            "doc_id": docs[0]["doc_id"],
            "doc_type": "10-K",
            "period": "FY2023",
        },
        {
            "path": docs[1]["path"],
            "doc_id": docs[1]["doc_id"],
            "doc_type": "press_release",
            "period": "FY2023",
        },
    ]
    started = client.post("/runs", json={"company": "ACME", "inputs": inputs})

    assert started.status_code == 200
    body = started.json()
    assert body["status"] == "paused"
    assert body["gate"] == "contradictions"
    assert body["contradictions"] >= 1


def test_upload_pdf_then_run_detects_contradiction(client: TestClient) -> None:
    """Exercises the real deterministic extractor over genuinely PDF-derived
    text, not just plain .txt — the point of the whole feature."""
    doc_a = make_text_pdf(
        ["Total revenue for the fiscal year ended December 31, 2023 was $1,000.0 million."]
    )
    doc_b = make_text_pdf(["Full year 2023 total revenue was $1,200 million."])

    up = client.post(
        "/documents",
        files=[
            ("files", ("10k.pdf", doc_a, "application/pdf")),
            ("files", ("press_release.pdf", doc_b, "application/pdf")),
        ],
    )
    assert up.status_code == 200
    docs = up.json()["documents"]
    assert len(docs) == 2
    assert all(d["char_len"] > 0 for d in docs)

    inputs = [
        {
            "path": docs[0]["path"],
            "doc_id": docs[0]["doc_id"],
            "doc_type": "10-K",
            "period": "FY2023",
        },
        {
            "path": docs[1]["path"],
            "doc_id": docs[1]["doc_id"],
            "doc_type": "press_release",
            "period": "FY2023",
        },
    ]
    started = client.post("/runs", json={"company": "ACME", "inputs": inputs})

    assert started.status_code == 200
    assert started.json()["contradictions"] >= 1


def test_run_status_surfaces_truncation_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Doubles as the visible-warning test for the ingest-level truncation logic:
    a tiny MAX_DOCUMENT_CHARS must surface a "truncated" notice all the way
    through POST /runs's ``errors`` field, not just at upload time.

    Builds its own TestClient (rather than the shared ``client`` fixture) with
    MAX_DOCUMENT_CHARS set BEFORE app startup: GraphRuntime builds one ``Deps``
    at lifespan startup and every graph node reads settings from it, so an
    env var changed after the app is already running never reaches ``ingest``
    (unlike the upload route, which calls ``get_settings()`` fresh per request).
    """
    monkeypatch.setenv("CONTENT_STORE_DIR", str(tmp_path / "content"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("CHECKPOINTER", "memory")
    documents_root = tmp_path / "documents"
    documents_root.mkdir()
    monkeypatch.setenv("DOCUMENTS_ROOT", str(documents_root))
    monkeypatch.setenv("MAX_DOCUMENT_CHARS", "1000")

    from filing_reconciler.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as c:
        long_text = "Total revenue was $1,000.0 million. " * 100  # well over 1,000 chars
        up = c.post(
            "/documents", files=[("files", ("long.txt", long_text.encode(), "text/plain"))]
        )
        assert up.status_code == 200
        doc = up.json()["documents"][0]
        assert doc["truncated"] is True

        started = c.post(
            "/runs",
            json={"company": "ACME", "inputs": [{"path": doc["path"], "doc_id": doc["doc_id"]}]},
        )
        assert started.status_code == 200
        assert any("truncated" in e for e in started.json()["errors"])
    get_settings.cache_clear()
