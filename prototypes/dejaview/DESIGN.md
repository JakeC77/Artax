# DejaView — Product Design Doc

## What is it?
Personal knowledge graph as a service. Capture facts, relationships, and context from your work life. Query by connection, not just keywords. Built for humans and AI agents.

## Core Principles
1. **Typed relationships** — "Jake WORKS_AT Geodesic" not "Jake RELATES_TO Geodesic"
2. **Smart entities** — automatic label inference (Person, Org, Project, etc.)
3. **Deduplication** — "Jake", "jake", "Jake C" → same entity
4. **Temporal** — when was this learned? is it still true?
5. **Multi-tenant** — isolated graphs per user, API key auth
6. **Agent-first** — designed as memory infrastructure for AI agents

## Entity Types (Default Ontology)
- Person, Organization, Project, Tool, Concept, Place, Event, Decision, Task, Document

## API Design (v1)

### Auth
- API key in header: `Authorization: Bearer dv_xxxxxxxx`
- Each key scopes to one graph

### Endpoints

#### POST /v1/facts
Store one or more facts (subject-predicate-object triples).
```json
{
  "facts": [
    {"subject": "Jake", "predicate": "works_at", "object": "Geodesic Works"},
    {"subject": "Jake", "predicate": "founded", "object": "Haven Tech Solutions"}
  ]
}
```
- Auto-creates entities if they don't exist
- Auto-infers entity labels from predicate context
- Predicate becomes the RELATIONSHIP TYPE (not generic RELATES_TO)
- Deduplicates entities by normalized name

#### GET /v1/entities/:name
Get everything about an entity — properties, all relationships in/out.
```json
{
  "entity": {"name": "Jake", "label": "Person", "aliases": ["jake", "Jake C"]},
  "relationships": [
    {"direction": "out", "type": "WORKS_AT", "target": "Geodesic Works", "since": "2024-01-01"},
    {"direction": "in", "type": "EMPLOYS", "source": "Haven Tech Solutions"}
  ]
}
```

#### GET /v1/search?q=...
Full-text + graph search. Returns entities and their immediate connections.

#### GET /v1/graph/:name?depth=2
Get subgraph around an entity. Returns nodes + edges for visualization.

#### POST /v1/query
Natural language query → Cypher → results.
"What projects is Jake working on?" → structured answer.

#### GET /v1/timeline
Recent facts, chronologically. Your knowledge activity feed.

#### DELETE /v1/entities/:name
Soft-delete an entity and its relationships.

## Tech Stack
- **API**: FastAPI (Python) — we already have this
- **Graph**: Neo4j Aura Free Tier (for free users) / Aura Pro (for paid)
- **Auth**: API keys stored in Postgres or simple KV
- **Hosting**: Fly.io or Railway (easy deploy, good free tier)
- **Payments**: Stripe Checkout

## MVP Scope (2 weeks)
Week 1: Core API with typed relationships, dedup, auth, deploy
Week 2: Simple web UI (graph viewer), landing page, Stripe, launch on HN/Twitter
