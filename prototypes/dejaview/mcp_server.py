#!/usr/bin/env python3
"""
DejaView MCP Server
Gives any MCP-compatible AI host (Claude Desktop, Cursor, Windsurf, etc.)
persistent memory via the DejaView knowledge graph API.

Install:
  pip install mcp httpx

Configure (Claude Desktop):
  ~/.config/claude/claude_desktop_config.json
  {
    "mcpServers": {
      "dejaview": {
        "command": "python3",
        "args": ["/path/to/mcp_server.py"],
        "env": { "DEJAVIEW_API_KEY": "dv_your_key_here" }
      }
    }
  }

Env vars:
  DEJAVIEW_API_KEY   required
  DEJAVIEW_ENDPOINT  optional, default https://api.dejaview.io
"""

import os, sys, httpx
from mcp.server.fastmcp import FastMCP

ENDPOINT = os.getenv("DEJAVIEW_ENDPOINT", "https://api.dejaview.io").rstrip("/")
API_KEY  = os.getenv("DEJAVIEW_API_KEY", "")

if not API_KEY:
    print("DEJAVIEW_API_KEY not set.", file=sys.stderr)
    sys.exit(1)

mcp = FastMCP(
    "DejaView",
    instructions=(
        "You have a persistent knowledge graph via DejaView. "
        "Call agent_context() at session start to load your memory. "
        "Use remember() whenever you learn something worth keeping. "
        "Use recall() for full details on any entity."
    ),
)

def _h():
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

def _call(method, path, **kw):
    with httpx.Client(timeout=15) as c:
        r = c.request(method, f"{ENDPOINT}{path}", headers=_h(), **kw)
        r.raise_for_status()
        return r.json()

# ─── Tools ───────────────────────────────────────────────────────────────────

@mcp.tool()
def remember(subject: str, predicate: str, object: str, context: str = None) -> str:
    """Store a fact as subject -> predicate -> object.

    Use for any relationship, preference, decision, or event worth keeping.
    Good predicates: works_at, founded, knows, prefers, uses, has_status,
    decided, attended, lives_in, expert_in, manages, built_with, is_agent_of

    Examples:
      remember("Alice", "works_at", "Orbit Labs")
      remember("Project Atlas", "has_status", "in progress", "As of Q1 2026")
    """
    payload = {"facts": [{"subject": subject, "predicate": predicate, "object": object}]}
    if context:
        payload["facts"][0]["context"] = context
    result = _call("POST", "/v1/facts", json=payload)
    if result.get("stored", 0):
        return f"Remembered: {subject} {predicate} {object}"
    errors = [r.get("error") for r in result.get("results", []) if "error" in r]
    return f"Not stored. Errors: {errors}" if errors else str(result)


@mcp.tool()
def remember_many(facts: list) -> str:
    """Store multiple facts at once (more efficient than looping remember()).

    Each dict needs: subject, predicate, object
    Optional: context, confidence (0-1), source

    Example:
      [{"subject": "Alice", "predicate": "works_at", "object": "Orbit Labs"},
       {"subject": "Alice", "predicate": "founded",  "object": "Cascade AI"}]
    """
    if not facts:
        return "No facts provided."
    result = _call("POST", "/v1/facts", json={"facts": facts[:100]})
    stored = result.get("stored", 0)
    total  = result.get("total", len(facts))
    errors = [r.get("error") for r in result.get("results", []) if "error" in r]
    msg = f"Stored {stored}/{total} facts."
    if errors:
        msg += f" Errors: {errors[:3]}"
    return msg


@mcp.tool()
def recall(entity: str) -> str:
    """Get everything known about an entity — all relationships in and out.

    Use for full context on a person, project, org, concept, etc.
    Try search() first if you are not sure of the exact name.
    """
    try:
        result = _call("GET", f"/v1/entities/{entity}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"Nothing found for '{entity}'. Try search() first."
        raise

    lines = [f"{entity}"]
    out = result.get("outgoing", [])
    if out:
        lines.append("Outgoing:")
        for r in out:
            rel = r.get("type", "").lower().replace("_", " ")
            ctx = f"  ({r['context']})" if r.get("context") else ""
            lines.append(f"  -> {rel}: {r.get('target','')}{ctx}")

    inc = result.get("incoming", [])
    if inc:
        lines.append("Incoming:")
        for r in inc:
            rel = r.get("type", "").lower().replace("_", " ")
            lines.append(f"  <- {r.get('source','')} {rel}")

    if not out and not inc:
        return f"'{entity}' exists but has no relationships yet."
    return "\n".join(lines)


@mcp.tool()
def search(query: str) -> str:
    """Search for entities in the graph by name (partial match).

    Use this to discover what's in the graph before calling recall().
    Returns names, types, and connection counts.
    """
    result = _call("POST", "/v1/search", json={"q": query, "limit": 20})
    results = result.get("results", [])
    if not results:
        return f"No entities found matching '{query}'."
    lines = [f"Found {len(results)} match(es) for '{query}':"]
    for r in results:
        lines.append(f"  - {r.get('name','')} ({r.get('type','Entity')}) -- {r.get('connections',0)} connection(s)")
    return "\n".join(lines)


@mcp.tool()
def timeline(limit: int = 20) -> str:
    """Get recent facts in reverse chronological order.

    Use this at session start to see what was recently remembered.
    limit: number of facts (default 20, max 100)
    """
    result = _call("GET", f"/v1/timeline?limit={min(limit, 100)}")
    facts = result.get("facts", [])
    if not facts:
        return "No facts recorded yet."
    lines = [f"Last {len(facts)} fact(s):"]
    for f in facts:
        subj = f.get("subject", "")
        pred = (f.get("predicate") or f.get("relationship") or "").lower().replace("_", " ")
        obj  = f.get("object", "")
        ts   = (f.get("created_at") or "")[:10]
        lines.append(f"  {subj} -> {pred} -> {obj}" + (f" [{ts}]" if ts else ""))
    return "\n".join(lines)


@mcp.tool()
def graph_stats() -> str:
    """Get a high-level summary: entity count, types, relationship count."""
    result = _call("GET", "/v1/stats")
    entities  = result.get("entities", 0)
    rels      = result.get("relationships", 0)
    types     = result.get("entity_types", result.get("types", []))
    rel_types = result.get("relationship_types", [])
    lines = [
        "Graph Summary",
        f"  Entities:      {entities}",
        f"  Relationships: {rels}",
    ]
    if types:
        lines.append(f"  Entity types:  {', '.join(t for t in types if t)}")
    if rel_types:
        sample = ', '.join(r.lower().replace('_',' ') for r in rel_types[:8] if r)
        lines.append(f"  Rel types:     {sample}{'...' if len(rel_types) > 8 else ''}")
    return "\n".join(lines)


@mcp.tool()
def agent_context() -> str:
    """Get a full context block summarizing the knowledge graph.

    Call this at session start to bootstrap your memory. Returns entity
    counts, most-connected entities, and recent activity.
    """
    result = _call("GET", "/v1/agent-context")
    return result.get("context", "Knowledge graph is empty or unavailable.")



@mcp.tool()
def forget(subject: str, predicate: str, object: str) -> str:
    """Remove a specific fact from the knowledge graph.

    Deletes the relationship between subject and object but leaves
    both entities intact. Use to correct wrong or outdated facts.

    Example:
      forget("SnapQuote", "is_a", "Insurance Quoting Platform")
    """
    try:
        result = _call("DELETE", "/v1/facts",
                       json={"subject": subject, "predicate": predicate, "object": object})
        return f"Forgotten: {subject} {predicate} {object}"
    except Exception as e:
        return f"Could not delete: {e}"


@mcp.tool()
def forget_entity(name: str) -> str:
    """Remove an entity AND all its relationships from the knowledge graph.

    Use with care — this wipes the node and every edge connected to it.
    Good for removing entirely wrong or duplicate entities.

    Example:
      forget_entity("Insurance Quoting Platform")
    """
    try:
        result = _call("DELETE", f"/v1/entities/{name}")
        rels = result.get("relationships_removed", 0)
        return f"Deleted entity '{name}' and {rels} relationship(s)."
    except Exception as e:
        return f"Could not delete: {e}"


if __name__ == "__main__":
    mcp.run()
