"""finalize — export the memo and log per-run cost and latency."""

import json
import logging
from pathlib import Path

from ..deps import Deps
from ..models import Memo
from ..state import GraphState
from .common import Timer, metric

logger = logging.getLogger("filing_reconciler.run")


def render_markdown(memo: Memo) -> str:
    lines = [f"# {memo.title}", ""]
    if memo.company or memo.period_coverage:
        company = memo.company or "n/a"
        period = memo.period_coverage or "n/a"
        lines.append(f"**Company:** {company}  |  **Period:** {period}")
        lines.append("")
    lines += ["## Executive summary", memo.executive_summary, ""]
    for section in memo.sections:
        lines += [f"## {section.heading}", section.body, ""]
    if memo.citations:
        lines.append("## Citations")
        lines += [f"- {c.marker()} {c.quote}".rstrip() for c in memo.citations]
    return "\n".join(lines)


def finalize(state: GraphState, deps: Deps) -> GraphState:
    with Timer() as timer:
        memo = state.get("draft_memo")
        run_id = state.get("run_id", "run")
        total_cost = state.get("cost_usd", 0.0)
        total_latency = sum(m.latency_ms for m in state.get("node_metrics", []))
        unresolved = state.get("critique_issues", []) or []

        update: GraphState = {}
        if memo is not None:
            out_dir = Path(deps.settings.output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"{run_id}.json").write_text(
                memo.model_dump_json(indent=2), encoding="utf-8"
            )
            (out_dir / f"{run_id}.md").write_text(render_markdown(memo), encoding="utf-8")
            update["final_memo"] = memo

        # Run record: contradictions (with HITL status) + decisions + cost. This is the
        # online→offline feedback hook — scripts/append_overrides.py replays confirmed
        # contradictions back into the eval set's gold labels.
        out_dir = Path(deps.settings.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        run_record = {
            "run_id": run_id,
            "cost_usd": total_cost,
            "contradictions": [
                c.model_dump(mode="json") for c in state.get("contradictions", []) or []
            ],
            "human_decisions": [
                d.model_dump(mode="json") for d in state.get("human_decisions", []) or []
            ],
        }
        (out_dir / f"{run_id}.run.json").write_text(
            json.dumps(run_record, indent=2), encoding="utf-8"
        )

        logger.info(
            "run=%s cost_usd=%.6f latency_ms=%.1f contradictions=%d unresolved_issues=%d",
            run_id,
            total_cost,
            total_latency,
            len(state.get("contradictions", []) or []),
            len(unresolved),
        )
        # Per-node cost/latency breakdown (the node_metrics add-reducer accumulated these).
        for m in state.get("node_metrics", []):
            logger.debug(
                "  node=%-20s cost_usd=%.6f latency_ms=%.1f", m.node, m.cost_usd, m.latency_ms
            )
        if unresolved:
            update["errors"] = [
                f"finalize: {len(unresolved)} unresolved faithfulness issue(s) after reflection cap"
            ]

    update["node_metrics"] = [metric("finalize", latency_ms=timer.latency_ms)]
    return update
