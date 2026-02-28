"""GraphQL client for saving AI teams and team members to the API."""

from typing import Any, Optional

# Import authenticated GraphQL client
from app.core.authenticated_graphql_client import execute_graphql, run_graphql


def _execute_graphql(
    query: str,
    variables: dict[str, Any],
    graphql_endpoint: Optional[str] = None,
    tenant_id: Optional[str] = None
) -> dict[str, Any]:
    """Execute a GraphQL mutation with authentication support.
    
    Args:
        query: GraphQL query/mutation string
        variables: Variables for the query
        graphql_endpoint: GraphQL endpoint URL (defaults to Config.GRAPHQL_ENDPOINT)
        tenant_id: Optional tenant ID to include in X-Tenant-Id header
        
    Returns:
        GraphQL response data dictionary
        
    Raises:
        RuntimeError: On HTTP errors, GraphQL errors, or invalid responses
    """
    return execute_graphql(query, variables, graphql_endpoint, tenant_id)


async def _run_graphql(
    query: str,
    variables: dict[str, Any],
    graphql_endpoint: Optional[str] = None,
    tenant_id: Optional[str] = None
) -> dict[str, Any]:
    """Run the blocking GraphQL call in a background thread.
    
    Args:
        query: GraphQL query/mutation string
        variables: Variables for the query
        graphql_endpoint: GraphQL endpoint URL (defaults to Config.GRAPHQL_ENDPOINT)
        tenant_id: Optional tenant ID to include in X-Tenant-Id header
        
    Returns:
        GraphQL response data dictionary
    """
    return await run_graphql(query, variables, graphql_endpoint, tenant_id)

