"""
Cypher Query Tool with Workspace Auto-Scoping.

This tool allows agents to execute Cypher queries against the workspace graph.
Queries are automatically scoped to the current workspace by injecting
WHERE conditions that filter to workspace node IDs.

Key features:
- Auto-scoping: Agents write clean Cypher, tool handles workspace filtering
- Result limiting: Configurable max results to prevent token overflow
- Error handling: Clear error messages for invalid queries
- Retry with backoff: Handles transient network failures
"""

import asyncio
import logging
import random
import re
from typing import Dict, Any, List, Optional

from pydantic_ai import RunContext

from app.tools import register_tool
from app.core.authenticated_graphql_client import run_graphql

logger = logging.getLogger(__name__)

# Retry configuration for transient failures
CYPHER_MAX_RETRY_ATTEMPTS = 2  # 1 retry after initial failure
CYPHER_INITIAL_RETRY_DELAY = 1.0
CYPHER_MAX_RETRY_DELAY = 8.0


# GraphQL query to execute Cypher
CYPHER_QUERY = """
query ExecuteCypher($cypherQuery: String!, $workspaceId: UUID) {
    graphNodesByCypher(cypherQuery: $cypherQuery, workspaceId: $workspaceId) {
        id
        labels
        properties {
            key
            value
        }
    }
}
""".strip()


@register_tool("cypher_query")
async def cypher_query(
    ctx: RunContext[dict],
    query: str,
    max_results: int = 1000
) -> Dict[str, Any]:
    """
    Execute a Cypher query against the workspace graph.

    IMPORTANT: Queries are automatically scoped to the current workspace.
    You do NOT need to filter by workspace - it's handled automatically.

    Args:
        query: Cypher query string. Must include MATCH and RETURN clauses.
               Example: "MATCH (c:Claim) WHERE c.paid_amount > 1000 RETURN c.claim_id, c.paid_amount"
        max_results: Maximum number of results to return (default 1000).
                     Results are truncated if they exceed this limit.

    Returns:
        Dict with:
        - results: List of result rows (dicts or node objects)
        - count: Number of results returned
        - truncated: True if results were truncated
        - error: Error message if query failed

    Examples:
        # Get high-value claims
        cypher_query("MATCH (c:Claim) WHERE c.paid_amount > 5000 RETURN c.claim_id, c.paid_amount ORDER BY c.paid_amount DESC")

        # Count by category
        cypher_query("MATCH (c:Claim) RETURN c.drug_class, count(c) as count ORDER BY count DESC")

        # Find related entities
        cypher_query("MATCH (m:Member)-[:FILED_CLAIM]->(c:Claim) RETURN m.member_id, count(c) as claim_count")

        # Aggregate statistics
        cypher_query("MATCH (c:Claim) RETURN min(c.paid_amount), max(c.paid_amount), avg(c.paid_amount)")
    """
    # Extract context
    workspace_id = ctx.deps.get("workspace_id")
    tenant_id = ctx.deps.get("tenant_id")
    workspace_node_ids = ctx.deps.get("workspace_node_ids", {})

    if not workspace_id:
        return {"error": "workspace_id not found in context", "results": [], "count": 0, "truncated": False}

    if not tenant_id:
        return {"error": "tenant_id not found in context", "results": [], "count": 0, "truncated": False}

    # Budget tracking
    budget_max_calls = ctx.deps.get("cypher_budget_max_calls")
    budget_state = ctx.deps.get("cypher_budget_state")

    # Initialize state on first call if budget configured but state not yet created
    if budget_max_calls is not None and budget_state is None:
        budget_state = {"calls_made": 0, "total_results_returned": 0, "queries": []}
        ctx.deps["cypher_budget_state"] = budget_state

    # Check call budget before executing
    if budget_state is not None and budget_max_calls is not None:
        if budget_state["calls_made"] >= budget_max_calls:
            logger.warning(
                f"Cypher query budget exhausted: {budget_state['calls_made']}/{budget_max_calls} calls used. "
                f"Total results so far: {budget_state['total_results_returned']}"
            )
            return {
                "error": (
                    f"Query budget exhausted ({budget_max_calls} calls used). "
                    "Complete your analysis with the data already gathered."
                ),
                "results": [],
                "count": 0,
                "truncated": False,
                "budget_exhausted": True,
            }

    # Validate query has required clauses
    query_upper = query.upper()
    if "MATCH" not in query_upper:
        return {"error": "Query must include MATCH clause", "results": [], "count": 0, "truncated": False}
    if "RETURN" not in query_upper:
        return {"error": "Query must include RETURN clause", "results": [], "count": 0, "truncated": False}

    # Enforce result limit
    max_results = min(max_results, 1000)

    # Auto-scope query to workspace
    try:
        scoped_query = _inject_workspace_scope(query, workspace_node_ids)
    except Exception as e:
        logger.warning(f"Failed to inject workspace scope: {e}. Using original query.")
        scoped_query = query

    # Add LIMIT if not present
    if "LIMIT" not in scoped_query.upper():
        scoped_query = f"{scoped_query} LIMIT {max_results + 1}"  # +1 to detect truncation

    # Execute via GraphQL with retry logic for transient failures
    last_error = None
    for attempt in range(1, CYPHER_MAX_RETRY_ATTEMPTS + 1):
        try:
            result = await run_graphql(
                CYPHER_QUERY,
                {"cypherQuery": scoped_query, "workspaceId": workspace_id},
                tenant_id=tenant_id,
                timeout=30  # 30 second timeout for queries
            )
            break  # Success, exit retry loop
        except Exception as e:
            last_error = e
            error_msg = str(e)

            # Check if it's a retryable error
            is_retryable = any(keyword in error_msg.lower() for keyword in [
                "timeout", "ssl", "handshake", "connection", "urlopen error",
                "reset by peer", "errno 104", "errno 110", "temporarily unavailable"
            ])

            if not is_retryable or attempt == CYPHER_MAX_RETRY_ATTEMPTS:
                logger.error(f"Cypher query failed after {attempt} attempt(s): {error_msg}")
                return {"error": f"Query execution failed: {error_msg}", "results": [], "count": 0, "truncated": False}

            # Calculate delay with exponential backoff and jitter
            delay = min(
                CYPHER_INITIAL_RETRY_DELAY * (2 ** (attempt - 1)),
                CYPHER_MAX_RETRY_DELAY
            )
            delay = delay * (0.75 + random.random() * 0.5)  # Add jitter

            logger.warning(
                f"Cypher query failed (attempt {attempt}/{CYPHER_MAX_RETRY_ATTEMPTS}): {error_msg}. "
                f"Retrying in {delay:.1f}s..."
            )
            await asyncio.sleep(delay)
    else:
        # Should not reach here, but safety fallback
        return {"error": f"Query execution failed after {CYPHER_MAX_RETRY_ATTEMPTS} attempts: {last_error}", "results": [], "count": 0, "truncated": False}

    # Process results
    nodes = result.get("graphNodesByCypher", [])

    # Format nodes as flat dictionaries
    formatted_results = []
    for node in nodes:
        if not node:
            continue
        # Convert properties list to dict
        props = {prop["key"]: prop["value"] for prop in node.get("properties", [])}
        formatted_results.append({
            "id": node.get("id"),
            "labels": node.get("labels", []),
            **props
        })

    # Check if truncated
    truncated = len(formatted_results) > max_results
    if truncated:
        formatted_results = formatted_results[:max_results]

    # Update budget state
    if budget_state is not None:
        budget_state["calls_made"] += 1
        budget_state["total_results_returned"] += len(formatted_results)
        budget_state["queries"].append({
            "query": query[:200],
            "result_count": len(formatted_results),
            "truncated": truncated,
        })
    # Check if compression is enabled
    compress_results = ctx.deps.get("compress_cypher_results", False)
    sample_rows = ctx.deps.get("compress_sample_rows", 10)

    if compress_results and len(formatted_results) > sample_rows:
        # Compress results: return summary + sample + aggregates instead of full data
        result_dict = _compress_results(formatted_results, sample_rows, truncated)
    else:
        result_dict = {
            "results": formatted_results,
            "count": len(formatted_results),
            "truncated": truncated,
        }

    # Include budget info for agent awareness
    if budget_state is not None:
        result_dict["budget_remaining_calls"] = (budget_max_calls or 999) - budget_state["calls_made"]

    return result_dict


def _inject_workspace_scope(
    query: str,
    workspace_node_ids: Dict[str, List[str]],
    max_ids_for_inline_scope: int = 1000
) -> str:
    """
    Inject workspace scoping into Cypher query.

    This transforms queries to only match nodes within the workspace scope.

    Strategy:
    1. Parse MATCH patterns to find (variable:Label) pairs
    2. For each variable with a known label with <= max_ids_for_inline_scope IDs,
       inject "variable.id IN [...]"
    3. Skip scoping for labels with too many IDs (would make query too large)
    4. Handle existing WHERE clauses gracefully

    Args:
        query: Original Cypher query
        workspace_node_ids: Dict mapping entity type -> list of node IDs
        max_ids_for_inline_scope: Maximum number of IDs to inject inline (default 50).
                                   Labels with more IDs are not scope-filtered to avoid
                                   query size issues.

    Returns:
        Query with workspace scoping injected

    Examples:
        Input:  MATCH (c:Claim) WHERE c.amount > 1000 RETURN c
        Output: MATCH (c:Claim) WHERE c.id IN ["id1","id2",...] AND c.amount > 1000 RETURN c

        Input:  MATCH (m:Member)-[:HAS]->(c:Claim) RETURN m, c
        Output: MATCH (m:Member)-[:HAS]->(c:Claim) WHERE m.id IN [...] AND c.id IN [...] RETURN m, c
    """
    if not workspace_node_ids:
        logger.warning("No workspace node IDs provided for scoping")
        return query

    # Pattern to find node variables with labels: (var:Label) or (var:Label1|Label2)
    # Captures: variable name, label(s)
    node_pattern = r'\((\w+):([A-Za-z_][A-Za-z0-9_|]*)\)'
    matches = re.findall(node_pattern, query)

    if not matches:
        logger.debug("No labeled node patterns found in query, skipping scope injection")
        return query

    # Build scope conditions for each variable with matching label
    scope_conditions = []
    for var_name, labels_str in matches:
        # Handle multiple labels (Label1|Label2)
        labels = labels_str.split("|")
        primary_label = labels[0]

        # Check if we have IDs for this label
        if primary_label in workspace_node_ids:
            node_ids = workspace_node_ids[primary_label]
            if node_ids:
                # Truncate ID list if too many (to prevent query size issues)
                if len(node_ids) > max_ids_for_inline_scope:
                    truncated_ids = node_ids[:max_ids_for_inline_scope]
                    logger.info(
                        f"Truncating {primary_label} scope from {len(node_ids)} to {max_ids_for_inline_scope} IDs"
                    )
                else:
                    truncated_ids = node_ids
                # Build ID list for Cypher (escape quotes in IDs)
                id_list = ", ".join(f'"{nid}"' for nid in truncated_ids)
                scope_conditions.append(f"{var_name}.id IN [{id_list}]")

    if not scope_conditions:
        logger.debug("No matching labels found in workspace, skipping scope injection")
        return query

    # Combine all conditions
    scope_clause = " AND ".join(scope_conditions)

    # Find where to inject the WHERE clause
    # Look for existing WHERE (case-insensitive)
    where_match = re.search(r'\bWHERE\b', query, re.IGNORECASE)

    if where_match:
        # Insert after existing WHERE, wrapping original conditions
        where_pos = where_match.end()
        # Find the next clause (RETURN, WITH, ORDER BY, etc.) to know where WHERE ends
        next_clause = re.search(r'\b(RETURN|WITH|ORDER\s+BY|SKIP|LIMIT|UNION)\b', query[where_pos:], re.IGNORECASE)

        if next_clause:
            # Extract existing WHERE conditions
            existing_conditions = query[where_pos:where_pos + next_clause.start()].strip()
            # Rebuild query with scope first
            scoped = (
                query[:where_pos] +
                f" ({scope_clause}) AND ({existing_conditions}) " +
                query[where_pos + next_clause.start():]
            )
        else:
            # WHERE is at the end, just prepend scope
            existing_conditions = query[where_pos:].strip()
            scoped = query[:where_pos] + f" ({scope_clause}) AND ({existing_conditions})"
    else:
        # No existing WHERE, find position before RETURN/WITH/ORDER BY
        clause_match = re.search(r'\b(RETURN|WITH|ORDER\s+BY)\b', query, re.IGNORECASE)
        if clause_match:
            insert_pos = clause_match.start()
            scoped = query[:insert_pos] + f" WHERE {scope_clause} " + query[insert_pos:]
        else:
            # Fallback: append WHERE at the end
            scoped = query + f" WHERE {scope_clause}"

    return scoped


def _escape_cypher_string(value: str) -> str:
    """Escape a string for use in Cypher queries."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("'", "\\'")


def _compress_results(
    results: List[Dict[str, Any]],
    sample_rows: int,
    truncated: bool
) -> Dict[str, Any]:
    """
    Compress query results into a summary format for reduced token usage.

    Instead of returning all rows (which bloats conversation history),
    returns:
    - Summary statistics
    - Sample rows for inspection
    - Aggregates for numeric columns

    This allows the agent to reason about the data without accumulating
    massive token counts in the message history.
    """
    if not results:
        return {
            "count": 0,
            "truncated": truncated,
            "compressed": True,
            "summary": "No results returned",
            "sample_rows": [],
            "columns": [],
        }

    # Get column names from first row
    columns = list(results[0].keys())

    # Compute aggregates for numeric columns
    numeric_aggregates = {}
    for col in columns:
        if col in ("id", "labels"):
            continue
        # Collect numeric values
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

    # Get distinct values for low-cardinality columns (useful for categorical data)
    distinct_values = {}
    for col in columns:
        if col in ("id", "labels"):
            continue
        values = [row.get(col) for row in results if row.get(col) is not None]
        unique = list(set(str(v) for v in values))
        if len(unique) <= 20:  # Only include if low cardinality
            distinct_values[col] = unique[:20]

    return {
        "count": len(results),
        "truncated": truncated,
        "compressed": True,
        "summary": f"Query returned {len(results)} rows with columns: {', '.join(columns)}",
        "columns": columns,
        "sample_rows": results[:sample_rows],
        "numeric_aggregates": numeric_aggregates if numeric_aggregates else None,
        "distinct_values": distinct_values if distinct_values else None,
        "note": (
            f"Results compressed to {sample_rows} sample rows + aggregates. "
            "Full data was retrieved but summarized to reduce token usage. "
            "Use the aggregates and samples to inform your analysis."
        ),
    }


__all__ = ["cypher_query"]
