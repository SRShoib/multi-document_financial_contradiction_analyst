"""Document conversion: encoding ladder, PDF extraction, normalization, and
truncation — the deterministic layer real (non-clean-.txt) filings go through
before the pipeline ever sees them.
"""

from pathlib import Path

import pytest
from filing_reconciler.tools.convert import (
    ConversionError,
    decode_bytes,
    load_document_text,
    normalize_extracted_text,
    truncate_at_boundary,
)
from filing_reconciler.tools.text import split_sentences

from .pdf_fixtures import (
    CORRUPT_PDF,
    make_encrypted_pdf,
    make_image_only_pdf,
    make_text_pdf,
)


def test_txt_utf8_and_bom_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "doc.txt"
    path.write_bytes("﻿Total revenue was $1,000.0 million.".encode())

    conv = load_document_text(path)

    assert conv.kind == "text"
    assert conv.text == "Total revenue was $1,000.0 million."  # BOM stripped


def test_cp1252_bytes_decode_without_raising() -> None:
    # cp1252-only bytes (curly quotes) that are not valid UTF-8.
    raw = '“Record revenue” for the year.'.encode("cp1252")
    text = decode_bytes(raw)
    assert "Record revenue" in text


def test_unsupported_suffix_raises(tmp_path: Path) -> None:
    path = tmp_path / "doc.docx"
    path.write_bytes(b"not a real docx")

    with pytest.raises(ConversionError, match=r"\.docx"):
        load_document_text(path)


def test_pdf_text_extracted(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    path.write_bytes(make_text_pdf(["Total revenue was $1,000.0 million."]))

    conv = load_document_text(path)

    assert conv.kind == "pdf"
    assert conv.page_count == 1
    assert "Total revenue was $1,000.0 million." in conv.text


def test_normalization_joins_hard_wraps(tmp_path: Path) -> None:
    """The test that protects the whole downstream sentence/claim extractor:
    a PDF that wraps mid-sentence must come back as ONE sentence, not two
    fragments split_sentences would otherwise shred it into.
    """
    path = tmp_path / "doc.pdf"
    path.write_bytes(
        make_text_pdf(["Total revenue for the year", "was $1,000.0 million."])
    )

    conv = load_document_text(path)
    sentences = [s for s, _, _ in split_sentences(conv.text)]

    assert any("Total revenue for the year was $1,000.0 million." in s for s in sentences)


def test_dehyphenation(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    path.write_bytes(make_text_pdf(["Full year reve-", "nue grew 8% year over year."]))

    conv = load_document_text(path)

    assert "revenue grew 8%" in conv.text
    assert "reve-" not in conv.text


def test_encrypted_pdf_raises_conversion_error(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    path.write_bytes(make_encrypted_pdf("secret"))

    with pytest.raises(ConversionError, match="password"):
        load_document_text(path)


def test_corrupt_pdf_raises_conversion_error(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    path.write_bytes(CORRUPT_PDF)

    with pytest.raises(ConversionError):
        load_document_text(path)


def test_image_only_pdf_raises_conversion_error(tmp_path: Path) -> None:
    path = tmp_path / "doc.pdf"
    path.write_bytes(make_image_only_pdf())

    with pytest.raises(ConversionError, match=r"scan|OCR"):
        load_document_text(path)


def test_truncation_flags_and_boundary(tmp_path: Path) -> None:
    original = "Sentence one is here. " * 40  # well over 100 chars
    path = tmp_path / "doc.txt"
    path.write_text(original, encoding="utf-8")

    conv = load_document_text(path, max_chars=100)

    assert conv.truncated is True
    # original_char_len is the length AFTER normalization (trailing-space strip
    # etc.) but BEFORE truncation — not the raw input's length.
    assert conv.original_char_len == len(normalize_extracted_text(original))
    assert len(conv.text) <= 100
    # The boundary logic should back up to a sentence end, not cut mid-word.
    assert conv.text.endswith(".") or conv.text.endswith("\n") or len(conv.text) == 100


def test_truncate_at_boundary_prefers_sentence_end() -> None:
    text = "A" * 50 + ". " + "B" * 3000
    truncated = truncate_at_boundary(text, max_chars=2000)
    assert truncated == "A" * 50 + "."


def test_conversion_is_deterministic(tmp_path: Path) -> None:
    """Offset stability guarantee: the same bytes must convert to byte-identical
    text every time, since Citation offsets are into this text."""
    data = make_text_pdf(["Total revenue was $1,000.0 million.", "Net income was $120 million."])
    path_a = tmp_path / "a.pdf"
    path_b = tmp_path / "b.pdf"
    path_a.write_bytes(data)
    path_b.write_bytes(data)

    conv_a = load_document_text(path_a)
    conv_b = load_document_text(path_b)

    assert conv_a.text == conv_b.text


def test_normalize_extracted_text_is_idempotent() -> None:
    raw = "Full year reve-\nnue grew\n“8%” year over year.\x0cPage 2 body."
    once = normalize_extracted_text(raw)
    twice = normalize_extracted_text(once)
    assert once == twice
