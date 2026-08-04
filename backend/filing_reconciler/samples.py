"""Load bundled sample document sets into ``DocInput`` lists.

The samples ship with deliberately injected contradictions and let the repo run
end-to-end with no external data. ``data/samples/<set_id>/manifest.json`` lists the
documents and their declared type/period.
"""

import json
from pathlib import Path

from .models import DocInput

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "data" / "samples"


def sample_dir(set_id: str) -> Path:
    return SAMPLES_DIR / set_id


def list_sample_sets() -> list[str]:
    if not SAMPLES_DIR.exists():
        return []
    return sorted(p.name for p in SAMPLES_DIR.iterdir() if (p / "manifest.json").exists())


def load_sample(set_id: str) -> tuple[str, list[DocInput]]:
    """Return ``(company, inputs)`` for a sample set."""
    base = sample_dir(set_id)
    manifest_path = base / "manifest.json"
    if not manifest_path.exists():
        available = ", ".join(list_sample_sets()) or "(none)"
        raise FileNotFoundError(
            f"Unknown sample set {set_id!r}. Available: {available}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    company = manifest.get("company", set_id)
    inputs = [
        DocInput(
            path=str((base / doc["path"]).resolve()),
            doc_id=doc.get("doc_id"),
            doc_type=doc.get("doc_type"),
            period=doc.get("period"),
            company=company,
        )
        for doc in manifest["documents"]
    ]
    return company, inputs
