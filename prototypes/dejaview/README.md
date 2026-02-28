# DejaView 🔮

**Your knowledge, connected.**

Personal knowledge graph as a service. Capture facts, relationships, and context. Query by connection, not just keywords.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env  # Edit with your Neo4j creds
uvicorn api:app --reload --port 8000
```

## API

```bash
# Store a fact
curl -X POST http://localhost:8000/v1/facts \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"facts": [{"subject": "Jake", "predicate": "works_at", "object": "Geodesic Works"}]}'

# Query an entity
curl http://localhost:8000/v1/entities/Jake \
  -H "Authorization: Bearer YOUR_KEY"

# Search
curl -X POST http://localhost:8000/v1/search \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"q": "Jake"}'

# Get subgraph for visualization
curl http://localhost:8000/v1/graph/Jake?depth=2 \
  -H "Authorization: Bearer YOUR_KEY"
```

## Key Improvements Over Prototype

- **Typed relationships**: `works_at` → `WORKS_AT` (not generic `RELATES_TO`)
- **Smart labels**: auto-infers Person, Organization, Project, etc.
- **Deduplication**: normalizes names to prevent duplicates
- **Multi-tenant**: API key auth, isolated graphs per user
- **Temporal**: timestamps on all entities and relationships
- **Backward compatible**: old `/remember` and `/context` endpoints still work

## Architecture

```
Client → FastAPI → Neo4j Aura
          ↓
       Auth (API keys)
       Label inference
       Name normalization
       Relationship typing
```

## License

MIT
