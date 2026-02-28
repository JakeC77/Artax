"""
Graph Data Formatting Utilities for LLM Context.

This module provides functions to transform raw graph data (nodes and relationships)
into LLM-friendly formats that improve understanding and reasoning about graph structures.

=============================================================================
WHY THIS FORMAT EXISTS: DESIGN RATIONALE
=============================================================================

Problem: Raw Graph Data is Hard for LLMs to Understand
-------------------------------------------------------
Traditional graph data separates nodes and relationships:
    {
        "nodes": [{"id": "m1", "name": "John"}],
        "relationships": [{"from": "m1", "to": "c1", "type": "HAS_CLAIM"}]
    }

This forces LLMs to:
1. Manually look up node IDs to understand connections
2. Mentally reconstruct the graph structure from separate lists
3. Track bidirectional relationships across multiple data structures
4. Miss semantic patterns in relationship types

Solution: Entity-Centric with Embedded Context
-----------------------------------------------
Our format embeds relationships directly in nodes and adds narrative context:
    {
        "overview": {
            "description": "Graph with 50 nodes and 75 relationships",
            "node_counts": {"Member": 25, "Claim": 15},
            "relationship_counts": {"HAS_CLAIM": 40}
        },
        "nodes_by_type": {
            "Member": [{
                "id": "m1",
                "name": "John",
                "_relationships": {
                    "HAS_CLAIM": [{"node_id": "c1", "node_type": "Claim"}]
                },
                "_connections": ["HAS_CLAIM → Claim $1500 medical"]
            }]
        }
    }

Key Benefits:
1. **No ID Lookups**: Relationships embedded directly in nodes
2. **Bidirectional Awareness**: Both outgoing and incoming relationships visible
3. **Human-Readable**: Connection summaries like "HAS_CLAIM → Claim $1500"
4. **Pattern Recognition**: Overview shows relationship type frequencies
5. **Contextual Understanding**: Summary statistics provide graph structure at a glance

=============================================================================
WHERE THIS IS USED
=============================================================================

1. Analysis Workflow (app/workflows/analysis_workflow.py)
   - _build_analysis_plan() - Full workspace graph for planning
   - _execute_analysis() - Filtered graph for analysis execution
   - _plan_scenarios_for_analysis() - Context for scenario planning
   - _execute_scenarios_parallel() - Shared context for parallel scenarios

2. Workspace GraphQL Tools (app/tools/workspace_graphql.py)
   - graph_node_lookup() - Formats individual nodes with flat properties
   - graph_neighbors_lookup() - Enriches neighborhood exploration

3. Future Use Cases:
   - Data recommender sample data formatting
   - Workspace chat contextual data
   - Report generation with graph context
   - Any workflow that feeds graph data to LLMs

=============================================================================
FORMAT SPECIFICATION
=============================================================================

Enriched Graph Format:
{
    "overview": {
        "description": str,              # Human-readable summary
        "node_counts": Dict[str, int],   # Counts by entity type
        "relationship_counts": Dict[str, int],  # Counts by relationship type
        "total_nodes": int,
        "total_relationships": int
    },
    "nodes_by_type": {
        "<EntityType>": [
            {
                "id": str,
                "labels": List[str],
                ...properties...,
                "_relationships": {        # Embedded relationships
                    "<REL_TYPE>": [        # Outgoing
                        {
                            "node_id": str,
                            "node_type": str,
                            "properties": Dict
                        }
                    ],
                    "<REL_TYPE>_FROM": [   # Incoming (note _FROM suffix)
                        {
                            "node_id": str,
                            "node_type": str,
                            "properties": Dict
                        }
                    ]
                },
                "_connections": [          # Human-readable summaries
                    "HAS_CLAIM → Claim $1500",
                    "← BELONGS_TO ← Plan Bronze"
                ]
            }
        ]
    },
    "relationship_patterns": [
        "40x HAS_CLAIM",
        "15x SERVICED_BY"
    ]
}

Special Conventions:
- Fields starting with "_" are enriched metadata (not from raw graph)
- Incoming relationships have "_FROM" suffix (e.g., "HAS_CLAIM_FROM")
- Connection summaries use → for outgoing, ← for incoming
- Overview provides "at a glance" understanding

=============================================================================

Usage:
    # For batch fetched workspace data
    formatted = format_graph_for_llm(nodes_data, relationships)

    # For single node + neighbors (from tools)
    formatted = format_node_with_neighbors(node, neighbors_data)

    # For workspace items + graph data
    formatted = format_workspace_items(items, nodes, edges)
"""

from typing import Dict, List, Any, Optional
import json


def format_graph_for_llm(
    nodes_data: Dict[str, List[Dict[str, Any]]],
    relationships: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Transform raw graph data into LLM-friendly format with narrative context.

    This is the primary formatting function used across the application. It takes
    raw graph data and enriches it with embedded relationships, connection summaries,
    and overview statistics.

    =========================================================================
    ALGORITHM OVERVIEW
    =========================================================================

    This function performs a three-phase transformation:

    Phase 1: Index Building
    -----------------------
    - Build node lookup: node_id -> {type, data} for O(1) access
    - Build relationship indices:
      * outgoing_rels: node_id -> [outgoing relationships]
      * incoming_rels: node_id -> [incoming relationships]

    Phase 2: Node Enrichment
    -------------------------
    For each node:
    1. Gather outgoing relationships and resolve target nodes
    2. Gather incoming relationships and resolve source nodes
    3. Create human-readable connection summaries:
       - "HAS_CLAIM → Claim $1500" for outgoing
       - "← BELONGS_TO ← Member John" for incoming
    4. Embed relationships directly in node as "_relationships"
    5. Embed summaries as "_connections"

    Phase 3: Overview Generation
    -----------------------------
    1. Count nodes by entity type
    2. Count relationships by type
    3. Generate relationship patterns ("40x HAS_CLAIM")
    4. Create human-readable description

    Why This Format?
    ----------------
    - **Embedded Relationships**: LLM doesn't need to look up IDs
    - **Bidirectional**: Both outgoing and incoming relationships visible
    - **Semantic Labels**: Connection summaries use node names/titles
    - **Pattern Recognition**: Overview shows relationship frequencies
    - **Type Safety**: Node types embedded with relationships

    Performance Characteristics:
    ----------------------------
    - Time: O(N + R) where N=nodes, R=relationships
    - Space: O(N + R) for indices + O(N*avg_degree) for embedded relationships
    - Optimized for: Graph sizes up to ~10K nodes with avg degree < 20

    =========================================================================

    Args:
        nodes_data: Dictionary mapping entity types to lists of nodes.
                   Each node should have: id, labels, and property key-value pairs.
                   Format: {"EntityType": [{"id": "...", "labels": [...], "prop": "value"}]}

        relationships: List of relationship dictionaries.
                      Each should have: id, type, from, to, and optional properties.
                      Format: [{"id": "...", "type": "...", "from": "...", "to": "...", "properties": {}}]

    Returns:
        Dict with LLM-friendly structure:
        {
            "overview": {
                "description": "Graph with N nodes... and M relationships",
                "node_counts": {"EntityType": count},
                "relationship_counts": {"REL_TYPE": count},
                "total_nodes": N,
                "total_relationships": M
            },
            "nodes_by_type": {
                "EntityType": [
                    {
                        ...node properties...,
                        "_relationships": {
                            "REL_TYPE": [{"node_id": "...", "node_type": "...", "properties": {}}],
                            "REL_TYPE_FROM": [...]  # incoming relationships
                        },
                        "_connections": [
                            "HAS_CLAIM → Claim claim_001",
                            "← BELONGS_TO ← Member member_123"
                        ]
                    }
                ]
            },
            "relationship_patterns": ["5x HAS_CLAIM", "3x BELONGS_TO"]
        }

    Example:
        >>> nodes = {
        ...     "Member": [{"id": "m1", "name": "John", "labels": ["Member"]}],
        ...     "Claim": [{"id": "c1", "amount": 1500, "labels": ["Claim"]}]
        ... }
        >>> rels = [{"id": "r1", "type": "HAS_CLAIM", "from": "m1", "to": "c1", "properties": {}}]
        >>> formatted = format_graph_for_llm(nodes, rels)
        >>> print(formatted["overview"]["description"])
        Graph with 2 nodes (1 Member, 1 Claim) and 1 relationships
    """
    # Build node lookup for quick access
    node_lookup = {}
    for entity_type, nodes in nodes_data.items():
        for node in nodes:
            node_lookup[node["id"]] = {
                "type": entity_type,
                "data": node
            }

    # Build relationship indices for each node
    outgoing_rels = {}  # node_id -> list of outgoing relationships
    incoming_rels = {}  # node_id -> list of incoming relationships

    for rel in relationships:
        from_id = rel["from"]
        to_id = rel["to"]

        if from_id not in outgoing_rels:
            outgoing_rels[from_id] = []
        outgoing_rels[from_id].append(rel)

        if to_id not in incoming_rels:
            incoming_rels[to_id] = []
        incoming_rels[to_id].append(rel)

    # Build enriched nodes with embedded relationships
    enriched_nodes = {}

    for entity_type, nodes in nodes_data.items():
        enriched_nodes[entity_type] = []

        for node in nodes:
            node_id = node["id"]

            # Build embedded relationships
            embedded_rels = {}
            connection_summaries = []

            # Outgoing relationships
            for rel in outgoing_rels.get(node_id, []):
                rel_type = rel["type"]
                to_id = rel["to"]
                to_node = node_lookup.get(to_id)

                if rel_type not in embedded_rels:
                    embedded_rels[rel_type] = []

                embedded_rels[rel_type].append({
                    "node_id": to_id,
                    "node_type": to_node["type"] if to_node else "Unknown",
                    "properties": rel.get("properties", {})
                })

                # Create human-readable description
                if to_node:
                    to_data = to_node["data"]
                    to_label = to_data.get("name") or to_data.get("title") or to_id
                    connection_summaries.append(
                        f"{rel_type} → {to_node['type']} {to_label}"
                    )

            # Incoming relationships
            for rel in incoming_rels.get(node_id, []):
                rel_type = rel["type"]
                from_id = rel["from"]
                from_node = node_lookup.get(from_id)

                rel_type_incoming = f"{rel_type}_FROM"
                if rel_type_incoming not in embedded_rels:
                    embedded_rels[rel_type_incoming] = []

                embedded_rels[rel_type_incoming].append({
                    "node_id": from_id,
                    "node_type": from_node["type"] if from_node else "Unknown",
                    "properties": rel.get("properties", {})
                })

                # Create human-readable description
                if from_node:
                    from_data = from_node["data"]
                    from_label = from_data.get("name") or from_data.get("title") or from_id
                    connection_summaries.append(
                        f"← {rel_type} ← {from_node['type']} {from_label}"
                    )

            # Create enriched node
            enriched_node = {**node}
            if embedded_rels:
                enriched_node["_relationships"] = embedded_rels
            if connection_summaries:
                enriched_node["_connections"] = connection_summaries

            enriched_nodes[entity_type].append(enriched_node)

    # Build relationship type summary
    rel_type_counts = {}
    for rel in relationships:
        rel_type = rel["type"]
        rel_type_counts[rel_type] = rel_type_counts.get(rel_type, 0) + 1

    # Build relationship patterns (human-readable)
    relationship_patterns = [f"{count}x {rel_type}" for rel_type, count in rel_type_counts.items()]

    # Calculate node counts
    node_counts = {entity_type: len(nodes) for entity_type, nodes in nodes_data.items()}

    # Generate overview description
    total_nodes = sum(node_counts.values())
    total_rels = len(relationships)
    entity_types = ", ".join([f"{count} {etype}" for etype, count in node_counts.items()])

    overview_desc = f"Graph with {total_nodes} nodes ({entity_types}) and {total_rels} relationships"

    return {
        "overview": {
            "description": overview_desc,
            "node_counts": node_counts,
            "relationship_counts": rel_type_counts,
            "total_nodes": total_nodes,
            "total_relationships": total_rels
        },
        "nodes_by_type": enriched_nodes,
        "relationship_patterns": relationship_patterns
    }


def format_graph_compact(
    nodes_data: Dict[str, List[Dict[str, Any]]],
    relationships: List[Dict[str, Any]],
    max_nodes_per_type: Optional[int] = None,
    exclude_fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Compact graph format optimized for reduced token count.

    This format reduces tokens by:
    1. Using abbreviated key names
    2. Removing redundant relationship embeddings (just IDs, not full objects)
    3. Using CSV-like format for homogeneous node lists
    4. Optional field exclusion for large/unnecessary properties

    Args:
        nodes_data: Dictionary mapping entity types to lists of nodes
        relationships: List of relationship dictionaries
        max_nodes_per_type: Optional limit on nodes per type (for sampling)
        exclude_fields: Fields to exclude from nodes (e.g., ["description", "full_text"])

    Returns:
        Compact representation with ~40-60% fewer tokens than format_graph_for_llm
    """
    exclude_fields = exclude_fields or []

    # Build compact nodes - just essential fields
    compact_nodes = {}
    for entity_type, nodes in nodes_data.items():
        # Optionally limit nodes
        nodes_to_process = nodes[:max_nodes_per_type] if max_nodes_per_type else nodes

        compact_list = []
        for node in nodes_to_process:
            # Filter out excluded fields and internal fields
            compact_node = {
                k: v for k, v in node.items()
                if k not in exclude_fields
                and not k.startswith("_")
                and v is not None
                and v != ""
            }
            compact_list.append(compact_node)

        compact_nodes[entity_type] = compact_list

    # Build compact relationships - just type and IDs
    compact_rels = []
    rel_counts = {}
    for rel in relationships:
        rel_type = rel["type"]
        rel_counts[rel_type] = rel_counts.get(rel_type, 0) + 1
        compact_rels.append({
            "t": rel_type,  # type
            "f": rel["from"],  # from
            "o": rel["to"]  # to
        })

    # Summary stats
    node_counts = {t: len(n) for t, n in compact_nodes.items()}
    total_nodes = sum(node_counts.values())

    return {
        "summary": {
            "nodes": total_nodes,
            "rels": len(relationships),
            "types": node_counts,
            "rel_types": rel_counts
        },
        "nodes": compact_nodes,
        "rels": compact_rels
    }


def format_graph_tabular(
    nodes_data: Dict[str, List[Dict[str, Any]]],
    relationships: List[Dict[str, Any]],
    max_nodes_per_type: Optional[int] = None
) -> str:
    """
    Ultra-compact tabular format using CSV-style representation.

    This format achieves maximum token reduction by representing nodes as CSV tables.
    Best for large datasets where structure is more important than formatting.

    Returns:
        String with markdown tables for each node type

    Example output:
        ## Member (25 nodes)
        |id|name|age|status|
        |m1|John|45|active|
        |m2|Jane|52|active|

        ## Relationships (40 total)
        HAS_CLAIM: m1→c1, m1→c2, m2→c3
        BELONGS_TO: c1→p1, c2→p1
    """
    lines = []

    # Nodes as tables
    for entity_type, nodes in nodes_data.items():
        nodes_to_show = nodes[:max_nodes_per_type] if max_nodes_per_type else nodes

        if not nodes_to_show:
            continue

        # Get all unique keys from nodes (excluding internal fields)
        all_keys = set()
        for node in nodes_to_show:
            for k in node.keys():
                if not k.startswith("_") and k != "labels":
                    all_keys.add(k)

        # Sort keys with 'id' first
        keys = ["id"] + sorted([k for k in all_keys if k != "id"])

        lines.append(f"## {entity_type} ({len(nodes)} nodes)")
        lines.append("|" + "|".join(keys) + "|")
        lines.append("|" + "|".join(["---"] * len(keys)) + "|")

        for node in nodes_to_show:
            row = []
            for k in keys:
                val = node.get(k, "")
                # Truncate long values
                str_val = str(val) if val is not None else ""
                if len(str_val) > 50:
                    str_val = str_val[:47] + "..."
                # Escape pipes
                str_val = str_val.replace("|", "\\|")
                row.append(str_val)
            lines.append("|" + "|".join(row) + "|")

        lines.append("")

    # Relationships grouped by type
    if relationships:
        rel_by_type = {}
        for rel in relationships:
            rel_type = rel["type"]
            if rel_type not in rel_by_type:
                rel_by_type[rel_type] = []
            rel_by_type[rel_type].append(f"{rel['from']}→{rel['to']}")

        lines.append(f"## Relationships ({len(relationships)} total)")
        for rel_type, pairs in rel_by_type.items():
            # Show first 10 pairs, then count
            if len(pairs) > 10:
                shown = ", ".join(pairs[:10])
                lines.append(f"**{rel_type}** ({len(pairs)}): {shown}, ...")
            else:
                lines.append(f"**{rel_type}** ({len(pairs)}): {', '.join(pairs)}")

    return "\n".join(lines)


def format_node_with_neighbors(
    node: Dict[str, Any],
    neighbors_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Format a single node with its neighbor information (useful for tool responses).

    This function is designed for the graph_neighbors_lookup tool and similar
    use cases where you have one focal node and its immediate neighborhood.

    Args:
        node: The focal node dict with id, labels, properties.
              Format: {"id": "...", "labels": [...], "property": "value"}

        neighbors_data: Dict with 'nodes' and 'edges' lists from graph_neighbors_lookup.
                       Format: {"nodes": [{id, labels}], "edges": [{id, type, fromId, toId}]}

    Returns:
        Dict with enriched node information:
        {
            "focal_node": {
                ...node properties...,
                "_outgoing": [{"type": "REL_TYPE", "to": {...neighbor node...}}],
                "_incoming": [{"type": "REL_TYPE", "from": {...neighbor node...}}],
                "_connection_summary": "Connected to 3 nodes via 2 relationship types"
            },
            "neighborhood_overview": {
                "total_neighbors": N,
                "relationship_types": ["REL_TYPE1", "REL_TYPE2"]
            }
        }

    Example:
        >>> node = {"id": "m1", "name": "John", "labels": ["Member"]}
        >>> neighbors = {
        ...     "nodes": [{"id": "c1", "labels": ["Claim"]}],
        ...     "edges": [{"id": "e1", "type": "HAS_CLAIM", "fromId": "m1", "toId": "c1"}]
        ... }
        >>> formatted = format_node_with_neighbors(node, neighbors)
        >>> print(formatted["focal_node"]["_outgoing"][0]["type"])
        HAS_CLAIM
    """
    node_id = node["id"]
    neighbor_nodes = neighbors_data.get("nodes", [])
    neighbor_edges = neighbors_data.get("edges", [])

    # Build neighbor lookup
    neighbor_lookup = {n["id"]: n for n in neighbor_nodes}

    # Categorize edges as outgoing or incoming
    outgoing = []
    incoming = []
    rel_types = set()

    for edge in neighbor_edges:
        rel_type = edge["type"]
        rel_types.add(rel_type)

        if edge["fromId"] == node_id:
            # Outgoing relationship
            to_node = neighbor_lookup.get(edge["toId"], {})
            outgoing.append({
                "type": rel_type,
                "edge_id": edge["id"],
                "to": to_node,
                "to_id": edge["toId"]
            })
        elif edge["toId"] == node_id:
            # Incoming relationship
            from_node = neighbor_lookup.get(edge["fromId"], {})
            incoming.append({
                "type": rel_type,
                "edge_id": edge["id"],
                "from": from_node,
                "from_id": edge["fromId"]
            })

    # Build connection summary
    total_connections = len(outgoing) + len(incoming)
    connection_summary = f"Connected to {len(neighbor_nodes)} nodes via {len(rel_types)} relationship types"

    # Enrich focal node
    enriched_node = {**node}
    if outgoing:
        enriched_node["_outgoing"] = outgoing
    if incoming:
        enriched_node["_incoming"] = incoming
    enriched_node["_connection_summary"] = connection_summary

    return {
        "focal_node": enriched_node,
        "neighborhood_overview": {
            "total_neighbors": len(neighbor_nodes),
            "total_connections": total_connections,
            "relationship_types": list(rel_types)
        }
    }


def format_workspace_items(
    items: List[Dict[str, Any]],
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Format workspace items with full graph context.

    This combines workspace item metadata (labels, pinned info) with the actual
    graph node/edge data to provide rich context.

    Args:
        items: List of workspace items from workspaceItems query.
               Format: [{"workspaceItemId": "...", "graphNodeId": "...", "labels": [...]}]

        nodes: List of graph nodes with full properties.
               Format: [{"id": "...", "labels": [...], "properties": [{key, value}]}]

        edges: List of graph edges with full properties.
               Format: [{"id": "...", "type": "...", "fromId": "...", "toId": "...", "properties": [{key, value}]}]

    Returns:
        Dict with workspace context:
        {
            "workspace_summary": "Workspace with N items (X nodes, Y edges)",
            "items": [
                {
                    "workspace_item_id": "...",
                    "labels": [...],
                    "graph_node": {...full node data with properties...},
                    "graph_edge": {...full edge data if applicable...}
                }
            ],
            "graph_overview": {...same as format_graph_for_llm overview...}
        }

    Example:
        >>> items = [{"workspaceItemId": "w1", "graphNodeId": "m1", "labels": ["Important"]}]
        >>> nodes = [{"id": "m1", "labels": ["Member"], "properties": [{"key": "name", "value": "John"}]}]
        >>> edges = []
        >>> formatted = format_workspace_items(items, nodes, edges)
        >>> print(formatted["workspace_summary"])
        Workspace with 1 items (1 nodes, 0 edges)
    """
    # Build lookups
    node_lookup = {n["id"]: n for n in nodes}
    edge_lookup = {e["id"]: e for e in edges}

    # Convert property lists to dicts for nodes and edges
    for node in nodes:
        if "properties" in node and isinstance(node["properties"], list):
            node["properties"] = {p["key"]: p["value"] for p in node["properties"]}

    for edge in edges:
        if "properties" in edge and isinstance(edge["properties"], list):
            edge["properties"] = {p["key"]: p["value"] for p in edge["properties"]}

    # Enrich workspace items with graph data
    enriched_items = []
    node_count = 0
    edge_count = 0

    for item in items:
        enriched_item = {
            "workspace_item_id": item.get("workspaceItemId"),
            "labels": item.get("labels", []),
            "pinned_by": item.get("pinnedBy"),
            "pinned_at": item.get("pinnedAt")
        }

        # Add graph node if present
        if "graphNodeId" in item and item["graphNodeId"]:
            node = node_lookup.get(item["graphNodeId"])
            if node:
                enriched_item["graph_node"] = node
                node_count += 1

        # Add graph edge if present
        if "graphEdgeId" in item and item["graphEdgeId"]:
            edge = edge_lookup.get(item["graphEdgeId"])
            if edge:
                enriched_item["graph_edge"] = edge
                edge_count += 1

        enriched_items.append(enriched_item)

    # Build nodes_data structure for format_graph_for_llm
    nodes_by_type = {}
    for node in nodes:
        labels = node.get("labels", [])
        entity_type = labels[0] if labels else "Unknown"

        if entity_type not in nodes_by_type:
            nodes_by_type[entity_type] = []

        node_dict = {"id": node["id"], "labels": labels, **node.get("properties", {})}
        nodes_by_type[entity_type].append(node_dict)

    # Build relationships structure for format_graph_for_llm
    relationships = []
    for edge in edges:
        relationships.append({
            "id": edge["id"],
            "type": edge["type"],
            "from": edge["fromId"],
            "to": edge["toId"],
            "properties": edge.get("properties", {})
        })

    # Get graph overview from main formatting function
    graph_formatted = format_graph_for_llm(nodes_by_type, relationships)

    return {
        "workspace_summary": f"Workspace with {len(items)} items ({node_count} nodes, {edge_count} edges)",
        "items": enriched_items,
        "graph_overview": graph_formatted["overview"],
        "nodes_by_type": graph_formatted["nodes_by_type"],
        "relationship_patterns": graph_formatted["relationship_patterns"]
    }
