"""Authenticated GraphQL client with Entra External IDs support."""

import asyncio
import json
import logging
import ssl
import time
from typing import Any, Optional
from urllib import error, request

from app.config import Config
from app.core.graphql_auth import get_auth_token

logger = logging.getLogger(__name__)

# Retry configuration for transient errors
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1.0
RETRYABLE_ERRORS = (
    ssl.SSLError,
    TimeoutError,
    ConnectionResetError,
    ConnectionRefusedError,
)


def _get_auth_header() -> Optional[str]:
    """Get Authorization header value if authentication is enabled.
    
    Returns:
        Authorization header value (e.g., "Bearer <token>") or None if auth is disabled/failed
    """
    if not Config.GRAPHQL_AUTH_ENABLED:
        return None
    
    if not Config.GRAPHQL_AUTH_SCOPE:
        logger.warning(
            "GRAPHQL_AUTH_ENABLED is true but GRAPHQL_AUTH_SCOPE is not set. "
            "GraphQL requests will be unauthenticated."
        )
        return None
    
    try:
        token = get_auth_token(Config.GRAPHQL_AUTH_SCOPE)
        if token:
            return f"Bearer {token}"
        else:
            logger.warning("Failed to acquire authentication token. GraphQL request will be unauthenticated.")
            return None
    except Exception as e:
        logger.warning(f"Error acquiring authentication token: {e}. GraphQL request will be unauthenticated.")
        return None


def execute_graphql(
    query: str,
    variables: dict[str, Any],
    graphql_endpoint: Optional[str] = None,
    tenant_id: Optional[str] = None,
    timeout: Optional[float] = None
) -> dict[str, Any]:
    """Execute a GraphQL query/mutation with authentication support.

    Automatically adds Authorization header if authentication is enabled.
    Maintains backward compatibility with existing code.

    Args:
        query: GraphQL query/mutation string
        variables: Variables for the query
        graphql_endpoint: GraphQL endpoint URL (defaults to Config.GRAPHQL_ENDPOINT)
        tenant_id: Optional tenant ID to include in X-Tenant-Id header
        timeout: Optional timeout in seconds (defaults to Config.GRAPHQL_TIMEOUT)

    Returns:
        GraphQL response data dictionary

    Raises:
        RuntimeError: On HTTP errors, GraphQL errors, or invalid responses
    """
    endpoint = graphql_endpoint or Config.GRAPHQL_ENDPOINT
    timeout_seconds = timeout if timeout is not None else Config.GRAPHQL_TIMEOUT
    
    # Extract query name for logging
    query_name = query.strip().split()[1] if len(query.strip().split()) > 1 else "unknown"
    if "{" in query_name:
        query_name = query_name.split("{")[0]
    
    # Build headers
    headers = {"Content-Type": "application/json"}
    
    # Add authentication header if enabled
    auth_header = _get_auth_header()
    has_auth = bool(auth_header)
    if auth_header:
        headers["Authorization"] = auth_header
        logger.debug(f"Added Authorization header to GraphQL request for query: {query_name}")
    else:
        logger.debug(f"No Authorization header for GraphQL request (auth disabled or failed) for query: {query_name}")
    
    # Add tenant ID header if provided
    has_tenant_id = bool(tenant_id)
    if tenant_id:
        headers["X-Tenant-Id"] = tenant_id
        logger.debug(f"Added X-Tenant-Id header ({tenant_id[:8]}...) to GraphQL request for query: {query_name}")
    else:
        logger.warning(f"GraphQL request for query '{query_name}' is missing tenant_id header")
    
    # Log request details
    logger.info(
        f"Executing GraphQL query: {query_name} "
        f"(auth: {has_auth}, tenant_id: {has_tenant_id}, variables: {list(variables.keys())})"
    )

    # Prepare request
    payload_dict = {"query": query, "variables": variables}
    payload = json.dumps(payload_dict).encode("utf-8")

    # Debug: Log full request payload
    logger.debug(f"GraphQL request payload: {json.dumps(payload_dict, indent=2)}")

    # Retry loop for transient errors (SSL handshake timeout, connection reset, etc.)
    last_error: Optional[Exception] = None
    for attempt in range(MAX_RETRIES):
        req = request.Request(
            endpoint,
            data=payload,
            headers=headers,
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=timeout_seconds) as resp:
                raw = resp.read().decode("utf-8")
                if attempt > 0:
                    logger.info(f"GraphQL query '{query_name}' succeeded on retry {attempt + 1}")
                else:
                    logger.debug(f"GraphQL query '{query_name}' succeeded (timeout: {timeout_seconds}s)")
                break  # Success - exit retry loop
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8") if exc.fp else ""
            status_code = exc.code

            # Enhanced logging for 401 errors
            if status_code == 401:
                logger.error(
                    f"GraphQL 401 Unauthorized for query '{query_name}': "
                    f"auth_header_present={has_auth}, tenant_id_present={has_tenant_id}, "
                    f"tenant_id={tenant_id[:8] + '...' if tenant_id else 'None'}, "
                    f"endpoint={endpoint}, "
                    f"variables={variables}, "
                    f"response_body={body[:500]}"
                )
            else:
                logger.warning(
                    f"GraphQL request failed for query '{query_name}': "
                    f"status={status_code}, response={body}"
                )
                logger.warning(
                    f"GraphQL request details - query: {query[:500]}, variables: {variables}"
                )

            raise RuntimeError(
                f"GraphQL request failed with status {status_code}: {body or exc.reason}"
            ) from exc
        except error.URLError as exc:
            # Check if the underlying cause is a retryable error
            is_retryable = isinstance(exc.reason, RETRYABLE_ERRORS)

            if is_retryable and attempt < MAX_RETRIES - 1:
                logger.warning(
                    f"GraphQL request failed for query '{query_name}': {exc.reason} "
                    f"(attempt {attempt + 1}/{MAX_RETRIES}, retrying in {RETRY_DELAY_SECONDS}s)"
                )
                last_error = exc
                time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))  # Exponential backoff
                continue

            logger.error(f"GraphQL request failed for query '{query_name}': {exc.reason}")
            raise RuntimeError(f"GraphQL request failed: {exc.reason}") from exc
    else:
        # All retries exhausted
        if last_error:
            raise RuntimeError(f"GraphQL request failed after {MAX_RETRIES} retries: {last_error}") from last_error
    
    # Parse response
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid GraphQL response: {raw[:200]}") from exc
    
    # Check for GraphQL errors
    if errors := data.get("errors"):
        first_error = errors[0]
        message = first_error.get("message") if isinstance(first_error, dict) else str(first_error)
        raise RuntimeError(f"GraphQL error: {message}")
    
    return data.get("data") or {}


async def run_graphql(
    query: str,
    variables: dict[str, Any],
    graphql_endpoint: Optional[str] = None,
    tenant_id: Optional[str] = None,
    timeout: Optional[float] = None
) -> dict[str, Any]:
    """Run the blocking GraphQL call in a background thread (async wrapper).

    Args:
        query: GraphQL query/mutation string
        variables: Variables for the query
        graphql_endpoint: GraphQL endpoint URL (defaults to Config.GRAPHQL_ENDPOINT)
        tenant_id: Optional tenant ID to include in X-Tenant-Id header
        timeout: Optional timeout in seconds (defaults to Config.GRAPHQL_TIMEOUT)

    Returns:
        GraphQL response data dictionary
    """
    return await asyncio.to_thread(execute_graphql, query, variables, graphql_endpoint, tenant_id, timeout)


