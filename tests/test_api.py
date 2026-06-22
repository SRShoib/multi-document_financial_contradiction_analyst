"""FastAPI flow: start → pending → submit contradiction decisions → approve memo."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # Isolate artifacts and force the offline defaults for the app's runtime.
    monkeypatch.setenv("CONTENT_STORE_DIR", str(tmp_path / "content"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("CHECKPOINTER", "memory")

    from filing_reconciler.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as c:  # triggers lifespan → builds the GraphRuntime
        yield c
    get_settings.cache_clear()


def test_full_hitl_flow_over_api(client: TestClient) -> None:
    # 1. Start a run → pauses at the contradiction gate.
    started = client.post("/runs", json={"sample": "set_a"})
    assert started.status_code == 200
    body = started.json()
    run_id = body["run_id"]
    assert body["status"] == "paused"
    assert body["gate"] == "contradictions"

    # 2. List pending and build confirm decisions.
    pend = client.get(f"/runs/{run_id}/pending").json()["pending"]
    review = pend[0]
    decisions = [
        {"target_id": c["contradiction_id"], "action": "confirm"}
        for c in review["contradictions"]
    ]

    # 3. Submit decisions → resumes to the final sign-off gate.
    after = client.post(f"/runs/{run_id}/decision", json={"decisions": decisions}).json()
    assert after["status"] == "paused"
    assert after["gate"] == "final_memo"

    # 4. Approve the memo → run completes with a memo carrying citations.
    done = client.post(f"/runs/{run_id}/decision", json={"action": "approve"}).json()
    assert done["status"] == "completed"
    assert done["memo"] is not None
    assert done["memo"]["citations"]
    assert done["contradictions"] == 3
