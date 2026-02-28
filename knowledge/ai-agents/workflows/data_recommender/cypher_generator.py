"""
Cypher query generator for ScopeRecommendation.

This module generates Neo4j Cypher queries from ScopeRecommendation objects.

Primary path: Deterministic template-based generation for common patterns
Fallback path: LLM-assisted generation for complex patterns

Query Patterns:
- SINGLE_ENTITY: One entity type with filters (most common)
- SINGLE_HOP: Two entities connected by one relationship
- MULTI_HOP: Chain of entities connected by relationships
- COMPLEX: Patterns that don't fit templates (requires LLM)
"""

import asyncio
import json
import logging
from enum import Enum
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from app.core.model_factory import create_model

from .models import (
    ScopeRecommendation,
    EntityScope,
    RelationshipPath,
    EntityFilter,
    FilterOperator,
)
from .agent import GraphSchema
from .cypher_prompts import (
    CYPHER_CHEAT_SHEET,
    CYPHER_GENERATION_PROMPT,
    CYPHER_CORRECTION_PROMPT,
    format_schema_for_prompt,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Query Pattern Classification
# =============================================================================


class QueryPattern(str, Enum):
    """Classification of query complexity for template selection."""
    SINGLE_ENTITY = "single_entity"      # One entity, filters only
    SINGLE_HOP = "single_hop"            # Two entities, one relationship
    MULTI_HOP = "multi_hop"              # 3+ entities, chain
    COMPLEX = "complex"                  # Doesn't fit templates


class CypherGenerationResult(BaseModel):
    """Result of Cypher query generation."""
    query: str = Field(description="The generated Cypher query")
    method: str = Field(description="How the query was generated: 'deterministic' or 'llm'")
    pattern: QueryPattern = Field(description="The query pattern used")
    warnings: List[str] = Field(default_factory=list, description="Any warnings during generation")
    entity_aliases: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of entity types to their Cypher aliases (e.g., {'Employee': 'e'})"
    )


# =============================================================================
# Cypher Generator
# =============================================================================


class CypherGenerator:
    """
    Generates Cypher queries from ScopeRecommendation objects.

    Uses deterministic templates for common patterns and falls back to
    LLM-assisted generation for complex queries.
    """

    # Mapping of FilterOperator to Cypher WHERE clause templates
    # {alias} = node alias, {prop} = property name, {value} = formatted value
    # Case-insensitive toLower() wrapping is applied dynamically in _filter_to_cypher
    # based on the actual value type (strings only, not numbers/booleans).
    OPERATOR_TEMPLATES = {
        FilterOperator.EQ: "{alias}.{prop} = {value}",
        FilterOperator.NEQ: "{alias}.{prop} <> {value}",
        FilterOperator.GT: "{alias}.{prop} > {value}",
        FilterOperator.GTE: "{alias}.{prop} >= {value}",
        FilterOperator.LT: "{alias}.{prop} < {value}",
        FilterOperator.LTE: "{alias}.{prop} <= {value}",
        FilterOperator.CONTAINS: "toLower({alias}.{prop}) CONTAINS toLower({value})",
        FilterOperator.IN: "{alias}.{prop} IN {value}",
        FilterOperator.BETWEEN: "{value_min} <= {alias}.{prop} <= {value_max}",
        FilterOperator.IS_NULL: "{alias}.{prop} IS NULL",
        FilterOperator.IS_NOT_NULL: "{alias}.{prop} IS NOT NULL",
    }

    def __init__(self, schema: GraphSchema, use_llm_fallback: bool = True):
        """
        Initialize the Cypher generator.

        Args:
            schema: Graph schema for validation
            use_llm_fallback: Whether to use LLM for complex patterns
        """
        self.schema = schema
        self.use_llm_fallback = use_llm_fallback

        # Build schema lookups for validation
        self._entity_names = {e.name for e in schema.entities}
        self._property_lookup: Dict[str, set] = {}
        for entity in schema.entities:
            self._property_lookup[entity.name] = {p.name for p in entity.properties}

    def generate(self, recommendation: ScopeRecommendation) -> CypherGenerationResult:
        """
        Generate Cypher query from scope recommendation.

        Args:
            recommendation: The scope recommendation to convert

        Returns:
            CypherGenerationResult with query and metadata

        Raises:
            ValueError: If query cannot be generated
        """
        # Classify the query pattern
        pattern = self._classify_pattern(recommendation)
        logger.debug(f"Query pattern classified as: {pattern}")

        # Validate against schema
        validation_errors = self.validate(recommendation)
        if validation_errors:
            logger.warning(f"Schema validation warnings: {validation_errors}")

        # Try deterministic generation for supported patterns
        if pattern != QueryPattern.COMPLEX:
            try:
                query, aliases = self._generate_deterministic(recommendation, pattern)
                if query:
                    return CypherGenerationResult(
                        query=query,
                        method="deterministic",
                        pattern=pattern,
                        warnings=validation_errors,
                        entity_aliases=aliases
                    )
            except Exception as e:
                logger.warning(f"Deterministic generation failed: {e}")

        # Fall back to LLM for complex patterns
        if self.use_llm_fallback:
            return self._generate_with_llm(recommendation, validation_errors)

        raise ValueError(f"Cannot generate Cypher for pattern: {pattern}")

    def _classify_pattern(self, rec: ScopeRecommendation) -> QueryPattern:
        """
        Classify scope recommendation into a query pattern.

        Args:
            rec: Scope recommendation to classify

        Returns:
            QueryPattern indicating the complexity
        """
        entity_count = len(rec.entities)
        rel_count = len(rec.relationships)

        if entity_count == 0:
            return QueryPattern.COMPLEX

        if rel_count == 0:
            # No relationships - just entity filters
            if entity_count == 1:
                return QueryPattern.SINGLE_ENTITY
            else:
                # Multiple unrelated entities - each needs separate query
                # For now, treat as complex (could be union later)
                return QueryPattern.COMPLEX

        elif entity_count == 2 and rel_count == 1:
            return QueryPattern.SINGLE_HOP

        elif entity_count > 2 and rel_count >= entity_count - 1:
            # Chain pattern: N entities need at least N-1 relationships
            return QueryPattern.MULTI_HOP

        else:
            return QueryPattern.COMPLEX

    def _generate_deterministic(
        self,
        rec: ScopeRecommendation,
        pattern: QueryPattern
    ) -> tuple[Optional[str], Dict[str, str]]:
        """
        Generate Cypher using deterministic templates.

        Args:
            rec: Scope recommendation
            pattern: Query pattern to use

        Returns:
            Tuple of (query_string, entity_aliases) or (None, {}) if failed
        """
        if pattern == QueryPattern.SINGLE_ENTITY:
            return self._generate_single_entity(rec)
        elif pattern == QueryPattern.SINGLE_HOP:
            return self._generate_single_hop(rec)
        elif pattern == QueryPattern.MULTI_HOP:
            return self._generate_multi_hop(rec)

        return None, {}

    def _generate_single_entity(self, rec: ScopeRecommendation) -> tuple[str, Dict[str, str]]:
        """
        Generate query for single entity with filters.

        Pattern:
            MATCH (alias:EntityType)
            WHERE <filters>
            RETURN alias
        """
        entity = rec.entities[0]
        alias = self._get_alias(entity.entity_type)
        aliases = {entity.entity_type: alias}

        # Build MATCH clause
        match_clause = f"MATCH ({alias}:{entity.entity_type})"

        # Build WHERE clause
        where_conditions = self._build_where_conditions(entity, alias)
        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

        # Build RETURN clause with DISTINCT
        return_clause = f"RETURN DISTINCT {alias}"

        # Assemble query
        parts = [match_clause]
        if where_clause:
            parts.append(where_clause)
        parts.append(return_clause)
        query = "\n".join(parts)
        return query, aliases

    def _generate_single_hop(self, rec: ScopeRecommendation) -> tuple[str, Dict[str, str]]:
        """
        Generate query for two entities with one relationship.

        Pattern:
            MATCH (a:Entity1)-[r:REL]->(b:Entity2)
            WHERE <filters on a> AND <filters on b>
            RETURN a, b
        """
        # Get entities and relationship
        rel = rec.relationships[0]
        from_entity = next((e for e in rec.entities if e.entity_type == rel.from_entity), None)
        to_entity = next((e for e in rec.entities if e.entity_type == rel.to_entity), None)

        if not from_entity or not to_entity:
            raise ValueError(f"Relationship entities not found in scope: {rel.from_entity} -> {rel.to_entity}")

        # Generate aliases
        alias_a = self._get_alias(from_entity.entity_type)
        alias_b = self._get_alias(to_entity.entity_type, exclude=[alias_a])
        aliases = {
            from_entity.entity_type: alias_a,
            to_entity.entity_type: alias_b
        }

        # Build MATCH clause with relationship
        match_clause = (
            f"MATCH ({alias_a}:{from_entity.entity_type})"
            f"-[r:{rel.relationship_type}]->"
            f"({alias_b}:{to_entity.entity_type})"
        )

        # Build WHERE conditions for both entities
        where_conditions = []
        where_conditions.extend(self._build_where_conditions(from_entity, alias_a))
        where_conditions.extend(self._build_where_conditions(to_entity, alias_b))

        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

        # Build RETURN clause with DISTINCT
        return_clause = f"RETURN DISTINCT {alias_a}, {alias_b}"

        # Assemble query
        parts = [match_clause]
        if where_clause:
            parts.append(where_clause)
        parts.append(return_clause)

        query = "\n".join(parts)
        return query, aliases

    def _generate_multi_hop(self, rec: ScopeRecommendation) -> tuple[str, Dict[str, str]]:
        """
        Generate query for chain of entities with relationships.

        Pattern:
            MATCH (a:E1)-[:R1]->(b:E2)-[:R2]->(c:E3)
            WHERE <filters>
            RETURN a, b, c
        """
        # Build the relationship chain
        # Start with first relationship and follow the chain
        if not rec.relationships:
            raise ValueError("No relationships for multi-hop query")

        # Build entity order from relationships
        entity_order = self._build_entity_chain(rec)
        if not entity_order:
            raise ValueError("Could not build entity chain from relationships")

        # Generate aliases
        aliases = {}
        used_aliases = []
        for entity_type in entity_order:
            alias = self._get_alias(entity_type, exclude=used_aliases)
            aliases[entity_type] = alias
            used_aliases.append(alias)

        # Build MATCH pattern
        match_parts = []
        for i, entity_type in enumerate(entity_order):
            alias = aliases[entity_type]

            if i == 0:
                match_parts.append(f"({alias}:{entity_type})")
            else:
                # Find relationship from previous entity
                prev_entity = entity_order[i - 1]
                rel = self._find_relationship(rec, prev_entity, entity_type)
                if rel:
                    match_parts.append(f"-[:{rel.relationship_type}]->({alias}:{entity_type})")
                else:
                    # Try reverse direction
                    rel = self._find_relationship(rec, entity_type, prev_entity)
                    if rel:
                        match_parts.append(f"<-[:{rel.relationship_type}]-({alias}:{entity_type})")
                    else:
                        raise ValueError(f"No relationship found between {prev_entity} and {entity_type}")

        match_clause = "MATCH " + "".join(match_parts)

        # Build WHERE conditions for all entities
        where_conditions = []
        for entity_type in entity_order:
            entity = next((e for e in rec.entities if e.entity_type == entity_type), None)
            if entity:
                where_conditions.extend(self._build_where_conditions(entity, aliases[entity_type]))

        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

        # Build RETURN clause with DISTINCT
        return_aliases = [aliases[et] for et in entity_order]
        return_clause = f"RETURN DISTINCT {', '.join(return_aliases)}"

        # Assemble query
        parts = [match_clause]
        if where_clause:
            parts.append(where_clause)
        parts.append(return_clause)

        query = "\n".join(parts)
        return query, aliases

    def _build_entity_chain(self, rec: ScopeRecommendation) -> List[str]:
        """
        Build ordered list of entities from relationship chain.

        Returns:
            List of entity types in traversal order
        """
        if not rec.relationships:
            return [e.entity_type for e in rec.entities]

        # Build adjacency for traversal
        entity_types = {e.entity_type for e in rec.entities}
        outgoing: Dict[str, List[tuple[str, str]]] = {et: [] for et in entity_types}
        incoming: Dict[str, List[tuple[str, str]]] = {et: [] for et in entity_types}

        for rel in rec.relationships:
            if rel.from_entity in entity_types and rel.to_entity in entity_types:
                outgoing[rel.from_entity].append((rel.to_entity, rel.relationship_type))
                incoming[rel.to_entity].append((rel.from_entity, rel.relationship_type))

        # Find start node (has outgoing but no incoming, or most outgoing)
        start = None
        for et in entity_types:
            if outgoing[et] and not incoming[et]:
                start = et
                break

        if not start:
            # Just pick first entity with outgoing relationships
            for et in entity_types:
                if outgoing[et]:
                    start = et
                    break

        if not start:
            return [e.entity_type for e in rec.entities]

        # BFS to build chain
        chain = [start]
        visited = {start}

        while True:
            current = chain[-1]
            next_entity = None

            # Try outgoing first
            for target, _ in outgoing[current]:
                if target not in visited:
                    next_entity = target
                    break

            # Then try incoming (reverse traversal)
            if not next_entity:
                for source, _ in incoming[current]:
                    if source not in visited:
                        next_entity = source
                        break

            if not next_entity:
                break

            chain.append(next_entity)
            visited.add(next_entity)

        return chain

    def _find_relationship(
        self,
        rec: ScopeRecommendation,
        from_entity: str,
        to_entity: str
    ) -> Optional[RelationshipPath]:
        """Find relationship between two entities."""
        for rel in rec.relationships:
            if rel.from_entity == from_entity and rel.to_entity == to_entity:
                return rel
        return None

    def _build_where_conditions(self, entity: EntityScope, alias: str) -> List[str]:
        """
        Build WHERE clause conditions for an entity's filters.

        Args:
            entity: Entity scope with filters
            alias: Cypher alias for this entity

        Returns:
            List of WHERE condition strings
        """
        conditions = []

        for filter in entity.filters:
            condition = self._filter_to_cypher(filter, alias)
            if condition:
                conditions.append(condition)

        return conditions

    def _filter_to_cypher(self, filter: EntityFilter, alias: str) -> Optional[str]:
        """
        Convert a single filter to Cypher WHERE condition.

        Args:
            filter: The filter to convert
            alias: Node alias in the query

        Returns:
            Cypher condition string or None
        """
        op = filter.operator
        prop = filter.property

        if op == FilterOperator.IS_NULL:
            return f"{alias}.{prop} IS NULL"

        if op == FilterOperator.IS_NOT_NULL:
            return f"{alias}.{prop} IS NOT NULL"

        if op == FilterOperator.BETWEEN:
            if not isinstance(filter.value, list) or len(filter.value) != 2:
                logger.warning(f"BETWEEN filter requires list of 2 values, got: {filter.value}")
                return None
            val_min = self._format_value(filter.value[0])
            val_max = self._format_value(filter.value[1])
            return f"{val_min} <= {alias}.{prop} <= {val_max}"

        if op == FilterOperator.IN:
            if not isinstance(filter.value, list):
                logger.warning(f"IN filter requires list value, got: {filter.value}")
                return None
            # Case-insensitive only when all values are strings
            if all(isinstance(v, str) for v in filter.value):
                formatted_values = [f"toLower({self._format_value(v)})" for v in filter.value]
                return f"toLower({alias}.{prop}) IN [{', '.join(formatted_values)}]"
            else:
                formatted_values = [self._format_value(v) for v in filter.value]
                return f"{alias}.{prop} IN [{', '.join(formatted_values)}]"

        # Standard operators
        template = self.OPERATOR_TEMPLATES.get(op)
        if not template:
            logger.warning(f"Unknown operator: {op}")
            return None

        formatted_value = self._format_value(filter.value)

        # Case-insensitive wrapping for string values on EQ/NEQ
        if isinstance(filter.value, str) and op in (FilterOperator.EQ, FilterOperator.NEQ):
            prop_expr = f"toLower({alias}.{prop})"
            val_expr = f"toLower({formatted_value})"
            operator_symbol = "=" if op == FilterOperator.EQ else "<>"
            return f"{prop_expr} {operator_symbol} {val_expr}"

        return template.format(alias=alias, prop=prop, value=formatted_value)

    def _format_value(self, value: Any) -> str:
        """
        Format a Python value for Cypher query.

        Args:
            value: The value to format

        Returns:
            Cypher-formatted string
        """
        if value is None:
            return "NULL"

        if isinstance(value, bool):
            # Cypher uses lowercase booleans
            return "true" if value else "false"

        if isinstance(value, str):
            # Escape single quotes and wrap in quotes
            escaped = value.replace("\\", "\\\\").replace("'", "\\'")
            return f"'{escaped}'"

        if isinstance(value, (int, float)):
            return str(value)

        if isinstance(value, list):
            formatted = [self._format_value(v) for v in value]
            return f"[{', '.join(formatted)}]"

        # Fallback: stringify and quote
        return f"'{str(value)}'"

    def _get_alias(self, entity_type: str, exclude: List[str] = None) -> str:
        """
        Generate a short alias for an entity type.

        Args:
            entity_type: The entity type name
            exclude: Aliases already in use

        Returns:
            Short alias (e.g., 'e' for Employee, 'p' for Patient)
        """
        exclude = exclude or []

        # Try first letter lowercase
        base = entity_type[0].lower()
        if base not in exclude:
            return base

        # Try first two letters
        base = entity_type[:2].lower()
        if base not in exclude:
            return base

        # Try full word lowercase with counter
        for i in range(1, 100):
            candidate = f"{entity_type[0].lower()}{i}"
            if candidate not in exclude:
                return candidate

        return entity_type.lower()

    def validate(self, recommendation: ScopeRecommendation) -> List[str]:
        """
        Validate scope recommendation against schema.

        Args:
            recommendation: The scope to validate

        Returns:
            List of validation error/warning messages
        """
        errors = []

        for entity in recommendation.entities:
            # Check entity exists
            if entity.entity_type not in self._entity_names:
                errors.append(f"Unknown entity type: {entity.entity_type}")
                continue

            # Check properties exist
            valid_props = self._property_lookup.get(entity.entity_type, set())
            for filter in entity.filters:
                if filter.property not in valid_props:
                    errors.append(
                        f"Unknown property '{filter.property}' on entity '{entity.entity_type}'"
                    )

        # Check relationships reference valid entities
        for rel in recommendation.relationships:
            if rel.from_entity not in self._entity_names:
                errors.append(f"Relationship references unknown entity: {rel.from_entity}")
            if rel.to_entity not in self._entity_names:
                errors.append(f"Relationship references unknown entity: {rel.to_entity}")

        return errors

    def _generate_with_llm(
        self,
        recommendation: ScopeRecommendation,
        validation_errors: List[str]
    ) -> CypherGenerationResult:
        """
        Generate Cypher using LLM for complex patterns.

        Uses pydantic-ai Agent for one-shot query generation.

        Args:
            recommendation: Scope recommendation
            validation_errors: Any validation warnings

        Returns:
            CypherGenerationResult with LLM-generated query
        """
        # Run the async method synchronously
        return asyncio.get_event_loop().run_until_complete(
            self._generate_with_llm_async(recommendation, validation_errors)
        )

    async def _generate_with_llm_async(
        self,
        recommendation: ScopeRecommendation,
        validation_errors: List[str]
    ) -> CypherGenerationResult:
        """
        Async implementation of LLM-based Cypher generation.

        Args:
            recommendation: Scope recommendation
            validation_errors: Any validation warnings

        Returns:
            CypherGenerationResult with LLM-generated query
        """
        logger.info("Using LLM fallback for Cypher generation")

        # Build the prompt
        schema_summary = format_schema_for_prompt(self.schema)
        scope_json = recommendation.model_dump_json(indent=2)

        prompt = CYPHER_GENERATION_PROMPT.format(
            cheat_sheet=CYPHER_CHEAT_SHEET,
            schema_summary=schema_summary,
            scope_json=scope_json
        )

        # Create a simple agent for one-shot generation
        model = create_model()
        agent = Agent(
            model=model,
            system_prompt="You are a Neo4j Cypher query expert. Generate only valid Cypher queries.",
        )
        agent.model_settings = {"temperature": 0.1}  # Low temperature for precise queries

        try:
            result = await agent.run(prompt)
            query = self._clean_llm_response(result.data)

            logger.debug(f"LLM generated query: {query}")

            # Extract aliases from the generated query (best effort)
            aliases = self._extract_aliases_from_query(query, recommendation)

            return CypherGenerationResult(
                query=query,
                method="llm",
                pattern=QueryPattern.COMPLEX,
                warnings=validation_errors,
                entity_aliases=aliases
            )

        except Exception as e:
            logger.error(f"LLM Cypher generation failed: {e}")
            raise ValueError(f"Failed to generate Cypher query: {e}")

    async def correct_with_llm(
        self,
        original_query: str,
        error_message: str,
        recommendation: ScopeRecommendation
    ) -> str:
        """
        Attempt to correct a failed Cypher query using LLM.

        Args:
            original_query: The query that failed
            error_message: Error message from execution
            recommendation: Original scope recommendation

        Returns:
            Corrected Cypher query string
        """
        logger.info(f"Attempting LLM correction for failed query")

        schema_summary = format_schema_for_prompt(self.schema)
        scope_json = recommendation.model_dump_json(indent=2)

        prompt = CYPHER_CORRECTION_PROMPT.format(
            original_query=original_query,
            error_message=error_message,
            schema_summary=schema_summary,
            scope_json=scope_json,
            cheat_sheet=CYPHER_CHEAT_SHEET
        )

        model = create_model()
        agent = Agent(
            model=model,
            system_prompt="You are a Neo4j Cypher query expert. Fix the query based on the error.",
        )
        agent.model_settings = {"temperature": 0.1}

        try:
            result = await agent.run(prompt)
            corrected_query = self._clean_llm_response(result.data)
            logger.debug(f"LLM corrected query: {corrected_query}")
            return corrected_query

        except Exception as e:
            logger.error(f"LLM query correction failed: {e}")
            raise ValueError(f"Failed to correct Cypher query: {e}")

    def _clean_llm_response(self, response: str) -> str:
        """
        Clean LLM response to extract just the Cypher query.

        Removes markdown code blocks, explanations, etc.

        Args:
            response: Raw LLM response

        Returns:
            Clean Cypher query string
        """
        text = response.strip()

        # Remove markdown code blocks
        if text.startswith("```"):
            # Find the content between ``` markers
            lines = text.split("\n")
            content_lines = []
            in_block = False

            for line in lines:
                if line.startswith("```"):
                    in_block = not in_block
                    continue
                if in_block:
                    content_lines.append(line)

            if content_lines:
                text = "\n".join(content_lines).strip()

        # Remove common prefixes
        prefixes_to_remove = [
            "cypher",
            "neo4j",
            "Here is the query:",
            "Here's the query:",
            "The query is:",
        ]
        for prefix in prefixes_to_remove:
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].strip()

        return text

    def _extract_aliases_from_query(
        self,
        query: str,
        recommendation: ScopeRecommendation
    ) -> Dict[str, str]:
        """
        Best-effort extraction of entity aliases from generated query.

        Args:
            query: The generated Cypher query
            recommendation: Original scope recommendation

        Returns:
            Dict mapping entity types to aliases
        """
        import re

        aliases = {}

        # Look for MATCH (alias:EntityType) patterns
        pattern = r'\((\w+):(\w+)\)'
        matches = re.findall(pattern, query)

        for alias, entity_type in matches:
            if entity_type in aliases:
                continue  # Keep first occurrence
            aliases[entity_type] = alias

        return aliases

    # =========================================================================
    # Per-Entity Traversal Query Generation
    # =========================================================================

    async def generate_entity_queries(
        self,
        recommendation: ScopeRecommendation,
    ) -> Dict[str, str]:
        """
        Generate per-entity Cypher queries with relationship traversal.

        Builds a tree rooted at the primary entity using BFS, then generates
        a MATCH path from root to each entity. Handles branching graphs correctly
        (unlike a linear chain approach).

        Each entity's query traverses from the primary entity to itself, applying
        ALL filters along the path. Only the RETURN clause differs per entity.

        Returns:
            Dict mapping entity_type -> Cypher query string
        """
        entity_queries: Dict[str, str] = {}

        if not recommendation.entities:
            return entity_queries

        if not recommendation.relationships:
            # No relationships — each entity gets its own simple query
            for entity in recommendation.entities:
                entity_queries[entity.entity_type] = self._build_simple_query(entity)
            return entity_queries

        # Build traversal tree from primary entity, generate path-based queries
        entity_queries = self._build_path_queries(recommendation)
        return entity_queries

    def _build_simple_query(self, entity: EntityScope) -> str:
        """Build a simple single-entity query with filters."""
        alias = self._get_alias(entity.entity_type)
        match_clause = f"MATCH ({alias}:{entity.entity_type})"
        where_conditions = self._build_where_conditions(entity, alias)
        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        parts = [match_clause]
        if where_clause:
            parts.append(where_clause)
        parts.append(f"RETURN DISTINCT {alias}")
        return "\n".join(parts)

    def _build_path_queries(self, rec: ScopeRecommendation) -> Dict[str, str]:
        """
        Build per-entity queries by finding paths from primary entity to each target.

        Uses BFS to build a tree of shortest paths from the primary entity,
        then generates a MATCH pattern for each entity following its path.
        Handles branching graphs correctly.
        """
        entity_lookup = {e.entity_type: e for e in rec.entities}
        entity_types = set(entity_lookup.keys())

        # Find primary entity (first with relevance_level='primary', or just first)
        primary = next(
            (e for e in rec.entities if e.relevance_level == "primary"),
            rec.entities[0]
        )

        # Build adjacency list (bidirectional for path finding)
        # Each entry: (neighbor_type, relationship_type, is_forward)
        adjacency: Dict[str, List[tuple]] = {et: [] for et in entity_types}
        for rel in rec.relationships:
            if rel.from_entity in entity_types and rel.to_entity in entity_types:
                adjacency[rel.from_entity].append(
                    (rel.to_entity, rel.relationship_type, True)
                )
                adjacency[rel.to_entity].append(
                    (rel.from_entity, rel.relationship_type, False)
                )

        # BFS from primary entity to find shortest path to every other entity
        # parent[entity_type] = (parent_type, relationship_type, is_forward)
        parent: Dict[str, Optional[tuple]] = {primary.entity_type: None}
        queue = [primary.entity_type]
        visited = {primary.entity_type}

        while queue:
            current = queue.pop(0)
            for neighbor, rel_type, is_forward in adjacency.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    parent[neighbor] = (current, rel_type, is_forward)
                    queue.append(neighbor)

        # Generate aliases for all entities
        aliases: Dict[str, str] = {}
        used_aliases: List[str] = []
        for entity_type in entity_types:
            alias = self._get_alias(entity_type, exclude=used_aliases)
            aliases[entity_type] = alias
            used_aliases.append(alias)

        # Collect all WHERE conditions keyed by entity type
        all_conditions: Dict[str, List[str]] = {}
        for entity_type, entity in entity_lookup.items():
            if entity_type in aliases:
                conditions = self._build_where_conditions(entity, aliases[entity_type])
                if conditions:
                    all_conditions[entity_type] = conditions

        # Generate one query per entity
        entity_queries: Dict[str, str] = {}

        for target_type in entity_types:
            if target_type not in parent:
                # Disconnected entity — simple query
                entity_queries[target_type] = self._build_simple_query(
                    entity_lookup[target_type]
                )
                continue

            # Reconstruct path from primary to target
            path = []  # List of (entity_type, rel_type, is_forward) steps
            current = target_type
            while parent.get(current) is not None:
                parent_type, rel_type, is_forward = parent[current]
                path.append((current, rel_type, is_forward))
                current = parent_type
            path.reverse()  # Now goes primary -> ... -> target

            # Build MATCH pattern following the path
            match_parts = [f"({aliases[primary.entity_type]}:{primary.entity_type})"]
            entities_in_path = [primary.entity_type]

            for step_entity, rel_type, is_forward in path:
                step_alias = aliases[step_entity]
                if is_forward:
                    match_parts.append(
                        f"-[:{rel_type}]->({step_alias}:{step_entity})"
                    )
                else:
                    match_parts.append(
                        f"<-[:{rel_type}]-({step_alias}:{step_entity})"
                    )
                entities_in_path.append(step_entity)

            match_clause = "MATCH " + "".join(match_parts)

            # Collect WHERE conditions for all entities in this path
            where_parts: List[str] = []
            for et in entities_in_path:
                where_parts.extend(all_conditions.get(et, []))

            where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

            # Build query
            target_alias = aliases[target_type]
            parts = [match_clause]
            if where_clause:
                parts.append(where_clause)
            parts.append(f"RETURN DISTINCT {target_alias}")

            entity_queries[target_type] = "\n".join(parts)

        return entity_queries

    # =========================================================================
    # Preview Query Methods (for Build Query / Preview Data UI)
    # =========================================================================

    def generate_count_query(self, entity_scope: EntityScope) -> str:
        """
        Generate a COUNT query for an entity scope.

        Used for getting total record count without fetching all data.

        Args:
            entity_scope: Entity definition with filters

        Returns:
            Cypher COUNT query string

        Example output:
            MATCH (e:Employee)
            WHERE e.status = 'active' AND e.salary > 100000
            RETURN count(e) as total
        """
        alias = self._get_alias(entity_scope.entity_type)

        # Build MATCH clause
        match_clause = f"MATCH ({alias}:{entity_scope.entity_type})"

        # Build WHERE clause from filters
        where_conditions = self._build_where_conditions(entity_scope, alias)
        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

        # Build RETURN count clause with DISTINCT
        return_clause = f"RETURN count(DISTINCT {alias}) as total"

        # Assemble query
        parts = [match_clause]
        if where_clause:
            parts.append(where_clause)
        parts.append(return_clause)

        return "\n".join(parts)

    def generate_single_entity_preview(
        self,
        entity_scope: EntityScope,
        limit: int = 25,
        offset: int = 0
    ) -> str:
        """
        Generate a paginated preview query for a single entity.

        Used for the Preview Data tab to fetch sample records with pagination.

        Args:
            entity_scope: Entity definition with filters
            limit: Max records to return (default 25)
            offset: Skip first N records (default 0)

        Returns:
            Cypher query string with SKIP and LIMIT

        Example output:
            MATCH (e:Employee)
            WHERE e.status = 'active' AND e.salary > 100000
            RETURN e
            SKIP 0
            LIMIT 25
        """
        alias = self._get_alias(entity_scope.entity_type)

        # Build MATCH clause
        match_clause = f"MATCH ({alias}:{entity_scope.entity_type})"

        # Build WHERE clause from filters
        where_conditions = self._build_where_conditions(entity_scope, alias)
        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

        # Build RETURN clause with DISTINCT and pagination
        return_clause = f"RETURN DISTINCT {alias}"
        skip_clause = f"SKIP {offset}"
        limit_clause = f"LIMIT {limit}"

        # Assemble query
        parts = [match_clause]
        if where_clause:
            parts.append(where_clause)
        parts.append(return_clause)
        parts.append(skip_clause)
        parts.append(limit_clause)

        return "\n".join(parts)

    async def validate_scope_queries(
        self,
        entities: List[EntityScope],
        graphql_client: Optional[Any] = None
    ) -> Dict[str, dict]:
        """
        Validate queries execute without error using LIMIT 1.

        Args:
            entities: List of EntityScope objects to validate
            graphql_client: Optional GraphQL client for live validation

        Returns:
            Dict mapping entity_type to validation result:
            {
                "EntityType": {
                    "valid": True/False,
                    "query": "MATCH ...",
                    "error": None or "error message"
                }
            }
        """
        results = {}

        for entity in entities:
            try:
                # Generate query with LIMIT 1 for validation
                query = self.generate_single_entity_preview(entity, limit=1, offset=0)
                validation = {
                    "valid": True,
                    "query": query,
                    "error": None
                }

                # If we have a GraphQL client, actually execute the query
                if graphql_client:
                    try:
                        await graphql_client.nodes_by_cypher(query)
                    except Exception as e:
                        validation["valid"] = False
                        validation["error"] = str(e)
                        logger.warning(
                            f"Query validation failed for {entity.entity_type}: {e}"
                        )

                results[entity.entity_type] = validation

            except Exception as e:
                results[entity.entity_type] = {
                    "valid": False,
                    "query": None,
                    "error": str(e)
                }
                logger.error(
                    f"Query generation failed for {entity.entity_type}: {e}"
                )

        return results
