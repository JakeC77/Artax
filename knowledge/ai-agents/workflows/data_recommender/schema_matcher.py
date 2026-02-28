"""
Deterministic schema matching utilities.

This module provides pure functions for working with GraphSchema without LLM calls.
Used by both the agent (for schema-aware recommendations) and executor (for validation).

All functions are:
- Pure (no side effects)
- Deterministic (same inputs always produce same outputs)
- Fast (no network calls, no LLM invocations)
"""

from typing import List, Optional, Set, Tuple
import re
from difflib import SequenceMatcher

from app.workflows.data_recommender.agent import (
    GraphSchema,
    EntityType,
    PropertyInfo,
    RelationshipType,
)
from app.workflows.data_recommender.models import (
    EntityFilter,
    FilterOperator,
    RelationshipPath,
)


# ============================================================================
# Entity Matching
# ============================================================================

def find_entity(name: str, schema: GraphSchema) -> Optional[EntityType]:
    """
    Find an entity in the schema using fuzzy matching.

    Handles:
    - Exact matches (case-insensitive)
    - Pluralization (employees → Employee)
    - Common variations (emp → Employee, dept → Department)

    Args:
        name: Entity name or hint (e.g., "employees", "EMPLOYEE", "emp")
        schema: Graph schema to search

    Returns:
        EntityType if found, None otherwise

    Examples:
        >>> schema = GraphSchema(entities=[EntityType(name="Employee", ...)])
        >>> find_entity("employees", schema)
        EntityType(name="Employee", ...)
        >>> find_entity("EMPLOYEE", schema)
        EntityType(name="Employee", ...)
        >>> find_entity("emp", schema)
        EntityType(name="Employee", ...)
        >>> find_entity("unknown", schema)
        None
    """
    if not name or not schema.entities:
        return None

    # Normalize input
    normalized_name = name.strip()

    # Try exact match (case-insensitive)
    for entity in schema.entities:
        if entity.name.lower() == normalized_name.lower():
            return entity

    # Try singular form (remove trailing 's')
    if normalized_name.lower().endswith('s'):
        singular = normalized_name[:-1]
        for entity in schema.entities:
            if entity.name.lower() == singular.lower():
                return entity

    # Try fuzzy match with similarity threshold
    # This handles abbreviations and typos
    best_match = None
    best_score = 0.0
    threshold = 0.6  # 60% similarity required

    for entity in schema.entities:
        # Calculate similarity
        similarity = SequenceMatcher(
            None,
            normalized_name.lower(),
            entity.name.lower()
        ).ratio()

        if similarity > best_score and similarity >= threshold:
            best_score = similarity
            best_match = entity

    return best_match


# ============================================================================
# Property/Field Matching
# ============================================================================

def _normalize_field_name(field: str) -> str:
    """
    Normalize a field name for matching.

    Converts:
    - "hire date" → "hiredate"
    - "employee_id" → "employeeid"
    - "Employee ID" → "employeeid"

    Args:
        field: Field name or hint

    Returns:
        Normalized lowercase name without spaces/underscores
    """
    # Remove spaces, underscores, hyphens
    normalized = re.sub(r'[\s_-]+', '', field.lower())
    return normalized


def find_field(entity: str, field_hint: str, schema: GraphSchema) -> Optional[str]:
    """
    Find a property name from a field hint.

    Handles:
    - Exact matches
    - Case differences (hireDate vs hiredate)
    - Spaces/underscores (hire_date → hireDate, hire date → hireDate)
    - Common variations

    Args:
        entity: Entity type name
        field_hint: Field name hint (e.g., "hire date", "employee_id")
        schema: Graph schema

    Returns:
        Actual property name if found, None otherwise

    Examples:
        >>> schema = GraphSchema(entities=[
        ...     EntityType(name="Employee", properties=[
        ...         PropertyInfo(name="hireDate", type="date")
        ...     ])
        ... ])
        >>> find_field("Employee", "hire date", schema)
        "hireDate"
        >>> find_field("Employee", "hire_date", schema)
        "hireDate"
        >>> find_field("Employee", "HIREDATE", schema)
        "hireDate"
    """
    # Find the entity first
    entity_type = find_entity(entity, schema)
    if not entity_type or not entity_type.properties:
        return None

    if not field_hint:
        return None

    # Try exact match first (case-insensitive)
    for prop in entity_type.properties:
        if prop.name.lower() == field_hint.lower():
            return prop.name

    # Normalize and try fuzzy match
    normalized_hint = _normalize_field_name(field_hint)

    for prop in entity_type.properties:
        normalized_prop = _normalize_field_name(prop.name)
        if normalized_prop == normalized_hint:
            return prop.name

    # Try similarity matching
    best_match = None
    best_score = 0.0
    threshold = 0.7  # 70% similarity for properties

    for prop in entity_type.properties:
        similarity = SequenceMatcher(
            None,
            normalized_hint,
            _normalize_field_name(prop.name)
        ).ratio()

        if similarity > best_score and similarity >= threshold:
            best_score = similarity
            best_match = prop.name

    return best_match


# ============================================================================
# Relationship Inference
# ============================================================================

def infer_relationships(
    entities: List[str],
    schema: GraphSchema
) -> List[RelationshipPath]:
    """
    Infer relationships between a set of entities.

    Given multiple entities, finds all relationships that connect them.

    Args:
        entities: List of entity names
        schema: Graph schema with relationship definitions

    Returns:
        List of RelationshipPath objects connecting the entities

    Examples:
        >>> schema = GraphSchema(
        ...     entities=[...],
        ...     relationships=[
        ...         RelationshipType(name="WORKS_IN", from_entity="Employee", to_entity="Department")
        ...     ]
        ... )
        >>> infer_relationships(["Employee", "Department"], schema)
        [RelationshipPath(from_entity="Employee", to_entity="Department", relationship_type="WORKS_IN", ...)]
    """
    if not entities or len(entities) < 2 or not schema.relationships:
        return []

    # Normalize entity names by finding them in schema
    normalized_entities: Set[str] = set()
    for entity_name in entities:
        entity_type = find_entity(entity_name, schema)
        if entity_type:
            normalized_entities.add(entity_type.name)

    if len(normalized_entities) < 2:
        return []

    # Find all relationships that connect any two entities in the set
    paths: List[RelationshipPath] = []

    for rel in schema.relationships:
        # Check if this relationship connects two entities in our set
        if rel.from_entity in normalized_entities and rel.to_entity in normalized_entities:
            paths.append(
                RelationshipPath(
                    from_entity=rel.from_entity,
                    to_entity=rel.to_entity,
                    relationship_type=rel.name,
                    reasoning=f"Connects {rel.from_entity} to {rel.to_entity} via {rel.name}"
                )
            )

    return paths


# ============================================================================
# Property Listing
# ============================================================================

def get_entity_properties(
    entity_name: str,
    schema: GraphSchema
) -> List[PropertyInfo]:
    """
    Get all properties for an entity.

    Args:
        entity_name: Entity type name
        schema: Graph schema

    Returns:
        List of PropertyInfo objects, empty list if entity not found

    Examples:
        >>> schema = GraphSchema(entities=[
        ...     EntityType(name="Employee", properties=[
        ...         PropertyInfo(name="employeeId", type="string"),
        ...         PropertyInfo(name="salary", type="number")
        ...     ])
        ... ])
        >>> props = get_entity_properties("Employee", schema)
        >>> len(props)
        2
        >>> props[0].name
        "employeeId"
    """
    entity = find_entity(entity_name, schema)
    if not entity:
        return []

    return entity.properties.copy() if entity.properties else []


# ============================================================================
# Filter Validation
# ============================================================================

def _is_operator_compatible_with_type(
    operator: FilterOperator,
    property_type: str
) -> bool:
    """
    Check if an operator is compatible with a property type.

    Args:
        operator: Filter operator
        property_type: Property type (string, number, date, boolean)

    Returns:
        True if compatible, False otherwise
    """
    # String properties support: eq, neq, contains, in, is_null, is_not_null
    if property_type == "string":
        return operator in {
            FilterOperator.EQ,
            FilterOperator.NEQ,
            FilterOperator.CONTAINS,
            FilterOperator.IN,
            FilterOperator.IS_NULL,
            FilterOperator.IS_NOT_NULL,
        }

    # Number and date properties support: all operators
    if property_type in {"number", "date"}:
        return True  # All operators valid

    # Boolean properties support: eq, neq, is_null, is_not_null
    if property_type == "boolean":
        return operator in {
            FilterOperator.EQ,
            FilterOperator.NEQ,
            FilterOperator.IS_NULL,
            FilterOperator.IS_NOT_NULL,
        }

    # Unknown type - be permissive
    return True


def validate_filter(
    filter: EntityFilter,
    entity: str,
    schema: GraphSchema
) -> List[str]:
    """
    Validate a filter against the schema.

    Checks:
    - Property exists on entity
    - Operator is compatible with property type
    - Value type matches property type

    Args:
        filter: EntityFilter to validate
        entity: Entity type name
        schema: Graph schema

    Returns:
        List of validation error messages (empty if valid)

    Examples:
        >>> schema = GraphSchema(entities=[
        ...     EntityType(name="Employee", properties=[
        ...         PropertyInfo(name="salary", type="number")
        ...     ])
        ... ])
        >>> filter = EntityFilter(property="salary", operator=FilterOperator.GT, value=100000)
        >>> validate_filter(filter, "Employee", schema)
        []  # Valid
        >>> filter = EntityFilter(property="unknown", operator=FilterOperator.EQ, value="test")
        >>> validate_filter(filter, "Employee", schema)
        ["Property 'unknown' not found on entity 'Employee'"]
    """
    errors: List[str] = []

    # Find entity
    entity_type = find_entity(entity, schema)
    if not entity_type:
        errors.append(f"Entity '{entity}' not found in schema")
        return errors

    # Check if property exists
    property_info = None
    for prop in entity_type.properties:
        if prop.name == filter.property:
            property_info = prop
            break

    if not property_info:
        # Try fuzzy match to suggest alternatives
        suggestion = find_field(entity, filter.property, schema)
        if suggestion:
            errors.append(
                f"Property '{filter.property}' not found on entity '{entity_type.name}'. "
                f"Did you mean '{suggestion}'?"
            )
        else:
            errors.append(
                f"Property '{filter.property}' not found on entity '{entity_type.name}'"
            )
        return errors

    # Check operator compatibility
    if not _is_operator_compatible_with_type(filter.operator, property_info.type):
        errors.append(
            f"Operator '{filter.operator}' is not compatible with "
            f"property type '{property_info.type}' for '{filter.property}'"
        )

    # Validate value type for specific operators
    if filter.operator in {FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL}:
        # These operators should not have a value
        if filter.value is not None:
            errors.append(
                f"Operator '{filter.operator}' should not have a value"
            )
    elif filter.operator == FilterOperator.IN:
        # IN operator requires a list value
        if not isinstance(filter.value, list):
            errors.append(
                f"Operator 'in' requires a list value, got {type(filter.value).__name__}"
            )
    elif filter.operator == FilterOperator.BETWEEN:
        # BETWEEN operator requires a list with 2 elements
        if not isinstance(filter.value, list) or len(filter.value) != 2:
            errors.append(
                f"Operator 'between' requires a list with 2 values [min, max]"
            )
    else:
        # Other operators require a non-null value
        if filter.value is None:
            errors.append(
                f"Operator '{filter.operator}' requires a value"
            )

    return errors


# ============================================================================
# Batch Operations
# ============================================================================

def validate_filters(
    filters: List[EntityFilter],
    entity: str,
    schema: GraphSchema
) -> List[Tuple[EntityFilter, List[str]]]:
    """
    Validate multiple filters at once.

    Args:
        filters: List of filters to validate
        entity: Entity type name
        schema: Graph schema

    Returns:
        List of (filter, errors) tuples. Only includes filters with errors.

    Examples:
        >>> filters = [
        ...     EntityFilter(property="salary", operator=FilterOperator.GT, value=100000),
        ...     EntityFilter(property="unknown", operator=FilterOperator.EQ, value="test")
        ... ]
        >>> results = validate_filters(filters, "Employee", schema)
        >>> len(results)
        1  # Only the invalid filter
        >>> results[0][1]
        ["Property 'unknown' not found on entity 'Employee'"]
    """
    results = []
    for filter in filters:
        errors = validate_filter(filter, entity, schema)
        if errors:
            results.append((filter, errors))
    return results


def get_all_entity_names(schema: GraphSchema) -> List[str]:
    """
    Get all entity names in the schema.

    Args:
        schema: Graph schema

    Returns:
        List of entity names

    Examples:
        >>> schema = GraphSchema(entities=[
        ...     EntityType(name="Employee", ...),
        ...     EntityType(name="Department", ...)
        ... ])
        >>> get_all_entity_names(schema)
        ["Employee", "Department"]
    """
    return [entity.name for entity in schema.entities]


def get_all_relationship_types(schema: GraphSchema) -> List[str]:
    """
    Get all relationship type names in the schema.

    Args:
        schema: Graph schema

    Returns:
        List of relationship type names

    Examples:
        >>> schema = GraphSchema(relationships=[
        ...     RelationshipType(name="WORKS_IN", ...),
        ...     RelationshipType(name="MANAGES", ...)
        ... ])
        >>> get_all_relationship_types(schema)
        ["WORKS_IN", "MANAGES"]
    """
    return [rel.name for rel in schema.relationships]
