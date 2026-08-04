"""Content store: keeps raw document text *out of* graph state.

State carries only ``text_ref`` pointers (cheap of long filings stays out of the
checkpointer). The default implementation persists text to the local filesystem so
refs resolve across process restarts — which matters for durable HITL resume, where
the resuming process may be different from the one that started the run.

Swap ``FileContentStore`` for an S3/GCS-backed store in production by implementing
the ``ContentStore`` Protocol.
"""

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class ContentStore(Protocol):
    def put(self, key: str, text: str) -> str:
        """Persist ``text`` under ``key``; return a durable ref."""

    def get(self, ref: str) -> str:
        """Resolve a ref previously returned by ``put``."""


class FileContentStore:
    """Filesystem-backed store. Refs are ``file://<absolute-path>``."""

    _SCHEME = "file://"

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, text: str) -> str:
        safe = key.replace("/", "_").replace("\\", "_")
        path = (self.base_dir / f"{safe}.txt").resolve()
        path.write_text(text, encoding="utf-8")
        return f"{self._SCHEME}{path}"

    def get(self, ref: str) -> str:
        path = ref[len(self._SCHEME) :] if ref.startswith(self._SCHEME) else ref
        return Path(path).read_text(encoding="utf-8")
