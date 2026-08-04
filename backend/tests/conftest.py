"""Test fixtures.

Tests are hermetic: they must not depend on a developer's local ``.env`` (which may
select a real LLM provider and a Postgres checkpointer). This autouse fixture forces
the offline stub + in-memory checkpointer for every test, regardless of local config,
and resets the cached settings around each test. OS env vars take precedence over the
``.env`` file in pydantic-settings, so this reliably overrides it.
"""

import pytest
from filing_reconciler.config import get_settings


@pytest.fixture(autouse=True)
def _offline_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "stub")
    monkeypatch.setenv("CHECKPOINTER", "memory")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
