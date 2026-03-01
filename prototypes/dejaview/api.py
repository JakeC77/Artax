"""
DejaView API v1
Personal Knowledge Graph as a Service

Core improvements over artax-kg prototype:
- Typed relationships (predicate becomes relationship type)
- Entity label inference
- Name deduplication / normalization
- API key auth
- Temporal metadata on everything
"""

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from neo4j import GraphDatabase
from typing import Optional, List, Dict, Any
from datetime import datetime
import os
import re
import hashlib
import secrets
from dotenv import load_dotenv
load_dotenv()

def _clean_props(props: dict) -> dict:
    """Clean Neo4j properties for JSON serialization."""
    clean = {}
    for k, v in props.items():
        if k.startswith('_'):
            continue
        try:
            import json
            json.dumps(v)
            clean[k] = v
        except (TypeError, ValueError):
            clean[k] = str(v)
    return clean

app = FastAPI(
    title="DejaView API",
    description="Personal knowledge graph as a service. Your knowledge, connected.",
    version="1.0.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Neo4j connection
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    auth=(
        os.getenv("NEO4J_USER", "neo4j"),
        os.getenv("NEO4J_PASSWORD", ""),
    ),
)

# ============ Auth ============

# For MVP: API keys stored in memory / env. Production: database.
API_KEYS: Dict[str, dict] = {}

def _load_keys():
    """Load API keys — from Neo4j first, fallback to env dev key."""
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (u:DejaViewUser {status: 'active'})
                RETURN u.api_key as key, u.user_id as user_id,
                       u.graph_id as graph_id, u.email as email, u.tier as tier
            """)
            loaded = 0
            for record in result:
                API_KEYS[record["key"]] = {
                    "user_id": record["user_id"],
                    "graph_id": record["graph_id"],
                    "email": record["email"],
                    "tier": record["tier"],
                }
                loaded += 1
            if loaded:
                print(f"✅ Loaded {loaded} API keys from Neo4j")
    except Exception as e:
        print(f"⚠️  Could not load keys from Neo4j: {e}")

    # Always ensure dev key works
    dev_key = os.getenv("DEJAVIEW_API_KEY", "dv_dev_" + secrets.token_hex(16))
    if dev_key not in API_KEYS:
        API_KEYS[dev_key] = {"user_id": "default", "graph_id": "default", "email": "dev", "tier": "pro"}
        print(f"🔑 Dev key: {dev_key}")


def _create_user(email: str, tier: str = "pro", source: str = "lemonsqueezy") -> dict:
    """Create a new user, generate API key, store in Neo4j."""
    import hashlib as _hl
    api_key = "dv_" + secrets.token_hex(24)
    user_id = "usr_" + _hl.md5(email.encode()).hexdigest()[:12]
    graph_id = "graph_" + secrets.token_hex(8)
    with driver.session() as session:
        session.run("""
            MERGE (u:DejaViewUser {email: $email})
            SET u.api_key = $api_key, u.user_id = $user_id,
                u.graph_id = $graph_id, u.tier = $tier,
                u.source = $source, u.status = 'active',
                u.created_at = datetime()
        """, {"email": email, "api_key": api_key, "user_id": user_id,
              "graph_id": graph_id, "tier": tier, "source": source})
    user = {"user_id": user_id, "graph_id": graph_id, "email": email, "tier": tier}
    API_KEYS[api_key] = user
    print(f"✅ Created user: {email} -> {api_key[:12]}...")
    return {"api_key": api_key, **user}


def _send_welcome_email(email: str, api_key: str):
    """Send welcome email with API key via Resend."""
    resend_key = os.getenv("RESEND_API_KEY")
    if not resend_key:
        print(f"⚠️  No RESEND_API_KEY — skipping welcome email to {email}")
        return
    import urllib.request as _ur, json as _js
    html = f"""<div style="font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:40px 20px">
<h1 style="color:#7c5cfc">Welcome to DejaView 🔮</h1>
<p>Your personal knowledge graph is ready. Here's your API key:</p>
<div style="background:#0a0e17;border-radius:12px;padding:20px;margin:24px 0">
  <code style="color:#00d4ff;font-size:16px">{api_key}</code>
</div>
<p><strong>Get started:</strong><br>
• <a href="https://app.dejaview.io">Open the web app</a> — paste your key to connect<br>
• API: <code>https://api.dejaview.io</code><br>
• Docs: <a href="https://api.dejaview.io/docs">api.dejaview.io/docs</a></p>
<p style="color:#aaa;font-size:13px">— The DejaView team</p></div>"""
    payload = _js.dumps({"from": "DejaView <hello@dejaview.io>", "to": [email],
                          "subject": "Your DejaView API Key 🔮", "html": html}).encode()
    req = _ur.Request("https://api.resend.com/emails", data=payload,
                      headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"})
    try:
        with _ur.urlopen(req, timeout=10) as r:
            print(f"📧 Welcome email sent to {email}")
    except Exception as e:
        print(f"❌ Email failed for {email}: {e}")

async def verify_api_key(authorization: str = Header(None)) -> dict:
    """Verify API key and return user context."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    
    key = authorization.replace("Bearer ", "").strip()
    if key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return API_KEYS[key]


# ============ Models ============

class Fact(BaseModel):
    subject: str = Field(..., description="The entity this fact is about", examples=["Jake"])
    predicate: str = Field(..., description="The relationship type", examples=["works_at", "founded", "knows"])
    object: str = Field(..., description="The related entity or value", examples=["Geodesic Works"])
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: str = Field(default="api", description="Where this fact came from")
    context: Optional[str] = Field(default=None, description="Additional context about this fact")

class FactsBatch(BaseModel):
    facts: List[Fact] = Field(..., min_length=1, max_length=100)

class SearchQuery(BaseModel):
    q: str = Field(..., min_length=1, description="Search query")
    limit: int = Field(default=20, ge=1, le=100)

class NLQuery(BaseModel):
    question: str = Field(..., min_length=1, description="Natural language question")


# ============ Entity Intelligence ============

# Predicate → implied subject/object labels
LABEL_HINTS = {
    "works_at": ("Person", "Organization"),
    "employed_by": ("Person", "Organization"),
    "founded": ("Person", "Organization"),
    "ceo_of": ("Person", "Organization"),
    "member_of": ("Person", "Organization"),
    "lives_in": ("Person", "Place"),
    "located_in": ("Organization", "Place"),
    "born_in": ("Person", "Place"),
    "works_on": ("Person", "Project"),
    "contributes_to": ("Person", "Project"),
    "manages": ("Person", "Project"),
    "built_with": ("Project", "Tool"),
    "uses": (None, "Tool"),
    "knows": ("Person", "Person"),
    "reports_to": ("Person", "Person"),
    "met_at": ("Person", "Event"),
    "attended": ("Person", "Event"),
    "decided": ("Person", "Decision"),
    "interested_in": ("Person", "Concept"),
    "expert_in": ("Person", "Concept"),
    "related_to": (None, None),
    "has_task": (None, "Task"),
    "documented_in": (None, "Document"),
}

# Patterns for label inference when predicates don't match
NAME_PATTERNS = {
    "Person": re.compile(r"^[A-Z][a-z]+(\s[A-Z][a-z]+){0,2}$"),  # "Jake", "Jake Smith"
}


def _normalize_name(name: str) -> str:
    """Normalize entity name for deduplication."""
    return name.strip().lower()


def _infer_label(name: str, role: str, predicate: str) -> str:
    """Infer entity label from context."""
    # Check predicate hints first
    pred_key = predicate.lower().replace(" ", "_")
    if pred_key in LABEL_HINTS:
        hint = LABEL_HINTS[pred_key]
        label = hint[0] if role == "subject" else hint[1]
        if label:
            return label
    
    # Fall back to name pattern matching
    for label, pattern in NAME_PATTERNS.items():
        if pattern.match(name):
            return label
    
    return "Entity"  # Default


def _predicate_to_rel_type(predicate: str) -> str:
    """Convert predicate string to Neo4j relationship type."""
    # Normalize: "works at" → "WORKS_AT", "works_at" → "WORKS_AT"
    clean = re.sub(r"[^a-zA-Z0-9\s_]", "", predicate)
    clean = re.sub(r"\s+", "_", clean.strip())
    return clean.upper()


# ============ Core Endpoints ============

@app.get("/")
def root():
    return {
        "service": "DejaView",
        "version": "1.0.0",
        "tagline": "Your knowledge, connected.",
        "docs": "/docs",
    }


@app.get("/v1/health")
def health():
    try:
        with driver.session() as session:
            session.run("RETURN 1")
        return {"status": "healthy", "graph": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


@app.post("/v1/facts")
def store_facts(batch: FactsBatch, user: dict = Depends(verify_api_key)):
    """
    Store one or more facts as subject-predicate-object triples.
    
    Entities are automatically created, labeled, and deduplicated.
    The predicate becomes a typed relationship (not generic RELATES_TO).
    """
    graph_id = user["graph_id"]
    stored = []
    
    with driver.session() as session:
        for fact in batch.facts:
            rel_type = _predicate_to_rel_type(fact.predicate)
            subj_label = _infer_label(fact.subject, "subject", fact.predicate)
            obj_label = _infer_label(fact.object, "object", fact.predicate)
            subj_norm = _normalize_name(fact.subject)
            obj_norm = _normalize_name(fact.object)
            
            # Use dynamic relationship type via APOC or string interpolation
            # Since Neo4j doesn't allow parameterized rel types, we validate and inject
            if not re.match(r"^[A-Z][A-Z0-9_]*$", rel_type):
                rel_type = "RELATED_TO"
            
            query = f"""
            MERGE (s:{subj_label} {{_norm_name: $subj_norm, _graph_id: $graph_id}})
            ON CREATE SET s.name = $subject, s.created_at = datetime(), s.label = $subj_label
            ON MATCH SET s.updated_at = datetime()
            
            MERGE (o:{obj_label} {{_norm_name: $obj_norm, _graph_id: $graph_id}})
            ON CREATE SET o.name = $object, o.created_at = datetime(), o.label = $obj_label
            ON MATCH SET o.updated_at = datetime()
            
            MERGE (s)-[r:{rel_type}]->(o)
            SET r.confidence = $confidence,
                r.source = $source,
                r.context = $context,
                r.created_at = datetime(),
                r._graph_id = $graph_id
            
            RETURN s.name as subject, type(r) as relationship, o.name as object
            """
            
            try:
                result = session.run(query, {
                    "subject": fact.subject,
                    "object": fact.object,
                    "subj_norm": subj_norm,
                    "obj_norm": obj_norm,
                    "subj_label": subj_label,
                    "obj_label": obj_label,
                    "confidence": fact.confidence,
                    "source": fact.source,
                    "context": fact.context,
                    "graph_id": graph_id,
                })
                record = result.single()
                stored.append({
                    "subject": record["subject"],
                    "relationship": record["relationship"],
                    "object": record["object"],
                    "subject_label": subj_label,
                    "object_label": obj_label,
                })
            except Exception as e:
                stored.append({"error": str(e), "fact": f"{fact.subject} → {fact.predicate} → {fact.object}"})
    
    return {"stored": len([s for s in stored if "error" not in s]), "total": len(stored), "results": stored}


@app.get("/v1/entities/{name}")
def get_entity(name: str, user: dict = Depends(verify_api_key)):
    """Get everything about an entity — properties and all relationships."""
    graph_id = user["graph_id"]
    norm = _normalize_name(name)
    
    with driver.session() as session:
        # Find entity
        result = session.run("""
            MATCH (n {_norm_name: $norm, _graph_id: $graph_id})
            OPTIONAL MATCH (n)-[r_out]->(target)
            OPTIONAL MATCH (source)-[r_in]->(n)
            RETURN n,
                collect(DISTINCT {type: type(r_out), target: target.name, target_label: target.label, 
                    confidence: r_out.confidence, context: r_out.context, created: toString(r_out.created_at)}) as outgoing,
                collect(DISTINCT {type: type(r_in), source: source.name, source_label: source.label,
                    confidence: r_in.confidence, context: r_in.context, created: toString(r_in.created_at)}) as incoming
        """, {"norm": norm, "graph_id": graph_id})
        
        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail=f"Entity '{name}' not found")
        
        entity = _clean_props(dict(record["n"]))
        
        return {
            "entity": entity,
            "outgoing": [r for r in record["outgoing"] if r["target"]],
            "incoming": [r for r in record["incoming"] if r["source"]],
        }


@app.get("/v1/graph/{name}")
def get_subgraph(name: str, depth: int = 2, user: dict = Depends(verify_api_key)):
    """Get subgraph around an entity for visualization. Returns nodes and edges."""
    graph_id = user["graph_id"]
    norm = _normalize_name(name)
    depth = min(depth, 3)  # Cap at 3 hops
    
    with driver.session() as session:
        result = session.run(f"""
            MATCH (start {{_norm_name: $norm, _graph_id: $graph_id}})
            CALL apoc.path.subgraphAll(start, {{maxLevel: $depth}})
            YIELD nodes, relationships
            RETURN nodes, relationships
        """, {"norm": norm, "graph_id": graph_id, "depth": depth})
        
        record = result.single()
        if not record:
            # Fallback without APOC
            result = session.run(f"""
                MATCH (start {{_norm_name: $norm, _graph_id: $graph_id}})
                MATCH path = (start)-[*1..{depth}]-(connected)
                WHERE connected._graph_id = $graph_id
                WITH start, collect(DISTINCT connected) as cnodes,
                     collect(DISTINCT relationships(path)) as rel_lists
                RETURN start, cnodes, rel_lists
            """, {"norm": norm, "graph_id": graph_id})
            record = result.single()
            if not record:
                raise HTTPException(status_code=404, detail=f"Entity '{name}' not found")
            all_nodes = [dict(record["start"])] + [dict(n) for n in record["cnodes"]]
            nodes = []
            seen_nodes = set()
            for n in all_nodes:
                n_name = n.get("name", "unknown")
                if n_name not in seen_nodes:
                    seen_nodes.add(n_name)
                    nodes.append({"id": n_name, "name": n_name,
                                  "label": n.get("label", "Entity"),
                                  "type": n.get("label", "Entity")})
            links = []
            seen_links = set()
            for rel_list in record["rel_lists"]:
                for r in (rel_list if isinstance(rel_list, list) else [rel_list]):
                    try:
                        src = dict(r.start_node).get("name", "")
                        tgt = dict(r.end_node).get("name", "")
                        key = f"{src}-{r.type}-{tgt}"
                        if key not in seen_links:
                            seen_links.add(key)
                            links.append({"source": src, "target": tgt,
                                         "type": r.type,
                                         "predicate": r.type.lower().replace("_"," ")})
                    except Exception:
                        pass
            return {"nodes": nodes, "edges": links, "links": links, "center": name}
    
    # Format APOC result
    nodes = []
    for n in record["nodes"]:
        props = dict(n)
        nodes.append({
            "id": props.get("name"),
            "label": props.get("label", "Entity"),
            "name": props.get("name"),
        })
    
    links = []
    for r in record["relationships"]:
        links.append({
            "source": dict(r.start_node).get("name"),
            "target": dict(r.end_node).get("name"),
            "type": r.type,
            "predicate": r.type.lower().replace("_", " "),
        })
    return {"nodes": nodes, "edges": links, "links": links, "center": name}


@app.post("/v1/search")
def search(query: SearchQuery, user: dict = Depends(verify_api_key)):
    """Full-text search across entities."""
    graph_id = user["graph_id"]
    
    with driver.session() as session:
        result = session.run("""
            MATCH (n {_graph_id: $graph_id})
            WHERE toLower(n.name) CONTAINS toLower($q)
            OPTIONAL MATCH (n)-[r]->(m {_graph_id: $graph_id})
            RETURN n.name as name, n.label as label,
                collect(DISTINCT {type: type(r), target: m.name})[..5] as connections
            LIMIT $limit
        """, {"q": query.q, "graph_id": graph_id, "limit": query.limit})
        
        results = []
        for record in result:
            conns = [c for c in record["connections"] if c["target"]]
            results.append({
                "name": record["name"],
                "label": record["label"],
                "type": record["label"] or "Entity",
                "connections": len(conns),
                "connection_list": conns,
            })
        
        return {"query": query.q, "results": results, "count": len(results)}


@app.get("/v1/timeline")
def timeline(limit: int = 50, user: dict = Depends(verify_api_key)):
    """Get recent facts chronologically."""
    graph_id = user["graph_id"]
    
    with driver.session() as session:
        result = session.run("""
            MATCH (s {_graph_id: $graph_id})-[r]->(o {_graph_id: $graph_id})
            WHERE r.created_at IS NOT NULL
            RETURN s.name as subject, type(r) as relationship,
                   toLower(type(r)) as predicate, o.name as object,
                   r.source as source, r.context as context,
                   toString(r.created_at) as created_at
            ORDER BY r.created_at DESC
            LIMIT $limit
        """, {"graph_id": graph_id, "limit": limit})
        
        return {"facts": [dict(r) for r in result]}


@app.get("/v1/stats")
def stats(user: dict = Depends(verify_api_key)):
    """Get graph statistics."""
    graph_id = user["graph_id"]
    
    with driver.session() as session:
        entities = session.run(
            "MATCH (n {_graph_id: $gid}) RETURN count(n) as count, collect(DISTINCT n.label) as labels",
            {"gid": graph_id}
        ).single()
        
        rels = session.run(
            "MATCH ({_graph_id: $gid})-[r]->({_graph_id: $gid}) RETURN count(r) as count, collect(DISTINCT type(r)) as types",
            {"gid": graph_id}
        ).single()
        
        return {
            "entities": entities["count"],
            "entity_types": entities["labels"],
            "relationships": rels["count"],
            "relationship_types": rels["types"],
        }


# ============ Backward Compatibility ============
# Support the old /remember endpoint for existing integrations

class LegacyMemory(BaseModel):
    subject: str
    predicate: str
    object: str
    confidence: Optional[float] = 1.0
    source: Optional[str] = "api"

@app.post("/remember")
def legacy_remember(memory: LegacyMemory):
    """Legacy endpoint — redirects to /v1/facts."""
    batch = FactsBatch(facts=[Fact(
        subject=memory.subject,
        predicate=memory.predicate,
        object=memory.object,
        confidence=memory.confidence or 1.0,
        source=memory.source or "api",
    )])
    # Use default graph for legacy endpoint
    user = {"user_id": "default", "graph_id": "default", "tier": "pro"}
    return store_facts(batch, user)

@app.get("/context/{entity}")
def legacy_context(entity: str):
    """Legacy endpoint — redirects to /v1/entities."""
    user = {"user_id": "default", "graph_id": "default", "tier": "pro"}
    try:
        return get_entity(entity, user)
    except HTTPException:
        return {"entity": None, "outgoing": [], "incoming": []}




@app.get("/v1/graph")
def get_full_graph(limit: int = 100, user: dict = Depends(verify_api_key)):
    """Get the full graph for visualization (all nodes and relationships)."""
    graph_id = user["graph_id"]
    with driver.session() as session:
        result = session.run("""
            MATCH (s {_graph_id: $gid})-[r]->(o {_graph_id: $gid})
            RETURN s.name as sname, s.label as slabel,
                   type(r) as rtype,
                   o.name as oname, o.label as olabel
            LIMIT $limit
        """, {"gid": graph_id, "limit": limit})
        nodes = {}
        links = []
        for rec in result:
            sn, sl = rec["sname"], rec["slabel"] or "Entity"
            on, ol = rec["oname"], rec["olabel"] or "Entity"
            rt = rec["rtype"]
            if sn: nodes[sn] = {"id": sn, "name": sn, "label": sl, "type": sl}
            if on: nodes[on] = {"id": on, "name": on, "label": ol, "type": ol}
            if sn and on:
                links.append({"source": sn, "target": on, "type": rt,
                              "predicate": rt.lower().replace("_", " ")})
        return {"nodes": list(nodes.values()), "links": links, "edges": links, "center": None}



@app.get("/v1/agent-context")
def agent_context_endpoint(user: dict = Depends(verify_api_key)):
    """
    Returns a natural-language context block summarizing the knowledge graph.
    Designed for injection into agent system prompts at session start.
    """
    graph_id = user["graph_id"]
    with driver.session() as session:
        type_counts = list(session.run("""
            MATCH (n {_graph_id: $gid})
            RETURN coalesce(n.label, 'Entity') as label, count(n) as count
            ORDER BY count DESC
        """, {"gid": graph_id}))

        rel_count_result = session.run("""
            MATCH ({_graph_id: $gid})-[r]->({_graph_id: $gid})
            RETURN count(r) as count
        """, {"gid": graph_id}).single()
        rel_count = rel_count_result["count"] if rel_count_result else 0

        top_entities = list(session.run("""
            MATCH (n {_graph_id: $gid})
            OPTIONAL MATCH (n)-[r]-()
            RETURN n.name as name, coalesce(n.label, 'Entity') as label, count(r) as conns
            ORDER BY conns DESC
            LIMIT 7
        """, {"gid": graph_id}))

        recent = list(session.run("""
            MATCH (s {_graph_id: $gid})-[r]->(o {_graph_id: $gid})
            WHERE r.created_at IS NOT NULL
            RETURN s.name as subject, type(r) as rel, o.name as object
            ORDER BY r.created_at DESC
            LIMIT 10
        """, {"gid": graph_id}))

    total_entities = sum(r["count"] for r in type_counts)
    lines = ["## DejaView Knowledge Graph", ""]

    if total_entities == 0:
        lines.append("The knowledge graph is empty. Use remember() to start building it.")
    else:
        type_str = ", ".join(f"{r['label']} ({r['count']})" for r in type_counts if r["label"])
        lines.append(f"**{total_entities} entities** across: {type_str}")
        lines.append(f"**{rel_count} relationships** total")
        lines.append("")

        if top_entities:
            lines.append("**Most connected:**")
            for r in top_entities:
                if r["name"]:
                    lines.append(f"  - {r['name']} ({r['label']}, {r['conns']} connections)")
            lines.append("")

        if recent:
            lines.append("**Recent activity:**")
            for r in recent:
                pred = (r["rel"] or "").lower().replace("_", " ")
                lines.append(f"  - {r['subject']} {pred} {r['object']}")
            lines.append("")

    lines.append("Tools: recall(entity) | remember(s,p,o) | search(query) | timeline()")
    return {"context": "\n".join(lines), "entities": total_entities, "relationships": rel_count}

# ============ LemonSqueezy Webhook ============

@app.post("/webhooks/lemonsqueezy")
async def lemonsqueezy_webhook(request: Request):
    """Handle LemonSqueezy webhooks — auto-provision users on payment."""
    import hmac as _hmac, hashlib as _hl, json as _js
    secret = os.getenv("LEMONSQUEEZY_WEBHOOK_SECRET", "")
    payload = await request.body()
    sig = request.headers.get("x-signature", "")
    if secret and sig:
        expected = _hmac.new(secret.encode(), payload, _hl.sha256).hexdigest()
        if not _hmac.compare_digest(expected, sig):
            raise HTTPException(status_code=401, detail="Invalid signature")
    event = _js.loads(payload)
    event_name = event.get("meta", {}).get("event_name", "")
    attrs = event.get("data", {}).get("attributes", {})
    print(f"📦 LemonSqueezy: {event_name}")
    if event_name in ("order_created", "subscription_created"):
        email = attrs.get("user_email") or attrs.get("customer_email", "")
        if not email:
            return {"status": "skipped", "reason": "no email"}
        user = _create_user(email=email, tier="pro", source="lemonsqueezy")
        _send_welcome_email(email, user["api_key"])
        return {"status": "ok", "provisioned": email}
    return {"status": "ok", "event": event_name}





# ============ Natural Language Query ============

def _llm_synthesize(question: str, graph_context: str) -> str:
    """Call available LLM to synthesize an answer from graph context."""
    import urllib.request as _ur, json as _js

    system = (
        "You are a knowledge graph assistant. The user has a personal knowledge graph. "
        "Answer their question using ONLY the graph context provided. "
        "Be concise and direct. If the graph doesn't contain enough info to answer, say so. "
        "Do not invent facts not present in the context."
    )
    prompt = f"""Knowledge graph context:
{graph_context}

Question: {question}

Answer based only on the above context:"""

    # Try Anthropic first
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        payload = _js.dumps({
            "model": "claude-haiku-4-5",
            "max_tokens": 1024,
            "system": system,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()
        req = _ur.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
        )
        try:
            with _ur.urlopen(req, timeout=20) as r:
                return _js.load(r)["content"][0]["text"].strip()
        except Exception as e:
            print(f"Anthropic error: {e}")

    # Try OpenAI
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        payload = _js.dumps({
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 1024,
        }).encode()
        req = _ur.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json",
            }
        )
        try:
            with _ur.urlopen(req, timeout=20) as r:
                return _js.load(r)["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"OpenAI error: {e}")

    return None  # No LLM available


@app.post("/v1/ask")
def ask(query: NLQuery, user: dict = Depends(verify_api_key)):
    """
    Natural language query against the knowledge graph.

    Ask anything — returns a synthesized answer backed by cited graph facts.
    No hallucination: every claim traces back to a real node in your graph.

    Example: {"question": "What do I know about Project Atlas?"}
    """
    graph_id = user["graph_id"]
    question = query.question.strip()

    # 1. Extract key terms from question for graph search
    # Simple heuristic: strip common words, search for each remaining token
    stopwords = {"what", "do", "i", "know", "about", "who", "is", "are", "the",
                 "a", "an", "how", "why", "when", "where", "tell", "me", "my",
                 "and", "or", "of", "to", "in", "on", "at", "for"}
    tokens = [w.strip("?.,!") for w in question.lower().split()
              if w.strip("?.,!") not in stopwords and len(w) > 2]

    # 2. Search graph for relevant entities
    citations = []
    seen_entities = set()

    with driver.session() as session:
        for token in tokens[:5]:  # limit to top 5 tokens
            result = session.run("""
                MATCH (n {_graph_id: $gid})
                WHERE toLower(n.name) CONTAINS toLower($q)
                RETURN n.name as name, n.label as label
                LIMIT 3
            """, {"q": token, "gid": graph_id})
            for rec in result:
                name = rec["name"]
                if name and name not in seen_entities:
                    seen_entities.add(name)

        # 3. Pull full context for each matched entity
        for entity_name in list(seen_entities)[:8]:  # cap at 8 entities
            result = session.run("""
                MATCH (n {_norm_name: $norm, _graph_id: $gid})
                OPTIONAL MATCH (n)-[r_out]->(target {_graph_id: $gid})
                OPTIONAL MATCH (source {_graph_id: $gid})-[r_in]->(n)
                RETURN n.name as name, n.label as label,
                    collect(DISTINCT {rel: type(r_out), target: target.name,
                        ctx: r_out.context, src: r_out.source,
                        ts: toString(r_out.created_at)}) as outgoing,
                    collect(DISTINCT {rel: type(r_in), source: source.name,
                        ctx: r_in.context, src: r_in.source}) as incoming
            """, {"norm": _normalize_name(entity_name), "gid": graph_id})
            rec = result.single()
            if rec:
                out = [r for r in rec["outgoing"] if r["target"]]
                inc = [r for r in rec["incoming"] if r["source"]]
                citations.append({
                    "entity": rec["name"],
                    "label": rec["label"],
                    "outgoing": out,
                    "incoming": inc,
                })

    if not citations:
        return {
            "question": question,
            "answer": "I don't have any information about that in the knowledge graph yet.",
            "citations": [],
            "llm_used": None,
        }

    # 4. Build context block for LLM
    context_lines = []
    for c in citations:
        context_lines.append(f"Entity: {c['entity']} ({c['label']})")
        for r in c["outgoing"]:
            rel = r["rel"].lower().replace("_", " ")
            line = f"  - {c['entity']} {rel} {r['target']}"
            if r.get("ctx"):
                line += f" [{r['ctx']}]"
            context_lines.append(line)
        for r in c["incoming"]:
            rel = r["rel"].lower().replace("_", " ")
            context_lines.append(f"  - {r['source']} {rel} {c['entity']}")
    graph_context = "\n".join(context_lines)

    # 5. Synthesize answer
    llm_answer = _llm_synthesize(question, graph_context)
    llm_used = "anthropic" if os.getenv("ANTHROPIC_API_KEY") and llm_answer else (
               "openai" if os.getenv("OPENAI_API_KEY") and llm_answer else None)

    return {
        "question": question,
        "answer": llm_answer or graph_context,  # fallback to raw context
        "citations": citations,
        "llm_used": llm_used,
        "entities_found": len(citations),
    }



# ============ Public Subgraph Sharing ============

import hashlib as _share_hashlib

@app.post("/v1/share")
def create_share(
    name: str,
    depth: int = 2,
    title: Optional[str] = None,
    user: dict = Depends(verify_api_key)
):
    """
    Create a public read-only shareable link for any entity's subgraph.
    Returns a share_id — accessible at GET /v1/public/{share_id} without auth.
    """
    graph_id = user["graph_id"]
    depth = min(depth, 3)
    norm = _normalize_name(name)

    # Fetch the subgraph
    with driver.session() as session:
        result = session.run(f"""
            MATCH (start {{_norm_name: $norm, _graph_id: $gid}})
            MATCH path = (start)-[*0..{depth}]-(connected)
            WHERE connected._graph_id = $gid
            WITH start, collect(DISTINCT connected) as cnodes,
                 collect(DISTINCT relationships(path)) as rel_lists
            RETURN start, cnodes, rel_lists
        """, {"norm": norm, "gid": graph_id})

        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail=f"Entity '{name}' not found")

        all_nodes = [dict(record["start"])] + [dict(n) for n in record["cnodes"]]
        nodes = []
        seen_nodes = set()
        for n in all_nodes:
            n_name = n.get("name", "unknown")
            if n_name not in seen_nodes:
                seen_nodes.add(n_name)
                nodes.append({"id": n_name, "type": n.get("label", "Entity")})

        links = []
        seen_links = set()
        for rel_list in record["rel_lists"]:
            for r in (rel_list if isinstance(rel_list, list) else [rel_list]):
                try:
                    src = dict(r.start_node).get("name", "")
                    tgt = dict(r.end_node).get("name", "")
                    key = f"{src}-{r.type}-{tgt}"
                    if key not in seen_links and src and tgt:
                        seen_links.add(key)
                        links.append({"source": src, "target": tgt,
                                     "predicate": r.type.lower().replace("_", " ")})
                except Exception:
                    pass

    import secrets as _sec
    share_id = _sec.token_urlsafe(12)
    share_title = title or f"{name} — Knowledge Graph"

    import json as _json
    graph_snapshot = _json.dumps({"nodes": nodes, "links": links})

    with driver.session() as session:
        session.run("""
            CREATE (s:DejaViewShare {
                share_id: $sid,
                entity: $entity,
                title: $title,
                graph_id: $gid,
                user_id: $uid,
                graph_snapshot: $snapshot,
                depth: $depth,
                created_at: datetime(),
                views: 0
            })
        """, {
            "sid": share_id, "entity": name, "title": share_title,
            "gid": graph_id, "uid": user["user_id"],
            "snapshot": graph_snapshot, "depth": depth
        })

    base_url = "https://dejaview.io"
    return {
        "share_id": share_id,
        "entity": name,
        "title": share_title,
        "url": f"{base_url}/share.html#{share_id}",
        "nodes": len(nodes),
        "links": len(links),
    }


@app.get("/v1/public/{share_id}")
def get_share(share_id: str):
    """Get a public shared subgraph — no auth required."""
    import json as _json
    with driver.session() as session:
        result = session.run("""
            MATCH (s:DejaViewShare {share_id: $sid})
            SET s.views = coalesce(s.views, 0) + 1
            RETURN s.entity as entity, s.title as title,
                   s.graph_snapshot as snapshot, s.created_at as created,
                   s.views as views, s.depth as depth
        """, {"sid": share_id})
        record = result.single()
        if not record:
            raise HTTPException(status_code=404, detail="Share not found or expired")

    graph = _json.loads(record["snapshot"])
    return {
        "share_id": share_id,
        "entity": record["entity"],
        "title": record["title"],
        "created_at": str(record["created"]),
        "views": record["views"],
        "depth": record["depth"],
        "nodes": graph["nodes"],
        "links": graph["links"],
    }


@app.delete("/v1/share/{share_id}")
def delete_share(share_id: str, user: dict = Depends(verify_api_key)):
    """Delete a share you created."""
    with driver.session() as session:
        result = session.run("""
            MATCH (s:DejaViewShare {share_id: $sid, user_id: $uid})
            DELETE s
            RETURN count(s) as deleted
        """, {"sid": share_id, "uid": user["user_id"]})
        record = result.single()
        if not record or record["deleted"] == 0:
            raise HTTPException(status_code=404, detail="Share not found or not yours")
    return {"deleted": share_id}

# ============ Delete Endpoints ============

class FactDelete(BaseModel):
    subject: str = Field(..., description="Subject entity name")
    predicate: str = Field(..., description="Relationship type to delete")
    object: str = Field(..., description="Object entity name")

@app.delete("/v1/facts")
def delete_fact(fact: FactDelete, user: dict = Depends(verify_api_key)):
    """
    Delete a specific fact (subject-predicate-object triple).
    Removes the relationship but leaves the entities intact.
    """
    graph_id = user["graph_id"]
    rel_type = _predicate_to_rel_type(fact.predicate)
    subj_norm = _normalize_name(fact.subject)
    obj_norm   = _normalize_name(fact.object)

    with driver.session() as session:
        result = session.run(f"""
            MATCH (s {{_norm_name: $sn, _graph_id: $gid}})-[r:{rel_type}]->(o {{_norm_name: $on, _graph_id: $gid}})
            DELETE r
            RETURN count(r) as deleted
        """, {"sn": subj_norm, "on": obj_norm, "gid": graph_id})
        record = result.single()
        deleted = record["deleted"] if record else 0

    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"Fact not found: {fact.subject} -{fact.predicate}-> {fact.object}")
    return {"deleted": deleted, "fact": f"{fact.subject} -{fact.predicate}-> {fact.object}"}


@app.delete("/v1/entities/{name}")
def delete_entity(name: str, user: dict = Depends(verify_api_key)):
    """
    Delete an entity and ALL its relationships.
    Use with care — this removes the node and every edge connected to it.
    """
    graph_id = user["graph_id"]
    norm = _normalize_name(name)

    with driver.session() as session:
        # Count first so we can report what was removed
        count = session.run("""
            MATCH (n {_norm_name: $norm, _graph_id: $gid})
            OPTIONAL MATCH (n)-[r]-()
            RETURN count(DISTINCT n) as nodes, count(r) as rels
        """, {"norm": norm, "gid": graph_id}).single()

        if not count or count["nodes"] == 0:
            raise HTTPException(status_code=404, detail=f"Entity '{name}' not found")

        nodes_count = count["nodes"]
        rels_count  = count["rels"]

        session.run("""
            MATCH (n {_norm_name: $norm, _graph_id: $gid})
            DETACH DELETE n
        """, {"norm": norm, "gid": graph_id})

    return {
        "deleted": name,
        "nodes_removed": nodes_count,
        "relationships_removed": rels_count,
    }

# ============ Startup ============

@app.on_event("startup")
def startup():
    _load_keys()
    try:
        with driver.session() as session:
            session.run("RETURN 1")
        print("✅ DejaView connected to Neo4j")
    except Exception as e:
        print(f"❌ Neo4j connection failed: {e}")


@app.on_event("shutdown")
def shutdown():
    driver.close()
