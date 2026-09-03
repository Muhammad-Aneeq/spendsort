"""The graph — exactly four nodes (spec 11 section 4 F2, and the brief's "<=4 nodes exactly").

    START -> normalize_vendor -> check_memory --(miss)--> llm_categorize -> route -> END
                                            \\--(hit)-----------------------^

The memory hit is a conditional **edge**, not a node. That is what lets the LLM be skipped
entirely while the node count stays at four.

LangGraph only (spec 00 F: "no LangChain-classic chains (LCEL/LangGraph only)").
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.agent.llm import Categorizer, build_categorizer
from app.agent.nodes import (
    make_check_memory,
    make_llm_categorize,
    memory_branch,
    normalize_vendor,
    route,
)
from app.agent.state import CategorizeState
from app.coa import ChartOfAccounts, get_coa

# The four node names, in order. Asserted by test_graph_shape.py so a fifth node cannot be
# added without the constraint failing loudly.
NODE_NAMES: tuple[str, ...] = ("normalize_vendor", "check_memory", "llm_categorize", "route")


def build_graph(
    db: Session,
    *,
    categorizer: Categorizer | None = None,
    coa: ChartOfAccounts | None = None,
) -> Any:
    """Compile the categorization graph.

    `categorizer` is injectable so tests can pass a fake that fails the test if it is called
    on a memory hit — which is how the "bypasses the LLM entirely" claim is actually proven.
    """
    resolved_coa = coa or get_coa()
    resolved_categorizer = categorizer or build_categorizer()

    builder = StateGraph(CategorizeState)

    # The two `type: ignore`s are third-party generics friction, not a real type problem:
    # LangGraph 1.x declares node arguments as `_Node[Never]`, which no explicitly-annotated
    # `Callable[[CategorizeState], CategorizeState]` can satisfy. The closure-built nodes are
    # annotated (so they stay checked internally) and therefore trip it; the two plain
    # functions are inferred and do not.
    builder.add_node("normalize_vendor", normalize_vendor)
    builder.add_node("check_memory", make_check_memory(db))  # type: ignore[arg-type]
    builder.add_node(
        "llm_categorize",
        make_llm_categorize(resolved_categorizer, resolved_coa),  # type: ignore[arg-type]
    )
    builder.add_node("route", route)

    builder.add_edge(START, "normalize_vendor")
    builder.add_edge("normalize_vendor", "check_memory")
    builder.add_conditional_edges(
        "check_memory",
        memory_branch,
        {"llm_categorize": "llm_categorize", "route": "route"},
    )
    builder.add_edge("llm_categorize", "route")
    builder.add_edge("route", END)

    return builder.compile()
