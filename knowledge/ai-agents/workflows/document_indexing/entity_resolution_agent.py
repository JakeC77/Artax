"""Entity resolution agent: ontology + document subgraph + domain Cypher -> assertions."""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic_ai import RunContext

from app.config import Config
from app.workflows.document_indexing import entity_cache
from app.workflows.document_indexing import neo4j_document_graph
from app.workflows.document_indexing import storage
from app.workflows.document_indexing.config import load_config
from app.workflows.document_indexing.status_tracker import update_attachment_status
from app.core.authenticated_graphql_client import run_graphql

logger = logging.getLogger(__name__)

# Default max tool calls per agent run (configurable via ENTITY_RESOLUTION_MAX_TOOL_CALLS)
_DEFAULT_MAX_TOOL_CALLS = 30

# GraphQL query for domain graph Cypher (same shape as cypher_query tool)
_DOMAIN_CYPHER_QUERY = """
query ExecuteCypher($cypherQuery: String!, $workspaceId: UUID) {
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


# ---------------------------------------------------------------------------
# Pydantic models for agent output (match user spec)
# ---------------------------------------------------------------------------

try:
    from pydantic import BaseModel, Field
except ImportError:
    BaseModel = None  # type: ignore[misc, assignment]
    Field = None  # type: ignore[misc, assignment]


def _ensure_pydantic():
    if BaseModel is None:
        raise ImportError("pydantic is required for entity resolution agent. pip install pydantic")


if BaseModel is not None:

    class MiningEntity(BaseModel):
        """Document-side entity only (no domain reconciliation)."""

        document_entity_name: str = Field(description="Name as it appears in the document")

    class MiningAssertionRecord(BaseModel):
        """One mined assertion: source_entity <assertion> terminal_entity (document-side only)."""

        source_entity: MiningEntity = Field(description="Subject entity (e.g. patient)")
        assertion: str = Field(description="Relationship or action, e.g. 'was prescribed'")
        terminal_entity: MiningEntity = Field(description="Object entity (e.g. medication)")
        source: str = Field(default="", description="Document name for provenance")
        source_url: str = Field(default="", description="Document URL for provenance")

    class MiningAssertionOutput(BaseModel):
        """Phase 1 output: list of mined assertions (no domain fields)."""

        assertions: list[MiningAssertionRecord] = Field(description="List of mined assertion records")

    class ResolvedEntity(BaseModel):
        """Source or terminal entity with optional domain reconciliation."""

        document_entity_name: str = Field(description="Name as it appears in the document")
        domain_entity_name: Optional[str] = Field(default=None, description="Canonical name in domain graph if reconciled")
        domain_node_id: Optional[str] = Field(default=None, description="Domain graph node id if reconciled")
        domain_entity_type: Optional[str] = Field(default=None, description="Domain entity type / node label if known")

    class AssertionRecord(BaseModel):
        """One assertion: source_entity <assertion> terminal_entity (with domain reconciliation)."""

        source_entity: ResolvedEntity = Field(description="Subject entity (e.g. patient)")
        assertion: str = Field(description="Relationship or action, e.g. 'was prescribed'")
        terminal_entity: ResolvedEntity = Field(description="Object entity (e.g. medication)")
        source: str = Field(default="", description="Document name for provenance")
        source_url: str = Field(default="", description="Document URL for provenance")

    class EntityResolutionOutput(BaseModel):
        """Phase 2 output: list of assertions with domain reconciliation."""

        assertions: list[AssertionRecord] = Field(description="List of assertion records")

    class ResolvedEntityRecord(BaseModel):
        """One document entity and its reconciled domain node (if matched)."""

        document_entity_id: Optional[str] = Field(default=None, description="Neo4j node id from document graph")
        document_entity_name: str = Field(description="Entity name from document graph")
        summary: Optional[str] = Field(default=None, description="Summary from document Entity node (context)")
        domain_node_id: Optional[str] = Field(default=None, description="Domain graph node id if matched")
        domain_entity_name: Optional[str] = Field(default=None, description="Canonical name in domain graph if matched")
        domain_entity_type: Optional[str] = Field(default=None, description="Domain entity type / node label if known")

    class ResolvedEntitiesOutput(BaseModel):
        """Output: list of document entities with reconciled domain_node_id when matched."""

        entities: list[ResolvedEntityRecord] = Field(description="List of resolved entity records")


def _assertion_to_dict(rec: Any) -> dict[str, Any]:
    """Convert AssertionRecord to JSON-serializable dict (snake_case for storage)."""
    if hasattr(rec, "model_dump"):
        d = rec.model_dump()
    else:
        d = dict(rec)
    return d


def _mining_record_to_dict(rec: Any) -> dict[str, Any]:
    """Convert MiningAssertionRecord to JSON-serializable dict."""
    if hasattr(rec, "model_dump"):
        return rec.model_dump()
    return dict(rec)


def _resolved_entity_record_to_dict(rec: Any) -> dict[str, Any]:
    """Convert ResolvedEntityRecord to JSON-serializable dict."""
    if hasattr(rec, "model_dump"):
        return rec.model_dump()
    return dict(rec)


async def _run_agent_with_tool_limit(agent: Any, prompt: str, deps: dict[str, Any], max_tool_calls: int) -> Any:
    """
    Run agent via iter(), stopping after max_tool_calls tool-call steps.
    Returns AgentRunResult if the run completed, None if limit exceeded or run did not finish.
    """
    tool_calls = 0
    result = None
    async with agent.iter(prompt, deps=deps) as agent_run:
        async for node in agent_run:
            if type(node).__name__ == "CallToolsNode":
                tool_calls += 1
                if tool_calls > max_tool_calls:
                    logger.warning(
                        "Entity resolution agent exceeded max tool calls (%s); stopping",
                        max_tool_calls,
                    )
                    break
        result = agent_run.result
    return result


async def _run_entity_resolution_agent(
    tenant_id: str,
    doc_id: str,
    source: str,
    source_url: str,
    *,
    workspace_id: Optional[str] = None,
    workspace_node_ids: Optional[dict[str, list[str]]] = None,
    blob_client: Any = None,
    scratchpad_attachment_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Single entity-resolution agent: query document subgraph for entities (with summary),
    use summary as context to reconcile each to the domain graph, return list of
    resolved entity records (document entity + domain_node_id when matched).
    """
    _ensure_pydantic()
    from pydantic_ai import Agent
    from app.core.model_factory import create_model

    async def get_ontology(ctx: RunContext[dict]) -> dict[str, Any]:
        tid = ctx.deps.get("tenant_id") or tenant_id
        entities = await entity_cache.get_semantic_entities(tid)
        return {
            "entities": [
                {
                    "semantic_entity_id": e.semantic_entity_id,
                    "node_label": e.node_label,
                    "name": e.name,
                    "description": e.description,
                    "fields": [{"name": f.name, "data_type": f.data_type, "description": f.description} for f in e.fields],
                }
                for e in entities
            ],
        }

    async def query_document_graph(
        ctx: RunContext[dict], query: str, max_results: int = 500
    ) -> dict[str, Any]:
        """Execute read-only Cypher against the document's Neo4j subgraph. Scope with $episode_prefix and $group_id. Schema: Episodic (chunk nodes), Entity (name, summary), (ep)-[:MENTIONS]->(ent). Return entities with name and summary for reconciliation."""
        tid = ctx.deps.get("tenant_id") or tenant_id
        did = ctx.deps.get("doc_id") or doc_id
        return await neo4j_document_graph.run_document_cypher(
            tid, did, query, params=None, max_results=max_results
        )

    async def query_domain_graph(ctx: RunContext[dict], query: str, max_results: int = 500) -> dict[str, Any]:
        tid = ctx.deps.get("tenant_id") or tenant_id
        if not query or "MATCH" not in query.upper() or "RETURN" not in query.upper():
            return {"error": "Query must include MATCH and RETURN", "results": [], "count": 0}
        q = query.strip()
        if "LIMIT" not in q.upper():
            q = f"{q} LIMIT {max_results + 1}"
        workspace_id = ctx.deps.get("workspace_id")
        variables = {"cypherQuery": q}
        if workspace_id:
            variables["workspaceId"] = workspace_id
        try:
            result = await run_graphql(
                _DOMAIN_CYPHER_QUERY,
                variables,
                tenant_id=tid,
                timeout=30,
            )
        except Exception as e:
            return {"error": str(e), "results": [], "count": 0}
        nodes = result.get("graphNodesByCypher", [])
        formatted = []
        for node in nodes:
            if not node:
                continue
            props = {p["key"]: p["value"] for p in node.get("properties", [])}
            formatted.append({"id": node.get("id"), "labels": node.get("labels", []), **props})
        return {"results": formatted, "count": len(formatted), "truncated": len(formatted) > max_results}

    async def write_note(ctx: RunContext[dict], key: str, content: str) -> dict[str, Any]:
        tid = ctx.deps.get("tenant_id") or tenant_id
        did = ctx.deps.get("doc_id") or doc_id
        bc = ctx.deps.get("blob_client")
        return storage.write_agent_note(tid, did, key, content, blob_service=bc)

    async def read_note(ctx: RunContext[dict], key: str) -> dict[str, Any]:
        tid = ctx.deps.get("tenant_id") or tenant_id
        did = ctx.deps.get("doc_id") or doc_id
        bc = ctx.deps.get("blob_client")
        return storage.read_agent_note(tid, did, key, blob_service=bc)

    # Load workflow config (with fallback to environment variables for backward compatibility)
    workflow_config = load_config()
    try:
        model = workflow_config.entity_resolution_model.create()
    except Exception as e:
        # Fallback to environment variables or default
        model_name = getattr(Config, "ENTITY_RESOLUTION_MODEL", None) or "gemini-2.5-flash"
        provider = getattr(Config, "ENTITY_RESOLUTION_PROVIDER", "google") or "google"
        try:
            model = create_model(model_name, provider=provider)
        except Exception as e2:
            logger.warning("Entity resolution create_model failed: %s; retrying gemini-2.5-flash", e2)
            model = create_model("gemini-2.5-flash", provider="google")

    agent = Agent(
        model=model,
        output_type=ResolvedEntitiesOutput,
        tools=[get_ontology, query_document_graph, query_domain_graph, write_note, read_note],
        deps_type=dict,
    )

    deps: dict[str, Any] = {"tenant_id": tenant_id, "doc_id": doc_id}
    if workspace_id:
        deps["workspace_id"] = workspace_id
    if workspace_node_ids:
        deps["workspace_node_ids"] = workspace_node_ids
    if blob_client is not None:
        deps["blob_client"] = blob_client

    system_prompt = """You are an entity resolution expert. Your job is to reconcile document entities to the domain graph.

Document graph: Episodic nodes (chunks) link to Entity nodes via MENTIONS. Each Entity has name and summary (facts about that entity). Scope queries with WHERE ep.name STARTS WITH $episode_prefix AND ep.group_id = $group_id.

Workflow:
1. Use query_document_graph to run Cypher that returns all Entity nodes linked to this document's episodes—include entity id (element_id(ent)), name, and summary. Example: MATCH (ep:Episodic)-[:MENTIONS]->(ent:Entity) WHERE ep.name STARTS WITH $episode_prefix AND ep.group_id = $group_id RETURN elementId(ent) AS document_entity_id, ent.name AS document_entity_name, ent.summary AS summary LIMIT 500
2. For each document entity, use its summary as context. Use get_ontology and query_domain_graph to find a matching domain node when possible (by name, type, or description).
3. Output one ResolvedEntityRecord per document entity. Set document_entity_id, document_entity_name, summary (optional). Set domain_node_id, domain_entity_name, domain_entity_type when you find a match; otherwise leave them null.

Output: ResolvedEntitiesOutput with entities list. Each ResolvedEntityRecord has document_entity_id (optional), document_entity_name, summary (optional), domain_node_id (optional), domain_entity_name (optional), domain_entity_type (optional)."""

    prompt = f"""Reconcile document entities to the domain graph for this document. Document name: {source or doc_id}. Document URL: {source_url or ''}.

Steps:
1. Call query_document_graph with Cypher to fetch all Entity nodes for this document's episodes (include document_entity_id, document_entity_name, summary). Use $episode_prefix and $group_id in WHERE.
2. For each entity, use its summary as context and query_domain_graph to find a matching domain node. Set domain_node_id, domain_entity_name, domain_entity_type when matched.
3. Return ResolvedEntitiesOutput with one record per document entity; include domain_node_id when a match was found."""

    max_tool_calls = getattr(Config, "ENTITY_RESOLUTION_MAX_TOOL_CALLS", _DEFAULT_MAX_TOOL_CALLS)
    result = await _run_agent_with_tool_limit(agent, prompt, deps, max_tool_calls)
    if result is None:
        return []
    out_obj = result.output
    if not out_obj or not getattr(out_obj, "entities", None):
        return []
    out_list = [_resolved_entity_record_to_dict(r) for r in out_obj.entities]
    for d in out_list:
        d.setdefault("source", source)
        d.setdefault("source_url", source_url)
    return out_list


async def _run_assertion_mining_agent(
    tenant_id: str,
    doc_id: str,
    source: str,
    source_url: str,
    *,
    blob_client: Any = None,
    scratchpad_attachment_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Phase 1: Mine document subgraph for assertions (document-side only). Tools: get_ontology, query_document_graph, write_note, read_note."""
    _ensure_pydantic()
    from pydantic_ai import Agent
    from app.core.model_factory import create_model

    async def get_ontology(ctx: RunContext[dict]) -> dict[str, Any]:
        tid = ctx.deps.get("tenant_id") or tenant_id
        entities = await entity_cache.get_semantic_entities(tid)
        return {
            "entities": [
                {
                    "semantic_entity_id": e.semantic_entity_id,
                    "node_label": e.node_label,
                    "name": e.name,
                    "description": e.description,
                    "fields": [{"name": f.name, "data_type": f.data_type, "description": f.description} for f in e.fields],
                }
                for e in entities
            ],
        }

    async def query_document_graph(
        ctx: RunContext[dict], query: str, max_results: int = 500
    ) -> dict[str, Any]:
        """Execute read-only Cypher against the document's Neo4j subgraph. Scope queries with $episode_prefix and $group_id. Schema: Episodic (chunk nodes: name, group_id); Entity (nodes with name, summary); (ep)-[:MENTIONS]->(ent). Each Entity's summary field contains facts about that entity—use these to derive assertions. Only MATCH/RETURN allowed."""
        tid = ctx.deps.get("tenant_id") or tenant_id
        did = ctx.deps.get("doc_id") or doc_id
        return await neo4j_document_graph.run_document_cypher(
            tid, did, query, params=None, max_results=max_results
        )

    async def write_note(ctx: RunContext[dict], key: str, content: str) -> dict[str, Any]:
        """Persist a working-memory note for this document run. Use for batch progress, assertions so far, or key entities when processing large data. Key: 1–64 chars, alphanumeric/underscore/hyphen only. Content: max 256 KB. Stored in same blob container as other processed artifacts."""
        tid = ctx.deps.get("tenant_id") or tenant_id
        did = ctx.deps.get("doc_id") or doc_id
        blob_client = ctx.deps.get("blob_client")
        return storage.write_agent_note(tid, did, key, content, blob_service=blob_client)

    async def read_note(ctx: RunContext[dict], key: str) -> dict[str, Any]:
        """Read a working-memory note previously written for this document run. Key: 1–64 chars, alphanumeric/underscore/hyphen only. Returns {ok: true, content: str} or {ok: false, error: str}."""
        tid = ctx.deps.get("tenant_id") or tenant_id
        did = ctx.deps.get("doc_id") or doc_id
        blob_client = ctx.deps.get("blob_client")
        return storage.read_agent_note(tid, did, key, blob_service=blob_client)

    # Load workflow config (with fallback to environment variables for backward compatibility)
    workflow_config = load_config()
    try:
        model = workflow_config.assertion_mining_model.create()
    except Exception as e:
        # Fallback to environment variables or default
        model_name = getattr(Config, "ENTITY_RESOLUTION_MODEL", None) or "gemini-2.5-flash"
        provider = getattr(Config, "ENTITY_RESOLUTION_PROVIDER", "google") or "google"
        try:
            model = create_model(model_name, provider=provider)
        except Exception as e2:
            logger.warning("Assertion mining create_model failed: %s; retrying gemini-2.5-flash", e2)
            model = create_model("gemini-2.5-flash", provider="google")

    agent = Agent(
        model=model,
        output_type=MiningAssertionOutput,
        tools=[get_ontology, query_document_graph, write_note, read_note],
        deps_type=dict,
    )

    deps: dict[str, Any] = {"tenant_id": tenant_id, "doc_id": doc_id}
    if blob_client is not None:
        deps["blob_client"] = blob_client
    system_prompt = """You are an assertion mining expert. Your job is to derive structured assertions from the document graph.

Document graph schema:
- Episodic: each node represents a chunk of the document (properties: name, group_id). Scope with WHERE ep.name STARTS WITH $episode_prefix AND ep.group_id = $group_id.
- Entity: nodes for people, things, concepts mentioned in the document (properties: name, summary). The summary field contains facts about that entity—this is your main source for assertions.
- (ep:Episodic)-[:MENTIONS]->(ent:Entity) links each chunk to the entities it mentions.

Workflow:
1. Use query_document_graph to run Cypher that gets, for this document's Episodic nodes, all linked Entity nodes and their summary (see example query below).
2. Read the summary text on each Entity; it contains facts (relationships, actions, attributes) about that entity and others.
3. Turn those facts into assertions of the form "source_entity <assertion> terminal_entity".

Example query to get entities by the episode they were mentioned in (use $episode_prefix and $group_id; the tool injects these):
  MATCH (ep:Episodic)-[:MENTIONS]->(ent:Entity)
  WHERE ep.name STARTS WITH $episode_prefix AND ep.group_id = $group_id
  RETURN ep.name AS episode_name, ent.name AS entity_name, ent.summary AS entity_summary
  LIMIT 500

When processing large data, you can use write_note(key, content) to persist progress (e.g. assertions so far, entities seen) and read_note(key) to read it back later; notes are stored in the same blob container as other processed artifacts. Key: alphanumeric/underscore/hyphen only, max 64 chars; content max 256 KB.

Output: MiningAssertionOutput with assertions list. Each MiningAssertionRecord has source_entity (MiningEntity with document_entity_name), assertion (short verb phrase), terminal_entity (MiningEntity with document_entity_name), source, source_url."""

    prompt = f"""Produce mined assertions for this document. Document name: {source or doc_id}. Document URL: {source_url or ''}.

Steps:
1. Call query_document_graph with Cypher to fetch all Entity nodes linked to this document's Episodic (chunk) nodes. Example query (entities by episode):
   MATCH (ep:Episodic)-[:MENTIONS]->(ent:Entity)
   WHERE ep.name STARTS WITH $episode_prefix AND ep.group_id = $group_id
   RETURN ep.name AS episode_name, ent.name AS entity_name, ent.summary AS entity_summary
   LIMIT 500
2. From each Entity's summary (facts about that entity), derive assertions: source_entity <assertion> terminal_entity.
3. Return MiningAssertionOutput with those assertions; set source and source_url from the document name/URL above.

Example of deriving assertions from a sentence:
- Sentence (or summary fact): "Dr. Chen prescribed metformin to the patient for type 2 diabetes."
- Assertions you might extract:
  - source_entity: Dr. Chen, assertion: prescribed, terminal_entity: metformin
  - source_entity: patient, assertion: was prescribed, terminal_entity: metformin
  - source_entity: patient, assertion: has condition, terminal_entity: type 2 diabetes

Do not fill in any domain fields (domain_entity_name, domain_node_id, domain_entity_type)."""

    # Use config max_tool_calls (with fallback to environment variable for backward compatibility)
    max_tool_calls = getattr(Config, "ENTITY_RESOLUTION_MAX_TOOL_CALLS", None) or workflow_config.entity_resolution_max_tool_calls
    result = await _run_agent_with_tool_limit(agent, prompt, deps, max_tool_calls)
    if result is None:
        return []
    out_obj = result.output
    if not out_obj or not getattr(out_obj, "assertions", None):
        return []
    out_list = [_mining_record_to_dict(r) for r in out_obj.assertions]
    for d in out_list:
        d.setdefault("source", source)
        d.setdefault("source_url", source_url)
    return out_list


async def _run_entity_resolution_phase2_agent(
    mined_assertions: list[dict[str, Any]],
    tenant_id: str,
    doc_id: str,
    source: str,
    source_url: str,
    workspace_id: Optional[str] = None,
    workspace_node_ids: Optional[dict[str, list[str]]] = None,
) -> list[dict[str, Any]]:
    """Phase 2: Resolve mined assertions to domain graph. Tools: get_ontology, query_domain_graph. Input: mined_assertions from phase 1."""
    _ensure_pydantic()
    from pydantic_ai import Agent
    from app.core.model_factory import create_model

    async def get_ontology(ctx: RunContext[dict]) -> dict[str, Any]:
        tid = ctx.deps.get("tenant_id") or tenant_id
        entities = await entity_cache.get_semantic_entities(tid)
        return {
            "entities": [
                {
                    "semantic_entity_id": e.semantic_entity_id,
                    "node_label": e.node_label,
                    "name": e.name,
                    "description": e.description,
                    "fields": [{"name": f.name, "data_type": f.data_type, "description": f.description} for f in e.fields],
                }
                for e in entities
            ],
        }

    async def query_domain_graph(ctx: RunContext[dict], query: str, max_results: int = 500) -> dict[str, Any]:
        tid = ctx.deps.get("tenant_id") or tenant_id
        if not query or "MATCH" not in query.upper() or "RETURN" not in query.upper():
            return {"error": "Query must include MATCH and RETURN", "results": [], "count": 0}
        q = query.strip()
        if "LIMIT" not in q.upper():
            q = f"{q} LIMIT {max_results + 1}"
        workspace_id = ctx.deps.get("workspace_id")
        variables = {"cypherQuery": q}
        if workspace_id:
            variables["workspaceId"] = workspace_id
        try:
            result = await run_graphql(
                _DOMAIN_CYPHER_QUERY,
                variables,
                tenant_id=tid,
                timeout=30,
            )
        except Exception as e:
            return {"error": str(e), "results": [], "count": 0}
        nodes = result.get("graphNodesByCypher", [])
        formatted = []
        for node in nodes:
            if not node:
                continue
            props = {p["key"]: p["value"] for p in node.get("properties", [])}
            formatted.append({"id": node.get("id"), "labels": node.get("labels", []), **props})
        return {"results": formatted, "count": len(formatted), "truncated": len(formatted) > max_results}

    # Load workflow config (with fallback to environment variables for backward compatibility)
    workflow_config = load_config()
    try:
        model = workflow_config.entity_resolution_phase2_model.create()
    except Exception as e:
        # Fallback to environment variables or default
        model_name = getattr(Config, "ENTITY_RESOLUTION_MODEL", None) or "gemini-2.5-flash"
        provider = getattr(Config, "ENTITY_RESOLUTION_PROVIDER", "google") or "google"
        try:
            model = create_model(model_name, provider=provider)
        except Exception as e2:
            logger.warning("Entity resolution phase2 create_model failed: %s; retrying gemini-2.5-flash", e2)
            model = create_model("gemini-2.5-flash", provider="google")

    agent = Agent(
        model=model,
        output_type=EntityResolutionOutput,
        tools=[get_ontology, query_domain_graph],
        deps_type=dict,
    )

    deps: dict[str, Any] = {
        "tenant_id": tenant_id,
        "doc_id": doc_id,
        "mined_assertions": mined_assertions,
    }
    if workspace_id:
        deps["workspace_id"] = workspace_id
    if workspace_node_ids:
        deps["workspace_node_ids"] = workspace_node_ids

    system_prompt = """You are an entity resolution expert. You have a list of mined assertions (source_entity document name, assertion, terminal_entity document name). You have access to:
1. get_ontology - semantic entity definitions for the enterprise ontology.
2. query_domain_graph - run Cypher against the domain/workspace graph to find candidate entities by name or type and get their id. All names have proper capitalization in the graph.

Your task: For each mined assertion, resolve source_entity and terminal_entity to the domain graph when possible. Use query_domain_graph to look up entities by name/label. Set domain_entity_name, domain_node_id, and domain_entity_type when you find a match. If you cannot reconcile, leave those fields null. Output EntityResolutionOutput with assertions list; each AssertionRecord has source_entity (ResolvedEntity: document_entity_name required, domain_entity_name/domain_node_id/domain_entity_type optional), assertion, terminal_entity (same), source, source_url."""
    prompt = f"""You have {len(mined_assertions)} mined assertions for document {source or doc_id}. Resolve each entity to the domain graph using get_ontology and query_domain_graph. Return EntityResolutionOutput with assertions; fill domain_entity_name, domain_node_id, domain_entity_type when you can match to a domain node, otherwise leave null."""

    # Use config max_tool_calls (with fallback to environment variable for backward compatibility)
    max_tool_calls = getattr(Config, "ENTITY_RESOLUTION_MAX_TOOL_CALLS", None) or workflow_config.entity_resolution_max_tool_calls
    result = await _run_agent_with_tool_limit(agent, prompt, deps, max_tool_calls)
    if result is None:
        return []
    out_obj = result.output
    if not out_obj or not getattr(out_obj, "assertions", None):
        return []
    out_list = [_assertion_to_dict(r) for r in out_obj.assertions]
    for d in out_list:
        d.setdefault("source", source)
        d.setdefault("source_url", source_url)
    return out_list


async def run_entity_resolution(
    tenant_id: str,
    doc_id: str,
    *,
    workspace_id: Optional[str] = None,
    workspace_node_ids: Optional[dict[str, list[str]]] = None,
    source: str = "",
    source_url: str = "",
    blob_client: Any = None,
    scratchpad_attachment_id: Optional[str] = None,
) -> tuple[list[dict[str, Any]], str]:
    """
    Run assertion mining (upload assertions.json), then entity resolution (query document subgraph,
    reconcile to domain graph, upload resolved_entities.json). Returns (resolved entities list,
    resolved_entities blob path). No dependency between the two; both run in the main path.
    """
    # Assertion mining (main path): mine assertions, upload assertions.json
    mined = await _run_assertion_mining_agent(
        tenant_id=tenant_id,
        doc_id=doc_id,
        source=source,
        source_url=source_url,
        blob_client=blob_client,
        scratchpad_attachment_id=scratchpad_attachment_id,
    )
    assertions_path = storage.upload_assertions(
        tenant_id,
        doc_id,
        mined,
        source=source,
        source_url=source_url,
        blob_service=blob_client,
    )
    logger.info("Assertion mining: %d assertions -> %s", len(mined), assertions_path)

    # Entity resolution (phase 2): query doc graph, reconcile, upload resolved_entities.json
    # Temporarily disabled via config flag (with fallback to environment variable)
    workflow_config = load_config()
    phase2_enabled = getattr(Config, "ENTITY_RESOLUTION_PHASE2_ENABLED", None)
    if phase2_enabled is None:
        phase2_enabled = workflow_config.entity_resolution_phase2_enabled
    if not phase2_enabled:
        logger.info("Entity resolution phase 2 disabled; skipping entity resolution")
        return [], ""
    
    # Update status: entity-resolution (will be updated with progress during execution)
    if scratchpad_attachment_id:
        try:
            await update_attachment_status(
                scratchpad_attachment_id,
                tenant_id,
                processing_status="entity-resolution",
            )
        except Exception:
            pass  # Don't let status update failure block workflow
    
    resolved = await _run_entity_resolution_agent(
        tenant_id=tenant_id,
        doc_id=doc_id,
        source=source,
        source_url=source_url,
        workspace_id=workspace_id,
        workspace_node_ids=workspace_node_ids,
        blob_client=blob_client,
        scratchpad_attachment_id=scratchpad_attachment_id,
    )
    path = storage.upload_resolved_entities(
        tenant_id,
        doc_id,
        resolved,
        source=source,
        source_url=source_url,
        blob_service=blob_client,
    )
    return resolved, path


async def run_entity_resolution_only(
    tenant_id: str,
    doc_id: str,
    *,
    workspace_id: Optional[str] = None,
    workspace_node_ids: Optional[dict[str, list[str]]] = None,
    source: str = "",
    source_url: str = "",
    blob_client: Any = None,
    scratchpad_attachment_id: Optional[str] = None,
) -> tuple[list[dict[str, Any]], str]:
    """
    Run entity resolution: query document subgraph for entities, reconcile to domain graph,
    upload resolved_entities.json. Same as run_entity_resolution (no blob input).
    Returns (resolved entities list, resolved_entities blob path).
    """
    return await run_entity_resolution(
        tenant_id=tenant_id,
        doc_id=doc_id,
        workspace_id=workspace_id,
        workspace_node_ids=workspace_node_ids,
        source=source,
        source_url=source_url,
        blob_client=blob_client,
        scratchpad_attachment_id=scratchpad_attachment_id,
    )
