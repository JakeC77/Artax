"""
Data Scope Recommendation Agent

This module provides conversational scope building using Pydantic AI with streaming.

Design:
- ScopeBuilder class orchestrates the conversation (following IntentBuilder pattern)
- Agent has tools: update_scope, ask_clarification, explore_graph_data
- Streaming text with discrete scope updates via tool calls
- Embodies Theo's persona (parsimonious, pattern-recognizing, efficient)
"""

import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext, ModelRetry
from pydantic_ai.models import KnownModelName
import logfire
from logfire import ConsoleOptions

from app.workflows.data_recommender.config import load_config
from app.workflows.theo.models import IntentPackage
from app.utils.streaming import stream_agent_text

from .models import (
    ScopeRecommendation,
    EntityScope,
    RelationshipPath,
    EntityFilter,
    FieldOfInterest,
    ClarificationOption,
    ClarificationQuestion,
    ScopePreview,
    # New unified state models
    ScopeState,
    QueryStructure,
    ScopeExecutionResults,
    ScopeMetadata,
    ScopeUIState,
    EntityPreviewData,
    # Diff helper for SSE integration
    compute_scope_diff,
)
from .prompts import (
    get_theo_persona,
    SCOPE_INTERVIEW_INSTRUCTIONS,
    SCHEMA_CONTEXT_TEMPLATE,
    INTENT_CONTEXT_TEMPLATE,
)


# =============================================================================
# Helper Functions
# =============================================================================


def sanitize_messages(messages: List[Any]) -> List[Any]:
    """
    Sanitize message list to ensure no null content values.

    Why: pydantic-ai's result.new_messages() can return ToolReturnMessage
    objects with None content when streaming with tool calls. The LLM API
    rejects null content values.

    Args:
        messages: List of message objects from result.new_messages()

    Returns:
        Same list with null content values replaced with empty strings
    """
    for msg in messages:
        # Handle messages that have a content attribute that could be None
        if hasattr(msg, 'content') and msg.content is None:
            msg.content = ""
        # Handle messages with 'parts' that might have None content
        if hasattr(msg, 'parts'):
            for part in msg.parts:
                if hasattr(part, 'content') and part.content is None:
                    part.content = ""
    return messages


# =============================================================================
# Schema Models (for agent context)
# =============================================================================


class PropertyInfo(BaseModel):
    """Property information for an entity."""
    name: str = Field(description="Property name (e.g., 'salary', 'hireDate')")
    type: str = Field(description="Property type (string, number, date, boolean)")
    description: Optional[str] = Field(default=None, description="Human-readable description of this property")
    min_value: Optional[str] = Field(default=None, description="Minimum value from rangeInfo (for numeric/date types)")
    max_value: Optional[str] = Field(default=None, description="Maximum value from rangeInfo (for numeric/date types)")


class EntityType(BaseModel):
    """Entity type definition from the graph schema."""
    name: str = Field(description="Entity type name (e.g., 'Employee', 'Department')")
    description: Optional[str] = Field(default=None, description="Human-readable description of this entity type")
    count: Optional[int] = Field(default=None, description="Number of nodes of this type in the graph")
    properties: List[PropertyInfo] = Field(
        default_factory=list,
        description="Available properties on this entity"
    )


class RelationshipType(BaseModel):
    """Relationship type definition."""
    name: str = Field(description="Relationship type (e.g., 'WORKS_IN', 'MANAGES')")
    from_entity: str = Field(description="Source entity type")
    to_entity: str = Field(description="Target entity type")


class SuggestedPattern(BaseModel):
    """Suggested Cypher query pattern from the graph schema."""
    name: str = Field(description="Pattern name (e.g., 'Medication Coverage')")
    description: Optional[str] = Field(default=None, description="What this pattern does")
    cypher_pattern: Optional[str] = Field(default=None, description="Cypher pattern template")
    example_query: Optional[str] = Field(default=None, description="Example Cypher query")


class GraphSchema(BaseModel):
    """
    Simplified schema representation for the agent.

    This is a subset of the full graph schema focused on what the agent
    needs to make scope recommendations.
    """
    entities: List[EntityType] = Field(
        description="Available entity types in the graph"
    )
    relationships: List[RelationshipType] = Field(
        default_factory=list,
        description="Available relationship types"
    )
    suggested_patterns: List[SuggestedPattern] = Field(
        default_factory=list,
        description="Suggested Cypher query patterns from the graph schema"
    )


# =============================================================================
# Logfire Configuration
# =============================================================================


def _configure_logfire():
    """Configure Logfire with Geodesic framework patterns."""
    import os

    environment = os.getenv("ENVIRONMENT", "development")
    if environment in ("sandbox", "production"):
        return

    repo_root = Path(__file__).parent.parent.parent.parent
    logfire_dir = repo_root / ".logfire"

    # Only show console output if explicitly enabled
    # CLI mode should be clean - no debug timestamps
    verbose_mode = os.getenv("LOGFIRE_VERBOSE", "false").lower() == "true"
    console_enabled = os.getenv("LOGFIRE_CONSOLE", "false").lower() == "true"

    logfire.configure(
        send_to_logfire='if-token-present',
        config_dir=logfire_dir if logfire_dir.exists() else None,
        service_name='data_recommender',
        environment='development',
        console=ConsoleOptions(verbose=verbose_mode) if console_enabled else False
    )

    logfire.instrument_pydantic_ai()


_configure_logfire()


# =============================================================================
# ScopeBuilder State
# =============================================================================


@dataclass
class ScopeBuilderState:
    """
    State for the scope builder conversation.

    Contains all context needed for scope recommendations:
    - User's intent (what they want to accomplish)
    - Graph schema (what data is available)
    - Sample data (shows actual value formats)
    - Current scope preview (updated via tool calls)
    - Unified scope state (for Build Query / Preview Data UI)
    - Clarification handling
    """

    # Inputs
    intent_package: IntentPackage
    graph_schema: GraphSchema
    sample_data: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    # For query execution (count estimation)
    tenant_id: Optional[str] = None
    workspace_id: Optional[str] = None

    # Log streamer for emitting events (None = CLI mode)
    log_streamer: Optional[Any] = None

    # CLI mode flag
    cli_mode: bool = False

    # Current scope (updated via tool calls) - legacy format
    current_scope: Optional[ScopePreview] = None

    # NEW: Unified scope state for Build Query / Preview Data UI
    scope_state: Optional[ScopeState] = None

    # NEW: Preview executor for fetching preview data (injected from workflow)
    preview_executor: Optional[Any] = None

    # NEW: Preview cache - invalidated on any scope change
    preview_cache: Dict[str, EntityPreviewData] = field(default_factory=dict)

    # Clarification handling
    pending_clarification: Optional[ClarificationQuestion] = None

    # Turn management
    _tools_locked: bool = False  # Set by ask_clarification, blocks further tool calls
    scope_ready: bool = False  # Set by update_scope when ready=True

    # Final state
    scope_finalized: bool = False
    final_recommendation: Optional[ScopeRecommendation] = None

    def get_schema_summary(self) -> str:
        """
        Generate a human-readable summary of the schema for the agent.

        Returns:
            Formatted string describing available entities, properties, and relationships
        """
        lines = []

        lines.append("### Entities and Properties")
        lines.append("")
        for entity in self.graph_schema.entities:
            header = f"**{entity.name}**"
            if entity.count is not None:
                header += f" ({entity.count:,} nodes)"
            lines.append(header)
            if entity.description:
                lines.append(f"  {entity.description}")
            if entity.properties:
                # Group properties: those with ranges or descriptions shown individually,
                # others grouped by type for compactness
                props_individual = []
                props_by_type = {}

                for prop in entity.properties:
                    if prop.min_value is not None or prop.max_value is not None or prop.description:
                        props_individual.append(prop)
                    else:
                        if prop.type not in props_by_type:
                            props_by_type[prop.type] = []
                        props_by_type[prop.type].append(prop.name)

                # Show properties with ranges/descriptions individually
                for prop in props_individual:
                    parts = [f"  - {prop.name} ({prop.type})"]
                    if prop.min_value is not None and prop.max_value is not None:
                        parts.append(f"range: {prop.min_value} to {prop.max_value}")
                    elif prop.min_value is not None:
                        parts.append(f"min: {prop.min_value}")
                    elif prop.max_value is not None:
                        parts.append(f"max: {prop.max_value}")
                    if prop.description:
                        parts.append(prop.description)
                    lines.append(" — ".join(parts))

                # Show grouped properties without ranges/descriptions
                for prop_type, prop_names in props_by_type.items():
                    lines.append(f"  - {prop_type}: {', '.join(prop_names)}")
            else:
                lines.append("  - (no properties defined)")
            lines.append("")

        if self.graph_schema.relationships:
            lines.append("### Relationships")
            lines.append("")
            for rel in self.graph_schema.relationships:
                lines.append(f"- `(:{rel.from_entity})-[:{rel.name}]->(:{rel.to_entity})`")

        if self.graph_schema.suggested_patterns:
            lines.append("")
            lines.append("### Suggested Query Patterns")
            lines.append("")
            for pattern in self.graph_schema.suggested_patterns:
                lines.append(f"**{pattern.name}**")
                if pattern.description:
                    lines.append(f"  {pattern.description}")
                if pattern.example_query:
                    lines.append(f"  ```cypher")
                    lines.append(f"  {pattern.example_query}")
                    lines.append(f"  ```")
                lines.append("")

        return "\n".join(lines)

    def get_sample_data_summary(self) -> str:
        """
        Generate a human-readable summary of sample data for the agent.

        Returns:
            Formatted string showing sample records for each entity type
        """
        if not self.sample_data:
            return ""

        lines = []
        lines.append("### Sample Data (for understanding value formats)")
        lines.append("")
        lines.append("**IMPORTANT:** These samples show the DATA FORMAT and VALUE TYPES only.")
        lines.append("They are NOT representative of all possible values in the dataset.")
        lines.append("Use these to understand HOW values are stored (e.g., `\"True\"` as a string vs `true` as boolean),")
        lines.append("but do NOT assume these are the only acceptable values.")
        lines.append("")

        for entity_type, samples in self.sample_data.items():
            if not samples:
                continue

            lines.append(f"**{entity_type}** (showing {len(samples)} sample records):")

            for i, sample in enumerate(samples, 1):
                filtered_sample = {k: v for k, v in sample.items() if v is not None}

                if len(filtered_sample) > 8:
                    keys = list(filtered_sample.keys())[:8]
                    filtered_sample = {k: filtered_sample[k] for k in keys}
                    filtered_sample["..."] = "(more properties)"

                props_str = ", ".join(
                    f'{k}: {repr(v)}'
                    for k, v in filtered_sample.items()
                )
                lines.append(f"  {i}. {{{props_str}}}")

            lines.append("")

        return "\n".join(lines)


# =============================================================================
# CLI Output Helpers
# =============================================================================


def _print_scope_update(scope: ScopePreview):
    """Print scope update to CLI in a readable format."""
    print("\n" + "-" * 50)
    print("📋 SCOPE UPDATE")
    print("-" * 50)
    print(f"Summary: {scope.summary}")
    print(f"Confidence: {scope.confidence}")

    if scope.entities:
        print(f"\nEntities ({len(scope.entities)}):")
        for e in scope.entities:
            filters_str = ""
            if e.filters:
                filters_str = " | Filters: " + ", ".join(
                    f"{f.property} {f.operator.value if hasattr(f.operator, 'value') else f.operator} {f.value}"
                    for f in e.filters
                )
            print(f"  • {e.entity_type} ({e.relevance_level}){filters_str}")

    if scope.relationships:
        print(f"\nRelationships ({len(scope.relationships)}):")
        for r in scope.relationships:
            print(f"  • {r.from_entity} --[{r.relationship_type}]--> {r.to_entity}")

    print("-" * 50 + "\n")


def _print_clarification(question: ClarificationQuestion):
    """Print clarification question to CLI."""
    print("\n" + "=" * 50)
    print("❓ CLARIFICATION NEEDED")
    print("=" * 50)
    print(f"\n{question.question}")

    if question.context:
        print(f"\n(Why: {question.context})")

    print("\nOptions:")
    for i, opt in enumerate(question.options, 1):
        rec = " ⭐ (recommended)" if opt.recommended else ""
        print(f"  {i}. {opt.label}{rec}")
        print(f"     {opt.description}")

    if question.allows_other:
        print(f"\n  Or type your own answer.")

    print("=" * 50)


# =============================================================================
# Schema Validation
# =============================================================================


def _validate_scope_against_schema(
    entities: List["EntityScope"],
    relationships: List["RelationshipPath"],
    schema: "GraphSchema",
) -> List[str]:
    """
    Validate entity types and relationship triples against the graph schema.

    Returns a list of error strings. Empty list means all valid.
    """
    errors: List[str] = []
    valid_entity_names = {e.name for e in schema.entities}

    # Build relationship lookups
    rels_from: Dict[str, List[tuple]] = {}  # entity -> [(rel_name, to_entity), ...]
    rels_to: Dict[str, List[tuple]] = {}    # entity -> [(rel_name, from_entity), ...]
    valid_triples: set = set()              # {(name, from, to)}

    for rel in schema.relationships:
        rels_from.setdefault(rel.from_entity, []).append((rel.name, rel.to_entity))
        rels_to.setdefault(rel.to_entity, []).append((rel.name, rel.from_entity))
        valid_triples.add((rel.name, rel.from_entity, rel.to_entity))

    # Validate entity types
    for entity in entities:
        if entity.entity_type and entity.entity_type not in valid_entity_names:
            errors.append(
                f'ERROR: "{entity.entity_type}" is not a valid entity type.\n'
                f"Available entity types: {', '.join(sorted(valid_entity_names))}"
            )

    # Validate relationships
    for rel in relationships:
        if not rel.relationship_type:
            continue

        triple = (rel.relationship_type, rel.from_entity, rel.to_entity)
        if triple in valid_triples:
            continue  # Valid

        lines = [f'ERROR: "{rel.relationship_type}" is not a valid relationship from {rel.from_entity} to {rel.to_entity}.']

        # Show valid outbound from from_entity
        outbound = rels_from.get(rel.from_entity, [])
        if outbound:
            lines.append(f"Valid outbound relationships from {rel.from_entity}:")
            for rname, to_ent in outbound:
                lines.append(f"  - {rname} -> {to_ent}")
        elif rel.from_entity in valid_entity_names:
            lines.append(f"{rel.from_entity} has no outbound relationships in the schema.")

        # Show valid inbound to to_entity
        inbound = rels_to.get(rel.to_entity, [])
        if inbound:
            lines.append(f"Valid inbound relationships to {rel.to_entity}:")
            for rname, from_ent in inbound:
                lines.append(f"  - {rname} (from {from_ent})")
        elif rel.to_entity in valid_entity_names:
            lines.append(f"{rel.to_entity} has no inbound relationships in the schema.")

        # Check if reverse direction exists
        reverse_matches = [
            (rname, fe, te)
            for (rname, fe, te) in valid_triples
            if fe == rel.to_entity and te == rel.from_entity
        ]
        if reverse_matches:
            for rname, fe, te in reverse_matches:
                lines.append(
                    f'Did you mean to start from {fe} using {rname}? '
                    f'(:{fe})-[:{rname}]->(:{te})'
                )

        errors.append("\n".join(lines))

    return errors


def _format_schema_for_entity(entity_name: str, schema: "GraphSchema") -> str:
    """
    Format schema information (relationships, properties) for a specific entity type.

    Returns a human-readable summary the agent can use to verify relationship names
    before calling update_scope().
    """
    valid_entity_names = {e.name for e in schema.entities}
    if entity_name not in valid_entity_names:
        return (
            f"Unknown entity type '{entity_name}'. "
            f"Available entity types: {', '.join(sorted(valid_entity_names))}"
        )

    lines = [f"=== Schema for {entity_name} ==="]

    # Outbound relationships
    outbound = [
        r for r in schema.relationships if r.from_entity == entity_name
    ]
    if outbound:
        lines.append("Outbound relationships:")
        for r in outbound:
            lines.append(f"  - (:{entity_name})-[:{r.name}]->(:{r.to_entity})")
    else:
        lines.append("Outbound relationships: (none)")

    # Inbound relationships
    inbound = [
        r for r in schema.relationships if r.to_entity == entity_name
    ]
    if inbound:
        lines.append("Inbound relationships:")
        for r in inbound:
            lines.append(f"  - (:{r.from_entity})-[:{r.name}]->(:{entity_name})")
    else:
        lines.append("Inbound relationships: (none)")

    # Properties
    entity_def = next((e for e in schema.entities if e.name == entity_name), None)
    if entity_def and entity_def.properties:
        prop_strs = [f"{p.name} ({p.type})" for p in entity_def.properties]
        lines.append(f"Properties: {', '.join(prop_strs)}")

    return "\n".join(lines)


# =============================================================================
# Tool Definitions
# =============================================================================


def create_scope_tools():
    """
    Create scope building tools.

    Tools are decorated functions that the agent can call to:
    - update_scope: Update the visual scope preview (with optional ready flag)
    - ask_clarification: Present structured question to user
    - explore_graph_data: Fetch sample nodes and neighbors to understand data values
    """

    async def update_scope(
        ctx: RunContext[ScopeBuilderState],
        summary: str,
        confidence: str = "medium",
        entities: Optional[List[dict]] = None,
        relationships: Optional[List[dict]] = None,
        primary_entity: Optional[str] = None,
        ready: bool = False,
    ) -> str:
        """
        Update the scope preview shown to the user.

        Args:
            summary: Natural language summary of current scope understanding (REQUIRED)
            confidence: 'high', 'medium', or 'low' (default: 'medium')
            entities: List of entity specs [{entity_type, relevance_level, filters?, fields_of_interest?}]
            relationships: List of relationship paths [{from_entity, to_entity, relationship_type}]
            primary_entity: The main entity being queried (optional, defaults to first entity with relevance_level='primary')
            ready: Set True when scope is ready for user to proceed (high confidence, no questions remain)

        Returns:
            Confirmation message
        """
        if ctx.deps._tools_locked:
            raise ModelRetry(
                "Clarification questions are pending user response. "
                "Generate your text response to the user now. Do not call any more tools."
            )

        # Default to empty lists if not provided
        entities = entities or []
        relationships = relationships or []

        # Store previous state for diff computation
        previous_state = ctx.deps.scope_state

        # Parse entities into EntityScope objects
        parsed_entities = []
        for e in entities:
            filters = []
            for f in e.get("filters", []):
                filters.append(EntityFilter(
                    property=f.get("property", ""),
                    operator=f.get("operator", "eq"),
                    value=f.get("value"),
                    reasoning=f.get("reasoning")
                ))

            # Parse fields_of_interest properly
            fields_of_interest = []
            for foi in e.get("fields_of_interest", []):
                if isinstance(foi, dict):
                    fields_of_interest.append(FieldOfInterest(
                        field=foi.get("field", ""),
                        justification=foi.get("justification", "")
                    ))
                elif isinstance(foi, FieldOfInterest):
                    fields_of_interest.append(foi)

            # Defensive fallback: ensure reasoning is never None
            reasoning = e.get("reasoning")
            if not reasoning:
                relevance = e.get("relevance_level", "primary")
                reasoning = f"{relevance.capitalize()} entity for the analysis"

            parsed_entities.append(EntityScope(
                entity_type=e.get("entity_type", ""),
                filters=filters,
                relevance_level=e.get("relevance_level", "primary"),
                fields_of_interest=fields_of_interest,
                reasoning=reasoning,
            ))

        # Parse relationships into RelationshipPath objects
        parsed_relationships = []
        for r in relationships:
            parsed_relationships.append(RelationshipPath(
                from_entity=r.get("from_entity", ""),
                to_entity=r.get("to_entity", ""),
                relationship_type=r.get("relationship_type", ""),
                reasoning=r.get("reasoning")
            ))

        # ─── Schema validation: entity types and relationships ───
        validation_errors = _validate_scope_against_schema(
            parsed_entities, parsed_relationships, ctx.deps.graph_schema
        )

        if validation_errors:
            # Still store scope state so UI shows what was attempted
            ctx.deps.current_scope = ScopePreview(
                entities=parsed_entities,
                relationships=parsed_relationships,
                summary=summary,
                confidence=confidence,
            )
            error_block = "SCHEMA VALIDATION ERRORS:\n\n" + "\n\n".join(validation_errors)
            error_block += "\n\nFIX REQUIRED: Correct relationship types to match the schema exactly. Relationships are DIRECTIONAL."
            return error_block

        # Store current scope in state (legacy format for backwards compatibility)
        ctx.deps.current_scope = ScopePreview(
            entities=parsed_entities,
            relationships=parsed_relationships,
            summary=summary,
            confidence=confidence
        )

        # Determine primary entity
        determined_primary = primary_entity
        if not determined_primary and parsed_entities:
            # Find first entity with relevance_level='primary', or just use first one
            primary_ent = next(
                (e for e in parsed_entities if e.relevance_level == "primary"),
                parsed_entities[0]
            )
            determined_primary = primary_ent.entity_type

        # Build the unified ScopeState
        query = QueryStructure(
            primary_entity=determined_primary,
            entities=parsed_entities,
            relationships=parsed_relationships,
        )

        # Determine update summary for tracking
        update_summary = None
        if ctx.deps.scope_state:
            # Calculate what changed
            old_entity_count = len(ctx.deps.scope_state.query.entities)
            new_entity_count = len(parsed_entities)
            if new_entity_count > old_entity_count:
                update_summary = f"Added {new_entity_count - old_entity_count} entity(ies)"
            elif new_entity_count < old_entity_count:
                update_summary = f"Removed {old_entity_count - new_entity_count} entity(ies)"
            else:
                update_summary = "Updated scope"

        # Build new ScopeState (immutable pattern)
        old_version = ctx.deps.scope_state.metadata.version if ctx.deps.scope_state else 0
        ctx.deps.scope_state = ScopeState(
            query=query,
            results=ScopeExecutionResults(),  # Clear preview cache on scope change
            metadata=ScopeMetadata(
                natural_language_summary=summary,
                confidence=confidence,
                version=old_version + 1,
                last_update_summary=update_summary,
            ),
            ui_state=ScopeUIState(
                active_tab="build_query",
                can_stage=confidence == "high",
                preview_loading=False,
                has_pending_clarification=False,
            ),
        )

        # Clear preview cache since scope changed
        ctx.deps.preview_cache = {}

        # Compute diff for UI highlighting
        diff = compute_scope_diff(previous_state, ctx.deps.scope_state)

        # Generate traversal queries for entities
        entity_queries: Dict[str, str] = {}
        try:
            from .cypher_generator import CypherGenerator
            generator = CypherGenerator(ctx.deps.graph_schema, use_llm_fallback=True)
            entity_queries = await generator.generate_entity_queries(
                ScopeRecommendation(
                    entities=parsed_entities,
                    relationships=parsed_relationships,
                    summary=summary,
                    confidence_level=confidence,
                )
            )
            # Set query on each entity
            for entity in parsed_entities:
                if entity.entity_type in entity_queries:
                    object.__setattr__(entity, 'query', entity_queries[entity.entity_type])
        except Exception as e:
            logfire.warning(f"Query generation failed: {e}")

        # Execute queries for estimated counts (if tenant_id available)
        if ctx.deps.tenant_id and entity_queries:
            try:
                from .graphql_client import GraphQLClient
                client = GraphQLClient(
                    workspace_id=ctx.deps.workspace_id or "",
                    tenant_id=ctx.deps.tenant_id,
                )

                async def count_entity(entity_type: str, cypher_query: str) -> tuple:
                    nodes = await client.nodes_by_cypher(cypher_query)
                    return entity_type, len(nodes)

                count_tasks = [
                    count_entity(et, q) for et, q in entity_queries.items()
                ]
                count_results = await asyncio.gather(*count_tasks, return_exceptions=True)

                for result in count_results:
                    if isinstance(result, Exception):
                        logfire.warning(f"Count query failed: {result}")
                        continue
                    entity_type, count = result
                    for entity in parsed_entities:
                        if entity.entity_type == entity_type:
                            object.__setattr__(entity, 'estimated_count', count)
                            break
            except Exception as e:
                logfire.warning(f"Count execution failed: {e}")

        # Build count summary for agent feedback
        count_lines: list[str] = []
        zero_warnings: list[str] = []

        for entity in parsed_entities:
            et = entity.entity_type
            count = getattr(entity, 'estimated_count', None)

            if count is not None:
                if count == 0:
                    # Look up total nodes from schema (already loaded, zero API cost)
                    schema_entity = next(
                        (e for e in ctx.deps.graph_schema.entities if e.name == et), None
                    )
                    total = schema_entity.count if schema_entity and schema_entity.count is not None else None

                    count_lines.append(f"  {et}: 0 *** ZERO RESULTS ***")

                    if total is not None and total > 0:
                        zero_warnings.append(
                            f"  WARNING: {et} = 0 results (but {total:,} total {et} nodes exist "
                            f"— filters or traversal path may be too restrictive)"
                        )
                    elif total == 0:
                        zero_warnings.append(
                            f"  WARNING: {et} = 0 results (0 total {et} nodes in workspace "
                            f"— entity type may not exist or is empty)"
                        )
                    else:
                        zero_warnings.append(
                            f"  WARNING: {et} = 0 results (total node count unknown — investigate)"
                        )
                else:
                    count_lines.append(f"  {et}: {count:,}")

        # Set ready state from parameter (LLM decides when scope is ready)
        ctx.deps.scope_ready = ready

        # When ready, build the final recommendation so end_data_scoping can use it
        if ready and ctx.deps.current_scope:
            ctx.deps.final_recommendation = ScopeRecommendation(
                entities=ctx.deps.current_scope.entities,
                relationships=ctx.deps.current_scope.relationships,
                summary=summary,
                requires_clarification=False,
                clarification_questions=[],
                confidence_level=confidence,
            )

        # Output to CLI or event stream
        if ctx.deps.cli_mode:
            _print_scope_update(ctx.deps.current_scope)
        elif ctx.deps.log_streamer:
            # Emit scope_updated event with flat frontend format
            await ctx.deps.log_streamer.log_event(
                event_type="scope_updated",
                message=summary,
                agent_id="theo",
                metadata={
                    "scope_state": ctx.deps.scope_state.to_frontend_format(),
                    "ready": ready,
                    "update_summary": update_summary,
                    "changed_entities": diff["changed_entities"],
                    "is_new_entity": diff["is_new_entity"],
                    "added_filter_ids": diff["added_filter_ids"],
                    "added_field_names": diff["added_field_names"],
                    "version": ctx.deps.scope_state.metadata.version,
                    # Legacy fields for backwards compatibility
                    "entities": [e.model_dump() for e in ctx.deps.current_scope.entities],
                    "relationships": [r.model_dump() for r in ctx.deps.current_scope.relationships],
                    "summary": summary,
                    "confidence": confidence,
                }
            )

        logfire.info("Scope preview updated",
                    entity_count=len(parsed_entities),
                    relationship_count=len(parsed_relationships),
                    confidence=confidence,
                    version=ctx.deps.scope_state.metadata.version,
                    ready=ready)

        if count_lines:
            parts = ["Scope preview updated. Entity counts:"]
            parts.extend(count_lines)
            if zero_warnings:
                parts.append("")
                parts.append("DIAGNOSTICS:")
                parts.extend(zero_warnings)
                parts.append("")
                parts.append(
                    "ACTION REQUIRED: Investigate 0-count entities before setting ready=True. "
                    "Consider: relaxing filters, checking property values/types match the data, "
                    "calling explore_graph_data() to see actual node values, or asking the user."
                )
            return "\n".join(parts)
        else:
            return "Scope preview updated and shown to user."

    async def ask_clarification(
        ctx: RunContext[ScopeBuilderState],
        question_id: str,
        question: str,
        options: List[dict],
        context: Optional[str] = None,
        affects_entities: Optional[List[str]] = None,
    ) -> str:
        """
        Ask the user a clarification question with structured options.

        IMPORTANT RULES:
        - Only call this ONCE per turn
        - Provide 2-5 concrete options with label AND description
        - Mark one as recommended if you have a suggestion
        - After calling this, STOP and wait for user response

        Args:
            question_id: Unique identifier (e.g., "high_cost_definition")
            question: The question to ask
            options: List of {label: str, description: str, recommended?: bool}
            context: Why you're asking (helps user understand)
            affects_entities: Which entities this impacts

        Returns:
            Instruction to wait for user response
        """
        # Parse options into ClarificationOption objects
        parsed_options = []
        for o in options:
            parsed_options.append(ClarificationOption(
                label=o.get("label", ""),
                description=o.get("description", ""),
                recommended=o.get("recommended", False)
            ))

        # Store pending question
        ctx.deps.pending_clarification = ClarificationQuestion(
            question_id=question_id,
            question=question,
            context=context,
            options=parsed_options,
            allows_other=True,
            affects_entities=affects_entities or []
        )

        # Output to CLI or event stream
        if ctx.deps.cli_mode:
            _print_clarification(ctx.deps.pending_clarification)
        elif ctx.deps.log_streamer:
            if hasattr(ctx.deps.log_streamer, "flush"):
                await ctx.deps.log_streamer.flush()
            await ctx.deps.log_streamer.log_event(
                event_type="clarification_needed",
                # message=question,
                agent_id="theo",
                metadata={
                    "question_id": question_id,
                    "question": question,
                    "context": context,
                    "options": [o.model_dump() for o in parsed_options],
                    "affects_entities": affects_entities or [],
                }
            )
            if hasattr(ctx.deps.log_streamer, "flush"):
                await ctx.deps.log_streamer.flush()

        logfire.info("Clarification requested",
                    question_id=question_id,
                    option_count=len(parsed_options))

        ctx.deps._tools_locked = True

        return "Clarification questions displayed to user. Generate your text response now."

    async def explore_graph_data(
        ctx: RunContext[ScopeBuilderState],
        entity_type: Optional[str] = None,
        include_neighbors: bool = True,
        show_schema_for: Optional[str] = None,
    ) -> str:
        """
        Fetch unfiltered sample nodes and their neighbors to understand actual data values,
        or show schema relationship info for an entity type.

        Call this to diagnose zero-count entities, understand property value formats,
        see how the graph is structured around specific entity types, or check valid
        relationships for an entity before calling update_scope().

        Args:
            entity_type: Specific entity to explore (e.g. "Employee"). If omitted,
                         explores ALL entities in the current scope (3 samples each).
            include_neighbors: Whether to fetch 1-hop connected nodes (default True)
            show_schema_for: Entity type to show schema relationships for (e.g. "Employee").
                            When provided, returns valid relationships and properties from
                            the schema without making any API calls. Takes priority over
                            entity_type if both are provided.

        Returns:
            Formatted summary of sample nodes and their neighbors, or schema info
        """
        if ctx.deps._tools_locked:
            raise ModelRetry(
                "Clarification questions are pending user response. "
                "Generate your text response to the user now. Do not call any more tools."
            )

        # ─── show_schema_for mode: return schema relationships, no API calls ───
        if show_schema_for:
            return _format_schema_for_entity(show_schema_for, ctx.deps.graph_schema)

        # Determine which entities to explore
        if entity_type:
            # Validate against schema
            valid_names = {e.name for e in ctx.deps.graph_schema.entities}
            if entity_type not in valid_names:
                return (
                    f"Unknown entity type '{entity_type}'. "
                    f"Available types: {', '.join(sorted(valid_names))}"
                )
            targets = [(entity_type, 5, 3)]  # (type, sample_size, max_neighbors)
        elif ctx.deps.scope_state and ctx.deps.scope_state.query.entities:
            targets = [
                (e.entity_type, 3, 2)
                for e in ctx.deps.scope_state.query.entities[:10]
            ]
        else:
            return (
                "No entity type specified and no scope defined yet. "
                "Either provide an entity_type or call update_scope() first."
            )

        if not ctx.deps.tenant_id:
            return "Graph exploration requires a workspace connection (no tenant_id available)."

        from .graphql_client import GraphQLClient

        client = GraphQLClient(
            workspace_id=ctx.deps.workspace_id or "",
            tenant_id=ctx.deps.tenant_id,
        )

        output_sections: list[str] = []

        for target_type, sample_size, max_neighbor_nodes in targets:
            try:
                # Fetch unfiltered sample nodes
                cypher = f"MATCH (n:{target_type}) RETURN n LIMIT {sample_size}"
                nodes = await client.nodes_by_cypher(cypher)

                if not nodes:
                    output_sections.append(
                        f"=== {target_type} (0 nodes found — entity may be empty) ==="
                    )
                    continue

                lines: list[str] = [
                    f"=== {target_type} ({len(nodes)} samples, unfiltered) ==="
                ]

                for i, node in enumerate(nodes, 1):
                    # Format properties compactly, truncating long values
                    props = {
                        k: (v[:97] + "..." if isinstance(v, str) and len(v) > 100 else v)
                        for k, v in node.properties.items()
                    }
                    props_str = ", ".join(f'{k}: {repr(v)}' for k, v in props.items())
                    lines.append(f"Node {i} ({node.id}): {{{props_str}}}")

                    # Fetch neighbors for first N nodes
                    if include_neighbors and i <= max_neighbor_nodes:
                        try:
                            result = await client.fetch_neighbors(node.id)
                            neighbor_nodes = result.get("nodes", [])
                            edges = result.get("edges", [])

                            if edges:
                                # Build edge lookup: edge -> (type, direction relative to this node)
                                for edge in edges[:8]:  # Cap displayed neighbors
                                    edge_type = edge.get("type", "UNKNOWN")
                                    from_id = edge.get("fromId", "")
                                    to_id = edge.get("toId", "")

                                    # Find the neighbor node
                                    neighbor_id = to_id if from_id == node.id else from_id
                                    neighbor = next(
                                        (n for n in neighbor_nodes if n.id == neighbor_id),
                                        None
                                    )

                                    if neighbor:
                                        n_label = neighbor.labels[0] if neighbor.labels else "?"
                                        # Show a few key properties of the neighbor
                                        n_props = dict(list(neighbor.properties.items())[:3])
                                        n_props_str = ", ".join(
                                            f'{k}: {repr(v)}' for k, v in n_props.items()
                                        )
                                        if from_id == node.id:
                                            lines.append(
                                                f"    -[{edge_type}]-> {n_label} {{{n_props_str}}}"
                                            )
                                        else:
                                            lines.append(
                                                f"    <-[{edge_type}]- {n_label} {{{n_props_str}}}"
                                            )
                            elif not neighbor_nodes:
                                lines.append("    (no neighbors)")
                        except Exception as e:
                            lines.append(f"    (neighbor fetch failed: {e})")

                output_sections.append("\n".join(lines))

            except Exception as e:
                output_sections.append(
                    f"=== {target_type} (exploration failed: {e}) ==="
                )

        full_output = "\n\n".join(output_sections)

        # Emit event for frontend
        if ctx.deps.log_streamer:
            await ctx.deps.log_streamer.log_event(
                event_type="graph_explored",
                message=f"Explored {len(targets)} entity type(s)",
                agent_id="theo",
                metadata={
                    "entity_types": [t[0] for t in targets],
                    "include_neighbors": include_neighbors,
                }
            )

        logfire.info("Graph data explored",
                    entity_types=[t[0] for t in targets],
                    include_neighbors=include_neighbors)

        return full_output

    return [update_scope, ask_clarification, explore_graph_data]


# =============================================================================
# Agent Creation
# =============================================================================


def create_scope_agent(
    temperature: float = None
) -> Agent[ScopeBuilderState, str]:
    """
    Create the data scope recommendation agent.

    Args:
        temperature: Optional temperature override. If not provided, uses workflow config.

    Returns:
        Configured Pydantic AI agent with scope building tools
    """
    # Get configuration from workflow config
    config = load_config()
    temp = temperature if temperature is not None else config.scope_builder_temperature

    model_instance = config.scope_builder_model.create()

    agent = Agent(
        model=model_instance,
        deps_type=ScopeBuilderState,
        system_prompt=get_theo_persona(),
        retries=config.scope_builder_retries
    )

    # get_model_settings() handles provider-specific settings like Google thinking config
    agent.model_settings = config.scope_builder_model.get_model_settings(temperature_override=temp)

    # Inject scope interview instructions
    @agent.instructions
    def inject_scope_instructions(ctx: RunContext[ScopeBuilderState]) -> str:
        """Inject scope interview instructions."""
        return SCOPE_INTERVIEW_INSTRUCTIONS

    # Inject schema context dynamically
    @agent.instructions
    def inject_schema_context(ctx: RunContext[ScopeBuilderState]) -> str:
        """Inject the workspace schema information."""
        schema_summary = ctx.deps.get_schema_summary()
        return SCHEMA_CONTEXT_TEMPLATE.format(schema_summary=schema_summary)

    # Inject intent context dynamically
    @agent.instructions
    def inject_intent_context(ctx: RunContext[ScopeBuilderState]) -> str:
        """Inject the user's intent information."""
        intent = ctx.deps.intent_package
        return INTENT_CONTEXT_TEMPLATE.format(
            intent_title=intent.title,
            intent_objective=intent.mission.objective,
            intent_why=intent.mission.why,
            intent_success=intent.mission.success_looks_like,
            intent_summary=intent.summary
        )

    # Inject sample data context if available
    @agent.instructions
    def inject_sample_data_context(ctx: RunContext[ScopeBuilderState]) -> str:
        """Inject sample data to help agent understand value formats."""
        sample_summary = ctx.deps.get_sample_data_summary()
        if sample_summary:
            return f"""
## SAMPLE DATA

{sample_summary}

Use this sample data to understand the exact format and type of values stored in each property.
For example, if you see `requiresDocumentation: 'True'` (a string), your filter should use `value="True"` not `value=true`.
"""
        return ""

    # Register scope building tools
    for tool_func in create_scope_tools():
        agent.tool(tool_func)

    return agent


# =============================================================================
# ScopeBuilder Class
# =============================================================================


class ScopeBuilder:
    """
    Orchestrates the conversation with Theo to build a data scope recommendation.

    Similar to IntentBuilder but for data scoping. Uses streaming for text
    and tool calls for scope updates and clarification questions.
    """

    def __init__(self, model: KnownModelName = None):
        """
        Initialize the Scope Builder.

        Args:
            model: Optional model name override. If not provided, uses workflow config.
        """
        # Get configuration from workflow config
        config = load_config()
        self.model = model or str(config.scope_builder_model)
        self.agent = create_scope_agent()

    async def get_next_user_message(
        self,
        message_source: Optional[Any] = None,
        timeout: Optional[float] = None
    ) -> tuple[Optional[str], str]:
        """
        Get next user message or control event from message source (event stream) or stdin.

        Args:
            message_source: EventStreamReader instance or None for stdin
            timeout: Optional timeout in seconds for event stream reads

        Returns:
            Tuple of (message, event_type):
            - ("message text", "user_message") for normal user messages
            - (None, "end_data_scoping") when user confirms scope via UI button
            - (None, "quit") if quit/exit or timeout
            - (None, "empty") if empty input (retry)
        """
        if message_source is None:
            # CLI mode: use stdin
            try:
                user_input = input("\nYou: ").strip()
                if user_input.lower() in ['quit', 'exit']:
                    return None, "quit"
                if user_input.lower() in ['confirm', 'done', 'finalize']:
                    # CLI simulation of end_data_scoping
                    return None, "end_data_scoping"
                return (user_input, "user_message") if user_input else (None, "empty")
            except (EOFError, KeyboardInterrupt):
                return None, "quit"
        else:
            # Event stream mode: read from stream
            try:
                # Wait for user_message OR end_data_scoping event
                event = await message_source.wait_for_event(
                    event_type=["user_message", "end_data_scoping"],
                    timeout=timeout
                )

                if event:
                    event_type = event.get("event_type", "user_message")

                    if event_type == "end_data_scoping":
                        logfire.info("Received end_data_scoping event - user confirmed scope")
                        return None, "end_data_scoping"

                    # Regular user message
                    user_message = event.get("message", "").strip()
                    if user_message.lower() in ['quit', 'exit']:
                        return None, "quit"
                    return (user_message, "user_message") if user_message else (None, "empty")
                else:
                    # Timeout
                    return None, "quit"
            except Exception as e:
                logfire.error("Error reading from event stream", error=str(e))
                return None, "quit"

    def _build_initial_prompt(self, state: ScopeBuilderState) -> str:
        """
        Build the initial prompt for starting the scope interview.

        Args:
            state: Current scope builder state

        Returns:
            Initial prompt for the agent
        """
        return f"""You're starting a data scope interview. The user's intent:

**Intent**: {state.intent_package.title}
**Objective**: {state.intent_package.mission.objective}

On this first turn:
1. Start with a brief greeting (1 sentence)
2. Call update_scope() with your initial recommendation based on the intent and schema
3. Call ask_clarification() for any questions you need answered (you can ask multiple)
4. Generate a short text summary of what you've recommended and what you're asking

The system will automatically pause for the user to respond after your turn."""

    async def _stream_response_cli(
        self,
        prompt: str,
        state: ScopeBuilderState,
        message_history: list
    ) -> tuple[str, list]:
        """
        Stream agent response to CLI, printing text as it arrives.

        Returns:
            Tuple of (final_text, new_messages)
        """
        print("\nTheo: ", end="", flush=True)

        full_text = ""
        new_messages = []

        async for event in self.agent.run_stream_events(
            prompt,
            deps=state,
            message_history=message_history
        ):
            from pydantic_ai import AgentRunResultEvent
            from pydantic_ai.messages import PartDeltaEvent, TextPartDelta

            if isinstance(event, PartDeltaEvent):
                if isinstance(event.delta, TextPartDelta):
                    chunk = event.delta.content_delta
                    print(chunk, end="", flush=True)
                    full_text += chunk

            elif isinstance(event, AgentRunResultEvent):
                if event.result:
                    new_messages = list(event.result.new_messages())

        print()  # Newline after streaming
        return full_text, new_messages

    def _check_for_malformed_tool_call(self, message_history: list) -> bool:
        """Check if the last model response had a malformed tool call (Gemini-specific).

        When Gemini returns MALFORMED_FUNCTION_CALL, pydantic-ai maps it to
        finish_reason='error' and drops the tool call. The agent produces text
        claiming it called the tool, but it never actually executed.

        Returns:
            True if a malformed tool call was detected.
        """
        from pydantic_ai.messages import ModelResponse
        for msg in reversed(message_history):
            if isinstance(msg, ModelResponse):
                if msg.finish_reason == 'error':
                    details = msg.provider_details or {}
                    raw_reason = details.get('finish_reason', 'unknown')
                    logfire.warning(
                        f"Model response ended with error: finish_reason='{raw_reason}'. "
                        f"The model likely attempted a tool call that was malformed. "
                        f"Text was returned but no tool was executed."
                    )
                    return True
                break
        return False

    async def _run_agent_turn(
        self,
        prompt: str,
        state: ScopeBuilderState,
        message_history: list,
        log_streamer=None,
        cli_mode: bool = False,
    ) -> tuple[str, list]:
        """
        Run one agent turn. Resets tool lock, invokes agent, returns output.

        Returns:
            Tuple of (agent_text, new_messages)
        """
        state._tools_locked = False  # Reset lock at start of each turn
        max_malformed_retries = 2

        for attempt in range(max_malformed_retries + 1):
            if cli_mode:
                theo_message, new_msgs = await self._stream_response_cli(
                    prompt, state, message_history
                )
                new_msgs = sanitize_messages(new_msgs)
                message_history.extend(new_msgs)
            elif log_streamer:
                async def on_batch(batch_text: str, acc_len: int, part_idx, metadata: dict):
                    await log_streamer.log_event(
                        event_type="agent_message",
                        message=batch_text,
                        agent_id="theo",
                        metadata=metadata
                    )

                theo_message = ""
                async for batch, acc_len, part_idx, metadata, result in stream_agent_text(
                    self.agent, prompt, deps=state,
                    message_history=message_history, on_batch=on_batch,
                    batch_size=30, flush_interval=0.05
                ):
                    if result is not None:
                        theo_message = result.output
                        message_history.extend(sanitize_messages(result.new_messages()))
                if hasattr(log_streamer, "flush"):
                    await log_streamer.flush()
                new_msgs = []  # Messages already extended in-place
            else:
                result = await self.agent.run(prompt, deps=state, message_history=message_history)
                theo_message = result.output
                new_msgs = sanitize_messages(list(result.new_messages()))
                message_history.extend(new_msgs)

            # Check for malformed tool call (Gemini MALFORMED_FUNCTION_CALL)
            if self._check_for_malformed_tool_call(message_history):
                if attempt < max_malformed_retries:
                    logfire.info(f"Retrying after malformed tool call (attempt {attempt + 1}/{max_malformed_retries})")
                    # Re-prompt the agent to try the tool call again
                    prompt = (
                        "Your previous tool call was malformed and did not execute. "
                        "The scope was NOT updated. Please call update_scope() again now."
                    )
                    state._tools_locked = False
                    continue
                else:
                    logfire.error(
                        f"Malformed tool call persisted after {max_malformed_retries} retries. "
                        f"Returning text-only response."
                    )

            if cli_mode:
                return theo_message, new_msgs
            elif log_streamer:
                return theo_message, []
            else:
                return theo_message, new_msgs

        # Fallback (shouldn't reach here but be safe)
        return theo_message, new_msgs if cli_mode else []

    async def start_conversation(
        self,
        intent_package: IntentPackage,
        graph_schema: GraphSchema,
        sample_data: Optional[Dict[str, List[Dict[str, Any]]]] = None,
        message_source: Optional[Any] = None,
        log_streamer: Optional[Any] = None,
        tenant_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ) -> Optional[ScopeRecommendation]:
        """
        Start interactive conversation to build scope recommendation.

        Args:
            intent_package: User's intent from Theo workflow
            graph_schema: Available entities/properties in workspace
            sample_data: Sample records for each entity type
            message_source: EventStreamReader for event stream mode
            log_streamer: ScenarioRunLogger for emitting events

        Returns:
            Final ScopeRecommendation, or None if cancelled
        """
        # CLI mode: no log_streamer provided (tools print to console)
        # Event stream mode: log_streamer provided (tools emit events)
        # Input can come from stdin (message_source=None) or event stream
        cli_mode = log_streamer is None
        use_stdin = message_source is None

        with logfire.span("scope_interview_conversation"):
            logfire.info("Starting scope interview", intent_title=intent_package.title)

            # Initialize state
            state = ScopeBuilderState(
                intent_package=intent_package,
                graph_schema=graph_schema,
                sample_data=sample_data or {},
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                log_streamer=log_streamer,
                cli_mode=cli_mode,
            )

            # CLI mode banner
            if cli_mode and use_stdin:
                print("\n" + "=" * 60)
                print("DATA SCOPE INTERVIEW WITH THEO")
                print("=" * 60)
                print("\nTheo will help you define the data scope for your analysis.")
                print("Type 'quit' or 'exit' to end the conversation early.")
                print("-" * 60)

            # Message history for multi-turn conversation
            message_history = []

            # Initial prompt
            initial_prompt = self._build_initial_prompt(state)

            # First response from Theo
            with logfire.span("theo_opening"):
                theo_message, new_msgs = await self._run_agent_turn(
                    initial_prompt, state, message_history,
                    log_streamer=log_streamer, cli_mode=cli_mode,
                )
                message_history.extend(new_msgs)

            # Main conversation loop — only breaks on end_data_scoping or quit
            exchange_count = 0
            while True:
                exchange_count += 1

                # Get user input (returns tuple of (message, event_type))
                user_input, event_type = await self.get_next_user_message(
                    message_source=message_source,
                    timeout=300.0 if message_source else None
                )

                # Handle end_data_scoping event - user confirmed scope via UI
                if event_type == "end_data_scoping":
                    logfire.info("User confirmed scope via end_data_scoping event",
                               exchanges=exchange_count,
                               has_scope=state.current_scope is not None)

                    if state.current_scope:
                        # Build final recommendation from current scope
                        state.scope_finalized = True
                        state.final_recommendation = ScopeRecommendation(
                            entities=state.current_scope.entities,
                            relationships=state.current_scope.relationships,
                            summary=state.current_scope.summary,
                            requires_clarification=False,
                            clarification_questions=[],
                            confidence_level=state.current_scope.confidence
                        )

                        if log_streamer:
                            await log_streamer.log_event(
                                event_type="scope_finalized",
                                message=f"Scope finalized: {state.current_scope.summary}",
                                agent_id="theo",
                                metadata={
                                    "scope": state.final_recommendation.model_dump() if state.final_recommendation else None
                                }
                            )

                        if use_stdin:
                            print("\n" + "=" * 50)
                            print("SCOPE FINALIZED")
                            print("=" * 50 + "\n")

                        break
                    else:
                        logfire.warning("end_data_scoping received but no current scope")
                        if use_stdin:
                            print("Theo: I don't have a scope to confirm yet. Let's keep talking.\n")
                        continue

                if event_type == "quit":
                    if use_stdin:
                        logfire.info("User quit conversation", exchanges=exchange_count)
                        print("\nTheo: No problem! We can continue this later.")
                    return None

                if event_type == "empty" or not user_input:
                    if use_stdin:
                        print("Theo: I didn't catch that. Could you say more?")
                    continue

                # Clear pending clarification since user has responded
                if state.pending_clarification:
                    state.pending_clarification = None

                # Process with Theo
                try:
                    with logfire.span("conversation_exchange",
                                     exchange=exchange_count,
                                     user_input_length=len(user_input)):

                        theo_message, new_msgs = await self._run_agent_turn(
                            user_input, state, message_history,
                            log_streamer=log_streamer, cli_mode=cli_mode,
                        )
                        message_history.extend(new_msgs)

                        logfire.info("Theo response",
                                    exchange=exchange_count,
                                    response_length=len(theo_message) if theo_message else 0)

                except Exception as e:
                    logfire.error("Conversation error",
                                exchange=exchange_count,
                                error=str(e))
                    if log_streamer:
                        await log_streamer.log_event(
                            event_type="error",
                            message=f"Error: {str(e)}",
                            agent_id="theo",
                        )
                    if use_stdin:
                        print(f"\nTheo: I ran into an issue: {e}")
                        print("Let's try that again.")
                    continue

            return state.final_recommendation

    async def quick_build(
        self,
        intent_package: IntentPackage,
        graph_schema: GraphSchema,
        sample_data: Optional[Dict[str, List[Dict[str, Any]]]] = None,
    ) -> ScopeRecommendation:
        """
        Quick build mode - generate scope without conversation.

        Useful for programmatic scope generation or testing.

        Args:
            intent_package: User's intent
            graph_schema: Available schema
            sample_data: Sample records

        Returns:
            ScopeRecommendation
        """
        with logfire.span("scope_quick_build"):
            logfire.info("Starting quick build mode")

            state = ScopeBuilderState(
                intent_package=intent_package,
                graph_schema=graph_schema,
                sample_data=sample_data or {}
            )

            prompt = f"""Generate a scope recommendation for this intent without asking questions.

**Intent**: {intent_package.title}
**Objective**: {intent_package.mission.objective}
**Success**: {intent_package.mission.success_looks_like}

1. Call update_scope() with your best recommendation based on the schema, with ready=True

Be decisive and comprehensive. This is automatic mode - no user interaction."""

            result = await self.agent.run(prompt, deps=state)

            if state.final_recommendation:
                logfire.info("Quick build completed",
                           entity_count=len(state.final_recommendation.entities))

            return state.final_recommendation


# =============================================================================
# Legacy API (for backwards compatibility)
# =============================================================================


async def recommend_scope(
    intent_package: IntentPackage,
    graph_schema: GraphSchema,
    sample_data: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> ScopeRecommendation:
    """
    Generate a data scope recommendation from intent and schema.

    This is the legacy single-shot API. For streaming/interactive mode,
    use ScopeBuilder.start_conversation() instead.

    Args:
        intent_package: User's intent from Theo workflow
        graph_schema: Available entities/properties in workspace
        sample_data: Sample records for each entity type

    Returns:
        ScopeRecommendation with entities, filters, and relationships
    """
    builder = ScopeBuilder()
    return await builder.quick_build(
        intent_package=intent_package,
        graph_schema=graph_schema,
        sample_data=sample_data
    )
