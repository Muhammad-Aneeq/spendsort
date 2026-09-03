"""The graph must have EXACTLY four nodes, in the order the spec names.

spec 11 section 4 F2:
    "Categorization graph (LangGraph, <=4 nodes): normalize_vendor -> check_memory
     (learned mappings first, zero LLM cost) -> llm_categorize (structured output:
     {account_code, confidence, reason}) -> route (auto >= threshold | queue)"

This is a structural constraint, so it gets a structural test. Adding a fifth node — however
reasonable it might seem at the time — fails here immediately.
"""

from __future__ import annotations

from app.agent.graph import NODE_NAMES, build_graph

# LangGraph adds these to every compiled graph; they are not nodes we wrote.
_BUILTINS = {"__start__", "__end__"}


def test_the_graph_has_exactly_four_nodes(db) -> None:
    graph = build_graph(db)
    ours = set(graph.get_graph().nodes) - _BUILTINS

    assert len(ours) == 4, f"expected exactly 4 nodes, found {len(ours)}: {sorted(ours)}"
    assert ours == set(NODE_NAMES)


def test_the_nodes_are_the_ones_the_spec_names(db) -> None:
    assert NODE_NAMES == ("normalize_vendor", "check_memory", "llm_categorize", "route")


def test_the_pipeline_is_wired_in_spec_order(db) -> None:
    graph = build_graph(db)
    edges = {(e.source, e.target) for e in graph.get_graph().edges}

    assert ("__start__", "normalize_vendor") in edges
    assert ("normalize_vendor", "check_memory") in edges
    assert ("llm_categorize", "route") in edges
    assert ("route", "__end__") in edges


def test_check_memory_can_reach_route_without_the_llm(db) -> None:
    """The bypass exists as an EDGE, not a fifth node. This edge is the "zero LLM cost"
    promise of spec 11 section 4 F4."""
    graph = build_graph(db)
    edges = {(e.source, e.target) for e in graph.get_graph().edges}

    assert ("check_memory", "route") in edges, "no memory bypass edge — hits would still pay for the LLM"
    assert ("check_memory", "llm_categorize") in edges, "no miss path to the LLM"


def test_the_llm_is_never_upstream_of_memory(db) -> None:
    """Memory must be consulted FIRST. If the LLM could run before check_memory, every
    learned mapping would still cost money and the cost curve would never bend."""
    graph = build_graph(db)
    edges = {(e.source, e.target) for e in graph.get_graph().edges}

    assert ("llm_categorize", "check_memory") not in edges
    assert not any(target == "normalize_vendor" for source, target in edges if source != "__start__")
