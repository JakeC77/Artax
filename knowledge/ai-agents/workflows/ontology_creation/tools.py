"""
tools.py - Custom tools for ontology creation agent
"""

from pydantic_ai import RunContext
from typing import List, Optional
import uuid
from .models import (
    OntologyPackage, EntityDefinition, FieldDefinition, RelationshipDefinition,
    OntologyState, increment_semantic_version
)
from .sql_schema import get_sql_schema

# Tool registry for ontology-specific tools
ONTOLOGY_TOOLS = {}


def register_tool(name: str):
    """Decorator to register a tool"""
    def decorator(func):
        ONTOLOGY_TOOLS[name] = func
        return func
    return decorator


def _generate_id(prefix: str = "") -> str:
    """Generate a temporary ID for entities/relationships."""
    return f"{prefix}{uuid.uuid4().hex[:8]}"


@register_tool("propose_ontology")
async def propose_ontology(
    ctx: RunContext[OntologyState],
    title: str,
    description: str,
    entities: List[dict],
    relationships: Optional[List[dict]] = None
) -> dict:
    """
    Propose an initial ontology structure to the user.
    
    Use this tool when you've gathered enough information about the domain
    and are ready to present a complete ontology proposal.
    
    Args:
        ctx: Pydantic AI context containing the OntologyState
        title: Domain name/title
        description: Domain description
        entities: List of entity definitions, each with:
            - name: Entity name
            - description: Entity description
            - fields: List of field definitions, each with:
                - name: Field name
                - data_type: Data type (string, integer, float, date, boolean, etc.)
                - nullable: Whether field can be null
                - is_identifier: Whether this is an ID field
                - description: Field description
        relationships: Optional list of relationship definitions, each with:
            - from_entity: Source entity name
            - to_entity: Target entity name
            - relationship_type: Relationship type name
            - description: Relationship description
            - cardinality: Optional cardinality (one-to-one, one-to-many, many-to-many)
    
    Returns:
        Status message indicating the ontology was proposed
    """
    state = ctx.deps
    
    # Create entity definitions with IDs
    entity_defs = []
    entity_name_to_id = {}
    
    for entity_data in entities:
        entity_id = _generate_id("ent_")
        entity_name = entity_data.get("name", "")
        entity_name_to_id[entity_name] = entity_id
        
        fields = []
        for field_data in entity_data.get("fields", []):
            fields.append(FieldDefinition(
                name=field_data.get("name", ""),
                data_type=field_data.get("data_type", "string"),
                nullable=field_data.get("nullable", True),
                is_identifier=field_data.get("is_identifier", False),
                description=field_data.get("description", "")
            ))
        
        entity_defs.append(EntityDefinition(
            entity_id=entity_id,
            name=entity_name,
            description=entity_data.get("description", ""),
            fields=fields
        ))
    
    # Create relationship definitions
    relationship_defs = []
    if relationships:
        for rel_data in relationships:
            from_name = rel_data.get("from_entity", "")
            to_name = rel_data.get("to_entity", "")
            
            from_id = entity_name_to_id.get(from_name)
            to_id = entity_name_to_id.get(to_name)
            
            if from_id and to_id:
                relationship_defs.append(RelationshipDefinition(
                    relationship_id=_generate_id("rel_"),
                    from_entity=from_id,
                    to_entity=to_id,
                    relationship_type=rel_data.get("relationship_type", ""),
                    description=rel_data.get("description", ""),
                    cardinality=rel_data.get("cardinality")
                ))
    
    # Create or update ontology package
    if state.ontology_package is None:
        # Require ontology_id from state - should be set by builder from incoming event
        ontology_id = getattr(state, 'ontology_id', None)
        if not ontology_id:
            return {
                "error": "ontology_id is required but not found in state. The ontology_id must be provided in the incoming event."
            }
        state.ontology_package = OntologyPackage(
            ontology_id=ontology_id,
            semantic_version="0.1.0",
            title=title,
            description=description,
            entities=entity_defs,
            relationships=relationship_defs
        )
    else:
        # Update existing package
        state.ontology_package.title = title
        state.ontology_package.description = description
        state.ontology_package.entities = entity_defs
        state.ontology_package.relationships = relationship_defs
        state.ontology_package.add_iteration(
            "Proposed initial ontology structure",
            change_type="minor"
        )
    
    state.ontology_proposed = True
    state.ontology_needs_broadcast = True
    state.last_update_summary = f"Proposed ontology: {title}"
    
    return {
        "status": "proposed",
        "message": f"Ontology '{title}' proposed with {len(entity_defs)} entities and {len(relationship_defs)} relationships",
        "entity_count": len(entity_defs),
        "relationship_count": len(relationship_defs)
    }


@register_tool("add_entity")
async def add_entity(
    ctx: RunContext[OntologyState],
    name: str,
    description: str,
    fields: Optional[List[dict]] = None
) -> dict:
    """
    Add a new entity to the ontology.
    
    Args:
        ctx: Pydantic AI context
        name: Entity name
        description: Entity description
        fields: Optional list of field definitions
    
    Returns:
        Status message
    """
    state = ctx.deps
    
    if state.ontology_package is None:
        return {"status": "error", "message": "No ontology package. Call propose_ontology first."}
    
    # Check if entity already exists
    if any(e.name == name for e in state.ontology_package.entities):
        return {"status": "error", "message": f"Entity '{name}' already exists"}
    
    entity_id = _generate_id("ent_")
    field_defs = []
    
    if fields:
        for field_data in fields:
            field_defs.append(FieldDefinition(
                name=field_data.get("name", ""),
                data_type=field_data.get("data_type", "string"),
                nullable=field_data.get("nullable", True),
                is_identifier=field_data.get("is_identifier", False),
                description=field_data.get("description", "")
            ))
    
    entity = EntityDefinition(
        entity_id=entity_id,
        name=name,
        description=description,
        fields=field_defs
    )
    
    state.ontology_package.entities.append(entity)
    state.ontology_package.add_iteration(
        f"Added entity: {name}",
        change_type="minor"
    )
    
    state.ontology_needs_broadcast = True
    state.last_update_summary = f"Added entity: {name}"
    
    return {
        "status": "added",
        "message": f"Added entity '{name}'",
        "entity_id": entity_id
    }


@register_tool("update_entity")
async def update_entity(
    ctx: RunContext[OntologyState],
    entity_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    fields: Optional[List[dict]] = None
) -> dict:
    """
    Update an existing entity.
    
    Args:
        ctx: Pydantic AI context
        entity_id: Entity ID to update
        name: New name (optional)
        description: New description (optional)
        fields: New fields list (optional, replaces all fields)
    
    Returns:
        Status message
    """
    state = ctx.deps
    
    if state.ontology_package is None:
        return {"status": "error", "message": "No ontology package."}
    
    entity = next((e for e in state.ontology_package.entities if e.entity_id == entity_id), None)
    if not entity:
        return {"status": "error", "message": f"Entity with ID '{entity_id}' not found"}
    
    changes = []
    
    if name is not None and name != entity.name:
        entity.name = name
        changes.append("name")
    
    if description is not None and description != entity.description:
        entity.description = description
        changes.append("description")
    
    if fields is not None:
        field_defs = []
        for field_data in fields:
            field_defs.append(FieldDefinition(
                name=field_data.get("name", ""),
                data_type=field_data.get("data_type", "string"),
                nullable=field_data.get("nullable", True),
                is_identifier=field_data.get("is_identifier", False),
                description=field_data.get("description", "")
            ))
        entity.fields = field_defs
        changes.append("fields")
    
    if changes:
        state.ontology_package.add_iteration(
            f"Updated entity '{entity.name}': {', '.join(changes)}",
            change_type="patch"
        )
        state.ontology_needs_broadcast = True
        state.last_update_summary = f"Updated entity '{entity.name}'"
    
    return {
        "status": "updated",
        "message": f"Updated entity '{entity.name}'",
        "changes": changes
    }


@register_tool("remove_entity")
async def remove_entity(
    ctx: RunContext[OntologyState],
    entity_id: str
) -> dict:
    """
    Remove an entity from the ontology.
    
    This is a breaking change - will increment MAJOR version.
    
    Args:
        ctx: Pydantic AI context
        entity_id: Entity ID to remove
    
    Returns:
        Status message
    """
    state = ctx.deps
    
    if state.ontology_package is None:
        return {"status": "error", "message": "No ontology package."}
    
    entity = next((e for e in state.ontology_package.entities if e.entity_id == entity_id), None)
    if not entity:
        return {"status": "error", "message": f"Entity with ID '{entity_id}' not found"}
    
    entity_name = entity.name
    
    # Remove entity
    state.ontology_package.entities = [e for e in state.ontology_package.entities if e.entity_id != entity_id]
    
    # Remove relationships involving this entity
    removed_rels = []
    remaining_rels = []
    for rel in state.ontology_package.relationships:
        if rel.from_entity == entity_id or rel.to_entity == entity_id:
            removed_rels.append(rel.relationship_type)
        else:
            remaining_rels.append(rel)
    state.ontology_package.relationships = remaining_rels
    
    state.ontology_package.add_iteration(
        f"Removed entity '{entity_name}'" + (f" and {len(removed_rels)} relationships" if removed_rels else ""),
        change_type="major"
    )
    
    state.ontology_needs_broadcast = True
    state.last_update_summary = f"Removed entity '{entity_name}'"
    
    return {
        "status": "removed",
        "message": f"Removed entity '{entity_name}'",
        "relationships_removed": len(removed_rels)
    }


@register_tool("add_relationship")
async def add_relationship(
    ctx: RunContext[OntologyState],
    from_entity_id: str,
    to_entity_id: str,
    relationship_type: str,
    description: str,
    cardinality: Optional[str] = None
) -> dict:
    """
    Add a relationship between entities.
    
    Args:
        ctx: Pydantic AI context
        from_entity_id: Source entity ID
        to_entity_id: Target entity ID
        relationship_type: Relationship type name
        description: Relationship description
        cardinality: Optional cardinality
    
    Returns:
        Status message
    """
    state = ctx.deps
    
    if state.ontology_package is None:
        return {"status": "error", "message": "No ontology package."}
    
    # Validate entities exist
    from_entity = next((e for e in state.ontology_package.entities if e.entity_id == from_entity_id), None)
    to_entity = next((e for e in state.ontology_package.entities if e.entity_id == to_entity_id), None)
    
    if not from_entity:
        return {"status": "error", "message": f"Source entity '{from_entity_id}' not found"}
    if not to_entity:
        return {"status": "error", "message": f"Target entity '{to_entity_id}' not found"}
    
    # Check if relationship already exists
    existing = next((
        r for r in state.ontology_package.relationships
        if r.from_entity == from_entity_id and r.to_entity == to_entity_id and r.relationship_type == relationship_type
    ), None)
    
    if existing:
        return {"status": "error", "message": f"Relationship '{relationship_type}' from '{from_entity.name}' to '{to_entity.name}' already exists"}
    
    rel_id = _generate_id("rel_")
    relationship = RelationshipDefinition(
        relationship_id=rel_id,
        from_entity=from_entity_id,
        to_entity=to_entity_id,
        relationship_type=relationship_type,
        description=description,
        cardinality=cardinality
    )
    
    state.ontology_package.relationships.append(relationship)
    state.ontology_package.add_iteration(
        f"Added relationship: {from_entity.name} --[{relationship_type}]--> {to_entity.name}",
        change_type="minor"
    )
    
    state.ontology_needs_broadcast = True
    state.last_update_summary = f"Added relationship: {relationship_type}"
    
    return {
        "status": "added",
        "message": f"Added relationship '{relationship_type}' from '{from_entity.name}' to '{to_entity.name}'",
        "relationship_id": rel_id
    }


@register_tool("update_relationship")
async def update_relationship(
    ctx: RunContext[OntologyState],
    relationship_id: str,
    relationship_type: Optional[str] = None,
    description: Optional[str] = None,
    cardinality: Optional[str] = None
) -> dict:
    """
    Update a relationship.
    
    Args:
        ctx: Pydantic AI context
        relationship_id: Relationship ID to update
        relationship_type: New relationship type (optional)
        description: New description (optional)
        cardinality: New cardinality (optional)
    
    Returns:
        Status message
    """
    state = ctx.deps
    
    if state.ontology_package is None:
        return {"status": "error", "message": "No ontology package."}
    
    rel = next((r for r in state.ontology_package.relationships if r.relationship_id == relationship_id), None)
    if not rel:
        return {"status": "error", "message": f"Relationship with ID '{relationship_id}' not found"}
    
    changes = []
    
    if relationship_type is not None and relationship_type != rel.relationship_type:
        rel.relationship_type = relationship_type
        changes.append("relationship_type")
    
    if description is not None and description != rel.description:
        rel.description = description
        changes.append("description")
    
    if cardinality is not None and cardinality != rel.cardinality:
        rel.cardinality = cardinality
        changes.append("cardinality")
    
    if changes:
        state.ontology_package.add_iteration(
            f"Updated relationship '{rel.relationship_type}': {', '.join(changes)}",
            change_type="patch"
        )
        state.ontology_needs_broadcast = True
        state.last_update_summary = f"Updated relationship '{rel.relationship_type}'"
    
    return {
        "status": "updated",
        "message": f"Updated relationship '{rel.relationship_type}'",
        "changes": changes
    }


@register_tool("remove_relationship")
async def remove_relationship(
    ctx: RunContext[OntologyState],
    relationship_id: str
) -> dict:
    """
    Remove a relationship.
    
    This is a breaking change - will increment MAJOR version.
    
    Args:
        ctx: Pydantic AI context
        relationship_id: Relationship ID to remove
    
    Returns:
        Status message
    """
    state = ctx.deps
    
    if state.ontology_package is None:
        return {"status": "error", "message": "No ontology package."}
    
    rel = next((r for r in state.ontology_package.relationships if r.relationship_id == relationship_id), None)
    if not rel:
        return {"status": "error", "message": f"Relationship with ID '{relationship_id}' not found"}
    
    rel_type = rel.relationship_type
    state.ontology_package.relationships = [r for r in state.ontology_package.relationships if r.relationship_id != relationship_id]
    
    state.ontology_package.add_iteration(
        f"Removed relationship '{rel_type}'",
        change_type="major"
    )
    
    state.ontology_needs_broadcast = True
    state.last_update_summary = f"Removed relationship '{rel_type}'"
    
    return {
        "status": "removed",
        "message": f"Removed relationship '{rel_type}'"
    }


@register_tool("update_field")
async def update_field(
    ctx: RunContext[OntologyState],
    entity_id: str,
    field_name: str,
    data_type: Optional[str] = None,
    nullable: Optional[bool] = None,
    is_identifier: Optional[bool] = None,
    description: Optional[str] = None
) -> dict:
    """
    Update a field on an entity.
    
    Args:
        ctx: Pydantic AI context
        entity_id: Entity ID containing the field
        field_name: Field name to update
        data_type: New data type (optional)
        nullable: New nullable value (optional)
        is_identifier: New is_identifier value (optional)
        description: New description (optional)
    
    Returns:
        Status message
    """
    state = ctx.deps
    
    if state.ontology_package is None:
        return {"status": "error", "message": "No ontology package."}
    
    entity = next((e for e in state.ontology_package.entities if e.entity_id == entity_id), None)
    if not entity:
        return {"status": "error", "message": f"Entity with ID '{entity_id}' not found"}
    
    field = next((f for f in entity.fields if f.name == field_name), None)
    if not field:
        return {"status": "error", "message": f"Field '{field_name}' not found on entity '{entity.name}'"}
    
    changes = []
    change_type = "patch"
    
    if data_type is not None and data_type != field.data_type:
        field.data_type = data_type
        changes.append("data_type")
        change_type = "major"  # Changing data type is breaking
    
    if nullable is not None and nullable != field.nullable:
        old_nullable = field.nullable
        field.nullable = nullable
        changes.append("nullable")
        # Making a field required (nullable=False) is breaking
        if not nullable and old_nullable:
            change_type = "major"
    
    if is_identifier is not None and is_identifier != field.is_identifier:
        field.is_identifier = is_identifier
        changes.append("is_identifier")
        change_type = "major"  # Changing ID status is breaking
    
    if description is not None and description != field.description:
        field.description = description
        changes.append("description")
    
    if changes:
        state.ontology_package.add_iteration(
            f"Updated field '{field_name}' on entity '{entity.name}': {', '.join(changes)}",
            change_type=change_type
        )
        state.ontology_needs_broadcast = True
        state.last_update_summary = f"Updated field '{field_name}' on entity '{entity.name}'"
    
    return {
        "status": "updated",
        "message": f"Updated field '{field_name}' on entity '{entity.name}'",
        "changes": changes
    }


@register_tool("finalize_ontology")
async def finalize_ontology(
    ctx: RunContext[OntologyState]
) -> dict:
    """
    Finalize the ontology - mark it as complete.
    
    If semantic version is still at 0.x.x, sets it to 1.0.0.
    
    Args:
        ctx: Pydantic AI context
    
    Returns:
        Status message
    """
    state = ctx.deps
    
    if state.ontology_package is None:
        return {"status": "error", "message": "No ontology package to finalize."}
    
    # Validate minimum requirements
    if not state.ontology_package.entities:
        return {"status": "error", "message": "Cannot finalize ontology without entities"}
    
    # If still at 0.x.x, promote to 1.0.0
    if state.ontology_package.semantic_version.startswith("0."):
        state.ontology_package.semantic_version = "1.0.0"
        state.ontology_package.add_iteration(
            "Finalized ontology - promoted to version 1.0.0",
            change_type="major"
        )
    
    state.ontology_package.finalized = True
    state.ontology_finalized = True
    state.ontology_needs_broadcast = True
    state.last_update_summary = "Ontology finalized"
    
    return {
        "status": "finalized",
        "message": f"Ontology '{state.ontology_package.title}' finalized at version {state.ontology_package.semantic_version}",
        "semantic_version": state.ontology_package.semantic_version
    }


@register_tool("read_database_schema")
async def read_database_schema(
    ctx: RunContext[OntologyState],
    connection_string: str,
    dialect: Optional[str] = None,
) -> dict:
    """
    Read the schema of a SQL database (tables, columns, types, primary keys, foreign keys).

    Use this when the user provides a database connection string so you can suggest
    or validate ontology entities and relationships based on the actual table structure.
    Do not log or repeat the connection string; use it only for this call.

    Args:
        ctx: Pydantic AI context (unused)
        connection_string: Database connection string (e.g. postgresql://user:pass@host/db
            or SQL Server / ODBC style). Never stored or logged in full.
        dialect: Optional hint: "postgresql", "sqlserver", "mysql". If omitted, inferred from URL.

    Returns:
        Dict with "schema_text" (human-readable summary for the agent) and "error" if introspection failed.
    """
    summary = get_sql_schema(connection_string, dialect=dialect)
    if summary.error:
        return {
            "schema_text": "",
            "error": summary.error,
            "message": f"Failed to introspect database: {summary.error}",
        }
    return {
        "schema_text": summary.to_agent_friendly_str(),
        "error": None,
        "message": f"Schema introspected: {len(summary.tables)} tables.",
        "table_count": len(summary.tables),
    }
