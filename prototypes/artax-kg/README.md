# Artax Knowledge Graph Prototype 🧠🐴

A working prototype demonstrating how an AI agent can connect to a personal knowledge graph for enhanced memory, context, and reasoning.

## Quick Start

```bash
# Start the services
docker-compose up -d

# Wait for Neo4j to be ready (~30 seconds)
sleep 30

# Seed the database with demo data
cat seed/seed_data.cypher | docker exec -i artax-kg cypher-shell -u neo4j -p artaxpassword

# Test the API
curl http://localhost:8000/
```

## What's Included

### Services
- **Neo4j** (port 7474 for browser, 7687 for Bolt)
- **FastAPI** (port 8000) - The API that Artax uses

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check and API info |
| `/ontology` | GET | Get graph schema (labels, relationships, properties) |
| `/query` | POST | Execute raw Cypher queries |
| `/context/{entity}` | GET | Get all context about an entity |
| `/related/{entity}` | GET | Find related entities (within N hops) |
| `/ask` | POST | Natural language query interface |
| `/remember` | POST | Store a new fact |
| `/agent/context` | GET | Get conversation-starting context for an agent |
| `/agent/learn` | POST | Batch store multiple facts |

## Demo: How Artax Uses This

### 1. Get conversation context at session start
```bash
curl http://localhost:8000/agent/context | jq
```

Returns: Active projects, recent decisions, pending tasks, key people.

### 2. Query for specific context
```bash
# What is Jake working on?
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Jake working on?"}'

# Tell me about Geodesic
curl http://localhost:8000/context/geodesic | jq

# What's related to knowledge graphs?
curl http://localhost:8000/related/knowledge%20graphs | jq
```

### 3. Store new facts learned during conversation
```bash
curl -X POST http://localhost:8000/remember \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Jake",
    "predicate": "mentioned interest in",
    "object": "voice interfaces",
    "confidence": 0.9,
    "source": "conversation-2026-02-27"
  }'
```

### 4. Execute complex queries
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "MATCH (p:Person {name: \"Jake\"})-[:INTERESTED_IN]->(c:Concept) RETURN c.name, c.jake_perspective"
  }'
```

## Neo4j Browser

Open http://localhost:7474 in your browser.
- Username: `neo4j`
- Password: `artaxpassword`

Try these queries:
```cypher
// See everything
MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 50

// Jake's world
MATCH (jake:Person {name: "Jake"})-[r]->(n) RETURN jake, r, n

// What does Artax know about?
MATCH (a:Agent {name: "Artax"})-[:KNOWS_ABOUT]->(c) RETURN a, c

// Project relationships
MATCH (p:Project)-[r]->(c:Concept) RETURN p.name, type(r), c.name
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│     Artax       │────▶│   KG API        │────▶│    Neo4j        │
│   (AI Agent)    │     │   (FastAPI)     │     │  (Graph DB)     │
│                 │◀────│                 │◀────│                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
     Queries &               REST/JSON            Cypher Queries
     Learns from
```

## The Vision

This prototype demonstrates how an AI agent can:

1. **Start with context** - Load relevant knowledge at session start
2. **Query during conversation** - Look up facts instead of hallucinating  
3. **Learn continuously** - Store new information from conversations
4. **Traverse relationships** - Find non-obvious connections
5. **Ground responses** - Back claims with graph-verified facts

## Next Steps

- [ ] Integrate with actual Artax agent (OpenClaw)
- [ ] Add authentication for production use
- [ ] Implement confidence scoring and source tracking
- [ ] Build ontology explorer UI
- [ ] Add vector embeddings for semantic search
- [ ] Connect to Geodesic platform

---

*Built by Artax 🐴 for Jake @ Geodesic Works*
