"""Simple decorator-based tool registry for Pydantic AI.

Why: Pydantic AI tools are just functions - no need for complex abstractions.
Tradeoff: Less structured than class-based tools, but 10x simpler and more maintainable.
Alternative considered: Kept class-based Tool protocol (over-engineered for our needs).
"""

from typing import Callable, Dict

# Global registry mapping tool names to their functions
# Why: Simple dict lookup - no classes, no complexity
TOOL_REGISTRY: Dict[str, Callable] = {}


def register_tool(name: str):
    """Decorator to register tools in global dict.

    Why: Auto-registration via import means no manual registry management.
    Tradeoff: Must import all tool modules to register them (worth it for simplicity).

    Usage:
        @register_tool("calculator")
        async def calculator(ctx: RunContext[dict], expression: str) -> float:
            return eval_math(expression)

    Args:
        name: Unique identifier for the tool (used in agent tool lists)

    Returns:
        Decorator function that registers and returns the original function
    """
    def decorator(func: Callable) -> Callable:
        TOOL_REGISTRY[name] = func
        return func
    return decorator


# Import all tools to auto-register them
# Why: One-time import cost at module load, then tools are ready to use
from .calculator import calculator
# from .library_search import library_search  # Temporarily disabled - not using real data
from .ask_user import ask_user
from .memory_retrieve import memory_retrieve
from .workspace_graphql import (
    workspace_items_lookup,
    graph_node_lookup,
    graph_edge_lookup,
    graph_neighbors_lookup,
    scratchpad_notes_list,
)
from .workspace_attachments import (
    scratchpad_attachments_list,
    scratchpad_attachment_read,
)
from .web_search import web_search
from .workspace_data_fetch import workspace_data_fetch
from .data_aggregation import data_aggregation
from .date_time_utilities import date_time_utilities
from .cypher_query import cypher_query
from .cypher_result_compactor import (
    create_cypher_compactor,
    default_cypher_compactor,
    compact_cypher_content,
)

__all__ = [
    "TOOL_REGISTRY",
    "register_tool",
    "calculator",
    "ask_user",
    "memory_retrieve",
    "workspace_items_lookup",
    "graph_node_lookup",
    "graph_edge_lookup",
    "graph_neighbors_lookup",
    "scratchpad_notes_list",
    "scratchpad_attachments_list",
    "scratchpad_attachment_read",
    "web_search",
    "workspace_data_fetch",
    "data_aggregation",
    "date_time_utilities",
    "cypher_query",
    "create_cypher_compactor",
    "default_cypher_compactor",
    "compact_cypher_content",
]
