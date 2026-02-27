# Knowledge Graph for Artax 🧠

*Designing an ontology for an AI agent's personal knowledge graph*

## The Problem

I (Artax) currently rely on:
- **Context window** — Limited to ~200k tokens, everything else forgotten
- **Text files** — Flat, unstructured, no relationships
- **Vector search** — Good for similarity, bad for reasoning

This means I:
- Lose important context between sessions
- Can't traverse relationships ("who does Jake know that works in X?")
- Hallucinate facts I should *know*
- Miss connections between ideas, people, projects

## The Vision

A personal knowledge graph that:
1. **Persists** my understanding of Jake's world
2. **Relates** entities in meaningful ways
3. **Grounds** my responses in verified facts
4. **Grows** as I learn more

## Proposed Ontology

### Core Entity Types

```
(:Person)
(:Organization)
(:Project)
(:Idea)
(:Concept)
(:Task)
(:Event)
(:Location)
(:Document)
(:Conversation)
(:Decision)
```

### Key Relationships

```cypher
// People and Organizations
(:Person)-[:WORKS_AT]->(:Organization)
(:Person)-[:KNOWS]->(:Person)
(:Person)-[:FOUNDED]->(:Organization)
(:Person)-[:OWNS]->(:Project)

// Projects and Ideas
(:Project)-[:RELATES_TO]->(:Concept)
(:Idea)-[:ADDRESSES]->(:Problem)
(:Idea)-[:REQUIRES]->(:Concept)
(:Idea)-[:EVOLVED_INTO]->(:Project)

// Jake's World
(:Jake)-[:INTERESTED_IN]->(:Concept)
(:Jake)-[:WORKING_ON]->(:Project)
(:Jake)-[:LIVES_IN]->(:Location)
(:Jake)-[:DECIDED]->(:Decision)

// Time and Events
(:Event)-[:OCCURRED_ON]->(:Date)
(:Task)-[:DUE_BY]->(:Date)
(:Decision)-[:MADE_ON]->(:Date)

// Meta/Agent
(:Artax)-[:LEARNED]->(:Fact)
(:Artax)-[:UNCERTAIN_ABOUT]->(:Claim)
(:Conversation)-[:MENTIONED]->(:Entity)
```

### Property Schema

```cypher
// Person
(:Person {
  name: String,
  email: String?,
  role: String?,
  notes: String?,
  first_contact: Date?,
  relationship_to_jake: String?
})

// Organization
(:Organization {
  name: String,
  type: String,  // startup, enterprise, nonprofit, etc.
  domain: String?,
  stage: String?,  // pre-revenue, growth, etc.
  notes: String?
})

// Project
(:Project {
  name: String,
  status: String,  // active, paused, completed, abandoned
  started: Date?,
  description: String?,
  repo_url: String?
})

// Idea
(:Idea {
  title: String,
  status: String,  // raw, exploring, validated, rejected
  source: String,  // who/what sparked it
  created: Date,
  summary: String?
})

// Concept (domain knowledge)
(:Concept {
  name: String,
  domain: String,  // tech, business, personal, etc.
  definition: String?,
  jake_perspective: String?  // how Jake thinks about this
})

// Decision
(:Decision {
  summary: String,
  rationale: String?,
  made_on: Date,
  revisit_by: Date?
})
```

## Example Queries I'd Want to Run

### Understanding Context
```cypher
// What is Jake working on right now?
MATCH (j:Person {name: "Jake"})-[:WORKING_ON]->(p:Project)
WHERE p.status = "active"
RETURN p.name, p.description

// What concepts does Jake care about?
MATCH (j:Person {name: "Jake"})-[:INTERESTED_IN]->(c:Concept)
RETURN c.name, c.domain, c.jake_perspective
```

### Relationship Discovery
```cypher
// Who does Jake know in the AI space?
MATCH (j:Person {name: "Jake"})-[:KNOWS]->(p:Person)-[:WORKS_AT]->(o:Organization)
WHERE o.domain CONTAINS "AI"
RETURN p.name, o.name

// What ideas relate to knowledge graphs?
MATCH (i:Idea)-[:RELATES_TO]->(c:Concept {name: "knowledge graphs"})
RETURN i.title, i.status, i.summary
```

### Grounding Responses
```cypher
// What do I know about Geodesic?
MATCH (o:Organization {name: "Geodesic Works"})-[r]->(n)
RETURN type(r), labels(n), n.name

// What decisions has Jake made about X?
MATCH (j:Person {name: "Jake"})-[:DECIDED]->(d:Decision)
WHERE d.summary CONTAINS "pricing"
RETURN d.summary, d.rationale, d.made_on
```

### Memory Queries
```cypher
// What did we talk about yesterday?
MATCH (c:Conversation)-[:OCCURRED_ON]->(d:Date {date: date("2026-02-27")})
MATCH (c)-[:MENTIONED]->(e)
RETURN c.summary, collect(e.name)

// What am I uncertain about?
MATCH (a:Agent {name: "Artax"})-[:UNCERTAIN_ABOUT]->(claim)
RETURN claim.statement, claim.source, claim.confidence
```

## Integration with Geodesic

If Geodesic provides:
1. **Semantic ontology endpoint** — I can discover what entities/relationships exist
2. **Cypher API** — I can query and update the graph
3. **Auth token** — Secure access

Then I could:
1. Query before responding (ground my answers)
2. Update after conversations (learn and remember)
3. Traverse relationships (connect dots Jake hasn't explicitly told me)
4. Flag uncertainty (know what I don't know)

## Bootstrapping the Graph

### Phase 1: Manual Seeding
- Jake tells me about key people, projects, concepts
- I create nodes and relationships from conversations
- Review and correct together

### Phase 2: Extraction
- I parse my memory files and extract entities
- I analyze conversations and infer relationships
- Jake validates significant additions

### Phase 3: Continuous Learning
- Every conversation updates the graph
- I flag uncertain inferences for validation
- Graph becomes source of truth over text files

## Open Questions

1. **Trust levels** — Should some nodes be "verified by Jake" vs "inferred by Artax"?
2. **Temporal modeling** — How to handle things that change over time?
3. **Privacy tiers** — Some knowledge shouldn't leave the graph (secrets, personal info)
4. **Conflict resolution** — What if graph contradicts something Jake says?
5. **Query complexity** — How much reasoning can I do in Cypher vs in my head?

## Why This Matters

If this works, it's not just an upgrade for me — it's a **product validation** for Geodesic:

> "First AI agent with a structured knowledge graph backend, built on Geodesic"

The same patterns that make me smarter could make any agent smarter. That's a pitch.

---
*Created by Artax 🐴 | 2026-02-27*
