"""
Cypher-based scope executor.

This module implements the Cypher-first execution strategy:
- Generate Cypher query from ScopeRecommendation
- Execute directly via graphNodesByCypher API
- No two-phase filtering (the query does all filtering)

Benefits:
- Single API call vs N+M calls
- Relationship traversal handled by Cypher
- Better performance for complex queries
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.workflows.data_recommender.models import (
    ScopeRecommendation,
    ScopeExecutionResult,
    ExecutionStats,
    EntityExecutionStats,
    GraphNode,
)
from app.workflows.data_recommender.agent import GraphSchema
from app.workflows.data_recommender.cypher_generator import CypherGenerator, QueryPattern
from app.workflows.data_recommender.graphql_client import GraphQLClient
from app.core.graphql_logger import ScenarioRunLogger

logger = logging.getLogger(__name__)


class CypherExecutor:
    """
    Executes a ScopeRecommendation via Cypher query.

    Uses the CypherGenerator to build a query, then executes via
    graphNodesByCypher API. Falls back to LLM correction on error.
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        log_streamer: Optional[ScenarioRunLogger] = None,
        graphql_client: Optional[GraphQLClient] = None,
        max_retries: int = 2,
        debug: bool = False
    ):
        """
        Initialize the Cypher executor.

        Args:
            tenant_id: Tenant ID for GraphQL authentication
            log_streamer: Optional logger for streaming events
            graphql_client: Optional GraphQL client (for dependency injection)
            max_retries: Maximum retry attempts for failed queries (default 2)
            debug: If True, enable detailed logging
        """
        self.tenant_id = tenant_id
        self.log_streamer = log_streamer
        self.graphql_client = graphql_client
        self.max_retries = max_retries
        self.debug = debug
        self.generator: Optional[CypherGenerator] = None

    async def _emit_event(
        self,
        event_type: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Emit an activity event."""
        if self.log_streamer:
            await self.log_streamer.log_event(
                event_type=event_type,
                message=message,
                metadata=metadata or {},
                agent_id="cypher_executor"
            )

    async def execute(
        self,
        recommendation: ScopeRecommendation,
        schema: GraphSchema
    ) -> ScopeExecutionResult:
        """
        Execute a scope recommendation via per-entity Cypher queries.

        Generates a separate query for each entity (using BFS path traversal
        from the primary entity), then executes them individually. This handles
        branching graph topologies correctly — unlike a single multi-hop query
        which forces entities into a linear chain and drops branches.

        Args:
            recommendation: ScopeRecommendation from agent
            schema: GraphSchema for query generation and validation

        Returns:
            ScopeExecutionResult with matching_node_ids and stats
        """
        start_time = datetime.utcnow()

        # Initialize generator with schema
        self.generator = CypherGenerator(schema, use_llm_fallback=True)

        await self._emit_event(
            event_type="cypher_execution_started",
            message=f"Starting Cypher execution for {len(recommendation.entities)} entities",
            metadata={
                "entity_count": len(recommendation.entities),
                "relationship_count": len(recommendation.relationships),
                "summary": recommendation.summary
            }
        )

        # Generate per-entity queries (BFS path traversal from primary entity)
        try:
            entity_queries = await self.generator.generate_entity_queries(recommendation)

            await self._emit_event(
                event_type="cypher_query_generated",
                message=f"Generated {len(entity_queries)} per-entity queries (deterministic, pattern: per_entity_path)",
                metadata={
                    "method": "deterministic",
                    "pattern": "per_entity_path",
                    "entity_count": len(entity_queries),
                    "warnings": []
                }
            )

            if self.debug:
                for et, q in entity_queries.items():
                    logger.info(f"Query for {et}:\n{q}")

        except Exception as e:
            logger.error(f"Per-entity query generation failed: {e}")
            return self._build_error_result(
                recommendation,
                f"Query generation failed: {e}",
                start_time
            )

        if not self.graphql_client:
            logger.warning("No GraphQL client configured - returning empty result")
            return self._build_error_result(
                recommendation, "No GraphQL client configured", start_time
            )

        # Execute each entity query separately
        nodes_by_type: Dict[str, List[str]] = {}
        sample_nodes: Dict[str, List[Dict[str, Any]]] = {}
        all_queries: List[str] = []
        total_matches = 0

        for entity_type, cypher_query in entity_queries.items():
            all_queries.append(cypher_query)

            try:
                nodes = await self.graphql_client.nodes_by_cypher(cypher_query)

                # Extract node IDs and samples for this entity
                node_ids = [n.id for n in nodes]
                entity_samples = [n.properties for n in nodes[:10]]

                nodes_by_type[entity_type] = node_ids
                sample_nodes[entity_type] = entity_samples
                total_matches += len(node_ids)

                logger.info(f"Entity {entity_type}: {len(node_ids)} nodes returned")

            except Exception as e:
                logger.warning(f"Query failed for {entity_type}: {e}")
                nodes_by_type[entity_type] = []
                sample_nodes[entity_type] = []

        execution_time = (datetime.utcnow() - start_time).total_seconds()
        entity_stats = self._build_entity_stats(nodes_by_type)

        await self._emit_event(
            event_type="cypher_execution_completed",
            message=f"Query completed: {total_matches} nodes returned",
            metadata={
                "total_matches": total_matches,
                "execution_time_seconds": execution_time,
                "entities_found": [et for et, ids in nodes_by_type.items() if ids]
            }
        )

        return ScopeExecutionResult(
            scope_recommendation=recommendation,
            matching_node_ids=nodes_by_type,
            sample_nodes=sample_nodes,
            stats=ExecutionStats(
                total_candidates=total_matches,
                total_matches=total_matches,
                execution_time_seconds=execution_time,
                entity_stats=entity_stats
            ),
            success=True,
            cypher_query="\n\n".join(all_queries),
            generation_method="deterministic_per_entity"
        )

    def _group_nodes_by_type(
        self,
        nodes: List[GraphNode],
        recommendation: ScopeRecommendation
    ) -> Dict[str, List[str]]:
        """
        Group nodes by their entity type (label).

        Args:
            nodes: List of GraphNode from query results
            recommendation: Original recommendation (for entity type hints)

        Returns:
            Dict mapping entity_type -> list of node IDs
        """
        # Get expected entity types from recommendation
        expected_types = {e.entity_type for e in recommendation.entities}

        nodes_by_type: Dict[str, List[str]] = {et: [] for et in expected_types}

        for node in nodes:
            # Check which expected type this node belongs to
            for label in node.labels:
                if label in expected_types:
                    nodes_by_type[label].append(node.id)
                    break
            else:
                # Node doesn't match any expected type - use first label
                if node.labels:
                    label = node.labels[0]
                    if label not in nodes_by_type:
                        nodes_by_type[label] = []
                    nodes_by_type[label].append(node.id)

        return nodes_by_type

    def _extract_sample_nodes(
        self,
        nodes: List[GraphNode],
        recommendation: ScopeRecommendation,
        samples_per_type: int = 10
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract sample nodes for preview.

        Args:
            nodes: List of GraphNode from query results
            recommendation: Original recommendation
            samples_per_type: Max samples per entity type (default 10)

        Returns:
            Dict mapping entity_type -> list of property dicts
        """
        expected_types = {e.entity_type for e in recommendation.entities}
        samples: Dict[str, List[Dict[str, Any]]] = {et: [] for et in expected_types}
        counts: Dict[str, int] = {et: 0 for et in expected_types}

        for node in nodes:
            for label in node.labels:
                if label in expected_types:
                    if counts[label] < samples_per_type:
                        samples[label].append(node.properties)
                        counts[label] += 1
                    break

        return samples

    def _build_entity_stats(
        self,
        nodes_by_type: Dict[str, List[str]]
    ) -> List[EntityExecutionStats]:
        """
        Build per-entity execution stats.

        Args:
            nodes_by_type: Dict mapping entity_type -> list of node IDs

        Returns:
            List of EntityExecutionStats
        """
        stats = []
        for entity_type, node_ids in nodes_by_type.items():
            count = len(node_ids)
            stats.append(EntityExecutionStats(
                entity_type=entity_type,
                candidates_fetched=count,  # With Cypher, all returned are matches
                matches_after_filtering=count,
                api_filters_applied=0,  # N/A for Cypher (all filtering in query)
                python_filters_applied=0
            ))
        return stats

    def _build_error_result(
        self,
        recommendation: ScopeRecommendation,
        error_message: str,
        start_time: datetime,
        cypher_query: Optional[str] = None,
        generation_method: Optional[str] = None
    ) -> ScopeExecutionResult:
        """
        Build error result for failed execution.

        Args:
            recommendation: Original scope recommendation
            error_message: Error description
            start_time: When execution started
            cypher_query: The query that failed (if any)
            generation_method: How the query was generated

        Returns:
            ScopeExecutionResult with success=False
        """
        execution_time = (datetime.utcnow() - start_time).total_seconds()

        return ScopeExecutionResult(
            scope_recommendation=recommendation,
            matching_node_ids={},
            stats=ExecutionStats(
                total_candidates=0,
                total_matches=0,
                execution_time_seconds=execution_time,
                entity_stats=[]
            ),
            success=False,
            error_message=error_message,
            cypher_query=cypher_query,
            generation_method=generation_method
        )
