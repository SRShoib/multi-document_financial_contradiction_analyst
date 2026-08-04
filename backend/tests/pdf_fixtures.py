"""Minimal hand-built PDFs for tests — no binary fixture files in the repo.

pypdf's ``PdfWriter`` has no ergonomic API for *drawing* text, so the
happy-path fixture emits the small set of PDF objects directly (a Catalog,
Pages, one Page, a Helvetica font, and a content stream of text-drawing
operators), tracking byte offsets as it goes so the xref table is correct —
deliberately not relying on pypdf's xref-recovery path for what's supposed to
be the well-formed case.
"""

from io import BytesIO


def _escape_pdf_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _stream_object(content: bytes) -> bytes:
    return f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"


def _build_pdf(objects: list[bytes]) -> bytes:
    """Assemble a minimal single-xref-table PDF from raw object bodies.

    ``objects[i]`` is object number ``i+1``'s body (e.g.
    ``b"<< /Type /Catalog /Pages 2 0 R >>"``); this wraps each in
    ``N 0 obj ... endobj`` and emits a header/xref/trailer with real offsets.
    """
    buf = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(buf))
        buf += f"{i} 0 obj\n".encode()
        buf += body
        buf += b"\nendobj\n"

    xref_offset = len(buf)
    n = len(objects) + 1
    buf += f"xref\n0 {n}\n".encode()
    buf += b"0000000000 65535 f \n"
    for off in offsets:
        buf += f"{off:010d} 00000 n \n".encode()
    buf += f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    return bytes(buf)


def make_text_pdf(lines: list[str]) -> bytes:
    """A single-page PDF whose content stream draws ``lines`` in Helvetica 12pt,
    one per line starting at (72, 720) — a plausible top-of-page filing excerpt.
    """
    parts = ["BT /F1 12 Tf 72 720 Td"]
    for i, line in enumerate(lines):
        escaped = _escape_pdf_string(line)
        if i == 0:
            parts.append(f"({escaped}) Tj")
        else:
            parts.append(f"0 -14 TD ({escaped}) Tj")
    parts.append("ET")
    content = " ".join(parts).encode()

    catalog = b"<< /Type /Catalog /Pages 2 0 R >>"
    pages = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
    page = (
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
    )
    contents = _stream_object(content)
    font = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    return _build_pdf([catalog, pages, page, contents, font])


def make_encrypted_pdf(password: str = "secret") -> bytes:
    """A one-page PDF encrypted with a real user password (pypdf can't decrypt
    it with an empty password — the "genuinely can't read this" case)."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(BytesIO(make_text_pdf(["Encrypted content."])))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(user_password=password, owner_password=None)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def make_image_only_pdf() -> bytes:
    """A one-page PDF with a filled rectangle and no text — pypdf's
    ``extract_text()`` returns ``""`` here with no exception, exercising the
    scanned/image-PDF path without needing a real raster image."""
    content = b"0 0 1 rg 100 100 200 200 re f"
    catalog = b"<< /Type /Catalog /Pages 2 0 R >>"
    pages = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
    page = (
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << >> /Contents 4 0 R >>"
    )
    contents = _stream_object(content)
    return _build_pdf([catalog, pages, page, contents])


CORRUPT_PDF = b"%PDF-1.7\n" + b"\x00\xff" * 256
