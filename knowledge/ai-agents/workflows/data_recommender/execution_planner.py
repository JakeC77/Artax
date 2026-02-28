"""
Execution Planner - Generates optimal execution plans for graph queries.

DEPRECATED: This module was used for the legacy two-phase executor which has been
replaced by the Cypher-first executor. The Cypher query handles traversal
optimization natively via the graph database query planner.

This module is kept for backward compatibility but should not be used in new code.
Use CypherExecutor and CypherGenerator instead.

Historical context:
This module analyzed ScopeRecommendations and generated execution plans that:
1. Start from the most selective entity (lowest cardinality after filtering)
2. Traverse relationships in optimal order
3. Minimize total nodes fetched and processed
"""

import warnings

from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from app.workflows.data_recommender.models import (
    ScopeRecommendation,
    EntityScope,
    EntityFilter,
    FilterOperator,
    RelationshipPath,
)
from app.workflows.data_recommender.agent import GraphSchema


class TraversalDirection(str, Enum):
    """Direction of relationship traversal."""
    OUTBOUND = "outbound"  # Follow relationship: A --[rel]--> B
    INBOUND = "inbound"    # Reverse relationship: A <--[rel]-- B


@dataclass
class TraversalStep:
    """Single step in graph traversal execution plan."""
    entity_type: str
    relationship_type: str
    direction: TraversalDirection
    filters: List[EntityFilter]
    source_entity: str  # Entity we're traversing from


@dataclass
class ExecutionPlan:
    """Optimized execution plan for graph query."""
    start_entity: str
    start_filters: List[EntityFilter]
    traversal_steps: List[TraversalStep]
    requires_traversal: bool


class ExecutionPlanner:
    """
    DEPRECATED: Generates optimal execution plans from scope recommendations.

    This class is deprecated and should not be used in new code.
    Use CypherExecutor and CypherGenerator instead, which handle
    traversal optimization natively via Cypher queries.

    Strategy (historical):
    1. Calculate selectivity for each entity (based on filters)
    2. Start from most selective entity (lowest estimated cardinality)
    3. Build traversal path using relationships to reach other entities
    4. Order traversals to minimize total nodes fetched
    """

    def __init__(self, debug: bool = False):
        """
        Initialize execution planner.

        .. deprecated::
            Use CypherExecutor instead. This class is kept for backward
            compatibility only.

        Args:
            debug: If True, log detailed planning decisions
        """
        warnings.warn(
            "ExecutionPlanner is deprecated. Use CypherExecutor instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.debug = debug

    def plan(
        self,
        recommendation: ScopeRecommendation,
        schema: GraphSchema
    ) -> ExecutionPlan:
        """
        Generate execution plan from recommendation.

        Args:
            recommendation: Scope recommendation from agent
            schema: Graph schema for validation

        Returns:
            ExecutionPlan with optimal traversal order
        """
        # If no relationships, use independent execution (no traversal needed)
        if not recommendation.relationships:
            return self._plan_independent_execution(recommendation)

        # Calculate selectivity for each entity
        selectivity_scores = self._calculate_selectivity(recommendation)

        if self.debug:
            print("\n📊 Selectivity Analysis:")
            for entity_type, score in sorted(selectivity_scores.items(), key=lambda x: x[1]):
                print(f"   {entity_type}: {score:.2%} (lower = more selective)")

        # Find most selective entity (best starting point)
        start_entity = min(selectivity_scores, key=selectivity_scores.get)

        if self.debug:
            print(f"\n🎯 Starting entity: {start_entity} (most selective)")

        # Build relationship graph
        rel_graph = self._build_relationship_graph(recommendation)

        # Build traversal path
        traversal_steps = self._build_traversal_path(
            start_entity=start_entity,
            recommendation=recommendation,
            rel_graph=rel_graph
        )

        # Get start entity filters
        start_scope = next(
            e for e in recommendation.entities
            if e.entity_type == start_entity
        )

        return ExecutionPlan(
            start_entity=start_entity,
            start_filters=start_scope.filters,
            traversal_steps=traversal_steps,
            requires_traversal=len(traversal_steps) > 0
        )

    def _calculate_selectivity(
        self,
        recommendation: ScopeRecommendation
    ) -> Dict[str, float]:
        """
        Calculate selectivity score for each entity.

        Lower score = more selective = better starting point.

        Selectivity estimation:
        - No filters: 1.0 (100% of nodes)
        - EQ filter: 0.1 (10% of nodes)
        - GT/LT/GTE/LTE: 0.5 (50% of nodes)
        - CONTAINS: 0.3 (30% of nodes)
        - IS_NULL/IS_NOT_NULL: 0.2 (20% of nodes)
        - Multiple filters: multiply selectivities

        Args:
            recommendation: Scope recommendation with entities and filters

        Returns:
            Dict mapping entity_type to selectivity score (0.0-1.0)
        """
        scores = {}

        for entity in recommendation.entities:
            if not entity.filters:
                # No filters = 100% selectivity (all nodes pass)
                scores[entity.entity_type] = 1.0
                continue

            # Calculate combined selectivity from all filters
            selectivity = 1.0
            for filter in entity.filters:
                selectivity *= self._estimate_filter_selectivity(filter)

            scores[entity.entity_type] = selectivity

        return scores

    def _estimate_filter_selectivity(self, filter: EntityFilter) -> float:
        """
        Estimate selectivity of a single filter.

        Args:
            filter: Entity filter to estimate

        Returns:
            Selectivity score (0.0-1.0, lower = more selective)
        """
        if filter.operator == FilterOperator.EQ:
            return 0.1  # Exact match = ~10% of nodes
        elif filter.operator in {FilterOperator.GT, FilterOperator.GTE, FilterOperator.LT, FilterOperator.LTE}:
            return 0.5  # Range comparison = ~50% of nodes
        elif filter.operator == FilterOperator.CONTAINS:
            return 0.3  # Contains = ~30% of nodes
        elif filter.operator in {FilterOperator.IS_NULL, FilterOperator.IS_NOT_NULL}:
            return 0.2  # Null check = ~20% of nodes
        elif filter.operator == FilterOperator.IN:
            # IN selectivity depends on list size, estimate ~20%
            return 0.2
        elif filter.operator == FilterOperator.BETWEEN:
            return 0.4  # Range = ~40% of nodes
        else:
            return 0.5  # Default estimate

    def _build_relationship_graph(
        self,
        recommendation: ScopeRecommendation
    ) -> Dict[str, List[Tuple[str, str]]]:
        """
        Build adjacency graph from relationships.

        Args:
            recommendation: Scope recommendation with relationships

        Returns:
            Dict mapping entity_type to list of (related_entity, relationship_type) tuples
        """
        graph = {}

        # Initialize graph with all entities
        for entity in recommendation.entities:
            graph[entity.entity_type] = []

        # Add edges (bidirectional)
        for rel in recommendation.relationships:
            # Ensure both entities exist in graph (may not be in entities list)
            if rel.from_entity not in graph:
                graph[rel.from_entity] = []
            if rel.to_entity not in graph:
                graph[rel.to_entity] = []

            # Outbound: from_entity -> to_entity
            graph[rel.from_entity].append((rel.to_entity, rel.relationship_type))
            # Inbound: to_entity -> from_entity (reversed)
            graph[rel.to_entity].append((rel.from_entity, rel.relationship_type))

        return graph

    def _build_traversal_path(
        self,
        start_entity: str,
        recommendation: ScopeRecommendation,
        rel_graph: Dict[str, List[Tuple[str, str]]]
    ) -> List[TraversalStep]:
        """
        Build traversal path from start entity using BFS.

        Args:
            start_entity: Most selective entity to start from
            recommendation: Scope recommendation with entities and relationships
            rel_graph: Relationship adjacency graph

        Returns:
            List of traversal steps in execution order
        """
        steps = []
        visited = {start_entity}
        queue = [(start_entity, [])]  # (current_entity, path_to_current)

        # Get entity filters map
        entity_filters = {
            e.entity_type: e.filters
            for e in recommendation.entities
        }

        while queue:
            current_entity, path = queue.pop(0)

            # Explore neighbors
            for neighbor_entity, relationship_type in rel_graph.get(current_entity, []):
                if neighbor_entity in visited:
                    continue

                visited.add(neighbor_entity)

                # Determine traversal direction
                # Check if this is an outbound or inbound relationship
                direction = self._get_traversal_direction(
                    source=current_entity,
                    target=neighbor_entity,
                    relationship_type=relationship_type,
                    relationships=recommendation.relationships
                )

                # Create traversal step
                step = TraversalStep(
                    entity_type=neighbor_entity,
                    relationship_type=relationship_type,
                    direction=direction,
                    filters=entity_filters.get(neighbor_entity, []),
                    source_entity=current_entity
                )

                steps.append(step)

                # Add to queue for further exploration
                queue.append((neighbor_entity, path + [step]))

        if self.debug:
            print(f"\n🔀 Traversal Path ({len(steps)} steps):")
            for i, step in enumerate(steps, 1):
                arrow = "-->" if step.direction == TraversalDirection.OUTBOUND else "<--"
                print(f"   {i}. {step.source_entity} {arrow}[{step.relationship_type}]{arrow} {step.entity_type}")
                if step.filters:
                    print(f"      Filters: {len(step.filters)}")

        return steps

    def _get_traversal_direction(
        self,
        source: str,
        target: str,
        relationship_type: str,
        relationships: List[RelationshipPath]
    ) -> TraversalDirection:
        """
        Determine traversal direction for a relationship.

        Args:
            source: Source entity we're traversing from
            target: Target entity we're traversing to
            relationship_type: Type of relationship
            relationships: All relationships from recommendation

        Returns:
            TraversalDirection (OUTBOUND or INBOUND)
        """
        # Find the relationship definition
        for rel in relationships:
            if rel.relationship_type != relationship_type:
                continue

            # Check if traversal matches original direction
            if rel.from_entity == source and rel.to_entity == target:
                return TraversalDirection.OUTBOUND
            elif rel.from_entity == target and rel.to_entity == source:
                return TraversalDirection.INBOUND

        # Default to outbound if not found
        return TraversalDirection.OUTBOUND

    def _plan_independent_execution(
        self,
        recommendation: ScopeRecommendation
    ) -> ExecutionPlan:
        """
        Create execution plan for independent entity fetching (no relationships).

        Args:
            recommendation: Scope recommendation with no relationships

        Returns:
            ExecutionPlan with no traversal steps
        """
        # Pick any entity as start (preferably one with filters)
        entities_with_filters = [e for e in recommendation.entities if e.filters]
        start_entity_scope = entities_with_filters[0] if entities_with_filters else recommendation.entities[0]

        return ExecutionPlan(
            start_entity=start_entity_scope.entity_type,
            start_filters=start_entity_scope.filters,
            traversal_steps=[],
            requires_traversal=False
        )
