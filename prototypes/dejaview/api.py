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

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from neo4j import GraphDatabase
from typing import Optional, List, Dict, Any
from datetime import datetime
import os
import re
import hashlib
import secrets

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
    """Load API keys from env or create default."""
    default_key = os.getenv("DEJAVIEW_API_KEY", "dv_dev_" + secrets.token_hex(16))
    API_KEYS[default_key] = {
        "user_id": "default",
        "graph_id": "default",
        "tier": "pro",
        "created": datetime.utcnow().isoformat(),
    }
    print(f"🔑 Dev API key: {default_key}")

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
        
        node = dict(record["n"])
        # Clean internal properties
        entity = {k: v for k, v in node.items() if not k.startswith("_")}
        
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
                WITH start, collect(DISTINCT connected) as nodes, 
                     [r IN relationships(path) | r] as rels
                RETURN start, nodes, rels
            """, {"norm": norm, "graph_id": graph_id})
            
            record = result.single()
            if not record:
                raise HTTPException(status_code=404, detail=f"Entity '{name}' not found")
            
            # Format for visualization
            all_nodes = [dict(record["start"])] + [dict(n) for n in record["nodes"]]
            nodes = []
            seen = set()
            for n in all_nodes:
                name_val = n.get("name", "unknown")
                if name_val not in seen:
                    seen.add(name_val)
                    nodes.append({
                        "id": n.get("name"),
                        "label": n.get("label", "Entity"),
                        "name": name_val,
                    })
            
            return {"nodes": nodes, "edges": [], "center": name}
    
    # Format APOC result
    nodes = []
    for n in record["nodes"]:
        props = dict(n)
        nodes.append({
            "id": props.get("name"),
            "label": props.get("label", "Entity"),
            "name": props.get("name"),
        })
    
    edges = []
    for r in record["relationships"]:
        edges.append({
            "source": dict(r.start_node).get("name"),
            "target": dict(r.end_node).get("name"),
            "type": r.type,
        })
    
    return {"nodes": nodes, "edges": edges, "center": name}


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
            results.append({
                "name": record["name"],
                "label": record["label"],
                "connections": [c for c in record["connections"] if c["target"]],
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
            RETURN s.name as subject, type(r) as relationship, o.name as object,
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
