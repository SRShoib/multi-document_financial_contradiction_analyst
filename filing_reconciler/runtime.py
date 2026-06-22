"""GraphRuntime — owns the checkpointer lifecycle and the compiled graph.

A single runtime is created per process (CLI run, or for the FastAPI app's
lifetime) so that:
* the in-memory checkpointer instance persists across HITL pause/resume calls, and
* the Postgres connection/pool stays open for every graph call made against it.

``start`` / ``resume`` (resume lands in step 5) wrap ``invoke`` with the thread
config required by the checkpointer.
"""

import uuid
from contextlib import ExitStack
from typing import Any

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

    def get_state(self, thread_id: str) -> Any:
        """Current checkpointed state snapshot for a thread (next nodes, values...)."""
        return self.graph.get_state(self.thread_config(thread_id))
