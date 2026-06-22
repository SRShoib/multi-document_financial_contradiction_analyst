"""Append human-confirmed contradictions from a completed run into a set's gold labels.

This closes the online → offline loop: contradictions a human confirmed/edited at the
HITL gate become new ground-truth labels, so future eval runs hold the system to the
reviewer's judgments. Reads the ``<run_id>.run.json`` written by the finalize node.

Usage:
    python scripts/append_overrides.py --set set_a --run-json .artifacts/output/<run_id>.run.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from filing_reconciler.samples import sample_dir


def _key(ctype: str, topic: str, period: str | None) -> tuple[str, str, str | None]:
    return (ctype, topic, None if ctype == "narrative_conflict" else period)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", required=True, dest="set_id", help="Sample set id, e.g. set_a")
    parser.add_argument("--run-json", required=True, help="Path to <run_id>.run.json")
    args = parser.parse_args(argv)

    record = json.loads(Path(args.run_json).read_text(encoding="utf-8"))
    labels_path = sample_dir(args.set_id) / "labels.json"
    labels = json.loads(labels_path.read_text(encoding="utf-8"))

    existing = {
        _key(g["ctype"], g["topic"], g.get("period")) for g in labels["gold_contradictions"]
    }
    added = 0
    for c in record.get("contradictions", []):
        if c.get("status") not in ("confirmed", "edited"):
            continue
        key = _key(c["ctype"], c["topic"], c.get("period"))
        if key in existing:
            continue
        doc_ids = sorted({cit["doc_id"] for cit in c.get("citations", [])})
        labels["gold_contradictions"].append(
            {
                "ctype": c["ctype"],
                "topic": c["topic"],
                "period": c.get("period"),
                "doc_ids": doc_ids,
                "note": "added from human override",
            }
        )
        existing.add(key)
        added += 1

    labels_path.write_text(json.dumps(labels, indent=2) + "\n", encoding="utf-8")
    print(f"Appended {added} human-confirmed contradiction(s) to {labels_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
