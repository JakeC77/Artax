"""
Artax Knowledge Graph API
A prototype for connecting an AI agent to a personal knowledge graph.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from neo4j import GraphDatabase
from typing import Optional, List, Any
import os
import json

app = FastAPI(
    title="Artax Knowledge Graph API",
    description="Personal knowledge graph backend for AI agents",
    version="0.1.0"
)

# Neo4j connection
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    auth=(
        os.getenv("NEO4J_USER", "neo4j"),
        os.getenv("NEO4J_PASSWORD", "artaxpassword")
    )
)


# ============ Models ============

class CypherQuery(BaseModel):
    query: str
    params: Optional[dict] = {}

class Entity(BaseModel):
    label: str
    properties: dict

class Relationship(BaseModel):
    from_id: int
    to_id: int
    type: str
    properties: Optional[dict] = {}

class Memory(BaseModel):
    subject: str
    predicate: str
    object: str
    confidence: Optional[float] = 1.0
    source: Optional[str] = "artax"

class Question(BaseModel):
    question: str


# ============ Core Endpoints ============

@app.get("/")
def root():
    """Health check and API info"""
    return {
        "status": "online",
        "service": "Artax Knowledge Graph",
        "version": "0.1.0",
        "endpoints": {
            "query": "POST /query - Execute raw Cypher",
            "ontology": "GET /ontology - Get schema information",
            "ask": "POST /ask - Natural language query (simplified)",
            "remember": "POST /remember - Store a new fact",
            "context": "GET /context/{entity} - Get context about an entity",
            "related": "GET /related/{entity} - Find related entities"
        }
    }


@app.post("/query")
def execute_query(q: CypherQuery):
    """Execute a raw Cypher query against the knowledge graph"""
    try:
        with driver.session() as session:
            result = session.run(q.query, q.params)
            records = [dict(record) for record in result]
            return {"results": records, "count": len(records)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/ontology")
def get_ontology():
    """Get the schema/ontology of the knowledge graph"""
    with driver.session() as session:
        # Get node labels
        labels_result = session.run("CALL db.labels()")
        labels = [record["label"] for record in labels_result]
        
        # Get relationship types
        rels_result = session.run("CALL db.relationshipTypes()")
        relationships = [record["relationshipType"] for record in rels_result]
        
        # Get property keys
        props_result = session.run("CALL db.propertyKeys()")
        properties = [record["propertyKey"] for record in props_result]
        
        return {
            "labels": labels,
            "relationships": relationships,
            "properties": properties,
            "description": {
                "Person": "A human being (e.g., Jake, contacts, collaborators)",
                "Organization": "A company, startup, or institution",
                "Project": "Something being built or worked on",
                "Idea": "A concept or proposal being explored",
                "Concept": "A domain topic or area of knowledge",
                "Task": "An action item or todo",
                "Decision": "A choice that was made",
                "Agent": "An AI agent (e.g., Artax)"
            }
        }


@app.get("/context/{entity}")
def get_context(entity: str):
    """Get all context about a specific entity"""
    query = """
    MATCH (n)
    WHERE toLower(n.name) CONTAINS toLower($entity)
    OPTIONAL MATCH (n)-[r]->(m)
    OPTIONAL MATCH (o)-[r2]->(n)
    RETURN n, 
           collect(DISTINCT {rel: type(r), target: m.name, props: properties(m)}) as outgoing,
           collect(DISTINCT {rel: type(r2), source: o.name, props: properties(o)}) as incoming
    LIMIT 5
    """
    with driver.session() as session:
        result = session.run(query, {"entity": entity})
        records = []
        for record in result:
            node = dict(record["n"])
            records.append({
                "entity": node,
                "outgoing_relationships": [r for r in record["outgoing"] if r["target"]],
                "incoming_relationships": [r for r in record["incoming"] if r["source"]]
            })
        return {"context": records}


@app.get("/related/{entity}")
def get_related(entity: str, hops: int = 2):
    """Find entities related to the given entity within N hops"""
    query = f"""
    MATCH (n)
    WHERE toLower(n.name) CONTAINS toLower($entity)
    MATCH path = (n)-[*1..{min(hops, 3)}]-(related)
    WHERE n <> related
    RETURN DISTINCT related.name as name, labels(related) as labels, 
           length(path) as distance
    ORDER BY distance
    LIMIT 20
    """
    with driver.session() as session:
        result = session.run(query, {"entity": entity})
        related = [dict(record) for record in result]
        return {"entity": entity, "related": related}


@app.post("/remember")
def remember(memory: Memory):
    """Store a new fact/memory in the knowledge graph"""
    # This creates or merges nodes and relationships based on the triple
    query = """
    MERGE (s:Entity {name: $subject})
    MERGE (o:Entity {name: $object})
    MERGE (s)-[r:RELATES_TO {type: $predicate}]->(o)
    SET r.confidence = $confidence,
        r.source = $source,
        r.created = datetime()
    RETURN s, r, o
    """
    with driver.session() as session:
        result = session.run(query, {
            "subject": memory.subject,
            "predicate": memory.predicate,
            "object": memory.object,
            "confidence": memory.confidence,
            "source": memory.source
        })
        record = result.single()
        return {
            "stored": True,
            "triple": f"{memory.subject} --[{memory.predicate}]--> {memory.object}"
        }


@app.post("/ask")
def ask(q: Question):
    """
    Simple natural language query interface.
    Maps common question patterns to Cypher queries.
    """
    question = q.question.lower()
    
    # Pattern matching for common questions
    if "working on" in question or "projects" in question:
        if "jake" in question:
            query = """
            MATCH (p:Person {name: "Jake"})-[:WORKING_ON]->(proj:Project)
            RETURN proj.name as project, proj.status as status, proj.description as description
            """
        else:
            query = """
            MATCH (p:Person)-[:WORKING_ON]->(proj:Project)
            RETURN p.name as person, proj.name as project, proj.status as status
            """
    
    elif "who is" in question or "tell me about" in question:
        # Extract entity name (simple heuristic)
        words = question.replace("who is", "").replace("tell me about", "").strip().split()
        entity = " ".join(words).strip("?")
        return get_context(entity)
    
    elif "related to" in question:
        words = question.replace("related to", "|||").split("|||")
        if len(words) > 1:
            entity = words[1].strip().strip("?")
            return get_related(entity)
        query = "MATCH (n) RETURN n.name LIMIT 10"
    
    elif "know about" in question or "what do you know" in question:
        query = """
        MATCH (n)
        RETURN labels(n)[0] as type, count(*) as count
        ORDER BY count DESC
        """
    
    else:
        # Default: return recent additions
        query = """
        MATCH (n)
        WHERE n.created IS NOT NULL
        RETURN n.name as name, labels(n) as type, n.created as created
        ORDER BY n.created DESC
        LIMIT 10
        """
    
    with driver.session() as session:
        result = session.run(query)
        records = [dict(record) for record in result]
        return {
            "question": q.question,
            "answer": records,
            "query_used": query
        }


# ============ Agent-Specific Endpoints ============

@app.get("/agent/context")
def get_agent_context():
    """
    Get context relevant for an AI agent starting a conversation.
    Returns: current projects, recent decisions, pending tasks, key relationships.
    """
    queries = {
        "active_projects": """
            MATCH (p:Person {name: "Jake"})-[:WORKING_ON]->(proj:Project)
            WHERE proj.status = "active"
            RETURN proj.name as name, proj.description as description
        """,
        "recent_decisions": """
            MATCH (p:Person {name: "Jake"})-[:DECIDED]->(d:Decision)
            RETURN d.summary as decision, d.made_on as date
            ORDER BY d.made_on DESC LIMIT 5
        """,
        "pending_tasks": """
            MATCH (t:Task)
            WHERE t.status = "pending"
            RETURN t.title as task, t.due_by as due
            ORDER BY t.due_by LIMIT 10
        """,
        "key_people": """
            MATCH (p:Person {name: "Jake"})-[:KNOWS]->(other:Person)
            RETURN other.name as name, other.role as role, other.relationship_to_jake as relationship
            LIMIT 10
        """
    }
    
    context = {}
    with driver.session() as session:
        for key, query in queries.items():
            try:
                result = session.run(query)
                context[key] = [dict(record) for record in result]
            except:
                context[key] = []
    
    return {"agent_context": context}


@app.post("/agent/learn")
def agent_learn(facts: List[Memory]):
    """Batch endpoint for an agent to store multiple facts at once"""
    stored = []
    for fact in facts:
        result = remember(fact)
        stored.append(result)
    return {"stored_count": len(stored), "facts": stored}


# ============ Startup ============

@app.on_event("startup")
def startup():
    """Verify connection on startup"""
    try:
        with driver.session() as session:
            session.run("RETURN 1")
        print("✅ Connected to Neo4j")
    except Exception as e:
        print(f"❌ Failed to connect to Neo4j: {e}")


@app.on_event("shutdown")
def shutdown():
    """Clean up on shutdown"""
    driver.close()
