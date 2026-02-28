"""History processor for compacting cypher_query results in message history.

This module provides a history_processor function that transforms verbose
cypher_query tool returns into compact summaries while preserving the
original query for re-fetching.

Usage:
    from app.tools.cypher_result_compactor import create_cypher_compactor

    agent = Agent(
        model="gpt-4o",
        tools=[cypher_query],
        history_processors=[create_cypher_compactor(sample_rows=10)]
    )
"""

import json
import logging
from dataclasses import replace
from typing import Any, Callable, Optional

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ToolReturnPart,
)

logger = logging.getLogger(__name__)

# Marker to identify already-compacted results
COMPACTED_MARKER = "compacted"


def is_cypher_result(content: Any) -> bool:
    """Check if content looks like a cypher_query result."""
    if not isinstance(content, dict):
        return False
    # Must have "results" key with list value
    # The "count" key alone is not sufficient (could be any dict with count)
    return "results" in content and isinstance(content.get("results"), list)


def is_already_compacted(content: Any) -> bool:
    """Check if content is already compacted (either by this module or cypher_query's compression)."""
    if not isinstance(content, dict):
        return False
    # Check for our marker or the cypher_query tool's compression marker
    return content.get(COMPACTED_MARKER) is True or content.get("compressed") is True


def compact_cypher_content(
    content: dict[str, Any],
    original_query: Optional[str] = None,
    sample_rows: int = 10,
) -> dict[str, Any]:
    """Compact verbose cypher_query content into a summary.

    Args:
        content: The original tool return content
        original_query: The Cypher query that produced this result
        sample_rows: Number of sample rows to include

    Returns:
        Compacted content dict
    """
    if is_already_compacted(content):
        return content

    results = content.get("results", [])
    count = content.get("count", len(results))
    truncated = content.get("truncated", False)

    if not results:
        return {
            COMPACTED_MARKER: True,
            "original_query": original_query or "(query not captured)",
            "result_count": 0,
            "truncated": truncated,
            "summary": "Query returned no results",
            "columns": [],
            "sample_rows": [],
            "sample_row_count": 0,
            "refetch_hint": "Re-run the query if you need to verify the empty result.",
        }

    # Get column names from first row
    columns = list(results[0].keys())

    # Compute aggregates for numeric columns
    numeric_aggregates = {}
    for col in columns:
        if col in ("id", "labels"):
            continue
        numeric_values = []
        for row in results:
            val = row.get(col)
            if val is not None:
                try:
                    numeric_values.append(float(val))
                except (ValueError, TypeError):
                    pass

        if numeric_values:
            numeric_aggregates[col] = {
                "min": min(numeric_values),
                "max": max(numeric_values),
                "sum": sum(numeric_values),
                "avg": sum(numeric_values) / len(numeric_values),
                "count_numeric": len(numeric_values),
            }

    # Get distinct values for low-cardinality columns
    distinct_values = {}
    for col in columns:
        if col in ("id", "labels"):
            continue
        values = [row.get(col) for row in results if row.get(col) is not None]
        unique = list(set(str(v) for v in values))
        if len(unique) <= 20:  # Low cardinality
            distinct_values[col] = unique[:20]

    return {
        COMPACTED_MARKER: True,
        "original_query": original_query or "(query not captured)",
        "result_count": count,
        "truncated": truncated,
        "summary": f"Query returned {count} rows with columns: {', '.join(columns)}",
        "columns": columns,
        "sample_rows": results[:sample_rows],
        "sample_row_count": min(sample_rows, len(results)),
        "numeric_aggregates": numeric_aggregates if numeric_aggregates else None,
        "distinct_values": distinct_values if distinct_values else None,
        "refetch_hint": "Re-run the original_query with cypher_query tool to retrieve full data if needed.",
    }


def find_query_for_tool_call(
    messages: list[ModelMessage],
    tool_call_id: str,
) -> Optional[str]:
    """Find the Cypher query string for a given tool call ID.

    Searches backwards through messages to find the ToolCallPart that
    matches the tool_call_id, then extracts the query argument.
    """
    for msg in reversed(messages):
        # Use duck typing to support both real ModelResponse and test mocks
        if not hasattr(msg, "parts"):
            continue
        for part in msg.parts:
            if hasattr(part, "part_kind") and part.part_kind == "tool-call":
                if hasattr(part, "tool_call_id") and part.tool_call_id == tool_call_id:
                    # Found matching tool call - extract query arg
                    args = part.args
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            return None
                    if isinstance(args, dict):
                        return args.get("query")
    return None


def create_cypher_compactor(
    sample_rows: int = 10,
    min_rows_to_compact: int = 20,
) -> Callable[[list[ModelMessage]], list[ModelMessage]]:
    """Create a history processor that compacts cypher_query results.

    Args:
        sample_rows: Number of sample rows to keep in compacted result
        min_rows_to_compact: Minimum result size to trigger compaction
                            (smaller results are kept as-is)

    Returns:
        History processor function compatible with pydantic-ai Agent
    """

    def compact_cypher_results(
        messages: list[ModelMessage],
    ) -> list[ModelMessage]:
        """Transform message history, compacting cypher_query tool returns."""

        result_messages = []

        for msg in messages:
            # Use duck typing: ModelRequest has parts with tool-return parts
            # ModelResponse has parts with tool-call parts
            # We only want to modify ModelRequest messages (contain ToolReturnPart)
            if not hasattr(msg, "parts"):
                result_messages.append(msg)
                continue

            # Check if this message has any tool-return parts (indicates ModelRequest)
            has_tool_return = any(
                hasattr(p, "part_kind") and p.part_kind == "tool-return"
                for p in msg.parts
            )

            if not has_tool_return:
                # Not a ModelRequest with tool returns, pass through
                result_messages.append(msg)
                continue

            # Process the parts
            new_parts = []
            modified = False

            for part in msg.parts:
                    if (
                        hasattr(part, "part_kind")
                        and part.part_kind == "tool-return"
                        and hasattr(part, "tool_name")
                        and part.tool_name == "cypher_query"
                    ):
                        content = part.content

                        # Check if should compact
                        if (
                            is_cypher_result(content)
                            and not is_already_compacted(content)
                            and content.get("count", len(content.get("results", [])))
                            >= min_rows_to_compact
                        ):
                            # Find the original query
                            original_query = find_query_for_tool_call(
                                messages, part.tool_call_id
                            )

                            # Compact the content
                            compacted_content = compact_cypher_content(
                                content,
                                original_query=original_query,
                                sample_rows=sample_rows,
                            )

                            # Create new ToolReturnPart with compacted content
                            new_part = replace(part, content=compacted_content)
                            new_parts.append(new_part)
                            modified = True

                            logger.debug(
                                f"Compacted cypher_query result: "
                                f"{content.get('count', 0)} rows -> {sample_rows} samples"
                            )
                        else:
                            new_parts.append(part)
                    else:
                        new_parts.append(part)

            if modified:
                # Create new message with modified parts
                new_msg = replace(msg, parts=new_parts)
                result_messages.append(new_msg)
            else:
                result_messages.append(msg)

        return result_messages

    return compact_cypher_results


# Convenience: Default compactor instance
default_cypher_compactor = create_cypher_compactor(sample_rows=10, min_rows_to_compact=20)

__all__ = [
    "create_cypher_compactor",
    "default_cypher_compactor",
    "compact_cypher_content",
    "is_already_compacted",
    "is_cypher_result",
]
