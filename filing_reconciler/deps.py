"""Dependency container injected into nodes.

Nodes close over a ``Deps`` instance (bound via ``functools.partial`` in
``graph.build_graph``) rather than importing globals or reading live objects from
the run config. This keeps nodes pure and unit-testable, and avoids putting
non-serializable objects (the LLM client, the store) into the checkpointed config.
"""

from dataclasses import dataclass

from .config import Settings, get_settings
from .llm import LLM, get_llm
from .store import ContentStore, FileContentStore


@dataclass
class Deps:
    settings: Settings
    llm: LLM
    store: ContentStore


def make_deps(settings: Settings | None = None) -> Deps:
    settings = settings or get_settings()
    return Deps(
        settings=settings,
        llm=get_llm(settings),
        store=FileContentStore(settings.content_store_dir),
    )
