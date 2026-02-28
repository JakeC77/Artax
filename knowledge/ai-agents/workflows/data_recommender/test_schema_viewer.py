"""
Test script to view workspace schema using semanticEntities and semanticFields.

This script validates the new schema discovery approach:
1. Fetch semanticEntities (entity id → name mapping)
2. Fetch semanticFields (properties + rangeInfo for ALL entities in one query)
3. Group fields by semanticEntityId
4. Display the combined schema with range information

Usage:
    python test_schema_viewer.py
    python test_schema_viewer.py --debug     # Show raw API responses
    python test_schema_viewer.py --compare   # Compare old vs new approach

Environment variables required:
    WORKSPACE_ID - Workspace UUID
    TENANT_ID - Tenant ID for authentication
"""

import asyncio
import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

# Load .env
try:
    from dotenv import load_dotenv
    env_paths = [
        Path(__file__).parent / ".env",
        Path(__file__).parent.parent.parent / ".env",
        Path(__file__).parent.parent.parent.parent / ".env",
    ]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path)
            print(f"✓ Loaded environment from: {env_path}")
            break
except ImportError:
    pass

from app.core.authenticated_graphql_client import run_graphql


# ========================================
# New Queries (semanticEntities + semanticFields)
# ========================================

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

SEMANTIC_FIELDS_QUERY = """
query SemanticFields {
  semanticFields {
    name
    dataType
    description
    rangeInfo
    semanticEntityId
    semanticFieldId
  }
}
""".strip()


# ========================================
# Old Queries (for comparison)
# ========================================

NODE_TYPES_QUERY = """
query {
  graphNodeTypes
}
""".strip()

NODE_PROPERTY_METADATA_QUERY = """
query NodePropertyMetadata($type: String!) {
  graphNodePropertyMetadata(type: $type) {
    name
    dataType
  }
}
""".strip()

NODE_RELATIONSHIP_TYPES_QUERY = """
query NodeRelationshipTypes($type: String!) {
  graphNodeRelationshipTypes(type: $type)
}
""".strip()


# ========================================
# Schema Fetching Functions
# ========================================

async def fetch_schema_new_approach(workspace_id: str, tenant_id: str, debug: bool = False) -> Dict[str, Any]:
    """
    Fetch schema using the NEW approach (semanticEntities + semanticFields).

    Args:
        workspace_id: Workspace UUID for filtering semantic entities
        tenant_id: Tenant ID for authentication
        debug: If True, show raw API responses

    Returns:
        Schema with rangeInfo included.
    """
    print("\n" + "="*70)
    print("FETCHING SCHEMA (New Approach: semanticEntities + semanticFields)")
    print("="*70)

    # Step 1: Fetch semantic entities
    print("\n1. Fetching semanticEntities...")
    entities_data = await run_graphql(SEMANTIC_ENTITIES_QUERY, {"workspaceId": workspace_id}, tenant_id=tenant_id)

    if debug:
        print("\n   Raw response:")
        print(json.dumps(entities_data, indent=4))

    entity_id_to_name = {
        e["semanticEntityId"]: e["name"]
        for e in entities_data.get("semanticEntities", [])
    }
    print(f"   ✓ Found {len(entity_id_to_name)} entities")

    # Step 2: Fetch all semantic fields
    print("\n2. Fetching semanticFields...")
    fields_data = await run_graphql(SEMANTIC_FIELDS_QUERY, {}, tenant_id=tenant_id)

    if debug:
        print("\n   Raw response (first 3 fields):")
        sample = fields_data.get("semanticFields", [])[:3]
        print(json.dumps(sample, indent=4))

    all_fields = fields_data.get("semanticFields", [])
    print(f"   ✓ Found {len(all_fields)} fields total")

    # Step 3: Group fields by entity and parse rangeInfo
    print("\n3. Grouping fields by entity...")
    fields_by_entity = {}

    for field in all_fields:
        entity_id = field.get("semanticEntityId")
        if not entity_id:
            continue
        entity_name = entity_id_to_name.get(entity_id, f"Unknown({entity_id[:8]}...)")

        if entity_name not in fields_by_entity:
            fields_by_entity[entity_name] = []

        # Parse rangeInfo JSON string
        range_info = None
        raw_range = field.get("rangeInfo")
        if raw_range:
            try:
                range_info = json.loads(raw_range)
            except json.JSONDecodeError:
                range_info = {"parse_error": raw_range}

        fields_by_entity[entity_name].append({
            "name": field.get("name"),
            "dataType": field.get("dataType"),
            "description": field.get("description"),
            "rangeInfo": range_info,
        })

    # Step 4: Fetch relationships (still per-entity)
    print("\n4. Fetching relationships for each entity...")
    relationships_by_entity = {}

    for entity_name in entity_id_to_name.values():
        try:
            rels_data = await run_graphql(
                NODE_RELATIONSHIP_TYPES_QUERY,
                {"type": entity_name},
                tenant_id=tenant_id
            )
            rel_types = rels_data.get("graphNodeRelationshipTypes", [])
            if rel_types:
                relationships_by_entity[entity_name] = rel_types
        except Exception as e:
            print(f"   ⚠️  Could not fetch relationships for {entity_name}: {e}")

    total_rels = sum(len(r) for r in relationships_by_entity.values())
    print(f"   ✓ Found {total_rels} relationships across {len(relationships_by_entity)} entities")

    return {
        "entities": entity_id_to_name,
        "fields_by_entity": fields_by_entity,
        "relationships_by_entity": relationships_by_entity,
        "query_count": 2 + len(entity_id_to_name),  # semanticEntities + semanticFields + N relationships
    }


async def fetch_schema_old_approach(tenant_id: str, debug: bool = False) -> Dict[str, Any]:
    """
    Fetch schema using the OLD approach (graphNodeTypes + N graphNodePropertyMetadata).

    For comparison purposes.
    """
    print("\n" + "="*70)
    print("FETCHING SCHEMA (Old Approach: graphNodeTypes + N×graphNodePropertyMetadata)")
    print("="*70)

    # Step 1: Fetch node types
    print("\n1. Fetching graphNodeTypes...")
    types_data = await run_graphql(NODE_TYPES_QUERY, {}, tenant_id=tenant_id)

    node_types = types_data.get("graphNodeTypes", [])
    print(f"   ✓ Found {len(node_types)} node types")

    # Step 2: Fetch properties for each type
    print("\n2. Fetching graphNodePropertyMetadata for each type...")
    fields_by_entity = {}

    for node_type in node_types:
        try:
            props_data = await run_graphql(
                NODE_PROPERTY_METADATA_QUERY,
                {"type": node_type},
                tenant_id=tenant_id
            )
            props = props_data.get("graphNodePropertyMetadata", [])
            fields_by_entity[node_type] = [
                {"name": p["name"], "dataType": p.get("dataType", "string"), "rangeInfo": None}
                for p in props
            ]
            print(f"   ✓ {node_type}: {len(props)} properties")
        except Exception as e:
            print(f"   ⚠️  {node_type}: Error - {e}")
            fields_by_entity[node_type] = []

    # Step 3: Fetch relationships
    print("\n3. Fetching graphNodeRelationshipTypes for each type...")
    relationships_by_entity = {}

    for node_type in node_types:
        try:
            rels_data = await run_graphql(
                NODE_RELATIONSHIP_TYPES_QUERY,
                {"type": node_type},
                tenant_id=tenant_id
            )
            rel_types = rels_data.get("graphNodeRelationshipTypes", [])
            if rel_types:
                relationships_by_entity[node_type] = rel_types
        except Exception as e:
            pass

    return {
        "entities": {t: t for t in node_types},  # No IDs in old approach
        "fields_by_entity": fields_by_entity,
        "relationships_by_entity": relationships_by_entity,
        "query_count": 1 + len(node_types) * 2,  # 1 + N props + N rels
    }


# ========================================
# Display Functions
# ========================================

def display_schema(schema: Dict[str, Any], title: str = "Schema"):
    """Pretty-print the schema."""
    print("\n" + "="*70)
    print(f"SCHEMA SUMMARY: {title}")
    print("="*70)

    fields_by_entity = schema["fields_by_entity"]
    relationships_by_entity = schema["relationships_by_entity"]

    total_fields = sum(len(f) for f in fields_by_entity.values())
    total_rels = sum(len(r) for r in relationships_by_entity.values())
    fields_with_range = sum(
        1 for fields in fields_by_entity.values()
        for f in fields if f.get("rangeInfo")
    )

    print(f"\n📊 Overview:")
    print(f"   Entities: {len(fields_by_entity)}")
    print(f"   Total Fields: {total_fields}")
    print(f"   Fields with Range Info: {fields_with_range}")
    print(f"   Total Relationships: {total_rels}")
    print(f"   API Queries Made: {schema['query_count']}")

    print(f"\n📋 Entities and Fields:")

    for entity_name, fields in sorted(fields_by_entity.items()):
        rels = relationships_by_entity.get(entity_name, [])
        print(f"\n   {entity_name} ({len(fields)} fields, {len(rels)} relationships)")

        for field in fields:
            name = field["name"]
            dtype = field.get("dataType", "?")
            range_info = field.get("rangeInfo")

            if range_info and isinstance(range_info, dict) and "min" in range_info:
                min_val = range_info.get("min", "?")
                max_val = range_info.get("max", "?")
                print(f"      • {name} ({dtype}) — range: {min_val} to {max_val}")
            else:
                print(f"      • {name} ({dtype})")

        if rels:
            print(f"      → Relationships: {', '.join(rels)}")


def compare_schemas(old_schema: Dict, new_schema: Dict):
    """Compare old and new schema approaches."""
    print("\n" + "="*70)
    print("COMPARISON: Old vs New Approach")
    print("="*70)

    old_entities = set(old_schema["fields_by_entity"].keys())
    new_entities = set(new_schema["fields_by_entity"].keys())

    print(f"\n📊 Entity Coverage:")
    print(f"   Old approach: {len(old_entities)} entities")
    print(f"   New approach: {len(new_entities)} entities")

    if old_entities != new_entities:
        only_old = old_entities - new_entities
        only_new = new_entities - old_entities
        if only_old:
            print(f"   ⚠️  Only in old: {only_old}")
        if only_new:
            print(f"   ⚠️  Only in new: {only_new}")
    else:
        print(f"   ✓ Same entities in both approaches")

    print(f"\n📊 API Efficiency:")
    print(f"   Old approach: {old_schema['query_count']} queries")
    print(f"   New approach: {new_schema['query_count']} queries")
    print(f"   Savings: {old_schema['query_count'] - new_schema['query_count']} fewer queries")

    print(f"\n📊 Range Information:")
    old_with_range = sum(
        1 for fields in old_schema["fields_by_entity"].values()
        for f in fields if f.get("rangeInfo")
    )
    new_with_range = sum(
        1 for fields in new_schema["fields_by_entity"].values()
        for f in fields if f.get("rangeInfo")
    )
    print(f"   Old approach: {old_with_range} fields with range info")
    print(f"   New approach: {new_with_range} fields with range info")


# ========================================
# Main
# ========================================

async def main():
    parser = argparse.ArgumentParser(description="View workspace schema using new API approach")
    parser.add_argument("--debug", action="store_true", help="Show raw API responses")
    parser.add_argument("--compare", action="store_true", help="Compare old vs new approach")
    args = parser.parse_args()

    # Get environment variables
    workspace_id = os.getenv("WORKSPACE_ID")
    tenant_id = os.getenv("TENANT_ID")

    if not workspace_id or not tenant_id:
        print("❌ Error: Missing required environment variables")
        print("   WORKSPACE_ID and TENANT_ID are required")
        return

    print(f"\n🔧 Configuration:")
    print(f"   WORKSPACE_ID: {workspace_id[:8]}...")
    print(f"   TENANT_ID: {tenant_id[:8]}...")

    # Fetch schema using new approach
    new_schema = await fetch_schema_new_approach(workspace_id, tenant_id, debug=args.debug)
    display_schema(new_schema, "New Approach (semanticFields)")

    # Compare with old approach if requested
    if args.compare:
        old_schema = await fetch_schema_old_approach(tenant_id, debug=args.debug)
        display_schema(old_schema, "Old Approach (graphNodePropertyMetadata)")
        compare_schemas(old_schema, new_schema)

    print("\n" + "="*70)
    print("DONE")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
