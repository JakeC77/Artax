"""
GraphQL client for data scope recommendation workflow.

This module provides a wrapper around the GraphQL API for querying graph nodes
with tenant authentication and proper error handling.
"""

import logging
from typing import List, Optional, Dict, Any

from app.core.authenticated_graphql_client import run_graphql
from app.workflows.data_recommender.models import GraphNode, GraphPropertyMatchInput

logger = logging.getLogger(__name__)


# GraphQL query for searching nodes with criteria
_GRAPH_NODES_SEARCH_QUERY = """
query NodesSearch($criteria: [GraphPropertySearchInput!]!, $type: String!, $workspaceId: UUID) {
  graphNodesSearch(criteria: $criteria, type: $type, workspaceId: $workspaceId) {
    id
    labels
    properties {
      key
      value
    }
  }
}
""".strip()

# GraphQL query for fetching all nodes of a type
_GRAPH_NODES_BY_TYPE_QUERY = """
query NodesByType($type: String!, $workspaceId: UUID) {
  graphNodesByType(type: $type, workspaceId: $workspaceId) {
    id
    labels
    properties {
      key
      value
    }
  }
}
""".strip()

# GraphQL query for fetching neighbors (connected nodes and edges)
_GRAPH_NEIGHBORS_QUERY = """
query Neighbors($id: String!, $workspaceId: UUID) {
  graphNeighbors(id: $id, workspaceId: $workspaceId) {
    nodes {
      id
      labels
      properties {
        key
        value
      }
    }
    edges {
      id
      fromId
      toId
      type
      properties {
        key
        value
      }
    }
  }
}
""".strip()

# GraphQL query for executing Cypher queries directly
_GRAPH_NODES_BY_CYPHER_QUERY = """
query NodesByCypher($cypherQuery: String!, $workspaceId: UUID) {
  graphNodesByCypher(cypherQuery: $cypherQuery, workspaceId: $workspaceId) {
    id
    labels
    properties {
      key
      value
    }
  }
}
""".strip()


class GraphQLClient:
    """
    GraphQL client for querying workspace graph nodes.

    Provides methods for:
    - Searching nodes with property filters
    - Fetching all nodes of a given type
    - Tenant authentication and context management

    Example:
        >>> client = GraphQLClient(
        ...     workspace_id="123e4567-e89b-12d3-a456-426614174000",
        ...     tenant_id="tenant_123"
        ... )
        >>>
        >>> # Search with criteria
        >>> criteria = [
        ...     GraphPropertyMatchInput(key="status", value="active", match_type="EXACT")
        ... ]
        >>> nodes = await client.nodes_search(criteria=criteria, entity_type="Claim")
        >>>
        >>> # Fetch all nodes of a type
        >>> all_patients = await client.nodes_by_type(entity_type="Patient")
    """

    def __init__(
        self,
        workspace_id: str,
        tenant_id: Optional[str] = None,
        graphql_endpoint: Optional[str] = None
    ):
        """
        Initialize the GraphQL client.

        Args:
            workspace_id: Workspace UUID for scoping queries
            tenant_id: Optional tenant ID for authentication
            graphql_endpoint: Optional GraphQL endpoint URL (defaults to Config.GRAPHQL_ENDPOINT)
        """
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id
        self.graphql_endpoint = graphql_endpoint

        logger.info(
            f"GraphQL client initialized: workspace={workspace_id[:8]}..., "
            f"tenant={'present' if tenant_id else 'none'}"
        )

    async def nodes_search(
        self,
        criteria: List[GraphPropertyMatchInput],
        entity_type: str
    ) -> List[GraphNode]:
        """
        Search for nodes matching the given criteria.

        .. deprecated::
            Use nodes_by_cypher() instead for more powerful query capabilities.
            This method is kept for backward compatibility.

        Uses graphNodesSearch with property-based filtering. API supports
        exact match and fuzzy search (contains) operations.

        Args:
            criteria: List of property match criteria (key, value, match_type)
            entity_type: Entity type to search (e.g., "Claim", "Patient")

        Returns:
            List of GraphNode objects matching the criteria

        Raises:
            RuntimeError: On GraphQL errors or HTTP failures

        Example:
            >>> criteria = [
            ...     GraphPropertyMatchInput(key="status", value="active", match_type="EXACT")
            ... ]
            >>> nodes = await client.nodes_search(criteria, "Claim")
            >>> print(f"Found {len(nodes)} active claims")
        """
        logger.debug(
            f"nodes_search called: entity_type={entity_type}, "
            f"criteria_count={len(criteria)}"
        )

        # If no criteria, fetch all nodes by type
        if not criteria:
            return await self.nodes_by_type(entity_type)

        # Convert criteria to GraphQL format
        # GraphPropertyMatchInput has: key, value, match_type
        # GraphQL expects: property, value, fuzzySearch
        criteria_dicts = []
        for c in criteria:
            criterion = {
                "property": c.key,
                "value": c.value,
                "fuzzySearch": c.match_type == "CONTAINS"
            }
            # Add maxDistance for fuzzy search
            if c.match_type == "CONTAINS":
                criterion["maxDistance"] = 3
            criteria_dicts.append(criterion)

        variables = {
            "criteria": criteria_dicts,
            "type": entity_type,
            "workspaceId": self.workspace_id
        }

        try:
            data = await run_graphql(
                _GRAPH_NODES_SEARCH_QUERY,
                variables,
                graphql_endpoint=self.graphql_endpoint,
                tenant_id=self.tenant_id
            )

            raw_nodes = data.get("graphNodesSearch", [])
            logger.info(
                f"nodes_search successful: entity_type={entity_type}, "
                f"criteria={len(criteria)}, results={len(raw_nodes)}"
            )

            # Convert to GraphNode objects
            nodes = self._parse_nodes(raw_nodes)
            return nodes

        except Exception as e:
            logger.error(
                f"nodes_search failed: entity_type={entity_type}, "
                f"error={type(e).__name__}: {str(e)}"
            )
            raise

    async def nodes_by_type(self, entity_type: str) -> List[GraphNode]:
        """
        Fetch all nodes of a given entity type.

        This method uses the graphNodesByType GraphQL query to fetch all
        nodes of the type for Python-side filtering.

        Note: For large datasets, consider pagination (future enhancement).

        Args:
            entity_type: Entity type to fetch (e.g., "Claim", "Patient")

        Returns:
            List of all GraphNode objects of the given type

        Raises:
            RuntimeError: On GraphQL errors or HTTP failures

        Example:
            >>> all_patients = await client.nodes_by_type("Patient")
            >>> print(f"Total patients: {len(all_patients)}")
        """
        logger.debug(f"nodes_by_type called: entity_type={entity_type}")

        variables = {
            "type": entity_type,
            "workspaceId": self.workspace_id
        }

        try:
            data = await run_graphql(
                _GRAPH_NODES_BY_TYPE_QUERY,
                variables,
                graphql_endpoint=self.graphql_endpoint,
                tenant_id=self.tenant_id
            )

            raw_nodes = data.get("graphNodesByType", [])
            logger.info(
                f"nodes_by_type successful: entity_type={entity_type}, "
                f"results={len(raw_nodes)}"
            )

            # Convert to GraphNode objects
            nodes = self._parse_nodes(raw_nodes)
            return nodes

        except Exception as e:
            logger.error(
                f"nodes_by_type failed: entity_type={entity_type}, "
                f"error={type(e).__name__}: {str(e)}"
            )
            raise

    async def nodes_sample(
        self,
        entity_type: str,
        limit: int = 3
    ) -> List[GraphNode]:
        """
        Fetch a limited sample of nodes for a given entity type.

        This method is used to get sample data that helps the AI agent
        understand the actual data shape, value formats, and types.

        Note: The GraphQL API does not support a `limit` argument on graphNodesByType,
        so we fetch all nodes and slice to the limit. For large datasets, consider
        adding server-side pagination support.

        Args:
            entity_type: Entity type to sample (e.g., "Claim", "Patient")
            limit: Maximum number of nodes to return (default 3)

        Returns:
            List of sample GraphNode objects

        Raises:
            RuntimeError: On GraphQL errors or HTTP failures

        Example:
            >>> samples = await client.nodes_sample("PolicyRequirement", limit=3)
            >>> for node in samples:
            ...     print(node.properties)
            {'status': 'active', 'requiresDocumentation': 'True', ...}
        """
        logger.debug(f"nodes_sample called: entity_type={entity_type}, limit={limit}")

        # Fetch all nodes and slice (API doesn't support limit parameter)
        try:
            all_nodes = await self.nodes_by_type(entity_type)
            samples = all_nodes[:limit]

            logger.debug(
                f"nodes_sample successful: entity_type={entity_type}, "
                f"limit={limit}, returned={len(samples)} of {len(all_nodes)} total"
            )

            return samples

        except Exception as e:
            logger.error(
                f"nodes_sample failed: entity_type={entity_type}, "
                f"error={type(e).__name__}: {str(e)}"
            )
            raise

    async def nodes_by_cypher(self, cypher_query: str) -> List[GraphNode]:
        """
        Execute a Cypher query and return matching nodes.

        Uses the graphNodesByCypher GraphQL query to run a Neo4j Cypher query
        directly. This enables complex graph traversals and filters that cannot
        be expressed with simpler property-based searches.

        The Cypher query should RETURN nodes (not scalar values or paths).

        Args:
            cypher_query: Neo4j Cypher query string (e.g., "MATCH (n:Plan) RETURN n LIMIT 100")

        Returns:
            List of GraphNode objects matching the query

        Raises:
            RuntimeError: On GraphQL errors, HTTP failures, or invalid Cypher

        Example:
            >>> query = "MATCH (p:Plan) WHERE p.planType = 'Exchange' RETURN p LIMIT 100"
            >>> nodes = await client.nodes_by_cypher(query)
            >>> print(f"Found {len(nodes)} Exchange plans")
        """
        logger.debug(f"nodes_by_cypher called: query_length={len(cypher_query)}")

        # Log first 200 chars of query for debugging
        query_preview = cypher_query[:200] + "..." if len(cypher_query) > 200 else cypher_query
        logger.debug(f"Cypher query: {query_preview}")

        variables = {
            "cypherQuery": cypher_query,
            "workspaceId": self.workspace_id
        }

        try:
            data = await run_graphql(
                _GRAPH_NODES_BY_CYPHER_QUERY,
                variables,
                graphql_endpoint=self.graphql_endpoint,
                tenant_id=self.tenant_id
            )

            raw_nodes = data.get("graphNodesByCypher", [])
            logger.info(f"nodes_by_cypher successful: results={len(raw_nodes)}")

            # Reuse existing _parse_nodes - response format is identical
            nodes = self._parse_nodes(raw_nodes)
            return nodes

        except Exception as e:
            logger.error(
                f"nodes_by_cypher failed: error={type(e).__name__}: {str(e)}"
            )
            raise

    async def fetch_neighbors(self, node_id: str) -> Dict[str, Any]:
        """
        Fetch connected nodes and edges for a given node.

        .. deprecated::
            Use nodes_by_cypher() with a relationship pattern instead.
            Cypher queries handle relationship traversal more efficiently.
            This method is kept for backward compatibility.

        Uses the graphNeighbors query to get all nodes connected to the
        specified node via any relationship, along with the edges connecting them.

        Args:
            node_id: ID of the node to fetch neighbors for

        Returns:
            Dict with 'nodes' and 'edges' keys containing connected graph elements

        Raises:
            RuntimeError: On GraphQL errors or HTTP failures

        Example:
            >>> result = await client.fetch_neighbors("medication_001")
            >>> print(f"Found {len(result['nodes'])} connected nodes")
            >>> print(f"Found {len(result['edges'])} edges")
        """
        logger.debug(f"fetch_neighbors called: node_id={node_id}")

        variables = {
            "id": node_id,
            "workspaceId": self.workspace_id
        }

        try:
            data = await run_graphql(
                _GRAPH_NEIGHBORS_QUERY,
                variables,
                graphql_endpoint=self.graphql_endpoint,
                tenant_id=self.tenant_id
            )

            neighbors = data.get("graphNeighbors", {})
            raw_nodes = neighbors.get("nodes", [])
            raw_edges = neighbors.get("edges", [])

            logger.info(
                f"fetch_neighbors successful: node_id={node_id}, "
                f"nodes={len(raw_nodes)}, edges={len(raw_edges)}"
            )

            # Parse nodes
            nodes = self._parse_nodes(raw_nodes)

            # Parse edges (keep as dicts for now)
            edges = raw_edges

            return {"nodes": nodes, "edges": edges}

        except Exception as e:
            logger.error(
                f"fetch_neighbors failed: node_id={node_id}, "
                f"error={type(e).__name__}: {str(e)}"
            )
            raise

    def _parse_nodes(self, raw_nodes: List[Dict[str, Any]]) -> List[GraphNode]:
        """
        Parse raw GraphQL response into GraphNode objects.

        The GraphQL API returns properties as a list of {key, value} dicts.
        This method converts that to a flat properties dictionary.

        Args:
            raw_nodes: List of raw node data from GraphQL response

        Returns:
            List of typed GraphNode objects

        Example raw_node:
            {
                "id": "claim_001",
                "labels": ["Claim"],
                "properties": [
                    {"key": "status", "value": "active"},
                    {"key": "paidAmount", "value": "1500.00"}
                ]
            }

        Example GraphNode:
            GraphNode(
                id="claim_001",
                labels=["Claim"],
                properties={"status": "active", "paidAmount": "1500.00"}
            )
        """
        nodes = []

        for raw_node in raw_nodes:
            # Convert properties list to dict
            properties_dict = {}
            for prop in raw_node.get("properties", []):
                key = prop.get("key")
                value = prop.get("value")
                if key:
                    properties_dict[key] = value

            # Create GraphNode
            node = GraphNode(
                id=raw_node["id"],
                labels=raw_node.get("labels", []),
                properties=properties_dict
            )
            nodes.append(node)

        return nodes


# Convenience function for creating clients
def create_client(
    workspace_id: str,
    tenant_id: Optional[str] = None,
    graphql_endpoint: Optional[str] = None
) -> GraphQLClient:
    """
    Create a GraphQL client instance.

    Convenience factory function for creating clients with proper configuration.

    Args:
        workspace_id: Workspace UUID for scoping queries
        tenant_id: Optional tenant ID for authentication
        graphql_endpoint: Optional GraphQL endpoint URL

    Returns:
        Configured GraphQLClient instance

    Example:
        >>> client = create_client(
        ...     workspace_id="123e4567-e89b-12d3-a456-426614174000",
        ...     tenant_id="tenant_123"
        ... )
    """
    return GraphQLClient(
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        graphql_endpoint=graphql_endpoint
    )
