"""
Schema discovery functions for data recommender workflow.

This module provides functions to fetch workspace schema and sample data
from the GraphQL API. Used by both the workflow harness and CLI tests.

Schema Discovery Flow (optimized):
1. graphSchema — entities (with count, descriptions, properties), relationships
   (with fromLabels/toLabels for directionality), and suggestedPatterns
2. semanticEntities — supplementary rangeInfo (min/max) for properties

Both queries run in parallel. Total: 2 queries.
"""

import asyncio
import json
import logging
import time
from typing import List, Dict, Any

from app.core.authenticated_graphql_client import run_graphql
from app.workflows.data_recommender.agent import (
    GraphSchema,
    EntityType,
    PropertyInfo,
    RelationshipType,
    SuggestedPattern,
)
from app.workflows.data_recommender.graphql_client import create_client

logger = logging.getLogger(__name__)


# ========================================
# GraphQL Queries for Schema Discovery
# ========================================

# Primary source: full graph schema with entities, relationships, and patterns
GRAPH_SCHEMA_QUERY = """
query GraphSchema($workspaceId: UUID!) {
  graphSchema(workspaceId: $workspaceId) {
    nodeTypes {
      count
      description
      label
      properties {
        dataType
        description
        name
      }
    }
    relationshipTypes {
      cardinality
      description
      fromLabels
      toLabels
      type
    }
    suggestedPatterns {
      cypherPattern
      description
      exampleQuery
      name
    }
  }
}
""".strip()

# Supplementary: rangeInfo for properties (min/max values)
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


# ========================================
# Schema Discovery Functions
# ========================================

async def fetch_workspace_schema(
    workspace_id: str,
    tenant_id: str,
    debug: bool = False,
    excluded_entities: list[str] | None = None,
) -> GraphSchema:
    """
    Fetch workspace schema from GraphQL API.

    Optimized approach (2 queries in parallel):
    1. graphSchema — entities (with count, description, properties), relationships
       (with fromLabels/toLabels), and suggestedPatterns
    2. semanticEntities — rangeInfo for properties (min/max values)

    Merges rangeInfo from semanticEntities into graphSchema properties by matching
    on nodeLabel/label.

    Args:
        workspace_id: Workspace UUID (used for logging, not in query)
        tenant_id: Tenant ID for authentication
        debug: If True, log detailed property and field information

    Returns:
        GraphSchema with entities, properties (with ranges and descriptions),
        relationships (with directionality), and suggested patterns
    """
    logger.info(f"Fetching workspace schema for workspace_id={workspace_id[:8]}...")

    # graphSchema can be slow on large graphs and may hit server-side timeouts.
    # Retry with backoff — the server often succeeds on retry once caches warm up.
    max_retries = 3
    retry_delays = [2, 5, 10]  # seconds between retries
    schema_data = None
    last_error = None

    for attempt in range(max_retries):
        # Run both queries in parallel (120s client timeout)
        schema_task = run_graphql(GRAPH_SCHEMA_QUERY, {"workspaceId": workspace_id}, tenant_id=tenant_id, timeout=120)
        semantic_task = run_graphql(SEMANTIC_ENTITIES_QUERY, {"workspaceId": workspace_id}, tenant_id=tenant_id, timeout=120)

        results = await asyncio.gather(schema_task, semantic_task, return_exceptions=True)
        schema_result = results[0]
        semantic_data = results[1]

        if not isinstance(schema_result, Exception):
            schema_data = schema_result
            break

        last_error = schema_result
        is_timeout = "timeout" in str(schema_result).lower()

        if attempt < max_retries - 1:
            delay = retry_delays[attempt]
            logger.warning(
                f"graphSchema query failed (attempt {attempt + 1}/{max_retries}): {schema_result}"
                f"{' (server timeout — retrying)' if is_timeout else ''}"
                f" — retrying in {delay}s"
            )
            await asyncio.sleep(delay)
        else:
            logger.error(f"graphSchema query failed after {max_retries} attempts: {schema_result}")

    if schema_data is None:
        raise RuntimeError(f"graphSchema query failed after {max_retries} attempts: {last_error}")

    # Build rangeInfo lookup from semanticEntities: {label: {fieldName: {min, max}}}
    range_lookup: Dict[str, Dict[str, dict]] = {}
    if not isinstance(semantic_data, Exception):
        for entity in semantic_data.get("semanticEntities", []):
            label = entity.get("nodeLabel") or entity.get("name")
            field_ranges: Dict[str, dict] = {}
            for field in entity.get("fields", []):
                raw_range = field.get("rangeInfo")
                if raw_range:
                    try:
                        field_ranges[field["name"]] = json.loads(raw_range)
                    except json.JSONDecodeError:
                        logger.debug(f"Could not parse rangeInfo for {field.get('name')}: {raw_range}")
            if field_ranges:
                range_lookup[label] = field_ranges
        logger.info(f"semanticEntities: {len(range_lookup)} entities with rangeInfo")
    else:
        logger.warning(f"semanticEntities query failed (rangeInfo unavailable): {semantic_data}")

    # Parse graphSchema
    graph_schema = schema_data.get("graphSchema", {})
    node_types = graph_schema.get("nodeTypes", [])

    # Build entities with properties (merged with rangeInfo)
    entities = []
    for node in node_types:
        label = node.get("label", "")
        ranges = range_lookup.get(label, {})

        properties = []
        for prop in node.get("properties", []):
            prop_name = prop.get("name", "")
            min_value = None
            max_value = None
            if prop_name in ranges:
                min_value = ranges[prop_name].get("min")
                max_value = ranges[prop_name].get("max")

            properties.append(PropertyInfo(
                name=prop_name,
                type=prop.get("dataType", "string"),
                description=prop.get("description"),
                min_value=min_value,
                max_value=max_value,
            ))

        entities.append(EntityType(
            name=label,
            description=node.get("description"),
            count=node.get("count"),
            properties=properties,
        ))

        if debug:
            props_with_range = sum(1 for p in properties if p.min_value or p.max_value)
            logger.debug(f"  {label}: {len(properties)} props ({props_with_range} with range), count={node.get('count')}")

    # Parse relationships (fromLabels/toLabels give directionality)
    relationships = []
    for rel in graph_schema.get("relationshipTypes", []):
        rel_type = rel.get("type", "")
        from_labels = rel.get("fromLabels", [])
        to_labels = rel.get("toLabels", [])

        # Expand each (from, to) pair into a RelationshipType
        for from_label in from_labels:
            for to_label in to_labels:
                relationships.append(RelationshipType(
                    name=rel_type,
                    from_entity=from_label,
                    to_entity=to_label,
                ))

    # Parse suggested patterns
    suggested_patterns = []
    for pattern in graph_schema.get("suggestedPatterns", []):
        suggested_patterns.append(SuggestedPattern(
            name=pattern.get("name", ""),
            description=pattern.get("description"),
            cypher_pattern=pattern.get("cypherPattern"),
            example_query=pattern.get("exampleQuery"),
        ))

    # Filter out excluded entity types
    if excluded_entities:
        exclude_set = set(excluded_entities)
        pre_count = len(entities)
        entities = [e for e in entities if e.name not in exclude_set]
        relationships = [
            r for r in relationships
            if r.from_entity not in exclude_set and r.to_entity not in exclude_set
        ]
        filtered = pre_count - len(entities)
        if filtered:
            logger.info(f"Excluded {filtered} entity types: {sorted(exclude_set)}")

    schema = GraphSchema(
        entities=entities,
        relationships=relationships,
        suggested_patterns=suggested_patterns,
    )

    # Summary logging
    props_with_range = sum(
        1 for e in entities
        for p in e.properties
        if p.min_value or p.max_value
    )

    logger.info(
        f"Schema loaded: {len(entities)} entities, "
        f"{sum(len(e.properties) for e in entities)} properties "
        f"({props_with_range} with range info), "
        f"{len(relationships)} relationships, "
        f"{len(suggested_patterns)} suggested patterns"
    )

    return schema


async def fetch_sample_data(
    workspace_id: str,
    tenant_id: str,
    entity_types: List[str],
    samples_per_entity: int = 3,
    debug: bool = False
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch sample data for specified entity types.

    This helps the AI agent understand the actual data shape and value formats.
    For example, seeing `requiresDocumentation: "True"` (string) instead of assuming boolean.

    Args:
        workspace_id: Workspace UUID
        tenant_id: Tenant ID for authentication
        entity_types: List of entity types to sample
        samples_per_entity: Number of sample records per entity (default 3)
        debug: If True, log sample data details

    Returns:
        Dict mapping entity_type -> list of property dicts
        Example: {"PolicyRequirement": [{"status": "active", "requiresDocumentation": "True"}, ...]}
    """
    logger.info(f"Fetching sample data for {len(entity_types)} entity types...")

    # Create GraphQL client
    client = create_client(workspace_id=workspace_id, tenant_id=tenant_id)

    sample_data: Dict[str, List[Dict[str, Any]]] = {}

    for entity_type in entity_types:
        try:
            # Fetch sample nodes
            sample_nodes = await client.nodes_sample(entity_type, limit=samples_per_entity)

            # Extract properties from each node
            samples = [node.properties for node in sample_nodes]
            sample_data[entity_type] = samples

            if debug and samples:
                logger.debug(f"  {entity_type}: {len(samples)} samples")

        except Exception as e:
            logger.warning(f"Could not fetch samples for {entity_type}: {type(e).__name__}")
            sample_data[entity_type] = []

    total_samples = sum(len(s) for s in sample_data.values())
    logger.info(f"Sample data loaded: {total_samples} total samples")

    return sample_data
