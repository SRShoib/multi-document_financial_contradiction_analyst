"""HITL interrupt/resume: pause at the contradiction gate, then confirm/reject/edit."""

from pathlib import Path
from typing import Any

from filing_reconciler.config import Settings
from filing_reconciler.runtime import GraphRuntime
from filing_reconciler.samples import load_sample


def _runtime(tmp_path: Path) -> GraphRuntime:
    settings = Settings(
        _env_file=None,
        content_store_dir=str(tmp_path / "content"),
        output_dir=str(tmp_path / "out"),
    )
    return GraphRuntime(settings)


def test_run_pauses_at_contradiction_gate(tmp_path: Path) -> None:
    with _runtime(tmp_path) as rt:
        company, inputs = load_sample("set_a")
        run_id, result = rt.start(inputs, company=company)
        pending = rt.interrupts_from_result(result)
        assert pending, "run should pause at the HITL contradiction gate"
        review = pending[0]
        assert review["kind"] == "contradictions"
        # revenue (high severity) and litigation (confidence < 0.75) are flagged;
        # the guidance revision (medium / 0.8) is auto-accepted and bypasses review.
        flagged = {c["topic"] for c in review["contradictions"]}
        assert flagged == {"revenue", "litigation"}
        # pending_reviews reads the same interrupt from the checkpoint.
        assert len(rt.pending_reviews(run_id)) == 1


def test_confirm_all_resumes_to_final_memo(tmp_path: Path) -> None:
    with _runtime(tmp_path) as rt:
        company, inputs = load_sample("set_a")
        _run_id, result = rt.drive(inputs, company=company)  # auto confirm + approve

    assert "__interrupt__" not in result
    memo = result["final_memo"]
    assert memo is not None and memo.sections
    statuses = {c.topic: c.status for c in result["contradictions"]}
    assert statuses["revenue"] == "confirmed"
    assert statuses["litigation"] == "confirmed"
    assert statuses["guidance.revenue"] == "auto_accepted"
    # decisions recorded: 2 contradiction confirms + 1 final sign-off
    assert len(result["human_decisions"]) == 3


def test_reject_drops_contradiction(tmp_path: Path) -> None:
    def decider(review: dict[str, Any]) -> Any:
        if review.get("kind") == "contradictions":
            out = []
            for c in review["contradictions"]:
                action = "reject" if c["topic"] == "revenue" else "confirm"
                out.append({"target_id": c["contradiction_id"], "action": action})
            return out
        return {"action": "approve"}

    with _runtime(tmp_path) as rt:
        company, inputs = load_sample("set_a")
        _run_id, result = rt.drive(inputs, company=company, decider=decider)

    topics = {c.topic for c in result["contradictions"]}
    assert "revenue" not in topics  # rejected → dropped from the downstream set
    # and dropped from the risk register too (guidance.revenue is a different topic)
    risk_titles = {i.title for i in result["risk_register"].items}
    assert "revenue: numeric_mismatch" not in risk_titles


def test_edit_changes_severity(tmp_path: Path) -> None:
    def decider(review: dict[str, Any]) -> Any:
        if review.get("kind") == "contradictions":
            out = []
            for c in review["contradictions"]:
                if c["topic"] == "revenue":
                    out.append(
                        {
                            "target_id": c["contradiction_id"],
                            "action": "edit",
                            "edited_severity": "low",
                            "note": "reclassified",
                        }
                    )
                else:
                    out.append({"target_id": c["contradiction_id"], "action": "confirm"})
            return out
        return {"action": "approve"}

    with _runtime(tmp_path) as rt:
        company, inputs = load_sample("set_a")
        _run_id, result = rt.drive(inputs, company=company, decider=decider)

    revenue = next(c for c in result["contradictions"] if c.topic == "revenue")
    assert revenue.status == "edited"
    assert revenue.severity == "low"
    assert revenue.human_note == "reclassified"
