"""Checkpointer factory — durable execution backing the HITL pause/resume gates.

``memory``   → ``InMemorySaver`` (default; resume only within one live process).
``postgres`` → ``PostgresSaver`` (durable; HITL pauses survive process restarts).

The Postgres saver opens a connection that must outlive every graph call made
against it, so we manage its lifecycle with an ``ExitStack`` owned by the caller
(see ``GraphRuntime``). ``.setup()`` is called once to create the checkpoint
tables (idempotent).
"""

from contextlib import ExitStack
from typing import Any

from .config import Settings


def open_checkpointer(settings: Settings, stack: ExitStack) -> Any:
    """Open a checkpointer, registering any cleanup on ``stack``."""
    if settings.checkpointer == "memory":
        from langgraph.checkpoint.memory import InMemorySaver

        return InMemorySaver()

    if settings.checkpointer == "postgres":
        from langgraph.checkpoint.postgres import PostgresSaver

        # from_conn_string yields a saver bound to an open connection/pool.
        saver = stack.enter_context(PostgresSaver.from_conn_string(settings.database_url))
        saver.setup()  # idempotent: creates checkpoint tables / runs migrations
        return saver

    raise ValueError(f"Unknown CHECKPOINTER: {settings.checkpointer!r}")
