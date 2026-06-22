"""End-to-end smoke test.

Currently RED on purpose (build order step 1): build_graph raises
NotImplementedError. It goes green at step 3 once the graph is wired with
stub nodes and runs over the sample data.
"""

from __future__ import annotations


def test_build_graph_compiles() -> None:
    from filing_reconciler.graph import build_graph

    graph = build_graph()
    assert graph is not None
