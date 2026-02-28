"""HTTP client for semantic entities GraphQL queries (used by entity resolution)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional
from urllib import error, request

from app.config import Config
from app.core.graphql_auth import get_auth_token
from app.workflows.document_indexing.config import load_config

logger = logging.getLogger(__name__)


def _auth_headers(tenant_id: Optional[str] = None) -> dict[str, str]:
    """Build headers with optional Bearer token and X-Tenant-Id."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if Config.GRAPHQL_AUTH_ENABLED and Config.GRAPHQL_AUTH_SCOPE:
        try:
            token = get_auth_token(Config.GRAPHQL_AUTH_SCOPE)
            if token:
                headers["Authorization"] = f"Bearer {token}"
        except Exception as e:
            logger.warning("GraphQL API auth failed: %s", e)
    if tenant_id:
        headers["X-Tenant-Id"] = tenant_id
    return headers


# GraphQL query for semantic entities (used by entity resolution).
_SEMANTIC_ENTITIES_QUERY = (
    "query { semanticEntities { createdOn description name nodeLabel semanticEntityId "
    "fields { dataType description name rangeInfo } } }"
)


def fetch_semantic_entities_sync(tenant_id: Optional[str] = None) -> list[dict[str, Any]]:
    """Fetch semantic entities via GraphQL. Returns list of entity dicts (semanticEntityId, nodeLabel, name, description, fields)."""
    url = Config.GRAPHQL_ENDPOINT.rstrip("/")
    if not url.endswith("/gql"):
        url = f"{url}/gql" if url else "/gql"
    payload: dict[str, Any] = {"query": _SEMANTIC_ENTITIES_QUERY}
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers=_auth_headers(tenant_id),
    )
    # Use config timeout (with fallback to environment variable for backward compatibility)
    workflow_config = load_config()
    timeout = getattr(Config, "DOCUMENT_INDEXING_TIMEOUT", None) or workflow_config.document_indexing_timeout
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        body_err = exc.read().decode("utf-8") if exc.fp else ""
        raise RuntimeError(
            f"Semantic entities request failed: HTTP {exc.code} - {body_err or exc.reason}"
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(f"Semantic entities request failed: {exc.reason}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Semantic entities invalid JSON: {e}") from e
    errors = data.get("errors")
    if errors:
        msg = "; ".join(
            e.get("message", str(e)) for e in (errors if isinstance(errors, list) else [errors])
        )
        raise RuntimeError(f"Semantic entities GraphQL errors: {msg}")
    inner = (data.get("data") or {}).get("semanticEntities")
    if not isinstance(inner, list):
        return []
    return [dict(obj) for obj in inner if isinstance(obj, dict)]


async def fetch_semantic_entities(tenant_id: Optional[str] = None) -> list[dict[str, Any]]:
    """Async wrapper for fetch_semantic_entities_sync."""
    return await asyncio.to_thread(fetch_semantic_entities_sync, tenant_id)
