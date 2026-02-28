"""Neo4j read client for document subgraph (Graphiti knowledge graph).

Queries the same Neo4j instance used by Graphiti to return nodes and edges
for a document's episodes (group_id + doc_id episode name prefix).

Supports run_document_cypher() for agent-defined read-only Cypher with guardrails.
"""

from __future__ import annotations

import re
import logging
from typing import Any, Optional

from app.config import Config

logger = logging.getLogger(__name__)

_neo4j_driver: Optional[Any] = None

try:
    from neo4j import AsyncGraphDatabase
    _NEO4J_AVAILABLE = True
except ImportError:
    _NEO4J_AVAILABLE = False
    AsyncGraphDatabase = None


def _is_neo4j_configured() -> bool:
    """Return True if Graphiti/Neo4j is enabled and credentials are set."""
    if not Config.GRAPHITI_ENABLED:
        return False
    if not _NEO4J_AVAILABLE:
        return False
    if not Config.NEO4J_URI or not Config.NEO4J_USER:
        return False
    if not Config.NEO4J_PASSWORD:
        logger.warning("Neo4j enabled but NEO4J_PASSWORD is empty")
        return False
    return True


def _group_id(tenant_id: str) -> str:
    """Namespace for tenant; must match graphiti_ingest._group_id."""
    if not tenant_id:
        return "default"
    if tenant_id.startswith("tenant_"):
        return tenant_id
    return f"tenant_{tenant_id}"


# Cypher keywords that indicate writes; reject queries containing these (whole-word).
_CYPHER_READ_FORBIDDEN = frozenset(
    {"CREATE", "MERGE", "SET", "DELETE", "REMOVE", "DROP", "DETACH", "FOREACH"}
)


def _is_read_only_cypher(cypher: str) -> bool:
    """Return True if the Cypher string appears to be read-only (no write clauses)."""
    if not cypher or not cypher.strip():
        return False
    upper = cypher.upper()
    for word in _CYPHER_READ_FORBIDDEN:
        if re.search(r"\b" + re.escape(word) + r"\b", upper):
            return False
    return True


def _to_json_safe(value: Any) -> Any:
    """Recursively convert Neo4j types (e.g. neo4j.time.DateTime) to JSON-serializable values."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {k: _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json_safe(x) for x in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    # Neo4j temporal types (DateTime, Date, Time, etc.) - convert to ISO string
    mod = type(value).__module__
    name = type(value).__name__
    if mod == "neo4j.time":
        if hasattr(value, "iso_format"):
            return value.iso_format()
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
    # Fallback for any other non-JSON type (e.g. neo4j.spatial.Point)
    if hasattr(value, "iso_format"):
        return value.iso_format()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


async def _get_driver():
    """Lazy init async Neo4j driver. Returns None if not configured."""
    global _neo4j_driver
    if _neo4j_driver is not None:
        return _neo4j_driver
    if not _is_neo4j_configured():
        return None
    try:
        _neo4j_driver = AsyncGraphDatabase.driver(
            Config.NEO4J_URI,
            auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD),
        )
        await _neo4j_driver.verify_connectivity()
        return _neo4j_driver
    except Exception as e:
        logger.warning("Failed to create Neo4j driver: %s", e)
        return None


async def run_document_cypher(
    tenant_id: str,
    doc_id: str,
    cypher: str,
    params: Optional[dict[str, Any]] = None,
    max_results: int = 500,
) -> dict[str, Any]:
    """
    Execute a read-only Cypher query scoped to the document's subgraph.

    Guardrails:
    - Rejects queries containing write clauses (CREATE, MERGE, SET, DELETE, REMOVE, DROP, DETACH, FOREACH).
    - Runs inside a read transaction (execute_read).
    - Injects $episode_prefix and $group_id so the query can scope to this doc/tenant; the agent
      must use these in WHERE (e.g. WHERE ep.name STARTS WITH $episode_prefix AND ep.group_id = $group_id).
    - Adds LIMIT if the query does not already contain LIMIT (cap at max_results).

    Returns:
        dict with keys: results (list of record dicts), count (int), truncated (bool).
        On validation or driver failure: results=[], count=0, error=str.
    """
    if not cypher or not cypher.strip():
        return {"results": [], "count": 0, "truncated": False, "error": "Cypher query is empty."}
    if not _is_read_only_cypher(cypher):
        return {
            "results": [],
            "count": 0,
            "truncated": False,
            "error": "Query is not read-only. Only SELECT-style Cypher (MATCH, RETURN, etc.) is allowed.",
        }
    if "MATCH" not in cypher.upper():
        return {"results": [], "count": 0, "truncated": False, "error": "Query must include MATCH."}
    if "RETURN" not in cypher.upper():
        return {"results": [], "count": 0, "truncated": False, "error": "Query must include RETURN."}

    driver = await _get_driver()
    if driver is None:
        return {
            "results": [],
            "count": 0,
            "truncated": False,
            "error": "Neo4j not configured or unavailable (GRAPHITI_ENABLED, NEO4J_*).",
        }

    group = _group_id(tenant_id or "")
    episode_prefix = f"doc_{doc_id}_"
    run_params: dict[str, Any] = dict(params) if params else {}
    run_params["episode_prefix"] = episode_prefix
    run_params["group_id"] = group

    run_cypher = cypher.strip().rstrip(";")
    if "LIMIT" not in run_cypher.upper():
        run_cypher = run_cypher + f" LIMIT {max_results + 1}"
    else:
        run_params["__max_results"] = max_results  # available if agent uses it

    async def _read(tx: Any) -> list[dict[str, Any]]:
        result = await tx.run(run_cypher, run_params)
        records = await result.data()
        out = []
        for rec in records or []:
            row = {}
            for k, v in rec.items():
                row[k] = _to_json_safe(v)
            out.append(row)
        return out

    try:
        async with driver.session() as session:
            records = await session.execute_read(_read)
        truncated = len(records) > max_results
        if truncated:
            records = records[:max_results]
        return {"results": records, "count": len(records), "truncated": truncated}
    except Exception as e:
        logger.exception("run_document_cypher failed: %s", e)
        return {"results": [], "count": 0, "truncated": False, "error": str(e)}


async def count_document_episodes(tenant_id: str, doc_id: str) -> int:
    """
    Count total Episodic nodes (chunks) for a document.
    
    Returns:
        Number of episodes/chunks for the document. Returns 0 if Neo4j is not configured,
        document not found, or query fails.
    """
    driver = await _get_driver()
    if driver is None:
        return 0
    
    group = _group_id(tenant_id or "")
    episode_prefix = f"doc_{doc_id}_"
    
    count_query = """
    MATCH (ep:Episodic)
    WHERE ep.name STARTS WITH $episode_prefix
      AND ep.group_id = $group_id
    RETURN count(ep) AS episode_count
    """
    
    try:
        async with driver.session() as session:
            result = await session.run(
                count_query,
                {"episode_prefix": episode_prefix, "group_id": group}
            )
            record = await result.single()
            if record:
                return record.get("episode_count", 0)
            return 0
    except Exception as e:
        logger.warning("Failed to count document episodes: %s", e)
        return 0


async def get_document_subgraph(tenant_id: str, doc_id: str) -> dict[str, Any]:
    """
    Return nodes and edges for the document's subgraph in Graphiti's Neo4j.

    Episodes are keyed by group_id (tenant_{tenant_id}) and name prefix doc_{doc_id}_.
    Entities connected via MENTIONS; entity-entity edges included when present.

    Returns:
        dict with:
          - nodes: list of {id, labels, properties (dict)}
          - edges: list of {source_id, target_id, type, properties (dict)}
          - error: optional str if query failed
    """
    driver = await _get_driver()
    if driver is None:
        return {
            "nodes": [],
            "edges": [],
            "error": "Neo4j not configured or unavailable (GRAPHITI_ENABLED, NEO4J_*).",
        }

    group = _group_id(tenant_id or "")
    episode_prefix = f"doc_{doc_id}_"

    # Graphiti: Episodic nodes have name, group_id; Entity nodes linked via MENTIONS.
    # Labels: Episodic (episode nodes), Entity.
    nodes_by_id: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def _node_to_dict(node: Any) -> dict[str, Any]:
        """Serialize Neo4j Node to dict (id, labels, properties)."""
        nid = getattr(node, "element_id", None)
        if nid is None and isinstance(node, dict):
            nid = node.get("uuid")
        if nid is None:
            nid = str(id(node))
        labels_list = list(getattr(node, "labels", [])) if hasattr(node, "labels") else (node.get("labels") or ["Entity"] if isinstance(node, dict) else ["Entity"])
        if not labels_list:
            labels_list = ["Entity"]
        props = {}
        if hasattr(node, "keys") and callable(getattr(node, "keys")):
            try:
                props = {k: node[k] for k in node.keys() if node.get(k) is not None}
            except Exception:
                pass
        elif isinstance(node, dict):
            props = {k: v for k, v in node.items() if v is not None and k not in ("labels", "element_id", "uuid")}
        return {"id": nid, "labels": labels_list, "properties": _to_json_safe(props)}

    async def run_query(cypher: str, params: dict[str, Any]) -> list[dict]:
        async with driver.session() as session:
            result = await session.run(cypher, params)
            records = await result.data()
            return list(records) if records else []

    try:
        # 1) Find episodes for this doc (name starts with doc_{doc_id}_ and group_id)
        # Graphiti uses label Episodic for episode nodes
        episode_query = """
        MATCH (ep:Episodic)
        WHERE ep.name STARTS WITH $episode_prefix
          AND ep.group_id = $group_id
        RETURN ep
        LIMIT 500
        """
        episode_records = await run_query(
            episode_query,
            {"episode_prefix": episode_prefix, "group_id": group},
        )
        for rec in episode_records:
            ep = rec.get("ep")
            if not ep:
                continue
            nd = _node_to_dict(ep)
            nid = nd["id"]
            nodes_by_id[nid] = nd

        if not nodes_by_id:
            return {"nodes": [], "edges": []}

        # 2) Entities mentioned by these episodes (MENTIONS)
        mentions_query = """
        MATCH (ep)-[r:MENTIONS]->(ent)
        WHERE ep.name STARTS WITH $episode_prefix AND ep.group_id = $group_id
        RETURN ep, r, ent
        LIMIT 2000
        """
        mention_records = await run_query(
            mentions_query,
            {"episode_prefix": episode_prefix, "group_id": group},
        )
        for rec in mention_records:
            ep = rec.get("ep")
            ent = rec.get("ent")
            if not ent:
                continue
            nd = _node_to_dict(ent)
            eid = nd["id"]
            nodes_by_id[eid] = nd
            if ep:
                sid = _node_to_dict(ep)["id"]
                edges.append({"source_id": sid, "target_id": eid, "type": "MENTIONS", "properties": {}})

        # 3) Entity-entity edges (if Graphiti creates them)
        entity_edges_query = """
        MATCH (ep)-[:MENTIONS]->(a:Entity)-[r]->(b:Entity)
        WHERE ep.name STARTS WITH $episode_prefix AND ep.group_id = $group_id
        RETURN a, type(r) AS rel_type, b
        LIMIT 1000
        """
        try:
            entity_edge_records = await run_query(
                entity_edges_query,
                {"episode_prefix": episode_prefix, "group_id": group},
            )
        except Exception:
            entity_edge_records = []
        for rec in entity_edge_records:
            a, rel_type, b = rec.get("a"), rec.get("rel_type"), rec.get("b")
            if not a or not b or not rel_type:
                continue
            aid = _node_to_dict(a)["id"]
            bid = _node_to_dict(b)["id"]
            if aid in nodes_by_id and bid in nodes_by_id:
                edges.append({"source_id": aid, "target_id": bid, "type": rel_type, "properties": {}})

    except Exception as e:
        logger.exception("Neo4j document subgraph failed: %s", e)
        return {"nodes": [], "edges": [], "error": str(e)}

    return {"nodes": list(nodes_by_id.values()), "edges": edges}
