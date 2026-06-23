"""LLM provider factory: selection + key guards (offline; no network calls).

Constructing a provider client does not hit the network — these assert routing and
that each real provider fails fast without its API key.
"""

import pytest
from filing_reconciler.config import Settings
from filing_reconciler.llm import StubLLM, get_llm


def test_factory_defaults_to_stub() -> None:
    assert isinstance(get_llm(Settings(_env_file=None)), StubLLM)


def test_openai_provider_selected() -> None:
    llm = get_llm(Settings(_env_file=None, llm_provider="openai", openai_api_key="sk-test"))
    assert llm.name == "gpt-4.1"


def test_openai_requires_key() -> None:
    with pytest.raises(RuntimeError):
        get_llm(Settings(_env_file=None, llm_provider="openai", openai_api_key=None))
