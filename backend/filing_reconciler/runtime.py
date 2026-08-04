"""GraphRuntime — owns the checkpointer lifecycle and the compiled graph.

A single runtime is created per process (CLI run, or for the FastAPI app's
lifetime) so that:
* the in-memory checkpointer instance persists across HITL pause/resume calls, and
* the Postgres connection/pool stays open for every graph call made against it.

``start`` / ``resume`` (resume lands in step 5) wrap ``invoke`` with the thread
config required by the checkpointer.
"""

import uuid
from collections.abc import Callable
from contextlib import ExitStack
from typing import Any

from langgraph.types import Command

from .checkpointer import open_checkpointer
from .config import Settings, get_settings
from .deps import make_deps
from .graph import build_graph
from .models import DocInput
from .state import GraphState


class GraphRuntime:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.deps = make_deps(self.settings)
        self._stack = ExitStack()
        self.checkpointer = open_checkpointer(self.settings, self._stack)
        self.graph = build_graph(self.deps, checkpointer=self.checkpointer)

    def close(self) -> None:
        self._stack.close()

    def __enter__(self) -> "GraphRuntime":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @staticmethod
    def thread_config(thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}}

    def start(
        self,
        inputs: list[DocInput],
        *,
        company: str | None = None,
        thread_id: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Start a run. Returns ``(thread_id, result_state)``.

        ``result_state`` contains ``__interrupt__`` when the run paused at a HITL
        gate (step 5); otherwise it is the completed final state.
        """
        thread_id = thread_id or uuid.uuid4().hex
        initial: GraphState = {"inputs": inputs, "run_id": thread_id, "company": company}
        result = self.graph.invoke(initial, self.thread_config(thread_id))
        return thread_id, result

    def resume(self, thread_id: str, payload: Any) -> dict[str, Any]:
        """Resume a paused run by feeding ``payload`` back to the waiting interrupt()."""
        return self.graph.invoke(Command(resume=payload), self.thread_config(thread_id))

    def get_state(self, thread_id: str) -> Any:
        """Current checkpointed state snapshot for a thread (next nodes, values...)."""
        return self.graph.get_state(self.thread_config(thread_id))

    @staticmethod
    def interrupts_from_result(result: dict[str, Any]) -> list[Any]:
        """Extract the interrupt payload values from an invoke/resume result."""
        return [getattr(itr, "value", itr) for itr in (result.get("__interrupt__") or [])]

    def pending_reviews(self, thread_id: str) -> list[Any]:
        """Interrupt payloads currently awaiting a human decision for a thread."""
        snap = self.graph.get_state(self.thread_config(thread_id))
        out: list[Any] = []
        for itr in getattr(snap, "interrupts", None) or []:
            out.append(getattr(itr, "value", itr))
        if out:
            return out
        for task in getattr(snap, "tasks", []) or []:
            for itr in getattr(task, "interrupts", None) or []:
                out.append(getattr(itr, "value", itr))
        return out

    def drive(
        self,
        inputs: list[DocInput],
        *,
        company: str | None = None,
        decider: Callable[[dict[str, Any]], Any] | None = None,
        thread_id: str | None = None,
        max_steps: int = 10,
    ) -> tuple[str, dict[str, Any]]:
        """Start a run and auto-resume through every HITL gate using ``decider``.

        Used by the CLI ``--auto-approve`` flow and tests to exercise the full
        interrupt/resume cycle in a single process. ``decider`` maps a review payload
        to a resume payload; defaults to confirm-all / approve.
        """
        decider = decider or auto_confirm_decider
        thread_id, result = self.start(inputs, company=company, thread_id=thread_id)
        for _ in range(max_steps):
            pending = self.interrupts_from_result(result)
            if not pending:
                break
            result = self.resume(thread_id, decider(pending[0]))
        return thread_id, result


def auto_confirm_decider(review: dict[str, Any]) -> Any:
    """Default decider: confirm every flagged contradiction; approve the final memo."""
    if review.get("kind") == "contradictions":
        return [
            {"target_id": c["contradiction_id"], "action": "confirm"}
            for c in review.get("contradictions", [])
        ]
    return {"action": "approve"}
