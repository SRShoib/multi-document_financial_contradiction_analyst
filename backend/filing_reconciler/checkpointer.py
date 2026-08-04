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
        from psycopg import Connection
        from psycopg.rows import DictRow, dict_row
        from psycopg_pool import ConnectionPool

        # A pool, not ``from_conn_string`` — that helper binds the saver to a
        # *single* Connection guarded by a lock, so concurrent API requests
        # serialize on one connection. The three kwargs mirror what it sets
        # internally; PostgresSaver requires all of them (notably ``dict_row``).
        # ``connection_class`` carries the row type statically (mypy can't see it
        # through ``kwargs``); at runtime the alias proxies to ``Connection``.
        pool: ConnectionPool[Connection[DictRow]] = ConnectionPool(
            conninfo=settings.database_url,
            connection_class=Connection[DictRow],
            min_size=settings.db_pool_min,
            max_size=settings.db_pool_max,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
            open=True,
        )
        stack.callback(pool.close)
        saver = PostgresSaver(pool)
        saver.setup()  # idempotent: creates checkpoint tables / runs migrations
        return saver

    raise ValueError(f"Unknown CHECKPOINTER: {settings.checkpointer!r}")
