"""GraphQL tools for querying workspace data."""

from __future__ import annotations

import json
import logging
from typing import Any

from typing import Optional
from pydantic_ai import RunContext

from app.core.authenticated_graphql_client import execute_graphql, run_graphql
from app.tools import register_tool
from app.utils.graph_formatting import format_node_with_neighbors

logger = logging.getLogger(__name__)

_WORKSPACE_ITEMS_QUERY = """
query WorkspaceItems($workspaceId: UUID!) {
    workspaceItems(where: { workspaceId: { eq: $workspaceId } }, order: [{ pinnedAt: ASC }]) {
      workspaceItemId
      workspaceId
      graphNodeId
      graphEdgeId
      labels
      pinnedBy
      pinnedAt
    }
}
""".strip()

_GRAPH_NODE_QUERY = """
query graphNodeById($id: String!, $workspaceId: UUID) {
  graphNodeById(id: $id, workspaceId: $workspaceId) {
    id
    labels
    properties {
      key
      value
    }
  }
}
""".strip()


_GRAPH_EDGE_QUERY = """
query graphEdgeById($id: String!, $workspaceId: UUID) {
  graphEdgeById(id: $id, workspaceId: $workspaceId) {
    id
    fromId
    toId
    type
    properties {
      key
      value
    }
  }
}
""".strip()

_GRAPH_NEIGHBORS_QUERY = """
query graphNeighbors($id: String!, $workspaceId: UUID) {
  graphNeighbors(id: $id, workspaceId: $workspaceId) {
    edges {
      fromId
      id
      toId
      type
    }
    nodes {
      id
      labels
    }
  }
}
""".strip()

_SCRATCHPAD_NOTES_QUERY = """
query ScratchpadNotes($workspaceId: UUID!) {
  scratchpadNotes(where: { workspaceId: { eq: $workspaceId }}) {
    scratchpadNoteId
    workspaceId
    title
    text
    createdOn
  }
}
""".strip()


def _execute_graphql(query: str, variables: dict[str, Any], tenant_id: Optional[str] = None) -> dict[str, Any]:
    """Execute a GraphQL query with authentication support."""
    return execute_graphql(query, variables, graphql_endpoint=None, tenant_id=tenant_id)


async def _run_graphql(query: str, variables: dict[str, Any], tenant_id: Optional[str] = None) -> dict[str, Any]:
    """Run the blocking GraphQL call in a background thread."""
    return await run_graphql(query, variables, graphql_endpoint=None, tenant_id=tenant_id)


@register_tool("workspace_items_lookup")
async def workspace_items_lookup(ctx: RunContext[dict], workspace_id: str | None = None) -> dict[str, Any]:
    """Get the list of pinned items in a workspace (starting point for exploring workspace data).
    
    Use this tool FIRST when you need to find data in the workspace. This returns a list
    of workspace items with their graph node IDs and edge IDs, which you can then use
    with graph_node_lookup or graph_edge_lookup to get detailed information.
    
    Workflow:
    1. Call workspace_items_lookup to get list of items
    2. Extract graphNodeId or graphEdgeId from items
    3. Use graph_node_lookup(node_id) or graph_edge_lookup(edge_id) for details
    4. Use graph_neighbors_lookup(node_id) to explore connections
    
    When to use:
    - Finding what data exists in the workspace
    - Getting node/edge IDs to look up details
    - Exploring workspace structure
    
    When NOT to use:
    - For external web data (use web_search instead)
    - For past research/memory (use memory_retrieve instead)
    - For scratchpad notes (use scratchpad_notes_list instead)
    
    Args:
        workspace_id: Workspace UUID. If not provided, will use workspace_id from context.
    
    Returns:
        Dict with workspace_id and list of items, each containing:
        - workspaceItemId, graphNodeId, graphEdgeId, labels, etc.
    
    Note: The workspace_id from the workflow context (from Service Bus message) will be used
          if not explicitly provided as a parameter.
    """
    tool_name = "workspace_items_lookup"
    logger.info(f"Tool called: {tool_name}")
    
    # If workspace_id not provided, try to get it from context
    if not workspace_id:
        workspace_id = ctx.deps.get("workspace_id")
        if workspace_id:
            logger.debug(f"Using workspace_id from context: {workspace_id}")
        else:
            available_keys = list(ctx.deps.keys()) if ctx.deps else []
            logger.error(f"Tool '{tool_name}' failed: workspace_id not found in context. Available keys: {available_keys}")
            raise ValueError(
                f"workspace_id is required. Either pass it as a parameter or ensure it's in the workflow context. "
                f"Available context keys: {available_keys}"
            )
    
    tenant_id = ctx.deps.get("tenant_id")
    logger.info(f"Tool '{tool_name}' executing with workspace_id={workspace_id}, tenant_id={'present' if tenant_id else 'missing'}")
    
    try:
        logger.debug(f"Fetching workspace items for workspace_id: {workspace_id}")
        data = await _run_graphql(_WORKSPACE_ITEMS_QUERY, {"workspaceId": workspace_id}, tenant_id=tenant_id)
        logger.info(f"Tool '{tool_name}' succeeded: found {len(data.get('workspaceItems', []))} items")
        return {
            "workspace_id": workspace_id,
            "items": data.get("workspaceItems", []),
        }
    except Exception as e:
        logger.error(f"Tool '{tool_name}' failed with error: {type(e).__name__}: {str(e)}")
        raise


@register_tool("graph_node_lookup")
async def graph_node_lookup(ctx: RunContext[dict], node_id: str) -> dict[str, Any]:
    """Get detailed information about a specific graph node by its ID.

    Use this tool AFTER you have a node ID (from workspace_items_lookup or
    graph_neighbors_lookup) to see the node's full properties, labels, and metadata.

    The returned node will have properties formatted as a flat dictionary for easy access.

    Workflow:
    1. Get node IDs from workspace_items_lookup or graph_neighbors_lookup
    2. Call graph_node_lookup(node_id) to get full node details
    3. Use graph_neighbors_lookup(node_id) to explore connected nodes

    When to use:
    - You have a node ID and need to see its properties
    - Exploring details of a specific workspace entity
    - Getting labels and metadata for a node

    When NOT to use:
    - To find nodes (use workspace_items_lookup first)
    - To explore connections (use graph_neighbors_lookup instead)
    - For external data (use web_search instead)

    Args:
        node_id: The graph node ID (string). Get this from workspace_items_lookup
                 or graph_neighbors_lookup first.

    Returns:
        Dict with node details:
        {
            "id": "node_id",
            "labels": ["Label1", "Label2"],
            "property1": "value1",
            "property2": "value2",
            ...
        }
    """
    tool_name = "graph_node_lookup"
    logger.info(f"Tool called: {tool_name} with node_id={node_id}")
    tenant_id = ctx.deps.get("tenant_id")
    workspace_id = ctx.deps.get("workspace_id")

    variables = {"id": node_id}
    if workspace_id:
        variables["workspaceId"] = workspace_id

    try:
        data = await _run_graphql(_GRAPH_NODE_QUERY, variables, tenant_id=tenant_id)
        node = data.get("graphNodeById")

        if not node:
            logger.info(f"Tool '{tool_name}' succeeded but node not found")
            return {}

        # Format properties as flat dict for LLM friendliness
        properties = {prop["key"]: prop["value"] for prop in node.get("properties", [])}

        formatted_node = {
            "id": node["id"],
            "labels": node.get("labels", []),
            **properties
        }

        logger.info(f"Tool '{tool_name}' succeeded")
        return formatted_node
    except Exception as e:
        logger.error(f"Tool '{tool_name}' failed with error: {type(e).__name__}: {str(e)}")
        raise


@register_tool("graph_edge_lookup")
async def graph_edge_lookup(ctx: RunContext[dict], edge_id: str) -> dict[str, Any]:
    """Get detailed information about a specific graph edge (relationship) by its ID.
    
    Use this tool to see the properties and type of a relationship between two nodes
    in the workspace graph. Get edge IDs from workspace_items_lookup or 
    graph_neighbors_lookup first.
    
    Workflow:
    1. Get edge IDs from workspace_items_lookup or graph_neighbors_lookup
    2. Call graph_edge_lookup(edge_id) to see relationship details
    3. Use fromId and toId to identify connected nodes
    
    When to use:
    - You have an edge ID and need to see relationship properties
    - Understanding how two nodes are connected
    - Getting relationship type and metadata
    
    When NOT to use:
    - To find edges (use workspace_items_lookup or graph_neighbors_lookup first)
    - For node information (use graph_node_lookup instead)
    - To explore all connections (use graph_neighbors_lookup instead)
    
    Args:
        edge_id: The graph edge ID (string). Get this from workspace_items_lookup
                 or graph_neighbors_lookup first.
    
    Returns:
        Dict with edge details: id, fromId, toId, type, properties (key-value pairs)
    """
    tool_name = "graph_edge_lookup"
    logger.info(f"Tool called: {tool_name} with edge_id={edge_id}")
    tenant_id = ctx.deps.get("tenant_id")
    workspace_id = ctx.deps.get("workspace_id")
    
    variables = {"id": edge_id}
    if workspace_id:
        variables["workspaceId"] = workspace_id
    
    try:
        data = await _run_graphql(_GRAPH_EDGE_QUERY, variables, tenant_id=tenant_id)
        logger.info(f"Tool '{tool_name}' succeeded")
        return data.get("graphEdgeById") or {}
    except Exception as e:
        logger.error(f"Tool '{tool_name}' failed with error: {type(e).__name__}: {str(e)}")
        raise


@register_tool("graph_neighbors_lookup")
async def graph_neighbors_lookup(ctx: RunContext[dict], node_id: str) -> dict[str, Any]:
    """Explore all nodes and edges connected to a specific node (graph traversal).

    Use this tool to discover what's connected to a node - both the connected nodes
    and the edges (relationships) that link them. The response is formatted to show
    clear relationship patterns with human-readable summaries.

    Workflow:
    1. Get a node ID from workspace_items_lookup or graph_node_lookup
    2. Call graph_neighbors_lookup(node_id) to see all connections
    3. Explore returned outgoing/incoming connections with node details

    When to use:
    - Exploring relationships and connections in the workspace
    - Finding related nodes to a known entity
    - Discovering the structure of workspace data
    - Graph traversal and relationship analysis

    When NOT to use:
    - To get details of a single node (use graph_node_lookup instead)
    - To get details of a single edge (use graph_edge_lookup instead)
    - For initial workspace exploration (use workspace_items_lookup first)

    Args:
        node_id: The graph node ID (string). Get this from workspace_items_lookup
                 or graph_node_lookup first.

    Returns:
        Dict with enriched neighborhood information:
        {
            "focal_node": {
                "id": "...",
                "_outgoing": [{"type": "REL_TYPE", "to": {...neighbor node...}}],
                "_incoming": [{"type": "REL_TYPE", "from": {...neighbor node...}}],
                "_connection_summary": "Connected to N nodes via M relationship types"
            },
            "neighborhood_overview": {
                "total_neighbors": N,
                "total_connections": M,
                "relationship_types": ["TYPE1", "TYPE2"]
            }
        }
    """
    tool_name = "graph_neighbors_lookup"
    logger.info(f"Tool called: {tool_name} with node_id={node_id}")
    tenant_id = ctx.deps.get("tenant_id")
    workspace_id = ctx.deps.get("workspace_id")

    variables = {"id": node_id}
    if workspace_id:
        variables["workspaceId"] = workspace_id

    try:
        # Get neighbors data
        neighbors_data = await _run_graphql(_GRAPH_NEIGHBORS_QUERY, variables, tenant_id=tenant_id)
        neighbors = neighbors_data.get("graphNeighbors", {})

        # Get focal node data
        node_data = await _run_graphql(_GRAPH_NODE_QUERY, {"id": node_id}, tenant_id=tenant_id)
        focal_node = node_data.get("graphNodeById")

        if not focal_node:
            logger.warning(f"Tool '{tool_name}' succeeded but focal node not found")
            return {"error": "Node not found"}

        # Format properties as flat dict
        properties = {prop["key"]: prop["value"] for prop in focal_node.get("properties", [])}
        formatted_focal_node = {
            "id": focal_node["id"],
            "labels": focal_node.get("labels", []),
            **properties
        }

        # Use formatting utility for rich context
        formatted = format_node_with_neighbors(formatted_focal_node, neighbors)

        logger.info(f"Tool '{tool_name}' succeeded with {formatted['neighborhood_overview']['total_neighbors']} neighbors")
        return formatted
    except Exception as e:
        logger.error(f"Tool '{tool_name}' failed with error: {type(e).__name__}: {str(e)}")
        raise


@register_tool("scratchpad_notes_list")
async def scratchpad_notes_list(ctx: RunContext[dict], workspace_id: str | None = None) -> dict[str, Any]:
    """Fetch scratchpad notes for a given workspace UUID.
    
    Scratchpad notes are simple text notes attached to the workspace. Use this to
    find relevant notes, context, or information that users have saved.
    
    Args:
        workspace_id: Workspace UUID. If not provided, will use workspace_id from context.
    
    Returns:
        Dict with workspace_id and list of notes:
        {
            "workspace_id": "...",
            "notes": [
                {
                    "scratchpadNoteId": "...",
                    "title": "...",
                    "text": "...",
                    "createdOn": "...",
                    ...
                },
                ...
            ],
            "count": 2
        }
    
    Note: The workspace_id from the workflow context (from Service Bus message) will be used
          if not explicitly provided as a parameter.
    """
    tool_name = "scratchpad_notes_list"
    logger.info(f"Tool called: {tool_name}")
    
    # If workspace_id not provided, try to get it from context
    if not workspace_id:
        workspace_id = ctx.deps.get("workspace_id")
        if workspace_id:
            logger.debug(f"Using workspace_id from context: {workspace_id}")
        else:
            available_keys = list(ctx.deps.keys()) if ctx.deps else []
            logger.error(f"Tool '{tool_name}' failed: workspace_id not found in context. Available keys: {available_keys}")
            raise ValueError(
                f"workspace_id is required. Either pass it as a parameter or ensure it's in the workflow context. "
                f"Available context keys: {available_keys}"
            )
    
    tenant_id = ctx.deps.get("tenant_id")
    logger.info(f"Tool '{tool_name}' executing with workspace_id={workspace_id}, tenant_id={'present' if tenant_id else 'missing'}")
    
    try:
        logger.debug(f"Fetching scratchpad notes for workspace_id: {workspace_id}")
        data = await _run_graphql(_SCRATCHPAD_NOTES_QUERY, {"workspaceId": workspace_id}, tenant_id=tenant_id)
        notes = data.get("scratchpadNotes", [])
        logger.info(f"Tool '{tool_name}' succeeded: found {len(notes)} notes")
        
        return {
            "workspace_id": workspace_id,
            "notes": notes,
            "count": len(notes),
        }
    except Exception as e:
        logger.error(f"Tool '{tool_name}' failed with error: {type(e).__name__}: {str(e)}")
        raise

