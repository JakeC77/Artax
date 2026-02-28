"""
Context Package Builder for Analysis Workflow.

This module provides compact workspace context for LLM prompts, replacing the
"data stuffing" approach with a "schema + tools" architecture.

The context package includes:
- Semantic schema (entity types, properties, data types)
- Field ranges (min/max for numeric/date fields from semanticFields API)
- Entity counts (workspace-specific node counts by type)
- Relationship patterns (from->to entity mappings)
- Cypher query examples (guidance for agents)

Target: ~5-10K tokens (vs 50K-200K for full data serialization)
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from app.core.authenticated_graphql_client import run_graphql

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class FieldRange:
    """Min/max range for a numeric or date field."""
    field_name: str
    data_type: str
    min_value: Optional[str] = None
    max_value: Optional[str] = None


@dataclass
class PropertySchema:
    """Schema for a single property on an entity."""
    name: str
    data_type: str
    description: Optional[str] = None
    range_info: Optional[FieldRange] = None


@dataclass
class EntitySchema:
    """Schema for a single entity type in the workspace."""
    entity_type: str
    properties: List[PropertySchema] = field(default_factory=list)
    relationship_types: List[str] = field(default_factory=list)
    node_count: int = 0  # Workspace-specific count


@dataclass
class RelationshipSchema:
    """Relationship type definition with direction."""
    name: str
    from_entity: str
    to_entity: str = "Unknown"  # GraphQL doesn't always tell us the target


@dataclass
class WorkspaceContextPackage:
    """
    Compact workspace context for LLM prompts.

    This replaces passing full workspace data to agents. Instead, agents
    receive schema understanding and use the cypher_query tool for data access.
    """
    workspace_id: str

    # Schema information
    entity_schemas: List[EntitySchema] = field(default_factory=list)
    relationship_schemas: List[RelationshipSchema] = field(default_factory=list)

    # Statistics
    entity_counts: Dict[str, int] = field(default_factory=dict)
    total_nodes: int = 0
    total_relationships: int = 0

    # For tool layer (not serialized to prompt)
    workspace_node_ids: Dict[str, List[str]] = field(default_factory=dict)

    # Whether nodes have actual labels in Neo4j (vs inferred from ID prefix)
    labels_exist_in_graph: bool = True

    def to_prompt_string(self) -> str:
        """
        Serialize context package to markdown for prompt injection.

        Returns formatted markdown with:
        - Entity schema tables
        - Field ranges for numeric/date fields
        - Relationship patterns
        - Workspace statistics
        """
        lines = []

        # Header
        lines.append("## Workspace Schema")
        lines.append("")

        # Entity counts summary
        lines.append("### Entity Counts")
        lines.append("")
        lines.append("| Entity Type | Count |")
        lines.append("|-------------|-------|")
        for entity_type, count in sorted(self.entity_counts.items()):
            lines.append(f"| {entity_type} | {count:,} |")
        lines.append(f"| **Total** | **{self.total_nodes:,}** |")
        lines.append("")

        # Entity schemas with properties
        lines.append("### Entity Schemas")
        lines.append("")

        for entity in sorted(self.entity_schemas, key=lambda e: e.entity_type):
            lines.append(f"#### {entity.entity_type}")
            lines.append("")

            if entity.properties:
                lines.append("| Property | Type | Range |")
                lines.append("|----------|------|-------|")
                for prop in sorted(entity.properties, key=lambda p: p.name):
                    range_str = ""
                    if prop.range_info and (prop.range_info.min_value or prop.range_info.max_value):
                        range_str = f"{prop.range_info.min_value or '?'} - {prop.range_info.max_value or '?'}"
                    lines.append(f"| {prop.name} | {prop.data_type} | {range_str} |")
                lines.append("")

            if entity.relationship_types:
                lines.append(f"**Relationships**: {', '.join(entity.relationship_types)}")
                lines.append("")

        # Relationship patterns
        if self.relationship_schemas:
            lines.append("### Relationship Patterns")
            lines.append("")
            lines.append("| Relationship | From | To |")
            lines.append("|--------------|------|-----|")
            for rel in sorted(self.relationship_schemas, key=lambda r: r.name):
                lines.append(f"| {rel.name} | {rel.from_entity} | {rel.to_entity} |")
            lines.append("")

        return "\n".join(lines)


# =============================================================================
# GraphQL Queries
# =============================================================================

# Get all node type names
NODE_TYPES_QUERY = """
query GraphNodeTypes($workspaceId: UUID!) {
  graphNodeTypes(workspaceId: $workspaceId)
}
""".strip()

# Get property metadata for a specific node type
NODE_PROPERTY_METADATA_QUERY = """
query NodePropertyMetadata($type: String!, $workspaceId: UUID!) {
  graphNodePropertyMetadata(type: $type, workspaceId: $workspaceId) {
    name
    dataType
  }
}
""".strip()

# Get relationship types for a specific node type
NODE_RELATIONSHIP_TYPES_QUERY = """
query NodeRelationshipTypes($type: String!, $workspaceId: UUID!) {
  graphNodeRelationshipTypes(type: $type, workspaceId: $workspaceId)
}
""".strip()

# Get semantic fields with range info (min/max for numeric/date fields)
SEMANTIC_FIELDS_QUERY = """
query {
  semanticFields {
    semanticFieldId
    semanticEntityId
    name
    dataType
    description
    rangeInfo
  }
}
""".strip()

# Get semantic entities (for mapping semanticEntityId to entity names)
SEMANTIC_ENTITIES_QUERY = """
query SemanticEntitiesForWorkspace($workspaceId: UUID!) {
  semanticEntities(workspaceId: $workspaceId) {
    semanticEntityId
    tenantId
    nodeLabel
    version
    description
    name
    createdOn
    fields {
      semanticFieldId
      name
      dataType
    }
  }
}
""".strip()

# Get workspace items to identify nodes in scope
WORKSPACE_ITEMS_QUERY = """
query GetWorkspaceItems($workspaceId: UUID!) {
    workspaceItems(
        where: {
            workspaceId: { eq: $workspaceId }
        }
    ) {
        workspaceItemId
        graphNodeId
        labels
    }
}
""".strip()


# =============================================================================
# Context Building Functions
# =============================================================================

async def build_context_package(
    workspace_id: str,
    tenant_id: str,
    timeout_seconds: int = 60
) -> WorkspaceContextPackage:
    """
    Build compact context package for workspace.

    This fetches schema information and workspace statistics without
    retrieving all node data. The resulting context is ~5-10K tokens
    regardless of workspace size.

    Args:
        workspace_id: UUID of the workspace
        tenant_id: Tenant ID for authentication
        timeout_seconds: Timeout for GraphQL queries

    Returns:
        WorkspaceContextPackage with schema, ranges, and statistics
    """
    logger.info(f"Building context package for workspace {workspace_id[:8]}...")

    # Step 1: Fetch workspace items to get node IDs and labels
    workspace_node_ids, entity_counts, labels_exist = await _fetch_workspace_items(
        workspace_id, tenant_id, timeout_seconds
    )

    total_nodes = sum(entity_counts.values())
    logger.info(f"Workspace has {total_nodes} nodes across {len(entity_counts)} entity types")

    # Step 2: Fetch schema (node types, properties, relationships)
    entity_schemas, relationship_schemas = await _fetch_schema(
        entity_types=list(entity_counts.keys()),
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        timeout_seconds=timeout_seconds
    )

    # Step 3: Fetch semantic fields with range info
    field_ranges = await _fetch_semantic_field_ranges(workspace_id, tenant_id, timeout_seconds)

    # Step 4: Enrich entity schemas with counts and ranges
    for entity in entity_schemas:
        entity.node_count = entity_counts.get(entity.entity_type, 0)

        # Add range info to properties
        for prop in entity.properties:
            range_key = f"{entity.entity_type}.{prop.name}"
            if range_key in field_ranges:
                prop.range_info = field_ranges[range_key]

    # Step 5: Estimate relationship count (approximate)
    total_relationships = len(relationship_schemas) * (total_nodes // max(len(entity_counts), 1))

    logger.info(
        f"Context package built: {len(entity_schemas)} entities, "
        f"{sum(len(e.properties) for e in entity_schemas)} properties, "
        f"{len(relationship_schemas)} relationship types"
    )

    return WorkspaceContextPackage(
        workspace_id=workspace_id,
        entity_schemas=entity_schemas,
        relationship_schemas=relationship_schemas,
        entity_counts=entity_counts,
        total_nodes=total_nodes,
        total_relationships=total_relationships,
        workspace_node_ids=workspace_node_ids,
        labels_exist_in_graph=labels_exist,
    )


async def _fetch_workspace_items(
    workspace_id: str,
    tenant_id: str,
    timeout_seconds: int
) -> tuple[Dict[str, List[str]], Dict[str, int], bool]:
    """
    Fetch workspace items and compute entity counts.

    Returns:
        Tuple of (workspace_node_ids by type, entity_counts, labels_exist)
    """
    try:
        result = await run_graphql(
            WORKSPACE_ITEMS_QUERY,
            {"workspaceId": workspace_id},
            tenant_id=tenant_id,
            timeout=timeout_seconds
        )
    except Exception as e:
        logger.error(f"Failed to fetch workspace items: {e}")
        return {}, {}, False

    items = result.get("workspaceItems", [])

    # Group node IDs by entity type (first label)
    workspace_node_ids: Dict[str, List[str]] = {}
    entity_counts: Dict[str, int] = {}

    labels_found = False  # Track if any nodes have actual labels

    for item in items:
        node_id = item.get("graphNodeId")
        if not node_id:
            continue

        labels = item.get("labels", [])
        if labels:
            entity_type = labels[0]
            labels_found = True
        else:
            # Infer entity type from node ID prefix (e.g., "prescription_123" -> "Prescription")
            entity_type = _infer_entity_type_from_id(node_id)

        if entity_type not in workspace_node_ids:
            workspace_node_ids[entity_type] = []
            entity_counts[entity_type] = 0

        workspace_node_ids[entity_type].append(node_id)
        entity_counts[entity_type] += 1

    return workspace_node_ids, entity_counts, labels_found


def _infer_entity_type_from_id(node_id: str) -> str:
    """
    Infer entity type from node ID prefix.

    Many graph databases use ID patterns like "prescription_123" or "medication_456".
    This function extracts and capitalizes the prefix to use as the entity type.

    Args:
        node_id: The graph node ID (e.g., "prescription_2152")

    Returns:
        Inferred entity type (e.g., "Prescription") or "Unknown" if no prefix found
    """
    if "_" in node_id:
        prefix = node_id.rsplit("_", 1)[0]
        # Handle multi-part prefixes like "state-compliance_46"
        # Capitalize each part: "state-compliance" -> "StateCompliance"
        parts = prefix.replace("-", " ").replace("_", " ").split()
        return "".join(part.capitalize() for part in parts)
    return "Unknown"


async def _fetch_schema(
    entity_types: List[str],
    workspace_id: str,
    tenant_id: str,
    timeout_seconds: int
) -> tuple[List[EntitySchema], List[RelationshipSchema]]:
    """
    Fetch schema for specified entity types.

    Returns:
        Tuple of (entity_schemas, relationship_schemas)
    """
    entity_schemas: List[EntitySchema] = []
    all_relationships: Dict[str, RelationshipSchema] = {}

    for entity_type in entity_types:
        # Fetch properties
        properties: List[PropertySchema] = []
        try:
            props_result = await run_graphql(
                NODE_PROPERTY_METADATA_QUERY,
                {"type": entity_type, "workspaceId": workspace_id},
                tenant_id=tenant_id,
                timeout=timeout_seconds
            )
            for prop in props_result.get("graphNodePropertyMetadata", []):
                properties.append(PropertySchema(
                    name=prop["name"],
                    data_type=prop.get("dataType", "string"),
                ))
        except Exception as e:
            logger.warning(f"Could not fetch properties for {entity_type}: {e}")

        # Fetch relationship types
        relationship_types: List[str] = []
        try:
            rels_result = await run_graphql(
                NODE_RELATIONSHIP_TYPES_QUERY,
                {"type": entity_type, "workspaceId": workspace_id},
                tenant_id=tenant_id,
                timeout=timeout_seconds
            )
            relationship_types = rels_result.get("graphNodeRelationshipTypes", [])

            # Track unique relationships
            for rel_type in relationship_types:
                key = f"{entity_type}:{rel_type}"
                if key not in all_relationships:
                    all_relationships[key] = RelationshipSchema(
                        name=rel_type,
                        from_entity=entity_type,
                        to_entity="Unknown"
                    )
        except Exception as e:
            logger.warning(f"Could not fetch relationships for {entity_type}: {e}")

        entity_schemas.append(EntitySchema(
            entity_type=entity_type,
            properties=properties,
            relationship_types=relationship_types,
        ))

    return entity_schemas, list(all_relationships.values())


async def _fetch_semantic_field_ranges(
    workspace_id: str,
    tenant_id: str,
    timeout_seconds: int
) -> Dict[str, FieldRange]:
    """
    Fetch field ranges from semanticFields API.

    Args:
        workspace_id: Workspace UUID for filtering semantic entities
        tenant_id: Tenant ID for authentication
        timeout_seconds: Timeout for GraphQL queries

    Returns:
        Dict mapping "EntityType.fieldName" to FieldRange
    """
    field_ranges: Dict[str, FieldRange] = {}

    try:
        # Fetch semantic entities first (to map IDs to names)
        entities_result = await run_graphql(
            SEMANTIC_ENTITIES_QUERY,
            {"workspaceId": workspace_id},
            tenant_id=tenant_id,
            timeout=timeout_seconds
        )
        entity_id_to_name: Dict[str, str] = {}
        for entity in entities_result.get("semanticEntities", []):
            entity_id_to_name[entity["semanticEntityId"]] = entity["name"]

        # Fetch semantic fields with range info
        fields_result = await run_graphql(
            SEMANTIC_FIELDS_QUERY,
            {},
            tenant_id=tenant_id,
            timeout=timeout_seconds
        )

        for field_data in fields_result.get("semanticFields", []):
            entity_id = field_data.get("semanticEntityId")
            entity_name = entity_id_to_name.get(entity_id, "Unknown")
            field_name = field_data.get("name")
            data_type = field_data.get("dataType", "string")
            range_info_str = field_data.get("rangeInfo")

            if not field_name:
                continue

            # Parse range info JSON
            min_val = None
            max_val = None
            if range_info_str:
                try:
                    range_info = json.loads(range_info_str)
                    min_val = range_info.get("min")
                    max_val = range_info.get("max")
                except json.JSONDecodeError:
                    pass

            key = f"{entity_name}.{field_name}"
            field_ranges[key] = FieldRange(
                field_name=field_name,
                data_type=data_type,
                min_value=min_val,
                max_value=max_val,
            )

    except Exception as e:
        logger.warning(f"Could not fetch semantic field ranges: {e}")

    return field_ranges


def build_cypher_guide(context: WorkspaceContextPackage, labels_exist: bool = False) -> str:
    """
    Build Cypher query guide based on workspace schema.

    This provides agents with example queries tailored to the actual
    entity types and relationships in the workspace.

    Args:
        context: The workspace context package
        labels_exist: If True, nodes have actual labels in Neo4j.
                      If False, nodes are identified by ID prefix patterns (e.g., "prescription_123").
    """
    lines = []

    lines.append("## Cypher Query Guide")
    lines.append("")
    lines.append("You have access to the `cypher_query` tool to fetch data on-demand.")
    lines.append("Queries are automatically scoped to this workspace.")
    lines.append("")

    # List available entity types
    entity_types = [e.entity_type for e in context.entity_schemas if e.node_count > 0]

    if not labels_exist:
        # CRITICAL: Explain that labels don't exist, must query by ID pattern
        lines.append("### IMPORTANT: Query by ID Pattern")
        lines.append("")
        lines.append("**Nodes in this workspace do NOT have labels in the graph database.**")
        lines.append("Entity types are identified by the `id` property prefix pattern:")
        lines.append("")
        for et in sorted(entity_types):
            count = context.entity_counts.get(et, 0)
            # Convert CamelCase back to the ID prefix pattern
            prefix = _entity_type_to_id_prefix(et)
            lines.append(f"- **{et}** ({count:,} nodes) - id starts with `{prefix}_`")
        lines.append("")
        lines.append("**You MUST query using `WHERE n.id STARTS WITH 'prefix_'` instead of labels.**")
        lines.append("")

    if entity_types:
        lines.append("### Available Entity Types")
        lines.append("")
        for et in sorted(entity_types):
            count = context.entity_counts.get(et, 0)
            lines.append(f"- **{et}** ({count:,} nodes)")
        lines.append("")

    # Example queries based on actual schema
    # ALL examples must use RETURN n (full nodes) since the API only returns node objects
    lines.append("### Example Queries")
    lines.append("")
    lines.append("```cypher")

    if entity_types:
        first_type = entity_types[0]
        first_prefix = _entity_type_to_id_prefix(first_type)

        if labels_exist:
            lines.append(f"# Get sample {first_type} nodes (count them yourself from the results)")
            lines.append(f"MATCH (n:{first_type}) RETURN n LIMIT 50")
        else:
            lines.append(f"# Get {first_type} nodes (count them yourself from the results)")
            lines.append(f"MATCH (n) WHERE n.id STARTS WITH '{first_prefix}_' RETURN n LIMIT 50")
        lines.append("")

    # Filtered query example
    for entity in context.entity_schemas:
        if entity.node_count > 0 and entity.properties:
            prefix = _entity_type_to_id_prefix(entity.entity_type)
            # Find a string property for filter example
            string_props = [p for p in entity.properties if p.data_type in ("String", "string")]
            if string_props:
                prop = string_props[0]
                if labels_exist:
                    lines.append(f"# Filter {entity.entity_type} nodes by property")
                    lines.append(f"MATCH (n:{entity.entity_type}) WHERE n.{prop.name} IS NOT NULL RETURN n LIMIT 50")
                else:
                    lines.append(f"# Filter {entity.entity_type} nodes by property")
                    lines.append(f"MATCH (n) WHERE n.id STARTS WITH '{prefix}_' AND n.{prop.name} IS NOT NULL RETURN n LIMIT 50")
                lines.append("")
                break

    # Second entity type if available
    if len(entity_types) > 1:
        second_type = entity_types[1]
        second_prefix = _entity_type_to_id_prefix(second_type)
        if labels_exist:
            lines.append(f"# Get all {second_type} nodes")
            lines.append(f"MATCH (n:{second_type}) RETURN n LIMIT 100")
        else:
            lines.append(f"# Get all {second_type} nodes")
            lines.append(f"MATCH (n) WHERE n.id STARTS WITH '{second_prefix}_' RETURN n LIMIT 100")
        lines.append("")

    # Relationship query (if we have relationships) - must RETURN nodes, not projections
    if context.relationship_schemas:
        rel = context.relationship_schemas[0]
        lines.append(f"# Find nodes connected via {rel.name} relationships")
        lines.append(f"MATCH (a)-[r:{rel.name}]->(b)")
        lines.append(f"RETURN a LIMIT 10")
        lines.append("")

    lines.append("```")
    lines.append("")

    # CRITICAL: API constraint
    lines.append("### CRITICAL: Return Format")
    lines.append("")
    lines.append("**The query API ONLY returns full node objects. You MUST always `RETURN n` (whole nodes).**")
    lines.append("")
    lines.append("These patterns WORK:")
    lines.append("```cypher")
    if labels_exist:
        lines.append("MATCH (n:SomeType) RETURN n LIMIT 10")
        lines.append("MATCH (n:SomeType) WHERE n.amount > 1000 RETURN n LIMIT 50")
        lines.append("MATCH (a:TypeA)-[r:REL]->(b:TypeB) RETURN a, b LIMIT 10")
    else:
        first_prefix = _entity_type_to_id_prefix(entity_types[0]) if entity_types else "entity"
        lines.append(f"MATCH (n) WHERE n.id STARTS WITH '{first_prefix}_' RETURN n LIMIT 10")
        lines.append(f"MATCH (n) WHERE n.id STARTS WITH '{first_prefix}_' AND n.amount > 1000 RETURN n LIMIT 50")
        lines.append("MATCH (a)-[r]->(b) WHERE a.id STARTS WITH 'type_a_' RETURN a, b LIMIT 10")
    lines.append("```")
    lines.append("")
    lines.append("These patterns DO NOT WORK (return 0 results):")
    lines.append("```cypher")
    lines.append("MATCH (n) RETURN count(n)           -- aggregations not supported")
    lines.append("MATCH (n) RETURN n.name, n.amount    -- property projections not supported")
    lines.append("MATCH (n) RETURN n.category, count(*) -- GROUP BY not supported")
    lines.append("```")
    lines.append("")
    lines.append("The tool will return all node properties as flat dictionaries. You perform ")
    lines.append("aggregations, counts, and grouping in your analysis after receiving the raw nodes.")
    lines.append("")

    # Query tips
    lines.append("### Query Tips")
    lines.append("")
    if not labels_exist:
        lines.append("- **ALWAYS use `WHERE n.id STARTS WITH 'prefix_'` to filter by entity type**")
        lines.append("- Do NOT use labels like `(n:Prescription)` - they don't exist in this database")
    lines.append("- **ALWAYS use `RETURN n` to return full nodes** - never use property projections or aggregations")
    lines.append("- Use `RETURN n LIMIT 5` first to see sample nodes and discover available properties")
    lines.append("- Use LIMIT when exploring (queries auto-limited to 500 results)")
    lines.append("- Filter early with WHERE clauses for large datasets")
    lines.append("- Perform aggregation/counting yourself on the returned nodes")
    lines.append("")

    return "\n".join(lines)


def _entity_type_to_id_prefix(entity_type: str) -> str:
    """
    Convert entity type back to ID prefix pattern.

    E.g., "Prescription" -> "prescription", "StateCompliance" -> "state-compliance"
    """
    # Handle camelCase by inserting hyphens before uppercase letters
    import re
    # Insert hyphen before uppercase letters (except at start)
    result = re.sub(r'(?<!^)(?=[A-Z])', '-', entity_type)
    return result.lower()


__all__ = [
    "WorkspaceContextPackage",
    "EntitySchema",
    "PropertySchema",
    "FieldRange",
    "RelationshipSchema",
    "build_context_package",
    "build_cypher_guide",
]
