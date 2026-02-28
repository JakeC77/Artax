from app.tools import register_tool
from pydantic_ai import RunContext
from typing import List, Dict, Any, Optional
import logging

from app.core.authenticated_graphql_client import run_graphql

logger = logging.getLogger(__name__)

@register_tool("workspace_data_fetch")
async def workspace_data_fetch(
    ctx: RunContext[dict],
    entity_types: List[str],
    filters: Optional[Dict[str, Dict[str, Any]]] = None,
    include_attributes: Optional[Dict[str, List[str]]] = None,
    limit_per_type: int = 1000
) -> Dict[str, Any]:
    """
    Fetch and filter workspace data by entity type for analysis.

    This tool queries workspace items and their associated graph nodes,
    applying optional property filters and attribute selection.

    Args:
        entity_types: List of entity types to fetch (e.g., ["Member", "Claim", "Drug"])
        filters: Optional filters per entity type {"Member": {"status": "active"}}
        include_attributes: Optional attribute selection per type {"Member": ["member_id", "age"]}
        limit_per_type: Maximum nodes per entity type (default 1000)

    Returns:
        {
            "entities": {
                "Member": [{"id": "...", "properties": {...}}, ...],
                "Claim": [...]
            },
            "counts": {"Member": 150, "Claim": 2340},
            "workspace_id": "..."
        }

    When to use:
        - Fetching workspace data for analysis
        - Getting filtered subsets of entities
        - Preparing data for aggregation

    When NOT to use:
        - Single node lookup (use graph_node_lookup)
        - Exploring relationships (use graph_neighbors_lookup)
    """
    workspace_id = ctx.deps.get("workspace_id")
    tenant_id = ctx.deps.get("tenant_id")

    if not workspace_id:
        return {"error": "workspace_id not found in context", "entities": {}, "counts": {}}

    filters = filters or {}
    include_attributes = include_attributes or {}

    results = {}
    counts = {}

    for entity_type in entity_types:
        try:
            # Get all nodes of this type
            nodes = await _fetch_nodes_by_type(entity_type, tenant_id, workspace_id)

            # Apply filters if specified
            entity_filters = filters.get(entity_type, {})
            if entity_filters:
                nodes = _apply_property_filters(nodes, entity_filters)

            # Select attributes if specified
            attrs = include_attributes.get(entity_type)
            if attrs:
                nodes = _select_attributes(nodes, attrs)

            # Apply limit
            nodes = nodes[:limit_per_type]

            results[entity_type] = nodes
            counts[entity_type] = len(nodes)

            logger.info(f"Fetched {len(nodes)} {entity_type} nodes for workspace {workspace_id}")

        except Exception as e:
            logger.error(f"Error fetching {entity_type}: {e}")
            results[entity_type] = []
            counts[entity_type] = 0

    return {
        "entities": results,
        "counts": counts,
        "workspace_id": workspace_id,
        "filters_applied": filters,
        "total_nodes": sum(counts.values())
    }


async def _fetch_nodes_by_type(entity_type: str, tenant_id: str, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch all nodes of a given type."""
    query = """
    query NodesByType($type: String!, $workspaceId: UUID) {
        graphNodesByType(type: $type, workspaceId: $workspaceId) {
            id
            labels
            properties { key value }
        }
    }
    """
    variables = {"type": entity_type}
    if workspace_id:
        variables["workspaceId"] = workspace_id
    data = await run_graphql(query, variables, tenant_id=tenant_id)

    nodes = []
    for node in data.get("graphNodesByType", []):
        props = {p["key"]: p["value"] for p in node.get("properties", [])}
        nodes.append({
            "id": node["id"],
            "labels": node.get("labels", []),
            "properties": props
        })
    return nodes


def _apply_property_filters(nodes: List[Dict], filters: Dict[str, Any]) -> List[Dict]:
    """Apply property filters to nodes."""
    filtered = []
    for node in nodes:
        props = node.get("properties", {})
        match = True
        for key, value in filters.items():
            node_value = props.get(key)
            if isinstance(value, dict):
                # Operator-based filter
                for op, op_value in value.items():
                    if op == "gte" and (node_value is None or float(node_value) < float(op_value)):
                        match = False
                    elif op == "lte" and (node_value is None or float(node_value) > float(op_value)):
                        match = False
                    elif op == "in" and node_value not in op_value:
                        match = False
                    elif op == "contains" and (node_value is None or str(op_value) not in str(node_value)):
                        match = False
            else:
                # Exact match
                if node_value != value:
                    match = False
            if not match:
                break
        if match:
            filtered.append(node)
    return filtered


def _select_attributes(nodes: List[Dict], attrs: List[str]) -> List[Dict]:
    """Select only specified attributes from nodes."""
    selected = []
    for node in nodes:
        props = node.get("properties", {})
        selected.append({
            "id": node["id"],
            "labels": node.get("labels", []),
            "properties": {k: v for k, v in props.items() if k in attrs}
        })
    return selected
