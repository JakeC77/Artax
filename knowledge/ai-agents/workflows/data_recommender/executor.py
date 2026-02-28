"""
Scope Executor - Cypher-first execution engine for data scope recommendations.

This module executes ScopeRecommendation objects by generating and running
Cypher queries against the graph database via the graphNodesByCypher API.

The Cypher-first approach replaces the previous two-phase execution strategy
(API-side + Python-side filtering) with a single optimized query.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from app.workflows.data_recommender.models import (
    ScopeRecommendation,
    ScopeExecutionResult,
    ExecutionStats,
    EntityScope,
    EntityPreviewData,
)
from app.workflows.data_recommender.agent import GraphSchema
from app.workflows.data_recommender.cypher_executor import CypherExecutor
from app.workflows.data_recommender.cypher_generator import CypherGenerator
from app.core.graphql_logger import ScenarioRunLogger

logger = logging.getLogger(__name__)


class ScopeExecutor:
    """
    Executes a ScopeRecommendation against the GraphQL API using Cypher queries.

    Delegates to CypherExecutor for query generation and execution.
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        log_streamer: Optional[ScenarioRunLogger] = None,
        graphql_client: Optional[Any] = None,
        debug: bool = False,
        test_mode: bool = False,
        max_nodes_to_traverse: int = 50,
        max_neighbors_per_node: int = 3
    ):
        """
        Initialize the scope executor.

        Args:
            tenant_id: Tenant ID for GraphQL authentication
            log_streamer: Optional logger for streaming events
            graphql_client: Optional GraphQL client (for dependency injection)
            debug: If True, enable detailed logging
            test_mode: If True, limit results for faster testing (passed to Cypher LIMIT)
            max_nodes_to_traverse: Deprecated - kept for API compatibility
            max_neighbors_per_node: Deprecated - kept for API compatibility
        """
        self.tenant_id = tenant_id
        self.log_streamer = log_streamer
        self.graphql_client = graphql_client
        self.debug = debug
        self.test_mode = test_mode
        # These are deprecated but kept for backward compatibility
        self._max_nodes_to_traverse = max_nodes_to_traverse
        self._max_neighbors_per_node = max_neighbors_per_node

    async def execute(
        self,
        recommendation: ScopeRecommendation,
        schema: GraphSchema
    ) -> ScopeExecutionResult:
        """
        Execute a scope recommendation using Cypher query.

        Args:
            recommendation: ScopeRecommendation from agent
            schema: GraphSchema for query generation and validation

        Returns:
            ScopeExecutionResult with matching_node_ids and stats
        """
        logger.info(f"Executing scope recommendation for {len(recommendation.entities)} entities")

        cypher_executor = CypherExecutor(
            tenant_id=self.tenant_id,
            log_streamer=self.log_streamer,
            graphql_client=self.graphql_client,
            debug=self.debug
        )

        return await cypher_executor.execute(recommendation, schema)

    async def execute_preview(
        self,
        recommendation: ScopeRecommendation,
        schema: GraphSchema,
        entity_type: str | None = None,
        limit: int = 25,
        offset: int = 0
    ) -> EntityPreviewData:
        """
        Execute a limited preview query for a single entity.

        This is for the Preview Data tab - quick results without full execution.
        Returns only sample records and a count, not full node IDs.

        Args:
            recommendation: Scope recommendation to preview
            schema: Graph schema for query generation
            entity_type: Specific entity to preview (defaults to primary/first)
            limit: Max records to return (default 25)
            offset: Pagination offset (default 0)

        Returns:
            EntityPreviewData with count and sample records
        """
        if not recommendation.entities:
            return EntityPreviewData(
                entity_type=entity_type or "unknown",
                count=0,
                sample_data=[],
                cypher_query=None
            )

        # Determine target entity
        target = entity_type
        if not target:
            # Find primary entity or use first one
            primary = next(
                (e for e in recommendation.entities if e.relevance_level == "primary"),
                recommendation.entities[0]
            )
            target = primary.entity_type

        # Find the entity scope
        target_scope = next(
            (e for e in recommendation.entities if e.entity_type == target),
            None
        )
        if not target_scope:
            logger.warning(f"Entity type {target} not found in recommendation")
            return EntityPreviewData(
                entity_type=target,
                count=0,
                sample_data=[],
                cypher_query=None
            )

        # Generate preview queries using the CypherGenerator
        generator = CypherGenerator(schema, use_llm_fallback=False)

        try:
            # Generate count query
            count_query = generator.generate_count_query(target_scope)

            # Generate sample query with pagination
            sample_query = generator.generate_single_entity_preview(
                target_scope,
                limit=limit,
                offset=offset
            )

            # Execute queries
            total_count = 0
            sample_data = []

            if self.graphql_client:
                # Execute count query
                try:
                    count_result = await self.graphql_client.nodes_by_cypher(count_query)
                    # Count query returns a single record with 'total' property
                    if count_result and len(count_result) > 0:
                        first_result = count_result[0]
                        if hasattr(first_result, 'properties'):
                            total_count = first_result.properties.get('total', 0)
                        elif isinstance(first_result, dict):
                            total_count = first_result.get('total', 0)
                        else:
                            logger.warning(f"Unexpected count result format: {type(first_result)}")
                except Exception as e:
                    logger.warning(f"Count query failed: {e}")

                # Execute sample query
                try:
                    sample_nodes = await self.graphql_client.nodes_by_cypher(sample_query)
                    sample_data = [
                        node.properties if hasattr(node, 'properties') else node
                        for node in sample_nodes
                    ]
                except Exception as e:
                    logger.warning(f"Sample query failed: {e}")

            logger.info(
                f"Preview for {target}: {total_count} total, "
                f"{len(sample_data)} samples (offset={offset}, limit={limit})"
            )

            return EntityPreviewData(
                entity_type=target,
                count=total_count,
                sample_data=sample_data,
                cypher_query=sample_query
            )

        except Exception as e:
            logger.error(f"Preview execution failed: {e}")
            return EntityPreviewData(
                entity_type=target,
                count=0,
                sample_data=[],
                cypher_query=None
            )
