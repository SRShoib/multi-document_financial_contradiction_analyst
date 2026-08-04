"""Document -> text conversion. Deterministic; a single bad document never
crashes a run — callers catch ``ConversionError`` and record a per-document
notice instead (see ``nodes/ingest.py``).

Char offsets in every ``Citation`` are relative to the text this module
returns, so conversion + normalization must be a pure function of the file
bytes: the same file must always yield the same offsets, or a stored citation
stops resolving. Normalization therefore happens exactly ONCE, here, before the
text is written to the content store — never afterwards.
"""

import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal

SUPPORTED_SUFFIXES: frozenset[str] = frozenset({".txt", ".md", ".pdf"})


class ConversionError(Exception):
    """A single document could not be converted. Callers record it per-document
    rather than letting it crash the run."""


@dataclass(frozen=True)
class Conversion:
    text: str
    kind: Literal["text", "pdf"]
    page_count: int | None = None  # PDFs only
    truncated: bool = False
    original_char_len: int = 0  # length of the normalized text, pre-truncation


def decode_bytes(data: bytes) -> str:
    """Deterministic decode ladder for .txt/.md — never raises.

    ``latin-1`` is deliberately excluded as a middle rung: it can decode any
    byte sequence, which would mask real encoding problems instead of falling
    through to the explicit, lossy ``errors="replace"`` rung.
    """
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def convert_pdf(data: bytes) -> tuple[str, int]:
    """Extract text from PDF bytes. Raises ``ConversionError`` for anything
    that isn't a plain, decryptable-with-empty-password, text-bearing PDF.

    The broad ``except Exception`` below is intentional: this is a
    hostile-input boundary (any bytes with a ``.pdf`` extension reach this
    function), and pypdf can raise many different exception types for a
    malformed file (``PdfReadError``, ``DependencyError``, ``EOFError``,
    ``struct.error``, ``KeyError``, plain ``ValueError``...). Enumerating them
    individually is a losing game — the contract is simply "one bad document
    must not crash the run".
    """
    try:
        from pypdf import PdfReader
        from pypdf._encryption import PasswordType
    except ImportError as exc:  # pragma: no cover - pypdf is a base dependency
        raise ConversionError(
            "PDF support requires the 'pypdf' package (should be installed by default)"
        ) from exc

    try:
        reader = PdfReader(BytesIO(data))
        # Many real filings carry an empty owner password and are readable; try
        # that before giving up.
        if reader.is_encrypted and reader.decrypt("") == PasswordType.NOT_DECRYPTED:
            raise ConversionError("PDF is password-protected")
        pages = list(reader.pages)
        text = "\n\n".join(page.extract_text() or "" for page in pages)
        return text, len(pages)
    except ConversionError:
        raise
    except Exception as exc:
        raise ConversionError(f"could not read PDF: {exc}") from exc


_LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"}
# Literal glyphs, deliberately: these are the actual characters PDF extraction
# emits. Some are visually confusable with plain ASCII punctuation (curly
# quotes/en-dash vs straight quote/hyphen), which ruff flags as RUF001 —
# suppressed per-line below rather than escaped, so the target character stays
# visible next to what it's replaced with.
_SMART_PUNCT = {
    "‘": "'",  # noqa: RUF001 - left single quote (U+2018)
    "’": "'",  # noqa: RUF001 - right single quote (U+2019)
    "“": '"',
    "”": '"',
    "–": "-",  # noqa: RUF001 - en dash (U+2013)
    "—": "-",
}
# "reve-\nnue" -> "revenue": scoped to lowercase-lowercase so hyphenated proper
# nouns and codes like "10-K" survive.
_SOFT_HYPHEN_JOIN_RE = re.compile(r"(?<=[a-z])-\n(?=[a-z])")
# A lone newline mid-sentence (a PDF hard line-wrap) -> a space. Without this,
# tools.text.split_sentences (which treats \n+ as a sentence boundary) shreds
# every PDF sentence into fragments and the numeric/guidance extractor never
# sees a complete claim.
_HARD_WRAP_RE = re.compile(r"(?<=[a-z,])\n(?=[a-z])")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def normalize_extracted_text(raw: str) -> str:
    """Normalize PDF/text-extracted text into something the sentence/claim
    heuristics (``tools.text.split_sentences``, ``tools.extraction``) can parse.

    Applied exactly once, before the text is written to the content store —
    ``Citation`` offsets are into THIS text.
    """
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x0c", "\n\n")  # form feed: pypdf's page separator
    text = text.replace("\xa0", " ").replace("\xad", "")  # NBSP, soft hyphen
    for lig, plain in _LIGATURES.items():
        text = text.replace(lig, plain)
    for smart, plain in _SMART_PUNCT.items():
        text = text.replace(smart, plain)
    text = _SOFT_HYPHEN_JOIN_RE.sub("", text)
    text = _HARD_WRAP_RE.sub(" ", text)
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return text


def truncate_at_boundary(text: str, max_chars: int) -> str:
    """Hard-cut ``text`` at ``max_chars``, then back up to the nearest sentence
    or line boundary within the final ~2000 chars so the cut never lands
    mid-figure (a half-cut number could otherwise be mis-parsed downstream).
    """
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    window_start = max(0, len(cut) - 2000)
    window = cut[window_start:]

    candidates: list[int] = []
    period_idx = window.rfind(". ")
    if period_idx >= 0:
        candidates.append(window_start + period_idx + 1)  # keep '.', drop the rest
    newline_idx = window.rfind("\n")
    if newline_idx >= 0:
        candidates.append(window_start + newline_idx + 1)  # keep the newline

    if candidates:
        return cut[: max(candidates)]
    return cut


def load_document_text(path: Path, *, max_chars: int | None = None) -> Conversion:
    """Single entry point ``ingest`` calls: read, convert, normalize, and (if
    ``max_chars`` is set) truncate the document at ``path``.

    Raises ``ConversionError`` for any per-document problem (unsupported
    format, corrupt/encrypted/scanned PDF, unreadable file) — callers must
    catch this and record it rather than letting one bad document abort a run.
    """
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ConversionError(
            f"unsupported file type '{suffix}' (supported: "
            f"{', '.join(sorted(SUPPORTED_SUFFIXES))})"
        )

    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ConversionError(f"could not read file: {exc}") from exc

    page_count: int | None = None
    kind: Literal["text", "pdf"]
    if suffix == ".pdf":
        raw, page_count = convert_pdf(data)
        kind = "pdf"
    else:
        raw = decode_bytes(data)
        kind = "text"

    text = normalize_extracted_text(raw)
    if not text.strip():
        raise ConversionError(
            "no extractable text — the PDF appears to be a scan/image; OCR is not supported"
            if suffix == ".pdf"
            else "file is empty"
        )

    original_char_len = len(text)
    truncated = False
    if max_chars is not None and len(text) > max_chars:
        text = truncate_at_boundary(text, max_chars)
        truncated = True

    return Conversion(
        text=text,
        kind=kind,
        page_count=page_count,
        truncated=truncated,
        original_char_len=original_char_len,
    )
